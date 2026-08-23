<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useJobsStore } from '../stores/jobs'
import { useToast } from '../composables/useToast'
import { useConfirm } from '../composables/useConfirm'
import { useI18n } from '../composables/useI18n'
import { formatBytes, formatDate, formatDuration, jobQualityScore, jobTitle, metadataValue, pipelineLabel, statusLabel, statusTone } from '../app/format'
import { sortJobsForList } from '../composables/jobOrdering'
import type { Job, JobStatus, RecommendedDiagnostics, WhisperExecutionMetadata } from '../api/types'

const { t } = useI18n()
const route = useRoute()
const jobs = useJobsStore()
const toast = useToast()
const { confirm } = useConfirm()

const filter = ref<'all' | 'completed' | 'failed'>((route.query.filter as any) || 'all')
const expandedJobId = ref('')
const currentPage = ref(1)
const pageSize = 10

const filterTabs = computed(() => [
  { label: t('history.filter.all'), icon: 'i-lucide-list', to: '/history' },
  { label: t('history.filter.completed'), icon: 'i-lucide-check-circle', to: { query: { filter: 'completed' } } },
  { label: t('history.filter.failed'), icon: 'i-lucide-x-circle', to: { query: { filter: 'failed' } } },
])

const failedStatuses = ['failed', 'cancelled', 'skipped'] as const

const filteredJobs = computed(() => {
  const all = jobs.historyJobs
  if (filter.value === 'completed') return all.filter(j => j.status === 'completed')
  if (filter.value === 'failed') return all.filter(j => failedStatuses.includes(j.status as any))
  return all
})

const sortedJobs = computed(() => sortJobsForList(filteredJobs.value))

const pagedJobs = computed(() => {
  const start = (currentPage.value - 1) * pageSize
  return sortedJobs.value.slice(start, start + pageSize)
})

const totalPages = computed(() => Math.max(1, Math.ceil(sortedJobs.value.length / pageSize)))

watch(filter, () => { currentPage.value = 1; expandedJobId.value = '' })
watch(() => route.query.filter, (val) => {
  if (val && ['all', 'completed', 'failed'].includes(val as string)) {
    filter.value = val as any
  } else if (!val) {
    filter.value = 'all'
  }
})

function historyStatusTone(status: string) {
  const tone = statusTone(status as JobStatus)
  if (tone === 'success') return 'success'
  if (tone === 'warning') return 'warning'
  if (tone === 'danger') return 'error'
  if (tone === 'info') return 'info'
  return 'neutral'
}

function formatDurationMs(ms: number) {
  if (!Number.isFinite(ms) || ms <= 0) return t('history.report.unknown')
  const seconds = Math.round(ms / 1000)
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const sec = seconds % 60
  if (h > 0) return `${h}h ${m}m ${sec}s`
  if (m > 0) return `${m}m ${sec}s`
  return `${sec}s`
}

function getJobDuration(job: Job) {
  if (!job.created_at || !job.completed_at) return t('history.report.unknown')
  return formatDurationMs(new Date(job.completed_at).getTime() - new Date(job.created_at).getTime())
}

function getRecommendedDiagnostics(job: Job): RecommendedDiagnostics | null {
  const data = job.result_metadata?.recommended_diagnostics
  if (!data || typeof data !== 'object') return null
  return data as RecommendedDiagnostics
}

function getWhisperExecution(job: Job): WhisperExecutionMetadata | null {
  const data = job.result_metadata?.whisper_execution
  if (!data || typeof data !== 'object') return null
  return data as WhisperExecutionMetadata
}

function getQualityScore(job: Job) {
  if (job.status === 'cancelled' || job.status === 'skipped') return null
  if (job.status === 'failed') return 20
  if (job.status !== 'completed') return null

  let score = 72
  if (job.output_path) score += 8
  if (job.job_type === 'whisper' || job.job_type === 'whisper_transcribe') {
    const diagnostics = getRecommendedDiagnostics(job)
    if (diagnostics?.segment_count) {
      const alignedRatio = diagnostics.aligned_segments / Math.max(1, diagnostics.segment_count)
      score += Math.round(alignedRatio * 12)
      score -= Math.min(12, diagnostics.large_v3_retry_segments * 2)
      score -= Math.min(12, diagnostics.qwen_retry_segments * 3)
      score -= Math.min(10, diagnostics.stepdown_segments * 3)
      score -= Math.min(8, diagnostics.aligner_empty_segments * 2)
      const cleanup = diagnostics.cleanup
      if (cleanup) {
        score -= Math.min(8, cleanup.noise_only_segments)
        score -= Math.min(6, cleanup.window_echo_segments * 2)
        if (cleanup.after_segments > 0 && cleanup.before_segments > 0) score += 3
      }
    } else {
      score -= 8
    }
  }
  return Math.max(0, Math.min(100, score))
}

