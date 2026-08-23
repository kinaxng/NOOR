<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed, watch } from 'vue'
import { useJobsStore } from '../stores/jobs'
import { useRoute, useRouter } from 'vue-router'
import type { BackgroundTask, Job, SSEEvent } from '../api/types'
import api from '../api'
import LogViewer from '../components/noor/LogViewer.vue'
import BaseIcon from '../components/noor/BaseIcon.vue'
import JobCard from '../components/noor/JobCard.vue'
import JobChainPanel from '../components/noor/JobChainPanel.vue'
import VuiButton from '../components/ui/Button/VuiButton.vue'
import VisionTabs from '../components/ui/Tabs.vue'
import NoorPagination from '../components/ui/Pagination.vue'
import { useI18n } from '../composables/useI18n'
import { useToast } from '../composables/useToast'
import { useJobPresentation } from '../composables/useJobPresentation'
import { useJobsTabs } from '../composables/useJobsTabs'
import { useJobEventState } from '../composables/useJobEventState'
import { useJobSelection } from '../composables/useJobSelection'
import { useJobRuntimePresentation, type JobTabKey } from '../composables/useJobRuntimePresentation'
import { useRouteTabs } from '../composables/useRouteTabs'
const { t } = useI18n()
const jobsStore = useJobsStore()
const route = useRoute()
const router = useRouter()
const toast = useToast()
const allJobs = () => jobsStore.jobs

const MAX_VISIBLE_LOG_LINES = 400

const {
  jobStatuses,
  sseConnected,
  watchedJobIds,
  getJobById,
  clampJobProgress,
  seedJobStatus,
  refreshJobStatus,
  ensureJobStatus,
  applyStructuredEvent,
  updateStorePhaseState,
  applyTerminalEvent,
  applyQueuedLikeEvent,
  pruneJobStatuses,
} = useJobEventState({
  allJobs,
  jobsStore,
})

function isExternalTask(job: Job) {
  return job.job_type === 'external_task' || !!job.result_metadata?.external_task
}

function shouldWatchJob(job: { status: string }) {
  return !isExternalTask(job as Job) && (job.status === 'running' || job.status === 'queued' || job.status === 'blocked' || job.status === 'pending')
}

function getErrorDetail(error: unknown) {
  if (typeof error === 'object' && error !== null) {
    const maybeMessage = (error as { message?: string }).message
    const maybeResponse = (error as { response?: { data?: { detail?: string } } }).response
    return maybeResponse?.data?.detail || maybeMessage || ''
  }
  return String(error ?? '')
}

function getFallbackRuntimeStatus(job: Job) {
  return job.status === 'running'
    ? getRunningBadgeLabel.value({ status: 'running' }, '')
    : fallbackStatusLabel.value(job.status)
}

function syncRuntimeStatusFromJob(jobId: string) {
  const job = getJobById(jobId)
  if (!job) return null
  refreshJobStatus(job, getFallbackRuntimeStatus(job))
  return job
}

function syncWatchableJobs() {
  for (const job of jobsStore.jobs) {
    if (shouldWatchJob(job) && !watchedJobIds.value.has(job.id)) {
      seedJobStatus(job, fallbackStatusLabel.value(job.status))
      void watchJob(job.id)
    }
  }
}

onMounted(async () => {
  await jobsStore.fetchJobs()
  syncWatchableJobs()
  await applyRouteFocus()
})

onUnmounted(() => {
  jobsStore.disconnectFromEvents()
  disposeSelection()
})

watch(() => [route.query.job, route.query.chain, jobsStore.jobs.length], async () => {
  await applyRouteFocus()
}, { flush: 'post' })

watch(
  () => jobsStore.jobs.map(job => `${job.id}:${job.status}`).join('|'),
  () => {
    syncWatchableJobs()
  },
)

