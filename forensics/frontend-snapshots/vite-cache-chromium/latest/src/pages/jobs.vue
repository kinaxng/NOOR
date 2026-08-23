<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useJobsStore } from '../stores/jobs'
import { useToast } from '../composables/useToast'
import { useI18n } from '../composables/useI18n'
import { formatBytes, formatDate, formatDuration, jobQualityScore, jobTitle, metadataValue, pipelineLabel, statusLabel, statusTone } from '../app/format'
import { sortRunningJobsForList, sortJobsForList } from '../composables/jobOrdering'
import type { Job, JobStatus, SSEEvent } from '../api/types'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const jobs = useJobsStore()
const toast = useToast()
const tab = ref((route.query.tab as string) || 'active')
const page = ref(1)
const pageSize = 10
const expandedJobId = ref('')
const selectedJobId = ref('')
const showLogViewer = ref(false)
const liveAutoScroll = ref(true)

const tabs = computed(() => [
  { label: t('jobs.running'), icon: 'i-lucide-play', badge: jobs.activeJobs.length, to: '/jobs' },
  { label: t('jobs.status.completed'), icon: 'i-lucide-check-circle', badge: jobs.completedJobs.length, to: { query: { tab: 'completed' } } },
  { label: t('jobs.status.failed'), icon: 'i-lucide-x-circle', badge: jobs.failedJobs.length, to: { query: { tab: 'failed' } } },
])

const sortedJobs = computed(() => {
  if (tab.value === 'completed') return sortJobsForList(jobs.completedJobs)
  if (tab.value === 'failed') return sortJobsForList(jobs.failedJobs)
  return sortRunningJobsForList(jobs.activeJobs)
})

const pagedJobs = computed(() =>
  sortedJobs.value.slice((page.value - 1) * pageSize, page.value * pageSize)
)

const selectedJob = computed(() => jobs.jobs.find(j => j.id === selectedJobId.value) || null)

const selectedJobLogEntries = computed(() => {
  const stored = jobs.jobLogs[selectedJobId.value] || []
  const live = jobs.liveLogBuffer.filter(l => l.jobId === selectedJobId.value).map(l => l.line)
  return [...stored.map(s => typeof s === 'string' ? s : (s as any).line || JSON.stringify(s)), ...live]
})

const chainMembers = computed(() => {
  if (!selectedJob.value?.chain_id) return []
  return jobs.jobs
    .filter(j => j.chain_id === selectedJob.value!.chain_id)
    .sort((a, b) => new Date(a.created_at || 0).getTime() - new Date(b.created_at || 0).getTime())
})

watch(tab, () => { page.value = 1; expandedJobId.value = ''; selectedJobId.value = '' })
watch(() => route.query.tab, (val) => {
	  if (val && ['active', 'completed', 'failed'].includes(val as string)) {
	    tab.value = val as string
	  } else if (!val) {
	    tab.value = 'active'
	  }
	})

async function toggleReport(job: Job) {
  expandedJobId.value = expandedJobId.value === job.id ? '' : job.id
  if (expandedJobId.value && !jobs.jobLogs[job.id]) {
    await jobs.fetchJobLogs(job.id).catch(() => [])
  }
}

function selectJob(job: Job) {
  selectedJobId.value = selectedJobId.value === job.id ? '' : job.id
  if (selectedJobId.value) {
    showLogViewer.value = false
    if (!jobs.jobLogs[job.id]) jobs.fetchJobLogs(job.id).catch(() => [])
  }
}

function toggleLogViewer() {
  showLogViewer.value = !showLogViewer.value
  liveAutoScroll.value = true
}

function copyAllLogs() {
  const all = selectedJobLogEntries.value.join('\n')
  navigator.clipboard.writeText(all).then(() => toast.success(t('jobs.logsCopied')))
}

async function handleCancel(job: Job) {
  try {
    await jobs.cancelJob(job.id)
    toast.success(t('jobs.cancelSuccess'))
  } catch (e: any) { toast.error(e?.message || t('jobs.cancelFailed')) }
}

function downloadJob(job: Job) {
  if (typeof window !== 'undefined') window.open(`/api/jobs/${job.id}/download`, '_blank')
}