function qualityToneClass(score: number | null) {
  if (score === null) return 'bg-(--ui-bg-elevated)/50'
  if (score >= 85) return 'bg-emerald-500/15'
  if (score >= 70) return 'bg-(--color-noor-600)/15'
  if (score >= 50) return 'bg-amber-400/15'
  return 'bg-red-500/15'
}

function getHistoryProgressValue(job: Job) {
  if (job.status === 'completed') return 100
  if (['failed', 'cancelled', 'skipped'].includes(job.status)) return 0
  return job.progress || 0
}

function getReportMetrics(job: Job) {
  const diagnostics = getRecommendedDiagnostics(job)
  const execution = getWhisperExecution(job)
  const rows = [
    { label: t('history.report.duration'), value: getJobDuration(job) },
    { label: t('history.report.progress'), value: `${getHistoryProgressValue(job)}%` },
    { label: t('history.report.type'), value: job.job_type || 'lada' },
    { label: t('history.report.output'), value: job.output_path || t('history.report.none') },
  ]
  if (execution?.summary) rows.push({ label: t('history.report.strategy'), value: execution.summary })
  if (diagnostics) {
    rows.push({ label: t('history.report.segments'), value: String(diagnostics.segment_count) })
    rows.push({ label: t('history.report.aligned'), value: `${diagnostics.aligned_segments}/${diagnostics.segment_count}` })
    rows.push({ label: t('history.report.fallback'), value: `large-v3 ${diagnostics.large_v3_retry_segments} · Qwen ${diagnostics.qwen_retry_segments}` })
  }
  if (job.error_message) rows.push({ label: t('history.report.error'), value: job.error_message })
  return rows
}

function getReportNotes(job: Job) {
  const notes: string[] = []
  const execution = getWhisperExecution(job)
  if (execution?.detail_lines?.length) notes.push(...execution.detail_lines)
  const diagnostics = getRecommendedDiagnostics(job)
  if (diagnostics?.cleanup) {
    notes.push(`${t('history.report.cleanup')}: ${diagnostics.cleanup.before_segments} → ${diagnostics.cleanup.after_segments}, ${t('history.report.deduped')} ${diagnostics.cleanup.deduped_segments}`)
  }
  if (!notes.length) notes.push(t('history.report.noExtraData'))
  return notes
}

function toggleJobReport(job: Job) {
  expandedJobId.value = expandedJobId.value === job.id ? '' : job.id
  if (expandedJobId.value && !jobs.jobLogs[job.id]) {
    jobs.fetchJobLogs(job.id).catch(() => [])
  }
}

function downloadOutput(job: Job) {
  if (job.output_path) window.open(`/api/jobs/${job.id}/download`, '_blank')
}

async function deleteJob(job: Job) {
  if (!await confirm({ message: t('history.deleteConfirm'), danger: true })) return
  try {
    await jobs.deleteJob(job.id)
    if (expandedJobId.value === job.id) expandedJobId.value = ''
  } catch (e: any) {
    toast.error(t('common.errorWithDetail', { detail: e?.response?.data?.detail || e.message }))
  }
}

function meta(job: Job, keys: string[]) { return metadataValue(job.result_metadata, keys) }

onMounted(() => jobs.fetchJobs())
</script>