async function watchJob(jobId: string) {
  if (watchedJobIds.value.has(jobId)) return
  watchedJobIds.value.add(jobId)

  const job = getJobById(jobId)
  if (job) {
    seedJobStatus(job, fallbackStatusLabel.value(job.status))
    if (job.status === 'running') {
      jobStatuses.value[jobId].status = connectingLabel.value
    }
  }

  jobsStore.connectToEvents(jobId, (event: SSEEvent) => {
    const time = new Date().toLocaleTimeString()

    switch (event.type) {
      case 'progress': {
        const progress = clampJobProgress(jobId, event.progress)
        applyStructuredEvent(jobId, event, {
          status: getRunningBadgeLabel.value({ status: 'running' }, ''),
          progress,
          keepPhaseProgressMonotonic: true,
        })
        updateStorePhaseState(jobId, progress, undefined, event, event.phase_label)
        break
      }
      case 'log':
        if (event.line && (selectedJobId.value === jobId || selectedJobId.value === null)) {
          appendVisibleLog({ time, line: event.line })
        }
        break
      case 'completed':
        applyTerminalEvent(
          jobId,
          event,
          'completed',
          completedStatusLabel.value,
          Math.max(ensureJobStatus(jobId).progress || 0, 100),
          event.phase_progress ?? 100,
        )
        break
      case 'cancelled':
        applyTerminalEvent(jobId, event, 'cancelled', cancelledStatusLabel.value, 0, 0)
        break
      case 'failed':
        applyTerminalEvent(jobId, event, 'failed', failedStatusLabel.value, 0, 0)
        break
      case 'skipped':
        applyTerminalEvent(jobId, event, 'skipped', t('jobs.status.skipped'), 0, 0)
        break
      case 'queued':
        applyQueuedLikeEvent(jobId, event, queuedStatusLabel.value)
        break
      case 'blocked':
        applyQueuedLikeEvent(jobId, event, blockedStatusLabel.value)
        break
    }
  })

  setTimeout(() => {
    if (!sseConnected.value.has(jobId)) {
      const dbJob = syncRuntimeStatusFromJob(jobId)
      if (dbJob && jobStatuses.value[jobId]) {
        jobStatuses.value[jobId].status = getFallbackRuntimeStatus(dbJob)
      }
    }
  }, 10000)
}

async function cancelJob(jobId: string) {
  try {
    await api.post(`/jobs/${jobId}/cancel`)
    await jobsStore.fetchJobs()

    const refreshedJob = syncRuntimeStatusFromJob(jobId)
    toast.success(t(refreshedJob?.status === 'cancelled' ? 'jobs.cancelSuccess' : 'jobs.cancelRequested'))
  } catch (error: unknown) {
    console.error('Cancel failed:', error)
    toast.error(t('common.errorWithDetail', { detail: getErrorDetail(error) }))
  }
}

async function cleanupOrphanedJobs() {
  try {
    const resp = await api.post('/jobs/cleanup')
    const cleaned = resp.data.cleaned
    const cleanedJobIds: string[] = Array.isArray(resp.data.cleaned_job_ids) ? resp.data.cleaned_job_ids : []
    if (cleaned > 0) {
      toast.success(t('jobs.cleanup.done', { n: cleaned }))
      jobsStore.pruneJobs(cleanedJobIds)
      pruneJobStatuses(cleanedJobIds)
    } else {
      toast.info(t('jobs.cleanup.none'))
    }
  } catch (error: unknown) {
    console.error('Cleanup failed:', error)
    toast.error(t('common.errorWithDetail', { detail: getErrorDetail(error) }))
  }
}

const cleanupLabel = computed(() => t('jobs.cleanup'))
const cancelTaskLabel = computed(() => t('jobs.cancelTask'))
const logsTitleLabel = computed(() => t('jobs.logsTitle'))
const chainTitleLabel = computed(() => t('jobs.chain.title'))

const activeTab = useRouteTabs<JobTabKey>({
  route,
  router,
  basePath: '/jobs',
  paramName: 'jobTab',
  tabs: ['running', 'completed', 'failed', 'background'],
  defaultTab: 'running',
})
const jobPage = ref(1)
const JOB_PAGE_SIZE = 10
const { connectingLabel, queuedLabel: queuedStatusLabel, blockedLabel: blockedStatusLabel, completedLabel: completedStatusLabel, failedLabel: failedStatusLabel, cancelledLabel: cancelledStatusLabel, fallbackStatusLabel, getRunningBadgeLabel, getJobHeaderMetaTokens, getWhisperStrategyHint, getJobDisplayName } = useJobPresentation(allJobs)
const { sortChainJobs, filterTabs, currentTabJobs, currentTabTitle, currentEmptyLabel } = useJobsTabs(allJobs, activeTab)
const backgroundTasks = ref<BackgroundTask[]>([])
const backgroundLoading = ref(false)
const backgroundError = ref('')
const backgroundRunLoading = ref<Record<string, boolean>>({})
let backgroundRefreshTimer: number | null = null
const allFilterTabs = computed(() => [
  ...filterTabs.value,
  { key: 'background', label: `${t('jobs.background')} ${backgroundTasks.value.length}` },
])
const currentTabTotalPages = computed(() => Math.max(1, Math.ceil(currentTabJobs.value.length / JOB_PAGE_SIZE)))
const paginatedCurrentTabJobs = computed(() => {
  const start = (jobPage.value - 1) * JOB_PAGE_SIZE
  return currentTabJobs.value.slice(start, start + JOB_PAGE_SIZE)
})
watch([activeTab, () => currentTabJobs.value.length], () => {
  if (jobPage.value > currentTabTotalPages.value) jobPage.value = currentTabTotalPages.value
  else jobPage.value = 1
})
function goJobPage(page: number) {
  jobPage.value = page
}