async function handleDelete(job: Job) {
  try {
    await jobs.deleteJob(job.id)
    if (selectedJobId.value === job.id) selectedJobId.value = ''
    if (expandedJobId.value === job.id) expandedJobId.value = ''
  } catch (e: any) { toast.error(e?.message || t('jobs.deleteFailed')) }
}

async function handleCleanup() {
  const result = await jobs.cleanupJobs()
  const n = (result as any)?.cleaned || 0
  if (n > 0) toast.success(t('jobs.cleanup.done', { n }))
  else toast.info(t('jobs.cleanup.none'))
}

function meta(job: Job, keys: string[]) { return metadataValue(job.result_metadata, keys) }

function getStatusColor(status: string) {
  const tone = statusTone(status as JobStatus)
  if (tone === 'success') return 'success'
  if (tone === 'warning') return 'warning'
  if (tone === 'danger') return 'error'
  if (tone === 'info') return 'info'
  return 'neutral'
}

function chainStepLabel(job: Job) {
  if (job.job_type === 'whisper' || job.job_type === 'whisper_transcribe') return t('jobs.chain.stepTranscribe')
  if (job.job_type === 'translate-srt' || job.job_type === 'subtitle_translate') return t('jobs.chain.stepTranslate')
  if (job.job_type === 'lada' || job.job_type === 'lada_restore') return t('jobs.chain.stepProcess')
  return t('jobs.chain.stepTask')
}

function chainRoleLabel(job: Job) {
  if (!job.chain_id) return ''
  if (job.depends_on_task_id) return t('jobs.chain.roleFollowup')
  if (jobs.jobs.some(j => j.depends_on_task_id === job.id)) return t('jobs.chain.rolePrimary')
  return ''
}

// Connect SSE for all active jobs
function connectActiveJobsSSE() {
  for (const job of jobs.activeJobs) {
    if (!jobs.sseConnected.has(job.id)) {
      jobs.connectToEvents(job.id, (event: SSEEvent) => {
        if (event.type === 'progress' || event.type === 'queued' || event.type === 'blocked') {
          // store already updated in connectToEvents
        } else if (event.type === 'completed' || event.type === 'failed' || event.type === 'cancelled' || event.type === 'skipped') {
          toast.info(`任务 ${jobTitle(job)} ${statusLabel(event.type)}`)
        }
      })
    }
  }
}

onMounted(async () => {
  await jobs.fetchJobs()
  connectActiveJobsSSE()
})

// Reconnect SSE when active jobs change
watch(() => jobs.activeJobs.length, () => connectActiveJobsSSE())

onBeforeUnmount(() => {
  jobs.disconnectFromEvents()
})
</script>