<template>
  <UDashboardPanel id="history" grow>
    <template #header>
      <UDashboardNavbar :title="t('history.title')">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #right>
          <UButton color="neutral" variant="ghost" icon="i-heroicons-arrow-path-20-solid" @click="jobs.fetchJobs()">{{ t('common.refresh') }}</UButton>
        </template>
      </UDashboardNavbar>

      <UDashboardToolbar>
        <UNavigationMenu :items="filterTabs" highlight class="-mx-1 flex-1" />
      </UDashboardToolbar>
    </template>

    <template #body>
      <div v-if="jobs.loading" class="flex flex-col items-center justify-center py-12 text-(--ui-text-muted)">
        <UIcon name="i-heroicons-arrow-path-20-solid" class="w-8 h-8 animate-spin mb-4" />
        <p>{{ t('common.loading') }}</p>
      </div>

      <div v-else-if="jobs.error" class="flex flex-col items-center justify-center py-12">
        <UIcon name="i-heroicons-exclamation-triangle-20-solid" class="w-12 h-12 text-(--ui-error) mb-4" />
        <p class="text-(--ui-error) font-medium">{{ jobs.error }}</p>
      </div>

      <div v-else-if="!sortedJobs.length" class="flex flex-col items-center justify-center py-12 text-(--ui-text-muted)">
        <UIcon name="i-heroicons-inbox-20-solid" class="w-12 h-12 mb-4 opacity-50" />
        <p>{{ t('history.noHistory') }}</p>
        <p class="text-xs mt-1">{{ t('history.noHistoryDesc') }}</p>
      </div>

      <template v-else>
        <div class="mb-4 text-xs text-(--ui-text-muted)">{{ t('history.recordCount', { n: sortedJobs.length }) }}</div>

        <div class="space-y-3">
          <UCard v-for="job in pagedJobs" :key="job.id" class="overflow-hidden cursor-pointer" @click="toggleJobReport(job)">
            <template #header>
              <div class="flex items-start justify-between gap-4">
                <div class="flex items-center gap-3 min-w-0">
                  <div class="w-10 h-10 rounded-md bg-(--color-noor-600) flex items-center justify-center text-white shrink-0">
                    <UIcon name="i-heroicons-film-20-solid" class="w-4 h-4" />
                  </div>
                  <div class="min-w-0">
                    <h3 class="text-sm font-semibold truncate max-w-[300px]">{{ jobTitle(job) }}</h3>
                    <p class="text-xs text-(--ui-text-muted) truncate max-w-[350px] mt-0.5">{{ job.input_path }}</p>
                    <div v-if="job.detail" class="text-[11px] text-(--ui-text-muted) truncate max-w-[300px] mt-0.5">{{ job.detail }}</div>
                  </div>
                </div>
                <div class="flex items-center gap-3 shrink-0">
                  <div class="hidden sm:flex items-center gap-2 w-28">
                    <UProgress :value="getHistoryProgressValue(job)" :color="job.status === 'completed' ? 'success' : job.status === 'failed' ? 'error' : 'warning'" size="xs" class="flex-1" />
                    <span class="text-xs text-(--ui-text-muted) w-10 text-right">{{ getHistoryProgressValue(job) }}%</span>
                  </div>
                  <UBadge :color="historyStatusTone(job.status)" variant="subtle">{{ statusLabel(job.status) }}</UBadge>
                </div>
              </div>
            </template>

            <div class="flex items-center justify-between text-xs text-(--ui-text-muted)">
              <span>{{ formatDate(job.created_at) }}</span>
              <span>{{ formatDate(job.completed_at) }}</span>
              <div class="flex items-center gap-2" @click.stop>
                <UButton v-if="job.status === 'completed' && job.output_path" color="primary" variant="soft" size="xs" @click="downloadOutput(job)">{{ t('common.download') }}</UButton>
                <UButton color="error" variant="ghost" size="xs" icon="i-heroicons-trash-20-solid" @click="deleteJob(job)" />
              </div>
            </div>

            <!-- Expanded report -->
            <div v-if="expandedJobId === job.id" class="mt-4 p-4 rounded-xl bg-(--ui-bg-elevated)/50 border border-(--ui-border) space-y-4" @click.stop>
              <div class="grid grid-cols-1 md:grid-cols-[8.5rem_1fr] gap-4">
                <!-- Quality score -->
                <div class="flex flex-col items-center justify-center py-4 rounded-xl" :class="qualityToneClass(getQualityScore(job))">
                  <span class="text-[11px] text-(--ui-text-muted)">{{ t('history.report.quality') }}</span>
                  <strong class="text-2xl font-bold">{{ getQualityScore(job) === null ? '--' : getQualityScore(job) }}</strong>
                  <span class="text-xs text-(--ui-text-muted)">{{ getQualityScore(job) === null ? t('history.report.insufficient') : '/ 100' }}</span>
                </div>

                <!-- Metrics -->
                <div class="grid grid-cols-2 lg:grid-cols-4 gap-2">
                  <div v-for="metric in getReportMetrics(job)" :key="metric.label" class="p-3 rounded-xl bg-(--ui-bg)/50">
                    <div class="text-[11px] text-(--ui-text-muted)">{{ metric.label }}</div>
                    <div class="text-sm font-medium mt-1 break-all">{{ metric.value }}</div>
                  </div>
                </div>
              </div>

              <!-- Notes -->
              <div class="p-3 rounded-xl bg-(--ui-bg)/30">
                <p class="mb-1.5 text-xs font-semibold text-(--ui-text-muted)">{{ t('history.report.details') }}</p>
                <p v-for="(note, i) in getReportNotes(job)" :key="i" class="my-1 text-xs leading-5 text-(--ui-text-dimmed)">{{ note }}</p>
              </div>
            </div>
          </UCard>
        </div>

        <div v-if="totalPages > 1" class="mt-4 flex justify-center">
          <UPagination v-model="currentPage" :total="sortedJobs.length" :items-per-page="pageSize" />
        </div>
      </template>
    </template>
  </UDashboardPanel>
</template>