function formatTaskDate(value?: string) {
  if (!value) return '无'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString()
}

function formatInterval(minutes?: number) {
  const value = Number(minutes || 0)
  if (!value) return ''
  if (value < 60) return `${value} 分钟`
  if (value % 1440 === 0) return `${value / 1440} 天`
  if (value % 60 === 0) return `${value / 60} 小时`
  return `${Math.floor(value / 60)} 小时 ${value % 60} 分钟`
}

function getBackgroundStatusLabel(task: BackgroundTask) {
  if (!task.enabled || task.status === 'disabled') return '已停用'
  if (task.status === 'running') return '运行中'
  if (task.status === 'failed') return '异常'
  return '待命'
}

function getBackgroundStatusClass(task: BackgroundTask) {
  if (!task.enabled || task.status === 'disabled') return 'background-task__status--disabled'
  if (task.status === 'running') return 'background-task__status--running'
  if (task.status === 'failed') return 'background-task__status--failed'
  return 'background-task__status--idle'
}

async function fetchBackgroundTasks() {
  backgroundLoading.value = true
  backgroundError.value = ''
  try {
    const resp = await api.get('/plugins/background/tasks')
    backgroundTasks.value = Array.isArray(resp.data?.items) ? resp.data.items : []
  } catch (error: unknown) {
    console.error('Fetch background tasks failed:', error)
    backgroundError.value = getErrorDetail(error) || t('common.error')
  } finally {
    backgroundLoading.value = false
  }
}

async function runBackgroundTask(task: BackgroundTask) {
  const runAction = task.run_action
  if (!runAction?.plugin_id || !runAction.action || backgroundRunLoading.value[task.id]) return
  backgroundRunLoading.value = { ...backgroundRunLoading.value, [task.id]: true }
  try {
    await api.post(`/plugins/${runAction.plugin_id}/actions/${runAction.action}`, {
      payload: runAction.payload || {},
    })
    toast.success('后台任务已触发')
    await fetchBackgroundTasks()
  } catch (error: unknown) {
    console.error('Run background task failed:', error)
    toast.error(t('common.errorWithDetail', { detail: getErrorDetail(error) }))
  } finally {
    backgroundRunLoading.value = { ...backgroundRunLoading.value, [task.id]: false }
  }
}

function resetBackgroundRefreshTimer() {
  if (backgroundRefreshTimer !== null) {
    window.clearInterval(backgroundRefreshTimer)
    backgroundRefreshTimer = null
  }
  if (activeTab.value === 'background') {
    void fetchBackgroundTasks()
    backgroundRefreshTimer = window.setInterval(() => {
      void fetchBackgroundTasks()
    }, 15000)
  }
}

onMounted(() => {
  if (activeTab.value !== 'background') void fetchBackgroundTasks()
  resetBackgroundRefreshTimer()
})

onUnmounted(() => {
  if (backgroundRefreshTimer !== null) window.clearInterval(backgroundRefreshTimer)
})

watch(activeTab, resetBackgroundRefreshTimer)

const {
  logs,
  selectedJobId,
  flashJobId,
  appendVisibleLog,
  selectJob,
  selectJobById,
  applyRouteFocus,
  dispose: disposeSelection,
} = useJobSelection({
  route,
  router,
  maxVisibleLogLines: MAX_VISIBLE_LOG_LINES,
  shouldWatchJob,
  watchJob,
  getJobById,
  findJobByChainId: (chainId: string) => allJobs().filter(job => job.chain_id === chainId).sort(sortChainJobs)[0] || null,
  onFocusTab: (status) => {
    activeTab.value = status
  },
})

