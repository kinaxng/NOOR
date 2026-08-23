<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed, watch } from 'vue'
import { useJobsStore } from '../stores/jobs'
import { useRoute, useRouter } from 'vue-router'
import type { BackgroundTask, Job, RecommendedDiagnostics, RecommendedDiagnosticsSegment, SSEEvent } from '../api/types'
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
const backgroundTasks = ref<BackgroundTask[]>([])
const backgroundTasksLoading = ref(false)
let backgroundTasksTimer: ReturnType<typeof setInterval> | null = null

async function fetchBackgroundTasks() {
  backgroundTasksLoading.value = true
  try {
    const response = await api.get('/plugins/background/tasks')
    backgroundTasks.value = Array.isArray(response.data?.items) ? response.data.items : []
  } catch (error) {
    console.error('Fetch background tasks failed:', error)
  } finally {
    backgroundTasksLoading.value = false
  }
}

function formatBackgroundTime(value?: string) {
  if (!value) return ''
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString()
}

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
  await fetchBackgroundTasks()
  backgroundTasksTimer = setInterval(fetchBackgroundTasks, 15000)
  syncWatchableJobs()
  await applyRouteFocus()
})

onUnmounted(() => {
  jobsStore.disconnectFromEvents()
  disposeSelection()
  if (backgroundTasksTimer) clearInterval(backgroundTasksTimer)
  backgroundTasksTimer = null
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
const jobTabs = computed(() => [
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
const selectedJobRecommendedDiagnostics = computed<RecommendedDiagnostics | null>(() => {
  const data = selectedJob.value?.result_metadata?.recommended_diagnostics
  if (!data || typeof data !== 'object') return null
  return data as RecommendedDiagnostics
})
const diagnosticsTitleLabel = computed(() => t('jobs.diagnosticsTitle'))
const diagnosticsEmptyLabel = computed(() => t('jobs.diagnosticsEmpty'))
const selectedJobDiagnosticSummary = computed(() => {
  const diagnostics = selectedJobRecommendedDiagnostics.value
  if (!diagnostics) return [] as string[]
  return [
    `${t('jobs.diagnosticsAligned')} ${diagnostics.aligned_segments}/${diagnostics.segment_count}`,
    `${t('jobs.diagnosticsLargeV3')} ${diagnostics.large_v3_retry_segments}`,
    `${t('jobs.diagnosticsFallback')} ${diagnostics.qwen_retry_segments}`,
    `${t('jobs.diagnosticsStepdown')} ${diagnostics.stepdown_segments}`,
  ]
})
const selectedJobDiagnosticCleanup = computed(() => {
  const cleanup = selectedJobRecommendedDiagnostics.value?.cleanup
  if (!cleanup) return [] as string[]
  return [
    `${t('jobs.diagnosticsDeduped')} ${cleanup.deduped_segments}`,
    `${t('jobs.diagnosticsNoise')} ${cleanup.noise_only_segments}`,
    `${t('jobs.diagnosticsTrimmed')} ${cleanup.trimmed_noise_chars}`,
    `${t('jobs.diagnosticsParticle')} ${cleanup.particle_merged_segments}`,
    `${t('jobs.diagnosticsEcho')} ${cleanup.window_echo_segments}`,
  ]
})
function diagnosticSegmentLine(segment: RecommendedDiagnosticsSegment) {
  const parts: string[] = [
    `${t('jobs.diagnosticsSegment')} ${segment.index}`,
    `${segment.subtitle_count ?? 0} ${t('jobs.diagnosticsSubtitles')}`,
  ]
  if (segment.large_v3_retry) parts.push(t('jobs.diagnosticsLargeV3'))
  if (segment.qwen_retry) parts.push(t('jobs.diagnosticsFallback'))
  if (segment.stepdown) {
    const windows = segment.stepdown_window_count ? ` · ${segment.stepdown_window_count} ${t('jobs.diagnosticsWindows')}` : ''
    parts.push(`${t('jobs.diagnosticsStepdown')}${windows}`)
  }
  if (segment.aligner_empty) parts.push('aligner_empty')
  if (segment.hardened) parts.push('hardening')
  return parts.join(' · ')
}
function diagnosticReasonLabel(reason?: string) {
  if (!reason) return ''
  const normalized = reason.trim()
  if (!normalized) return ''
  return normalized
    .replace(/-/g, ' ')
    .replace(/\b\w/g, (ch) => ch.toUpperCase())
}
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
      <VisionTabs v-model="activeTab" :tabs="jobTabs" />
      <VuiButton variant="contained" color="info" size="small" customClass="jobs-toolbar__action" @click="cleanupOrphanedJobs">
        {{ cleanupLabel }}
      </VuiButton>
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <!-- Jobs List -->
      <div class="lg:col-span-2 space-y-4">
        <div v-if="activeTab === 'background'" class="background-task-list">
          <div v-if="backgroundTasksLoading && !backgroundTasks.length" class="empty-state-card ui-card flex items-center justify-center text-sm text-white/40">
            {{ t('common.loading') }}
          </div>
          <div v-else-if="!backgroundTasks.length" class="empty-state-card ui-card flex flex-col items-center justify-center text-center">
            <div class="w-14 h-14 rounded-2xl flex items-center justify-center mb-4 empty-state-icon">
              <BaseIcon name="history" class="w-7 h-7 text-white/20" />
            </div>
            <h3 class="text-base font-medium mb-1 text-white font-display">{{ t('jobs.background') }}</h3>
            <p class="text-sm text-white/30">{{ t('jobs.noBackground') }}</p>
          </div>
          <template v-else>
            <article v-for="task in backgroundTasks" :key="task.id" class="background-task-card ui-card">
              <div class="background-task-card__header">
                <div class="min-w-0">
                  <h3 class="background-task-card__title">{{ task.title || task.id }}</h3>
                  <p class="background-task-card__plugin">{{ task.plugin_name || task.plugin_id }}</p>
                </div>
                <span class="background-task-card__status" :class="`is-${task.status || 'idle'}`">
                  {{ task.status === 'running' ? t('jobs.running') : task.status === 'failed' ? t('history.filter.failed') : task.status === 'disabled' ? '已禁用' : '待机' }}
                </span>
              </div>
              <p v-if="task.summary" class="background-task-card__summary">{{ task.summary }}</p>
              <p v-if="task.detail" class="background-task-card__detail">{{ task.detail }}</p>
              <div class="background-task-card__meta">
                <span v-if="task.last_run_at">最近运行 {{ formatBackgroundTime(task.last_run_at) }}</span>
                <span v-if="task.last_finished_at">完成 {{ formatBackgroundTime(task.last_finished_at) }}</span>
              </div>
            </article>
          </template>
        </div>
        <div v-if="activeTab !== 'background' && currentTabJobCards.length > 0" class="space-y-3">
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
          v-if="activeTab !== 'background' && currentTabJobCards.length === 0"
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
          <div v-if="selectedJobId && selectedJobRecommendedDiagnostics" class="jobs-diagnostics">
            <div class="jobs-diagnostics__head">
              <div class="jobs-diagnostics__title-wrap">
                <div class="jobs-diagnostics__icon">
                  <BaseIcon name="jobs" class="w-4 h-4" />
                </div>
                <div class="min-w-0">
                  <p class="jobs-diagnostics__title">{{ diagnosticsTitleLabel }}</p>
                  <p class="jobs-diagnostics__summary">{{ selectedJobDiagnosticSummary.join(' · ') }}</p>
                </div>
              </div>
            </div>
            <div class="jobs-diagnostics__stats">
              <div class="jobs-diagnostics__stat">
                <span class="jobs-diagnostics__stat-label">{{ t('jobs.diagnosticsAligned') }}</span>
                <strong class="jobs-diagnostics__stat-value">
                  {{ selectedJobRecommendedDiagnostics.aligned_segments }}/{{ selectedJobRecommendedDiagnostics.segment_count }}
                </strong>
              </div>
              <div class="jobs-diagnostics__stat">
                <span class="jobs-diagnostics__stat-label">{{ t('jobs.diagnosticsLargeV3') }}</span>
                <strong class="jobs-diagnostics__stat-value">{{ selectedJobRecommendedDiagnostics.large_v3_retry_segments }}</strong>
              </div>
              <div class="jobs-diagnostics__stat">
                <span class="jobs-diagnostics__stat-label">{{ t('jobs.diagnosticsFallback') }}</span>
                <strong class="jobs-diagnostics__stat-value">{{ selectedJobRecommendedDiagnostics.qwen_retry_segments }}</strong>
              </div>
              <div class="jobs-diagnostics__stat">
                <span class="jobs-diagnostics__stat-label">{{ t('jobs.diagnosticsStepdown') }}</span>
                <strong class="jobs-diagnostics__stat-value">{{ selectedJobRecommendedDiagnostics.stepdown_segments }}</strong>
              </div>
              <div class="jobs-diagnostics__stat">
                <span class="jobs-diagnostics__stat-label">Hardening</span>
                <strong class="jobs-diagnostics__stat-value">{{ selectedJobRecommendedDiagnostics.hardened_segments }}</strong>
              </div>
            </div>
            <div v-if="selectedJobDiagnosticCleanup.length" class="jobs-diagnostics__chips">
              <span v-for="item in selectedJobDiagnosticCleanup" :key="item" class="jobs-diagnostics__chip">{{ item }}</span>
            </div>
            <div class="jobs-diagnostics__list">
              <div v-for="segment in selectedJobRecommendedDiagnostics.segments || []" :key="segment.index" class="jobs-diagnostics__item">
                <p class="jobs-diagnostics__item-title">{{ diagnosticSegmentLine(segment) }}</p>
                <p v-if="segment.chain_state" class="jobs-diagnostics__item-meta">{{ segment.chain_state }}</p>
                <div
                  v-if="segment.large_v3_retry_reason || segment.qwen_retry_reason || segment.stepdown_reason"
                  class="jobs-diagnostics__reason-list"
                >
                  <p v-if="segment.large_v3_retry_reason" class="jobs-diagnostics__reason">
                    <span class="jobs-diagnostics__reason-label">large-v3 · {{ t('jobs.diagnosticsReason') }}</span>
                    <span>{{ diagnosticReasonLabel(segment.large_v3_retry_reason) }}</span>
                  </p>
                  <p v-if="segment.qwen_retry_reason" class="jobs-diagnostics__reason">
                    <span class="jobs-diagnostics__reason-label">Qwen · {{ t('jobs.diagnosticsReason') }}</span>
                    <span>{{ diagnosticReasonLabel(segment.qwen_retry_reason) }}</span>
                  </p>
                  <p v-if="segment.stepdown_reason" class="jobs-diagnostics__reason">
                    <span class="jobs-diagnostics__reason-label">Step-down · {{ t('jobs.diagnosticsReason') }}</span>
                    <span>{{ diagnosticReasonLabel(segment.stepdown_reason) }}</span>
                  </p>
                </div>
              </div>
            </div>
          </div>
          <div v-if="selectedJobId && selectedJob?.job_type === 'whisper' && !selectedJobRecommendedDiagnostics" class="jobs-diagnostics jobs-diagnostics--empty">
            <p class="jobs-diagnostics__title">{{ diagnosticsTitleLabel }}</p>
            <p class="jobs-log-empty__hint">{{ diagnosticsEmptyLabel }}</p>
          </div>
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

.background-task-list {
  display: grid;
  gap: 0.75rem;
}

.background-task-card {
  padding: 1rem 1.1rem;
}

.background-task-card__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
}

.background-task-card__title {
  color: var(--color-text-primary);
  font-size: 0.92rem;
  font-weight: 650;
}

.background-task-card__plugin,
.background-task-card__detail,
.background-task-card__meta {
  color: var(--color-text-muted);
  font-size: 0.74rem;
}

.background-task-card__plugin { margin-top: 0.22rem; }
.background-task-card__summary { margin-top: 0.8rem; color: var(--color-text-secondary); font-size: 0.82rem; }
.background-task-card__detail { margin-top: 0.35rem; line-height: 1.5; }
.background-task-card__meta { display: flex; flex-wrap: wrap; gap: 0.75rem; margin-top: 0.75rem; }

.background-task-card__status {
  flex-shrink: 0;
  border: 1px solid var(--color-border-subtle);
  border-radius: 999px;
  padding: 0.2rem 0.55rem;
  color: var(--color-text-muted);
  font-size: 0.7rem;
}
.background-task-card__status.is-running { border-color: rgba(0,117,255,.38); color: #65a9ff; }
.background-task-card__status.is-failed { border-color: rgba(227,26,26,.38); color: #ff8d8d; }
.background-task-card__status.is-disabled { color: #aab3c2; }

.empty-state-card {
  min-height: 15rem;
}

.empty-state-icon {
  background: rgba(255,255,255,0.03);
  border: 1px solid var(--color-border-subtle);
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

  .jobs-diagnostics__stats {
    grid-template-columns: 1fr;
  }

}

.jobs-diagnostics {
  padding: 0.95rem 1rem;
  border-top: 1px solid rgba(255,255,255,0.06);
  border-bottom: 1px solid rgba(255,255,255,0.06);
  background: rgba(255,255,255,0.018);
}

.jobs-diagnostics--empty {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.jobs-diagnostics__head {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

.jobs-diagnostics__title-wrap {
  display: flex;
  align-items: flex-start;
  gap: 0.7rem;
}

.jobs-diagnostics__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 1.9rem;
  height: 1.9rem;
  border-radius: 0.75rem;
  border: 1px solid rgba(0,117,255,0.2);
  background: rgba(0,117,255,0.09);
  color: rgba(255,255,255,0.78);
  flex-shrink: 0;
}

.jobs-diagnostics__title {
  font-size: 12px;
  font-weight: 600;
  color: rgba(255,255,255,0.82);
}

.jobs-diagnostics__summary {
  font-size: 11px;
  color: rgba(255,255,255,0.42);
}

.jobs-diagnostics__stats {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.55rem;
  margin-top: 0.7rem;
}

.jobs-diagnostics__stat {
  display: flex;
  flex-direction: column;
  gap: 0.12rem;
  padding: 0.6rem 0.7rem;
  border-radius: 0.8rem;
  border: 1px solid rgba(255,255,255,0.05);
  background: rgba(255,255,255,0.026);
}

.jobs-diagnostics__stat-label {
  font-size: 10px;
  color: rgba(255,255,255,0.38);
}

.jobs-diagnostics__stat-value {
  font-size: 14px;
  font-weight: 600;
  color: rgba(255,255,255,0.84);
}

.jobs-diagnostics__chips {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
  margin-top: 0.65rem;
}

.jobs-diagnostics__chip {
  padding: 0.2rem 0.5rem;
  border-radius: 999px;
  border: 1px solid rgba(255,255,255,0.08);
  background: rgba(255,255,255,0.025);
  font-size: 11px;
  color: rgba(255,255,255,0.5);
}

.jobs-diagnostics__list {
  display: flex;
  flex-direction: column;
  gap: 0.55rem;
  margin-top: 0.7rem;
}

.jobs-diagnostics__item {
  padding: 0.55rem 0.65rem;
  border-radius: 0.75rem;
  background: rgba(255,255,255,0.024);
  border: 1px solid rgba(255,255,255,0.05);
}

.jobs-diagnostics__item-title {
  font-size: 11px;
  color: rgba(255,255,255,0.64);
}

.jobs-diagnostics__item-meta {
  margin-top: 0.22rem;
  font-size: 11px;
  color: rgba(255,255,255,0.34);
}

.jobs-diagnostics__reason-list {
  display: flex;
  flex-direction: column;
  gap: 0.22rem;
  margin-top: 0.35rem;
}

.jobs-diagnostics__reason {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
  font-size: 10px;
  color: rgba(255,255,255,0.46);
}

.jobs-diagnostics__reason-label {
  color: rgba(255,255,255,0.3);
}

</style>
