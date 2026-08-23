<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed, watch } from 'vue'
import { useJobsStore } from '../stores/jobs'
import { useRoute, useRouter } from 'vue-router'
import type { Job, SSEEvent } from '../api/types'
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

function shouldWatchJob(job: { status: string }) {
  return job.status === 'running' || job.status === 'queued' || job.status === 'blocked' || job.status === 'pending'
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

const activeTab = ref<JobTabKey>('running')
const jobPage = ref(1)
const JOB_PAGE_SIZE = 10
const { connectingLabel, queuedLabel: queuedStatusLabel, blockedLabel: blockedStatusLabel, completedLabel: completedStatusLabel, failedLabel: failedStatusLabel, cancelledLabel: cancelledStatusLabel, fallbackStatusLabel, getRunningBadgeLabel, getJobHeaderMetaTokens, getWhisperStrategyHint, getJobDisplayName } = useJobPresentation(allJobs)
const { sortChainJobs, filterTabs, currentTabJobs, currentTabTitle, currentEmptyLabel } = useJobsTabs(allJobs, activeTab)
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
      <VisionTabs v-model="activeTab" :tabs="filterTabs" />
      <VuiButton variant="contained" color="info" size="small" customClass="jobs-toolbar__action" @click="cleanupOrphanedJobs">
        {{ cleanupLabel }}
      </VuiButton>
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <!-- Jobs List -->
      <div class="lg:col-span-2 space-y-4">
        <div v-if="currentTabJobCards.length > 0" class="space-y-3">
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
          v-if="currentTabJobCards.length === 0"
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

}

</style>