const selectedJob = computed(() => selectedJobId.value ? getJobById(selectedJobId.value) : null)
const selectedJobChain = computed(() => {
  const job = selectedJob.value
  if (!job) return [] as Job[]
  if (!job.chain_id) return [job]
  return allJobs().filter(candidate => candidate.chain_id === job.chain_id).sort(sortChainJobs)
})
const selectedJobHeaderName = computed(() => selectedJob.value ? getJobDisplayName.value(selectedJob.value) : '')
const selectedJobHeaderMeta = computed(() => selectedJob.value ? getJobHeaderMetaTokens.value(selectedJob.value) : [] as string[])
const selectedJobStrategyHint = computed(() => selectedJob.value ? getWhisperStrategyHint.value(selectedJob.value) : '')
const { currentTabJobCards, selectedJobStatusLabel, selectedJobActivityLine, selectedJobChainFlow, selectedJobChainSummary, selectedJobChainModels } = useJobRuntimePresentation({
  allJobs,
  jobStatuses,
  selectedJobId,
  flashJobId,
  activeTab,
  currentTabJobs: paginatedCurrentTabJobs,
  selectedJob,
  selectedJobChain,
  cancelLabel: cancelTaskLabel,
})

function selectChainMember(jobId: string) {
  void selectJobById(jobId)
}


</script>

<template>
  <div class="w-full space-y-6 animate-fade-in">
    <!-- Header -->
    <div class="jobs-toolbar flex items-center justify-between gap-4">
      <VisionTabs v-model="activeTab" :tabs="allFilterTabs" />
      <VuiButton v-if="activeTab !== 'background'" variant="contained" color="info" size="small" customClass="jobs-toolbar__action" @click="cleanupOrphanedJobs">
        {{ cleanupLabel }}
      </VuiButton>
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <!-- Jobs List -->
      <div class="lg:col-span-2 space-y-4">
        <div v-if="activeTab === 'background'" class="space-y-3">
          <div v-if="backgroundError" class="background-error ui-card">
            {{ backgroundError }}
          </div>
          <div v-if="backgroundLoading && backgroundTasks.length === 0" class="background-loading ui-card">
            正在读取后台任务...
          </div>
          <div
            v-for="task in backgroundTasks"
            :key="task.id"
            class="background-task ui-card"
          >
            <div class="background-task__main">
              <div class="background-task__icon">
                <BaseIcon name="jobs" :class="task.status === 'running' ? 'w-4 h-4 animate-spin' : 'w-4 h-4'" />
              </div>
              <div class="background-task__content">
                <div class="background-task__header">
                  <div class="background-task__title-wrap">
                    <span class="background-task__plugin">{{ task.plugin_name }}</span>
                    <h3 class="background-task__title">{{ task.title }}</h3>
                  </div>
                  <span class="background-task__status" :class="getBackgroundStatusClass(task)">
                    {{ getBackgroundStatusLabel(task) }}
                  </span>
                </div>
                <p v-if="task.summary" class="background-task__summary">{{ task.summary }}</p>
                <p v-if="task.detail" class="background-task__detail">{{ task.detail }}</p>
                <div v-if="task.metrics && Object.keys(task.metrics).length" class="background-task__metrics">
                  <span v-for="(value, key) in task.metrics" :key="key" class="background-task__metric">
                    <span>{{ key }}</span>
                    <strong>{{ value }}</strong>
                  </span>
                </div>
                <div class="background-task__meta">
                  <span v-if="task.interval_minutes">间隔 {{ formatInterval(task.interval_minutes) }}</span>
                  <span>上次 {{ formatTaskDate(task.last_finished_at || task.last_run_at) }}</span>
                  <span v-if="task.next_run_at">下次 {{ formatTaskDate(task.next_run_at) }}</span>
                </div>
              </div>
              <VuiButton
                v-if="task.can_run && task.run_action"
                variant="outlined"
                color="info"
                size="small"
                customClass="background-task__run"
                :disabled="task.status === 'running' || backgroundRunLoading[task.id]"
                @click.stop="runBackgroundTask(task)"
              >
                {{ backgroundRunLoading[task.id] ? '运行中' : '立即运行' }}
              </VuiButton>
            </div>
          </div>
        </div>

        <div v-else-if="currentTabJobCards.length > 0" class="space-y-3">
          <JobCard
            v-for="entry in currentTabJobCards"
            :key="entry.job.id"
            :job="entry.job"
            :view="entry.view"
            @click="selectJob"
            @cancel="cancelJob"
          />
          <NoorPagination
            :page="jobPage"
            :total-pages="currentTabTotalPages"
            @page="goJobPage"
          />
        </div>

        <!-- Empty State -->
        <div
          v-if="(activeTab === 'background' && !backgroundLoading && backgroundTasks.length === 0) || (activeTab !== 'background' && currentTabJobCards.length === 0)"
          class="empty-state-card ui-card flex flex-col items-center justify-center text-center"
        >
          <div class="w-14 h-14 rounded-2xl flex items-center justify-center mb-4 empty-state-icon">
            <BaseIcon name="jobs" class="w-7 h-7 text-white/20" />
          </div>
          <h3 class="text-base font-medium mb-1 text-white font-display">{{ currentTabTitle }}</h3>
          <p class="text-sm text-white/30">{{ currentEmptyLabel }}</p>
        </div>
      </div>

      <!-- Log Viewer -->
      <div class="lg:col-span-1">
        <div class="log-card ui-card sticky top-24">
          <div class="px-4 py-3 flex items-start justify-between gap-3 log-card__header">
            <div class="min-w-0">
              <h3 class="text-sm font-medium log-card__title">{{ logsTitleLabel }}</h3>
              <p v-if="selectedJobHeaderName" class="log-card__job-name">{{ selectedJobHeaderName }}</p>
              <p v-if="selectedJobHeaderMeta.length" class="log-card__job-meta">{{ selectedJobHeaderMeta.join(' · ') }}</p>
              <p v-if="selectedJobStrategyHint" class="log-card__job-hint">{{ selectedJobStrategyHint }}</p>
              <p v-if="selectedJobActivityLine" class="log-card__job-phase">{{ selectedJobActivityLine }}</p>
            </div>
            <span v-if="selectedJobId" class="log-card__status">
              {{ selectedJobStatusLabel }}
            </span>
          </div>
          <JobChainPanel
            v-if="selectedJobChain.length > 1"
            :title="chainTitleLabel"
            :flow="selectedJobChainFlow"
            :summary="selectedJobChainSummary"
            :members="selectedJobChainModels"
            @select="selectChainMember"
          />
          <div v-if="!selectedJobId" class="jobs-log-empty">
            <div class="jobs-log-empty__icon">
              <BaseIcon name="terminal" class="w-5 h-5" />
            </div>
            <p class="jobs-log-empty__title">{{ t('jobs.logsTitle') }}</p>
            <p class="jobs-log-empty__hint">{{ t('jobs.clickForLogs') }}</p>
          </div>
          <LogViewer v-if="selectedJobId" :logs="logs" :auto-scroll="true" />
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.jobs-toolbar {
  align-items: center;
}