<template>
  <UDashboardPanel id="jobs" grow>
    <template #header>
      <UDashboardNavbar :title="t('jobs.title')">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #right>
          <div class="flex items-center gap-2">
            <UButton color="neutral" variant="ghost" @click="handleCleanup">{{ t('jobs.cleanup') }}</UButton>
            <UButton color="neutral" variant="ghost" icon="i-heroicons-arrow-path-20-solid" @click="jobs.fetchJobs()">{{ t('common.refresh') }}</UButton>
          </div>
        </template>
      </UDashboardNavbar>

      <UDashboardToolbar>
        <UNavigationMenu :items="tabs" highlight class="-mx-1 flex-1" />
      </UDashboardToolbar>
    </template>

    <template #body>
      <!-- Loading -->
      <div v-if="jobs.loading" class="flex flex-col items-center justify-center py-12 text-(--ui-text-muted)">
        <UIcon name="i-heroicons-arrow-path-20-solid" class="w-8 h-8 animate-spin mb-4" />
        <p>{{ t('common.loading') }}</p>
      </div>

      <!-- Error -->
      <div v-else-if="jobs.error" class="flex flex-col items-center justify-center py-12">
        <UIcon name="i-heroicons-exclamation-triangle-20-solid" class="w-12 h-12 text-(--ui-error) mb-4" />
        <p class="text-(--ui-error) font-medium">{{ jobs.error }}</p>
      </div>

      <!-- Empty -->
      <div v-else-if="!sortedJobs.length" class="flex flex-col items-center justify-center py-12 text-(--ui-text-muted)">
        <UIcon name="i-heroicons-inbox-20-solid" class="w-12 h-12 mb-4 opacity-50" />
        <p>{{ t('jobs.emptyTitle') }}</p>
      </div>

      <div v-else class="grid grid-cols-1" :class="selectedJobId ? 'lg:grid-cols-[1fr_380px]' : ''">
        <!-- Job list -->
        <div class="space-y-4 min-w-0">
          <UCard v-for="job in pagedJobs" :key="job.id" class="overflow-hidden cursor-pointer" :class="selectedJobId === job.id ? 'ring-1 ring-(--color-noor-500)' : ''" @click="selectJob(job)">
            <template #header>
              <div class="flex items-start justify-between gap-4">
                <div class="min-w-0 flex-1">
                  <div class="flex items-center gap-2">
                    <h3 class="text-base font-semibold truncate" :title="jobTitle(job)">{{ jobTitle(job) }}</h3>
                    <UIcon v-if="jobs.sseConnected.has(job.id)" name="i-heroicons-signal-20-solid" class="w-4 h-4 text-green-400 shrink-0" />
                  </div>
                  <p class="mt-1 text-sm text-(--ui-text-muted) truncate" :title="job.input_path">{{ job.input_path }}</p>
                  <div v-if="job.detail || job.phase_label" class="mt-1 flex items-center gap-2">
                    <span class="text-xs text-(--ui-text-muted) truncate">
                      {{ job.phase_group ? `${job.phase_group} · ` : '' }}{{ job.phase_label || job.detail }}
                    </span>
                  </div>
                </div>
                <UBadge :color="getStatusColor(job.status)" variant="subtle" class="shrink-0">
                  {{ statusLabel(job.status) }}
                </UBadge>
              </div>
            </template>

            <div class="space-y-4" @click.stop>
              <div class="flex items-center gap-3">
                <UProgress :value="Math.max(0, Math.min(100, job.progress || 0))" :color="getStatusColor(job.status)" class="flex-1" />
                <span class="text-sm font-medium text-(--ui-text-muted) w-12 text-right">{{ Math.round(job.progress || 0) }}%</span>
              </div>

              <div v-if="job.phase_progress != null && job.phase_progress > 0 && job.status === 'running'" class="flex items-center gap-3">
                <UProgress :value="job.phase_progress" color="info" class="flex-1" size="xs" />
                <span class="text-xs text-(--ui-text-muted) w-10 text-right">{{ Math.round(job.phase_progress) }}%</span>
                <span class="text-xs text-(--ui-text-muted) w-14 text-right shrink-0">{{ t('jobs.progress.phase') }}</span>
              </div>

              <div class="flex items-center justify-between text-sm text-(--ui-text-muted)">
                <span>{{ formatDate(job.created_at) }}</span>
                <span>{{ job.job_type }}</span>
              </div>

              <div class="flex items-center justify-end gap-2 pt-2 border-t border-(--ui-border)">
                <UButton color="neutral" variant="ghost" size="sm" @click="toggleReport(job)">
                  {{ expandedJobId === job.id ? t('jobs.hideReport') : t('jobs.showReport') }}
                </UButton>
                <UButton v-if="['pending', 'queued', 'running', 'blocked'].includes(job.status)" color="error" variant="soft" size="sm" @click="handleCancel(job)">{{ t('jobs.cancel') }}</UButton>
                <UButton v-if="job.status === 'completed' && job.output_path" color="primary" variant="soft" size="sm" @click="downloadJob(job)">{{ t('common.download') }}</UButton>
                <UButton color="neutral" variant="ghost" size="sm" icon="i-heroicons-trash-20-solid" @click="handleDelete(job)" />
              </div>
            </div>

            <!-- Report block -->
            <div v-if="expandedJobId === job.id" class="mt-4 p-4 rounded-lg space-y-4 text-sm job-report" @click.stop>
              <div class="grid grid-cols-2 sm:grid-cols-4 gap-4">
                <div>
                  <div class="text-(--ui-text-muted) mb-1">{{ t('jobs.report.duration') }}</div>
                  <div class="font-medium">{{ formatDuration(job.created_at, job.completed_at) }}</div>
                </div>
                <div>
                  <div class="text-(--ui-text-muted) mb-1">{{ t('jobs.report.quality') }}</div>
                  <div class="font-medium">{{ jobQualityScore(job) }}</div>
                </div>
                <div>
                  <div class="text-(--ui-text-muted) mb-1">{{ t('jobs.report.outputSize') }}</div>
                  <div class="font-medium">{{ formatBytes(meta(job, ['output_size', 'output_bytes', 'file_size']) as any) }}</div>
                </div>
                <div>
                  <div class="text-(--ui-text-muted) mb-1">{{ t('jobs.report.phase') }}</div>
                  <div class="font-medium">{{ job.phase_label || job.phase_key || '-' }}</div>
                </div>
              </div>

              <div class="space-y-2 pt-4 border-t border-(--ui-border)">
                <div v-if="job.error_message" class="grid grid-cols-[60px_1fr] gap-2">
                  <div class="text-(--ui-text-muted)">{{ t('history.report.error') }}</div>
                  <div class="text-(--ui-error) font-mono text-xs break-all">{{ job.error_message }}</div>
                </div>
                <div class="grid grid-cols-[60px_1fr] gap-2">
                  <div class="text-(--ui-text-muted)">{{ t('jobs.report.input') }}</div>
                  <div class="font-mono text-xs break-all text-(--ui-text-dimmed)">{{ job.input_path }}</div>
                </div>
                <div class="grid grid-cols-[60px_1fr] gap-2">
                  <div class="text-(--ui-text-muted)">{{ t('jobs.report.output') }}</div>
                  <div class="font-mono text-xs break-all text-(--ui-text-dimmed)">{{ job.output_path || '-' }}</div>
                </div>
                <div class="grid grid-cols-[60px_1fr] gap-2">
                  <div class="text-(--ui-text-muted)">{{ t('jobs.report.pipeline') }}</div>
                  <div>{{ pipelineLabel(job.settings?.strategy || job.settings?.pipeline_mode || job.job_type) }}</div>
                </div>
              </div>
            </div>
          </UCard>
        </div>

        <!-- Side detail panel -->
        <div v-if="selectedJobId" class="space-y-4 min-w-0">
          <UCard>
            <template #header>
              <div class="flex items-center justify-between">
                <h3 class="text-base font-semibold truncate">{{ jobTitle(selectedJob!) }}</h3>
                <div class="flex items-center gap-1">
                  <UButton color="neutral" variant="ghost" size="xs" icon="i-heroicons-document-text-20-solid" :class="showLogViewer ? 'text-(--color-noor-400)' : ''" @click="toggleLogViewer" />
                  <UButton color="neutral" variant="ghost" size="xs" icon="i-heroicons-x-mark-20-solid" @click="selectedJobId = ''" />
                </div>
              </div>
            </template>

            <div class="space-y-4 text-sm">
              <!-- Job chain -->
              <div v-if="chainMembers.length > 1" class="space-y-2">
                <h4 class="text-xs font-semibold text-(--ui-text-muted) uppercase tracking-wider">{{ t('jobs.chain.title') }}</h4>
                <div v-for="(member, idx) in chainMembers" :key="member.id" class="flex items-center gap-2 p-2 rounded-md" :class="member.id === selectedJobId ? 'bg-(--color-noor-600)/20 border border-(--color-noor-500)/30' : 'bg-(--ui-bg-elevated)/50'">
                  <span class="text-xs text-(--ui-text-muted) w-6 shrink-0">{{ idx + 1 }}</span>
                  <div class="min-w-0 flex-1">
                    <div class="text-xs font-medium truncate">{{ chainStepLabel(member) }}</div>
                    <div class="text-xs text-(--ui-text-muted) truncate">{{ jobTitle(member) }}</div>
                  </div>
                  <div class="flex items-center gap-1 shrink-0">
                    <span v-if="chainRoleLabel(member)" class="text-[10px] text-(--ui-text-muted)">{{ chainRoleLabel(member) }}</span>
                    <UBadge :color="getStatusColor(member.status)" variant="subtle" size="xs">
                      {{ statusLabel(member.status) }}
                    </UBadge>
                  </div>
                </div>
              </div>

              <!-- Log viewer -->
              <div v-if="showLogViewer" class="space-y-2">
                <div class="flex items-center justify-between">
                  <h4 class="text-xs font-semibold text-(--ui-text-muted) uppercase tracking-wider">{{ t('jobs.logsTitle') }}</h4>
                  <div class="flex items-center gap-1">
                    <UButton color="neutral" variant="ghost" size="2xs" @click="copyAllLogs">{{ t('jobs.copyAllLogs') }}</UButton>
                    <UButton color="neutral" variant="ghost" size="2xs" :class="liveAutoScroll ? 'text-(--color-noor-400)' : ''" @click="liveAutoScroll = !liveAutoScroll">
                      {{ liveAutoScroll ? t('jobs.logs.autoScroll') : t('jobs.logs.manual') }}
                    </UButton>
                  </div>
                </div>
                <div ref="logContainer" class="max-h-[400px] overflow-auto rounded-md p-3 bg-(--ui-bg) border border-(--ui-border) font-mono text-xs leading-relaxed">
                  <div v-if="!selectedJobLogEntries.length" class="text-(--ui-text-muted)">{{ t('jobs.logs.waiting') }}</div>
                  <div v-for="(line, i) in selectedJobLogEntries" :key="i" class="text-(--ui-text-dimmed) whitespace-pre-wrap break-all">{{ line }}</div>
                </div>
              </div>

              <!-- Diagnostics -->
              <div v-if="(selectedJob?.result_metadata as any)?.recommended_diagnostics" class="space-y-2">
                <h4 class="text-xs font-semibold text-(--ui-text-muted) uppercase tracking-wider">{{ t('jobs.diagnosticsTitle') }}</h4>
                <div class="grid grid-cols-2 gap-2">
                  <div v-if="(selectedJob!.result_metadata as any).recommended_diagnostics.segment_count" class="p-2 rounded bg-(--ui-bg-elevated)">
                    <div class="text-xs text-(--ui-text-muted)">{{ t('jobs.diagnostics.segments') }}</div>
                    <div class="font-medium">{{ (selectedJob!.result_metadata as any).recommended_diagnostics.segment_count }}</div>
                  </div>
                  <div v-if="(selectedJob!.result_metadata as any).recommended_diagnostics.aligned_segments != null" class="p-2 rounded bg-(--ui-bg-elevated)">
                    <div class="text-xs text-(--ui-text-muted)">{{ t('jobs.diagnosticsAligned') }}</div>
                    <div class="font-medium">{{ (selectedJob!.result_metadata as any).recommended_diagnostics.aligned_segments }}/{{ (selectedJob!.result_metadata as any).recommended_diagnostics.segment_count }}</div>
                  </div>
                  <div v-if="(selectedJob!.result_metadata as any).recommended_diagnostics.large_v3_retry_segments" class="p-2 rounded bg-(--ui-bg-elevated)">
                    <div class="text-xs text-(--ui-text-muted)">{{ t('jobs.diagnosticsLargeV3') }}</div>
                    <div class="font-medium">{{ (selectedJob!.result_metadata as any).recommended_diagnostics.large_v3_retry_segments }}</div>
                  </div>
                  <div v-if="(selectedJob!.result_metadata as any).recommended_diagnostics.qwen_retry_segments" class="p-2 rounded bg-(--ui-bg-elevated)">
                    <div class="text-xs text-(--ui-text-muted)">{{ t('jobs.diagnosticsFallback') }}</div>
                    <div class="font-medium">{{ (selectedJob!.result_metadata as any).recommended_diagnostics.qwen_retry_segments }}</div>
                  </div>
                </div>
              </div>
            </div>
          </UCard>
        </div>
      </div>

      <div v-if="sortedJobs.length > pageSize" class="mt-4 flex justify-center">
        <UPagination v-model="page" :total="sortedJobs.length" :items-per-page="pageSize" />
      </div>

      <!-- Toast container -->
      <div class="fixed bottom-4 right-4 z-50 flex flex-col gap-2">
        <div v-for="toast in useToast().toasts.value" :key="toast.id" class="px-4 py-3 rounded-lg shadow-lg text-sm font-medium animate-fade-in max-w-sm"
          :class="{
            'bg-green-600 text-white': toast.type === 'success',
            'bg-red-600 text-white': toast.type === 'error',
            'bg-amber-500 text-black': toast.type === 'warning',
            'bg-blue-500 text-white': toast.type === 'info',
          }">
          {{ toast.message }}
        </div>
      </div>
    </template>
  </UDashboardPanel>
</template>