.jobs-toolbar__action {
  flex-shrink: 0;
}

.empty-state-card {
  min-height: 15rem;
}

.empty-state-icon {
  background: rgba(255,255,255,0.03);
  border: 1px solid var(--color-border-subtle);
}

.background-loading,
.background-error {
  color: var(--color-text-secondary);
  font-size: var(--font-size-sm);
}

.background-error {
  border-color: rgba(255, 59, 92, 0.28);
  color: rgba(255, 160, 176, 0.9);
}

.background-task {
  padding: 1rem;
  transition: border-color var(--transition-normal), box-shadow var(--transition-normal), transform var(--transition-normal);
}

.background-task:hover {
  border-color: rgba(0, 117, 255, 0.26);
  box-shadow: 0 8px 26px -4px rgba(0, 117, 255, 0.16);
  transform: translateY(-1px);
}

.background-task__main {
  display: flex;
  align-items: flex-start;
  gap: 0.85rem;
}

.background-task__icon {
  display: inline-flex;
  width: 2.25rem;
  height: 2.25rem;
  flex-shrink: 0;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-lg);
  border: 1px solid rgba(0, 117, 255, 0.18);
  background: rgba(0, 117, 255, 0.1);
  color: rgba(125, 190, 255, 0.92);
}

.background-task__content {
  min-width: 0;
  flex: 1;
}

.background-task__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.75rem;
}

.background-task__title-wrap {
  min-width: 0;
}

.background-task__plugin {
  display: block;
  margin-bottom: 0.15rem;
  font-size: 11px;
  color: rgba(255,255,255,0.36);
}

.background-task__title {
  margin: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--color-text-primary);
  font-family: var(--font-display);
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-semibold);
}

.background-task__status {
  flex-shrink: 0;
  border-radius: var(--radius-pill);
  border: 1px solid rgba(255,255,255,0.1);
  padding: 0.25rem 0.55rem;
  font-size: 11px;
  line-height: 1;
}

.background-task__status--running {
  border-color: rgba(33, 212, 253, 0.24);
  background: rgba(33, 212, 253, 0.09);
  color: rgba(158, 237, 255, 0.92);
}

.background-task__status--idle {
  border-color: rgba(52, 211, 153, 0.22);
  background: rgba(52, 211, 153, 0.08);
  color: rgba(164, 244, 210, 0.9);
}

.background-task__status--failed {
  border-color: rgba(255, 59, 92, 0.25);
  background: rgba(255, 59, 92, 0.08);
  color: rgba(255, 166, 182, 0.92);
}

.background-task__status--disabled {
  border-color: rgba(255,255,255,0.08);
  background: rgba(255,255,255,0.04);
  color: rgba(255,255,255,0.4);
}

.background-task__summary {
  margin-top: 0.55rem;
  color: rgba(255,255,255,0.62);
  font-size: var(--font-size-sm);
}

.background-task__detail {
  margin-top: 0.35rem;
  color: rgba(255, 208, 122, 0.82);
  font-size: 11px;
  line-height: 1.5;
}

.background-task__metrics {
  display: flex;
  flex-wrap: wrap;
  gap: 0.45rem;
  margin-top: 0.8rem;
}

.background-task__metric {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  border-radius: var(--radius-pill);
  border: 1px solid rgba(255,255,255,0.08);
  background: rgba(255,255,255,0.04);
  padding: 0.28rem 0.55rem;
  color: rgba(255,255,255,0.42);
  font-size: 11px;
}

.background-task__metric strong {
  color: rgba(255,255,255,0.82);
  font-weight: var(--font-weight-semibold);
}

.background-task__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 0.55rem;
  margin-top: 0.8rem;
  color: rgba(255,255,255,0.34);
  font-size: 11px;
}

.background-task__run {
  flex-shrink: 0;
}

.log-card {
  min-width: 0;
  overflow: hidden;
}

.log-card__job-name {
  margin-top: 0.25rem;
  font-size: 0.82rem;
  color: rgba(255,255,255,0.8);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.log-card__job-meta {
  margin-top: 0.18rem;
  font-size: 11px;
  color: rgba(255,255,255,0.4);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.log-card__job-phase {
  margin-top: 0.28rem;
  font-size: 11px;
  color: rgba(255,255,255,0.54);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.log-card__job-hint {
  margin-top: 0.3rem;
  font-size: 11px;
  line-height: 1.45;
  color: rgba(255, 208, 122, 0.82);
}

.log-card__status {
  flex-shrink: 0;
  font-size: 11px;
  font-family: var(--font-mono, 'JetBrains Mono', monospace);
  color: rgba(255,255,255,0.34);
  margin-top: 0.15rem;
}

.jobs-log-empty {
  display: flex;
  min-height: 22rem;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.7rem;
  color: var(--color-text-secondary);
}

.jobs-log-empty__icon {
  display: inline-flex;
  width: 2.5rem;
  height: 2.5rem;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-lg);
  border: 1px solid var(--color-border-subtle);
  background: rgba(255,255,255,0.03);
  color: rgba(255,255,255,0.42);
}

.jobs-log-empty__title {
  font-family: var(--font-display);
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-semibold);
  color: var(--color-text-primary);
}

.jobs-log-empty__hint {
  font-size: var(--font-size-sm);
  color: var(--color-text-muted);
}



@media (max-width: 900px) {
  .jobs-toolbar {
    align-items: stretch;
    flex-direction: column;
  }

  .jobs-toolbar__action {
    align-self: flex-end;
  }

  .background-task__main,
  .background-task__header {
    flex-direction: column;
  }

  .background-task__run {
    align-self: flex-start;
  }

  .log-card__header {
    flex-direction: column;
    align-items: flex-start;
  }

  .log-card__status {
    margin-top: 0;
  }

  .log-card__job-name,
  .log-card__job-meta,
  .log-card__job-hint,
  .log-card__job-phase {
    white-space: normal;
  }

  .jobs-log-empty {
    min-height: 14rem;
  }

}

</style>
