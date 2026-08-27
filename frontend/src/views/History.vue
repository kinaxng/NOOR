<script setup lang="ts">
import { ref, onMounted, computed, watch } from 'vue'
import { useJobsStore } from '../stores/jobs'
import { useI18n } from '../composables/useI18n'
import { useToast } from '../composables/useToast'
import { useConfirm } from '../composables/useConfirm'
import BaseIcon from '../components/noor/BaseIcon.vue'
import VuiBadge from '../components/ui/Badge/VuiBadge.vue'
import VuiButton from '../components/ui/Button/VuiButton.vue'
import VuiProgress from '../components/ui/Progress/VuiProgress.vue'
import VisionTabs from '../components/ui/Tabs.vue'
import NoorPagination from '../components/ui/Pagination.vue'
import { useJobPresentation } from '../composables/useJobPresentation'
import { sortJobsForList } from '../composables/jobOrdering'
import type { Job, RecommendedDiagnostics } from '../api/types'
import api from '../api'

const { t, i18nVersion } = useI18n()
const { getStatusTone, getTerminalBadgeVariant, getTerminalBadgeLabel, getHistoryProgressValue, getHistoryProgressTone, getActivityDetailLine, getJobDisplayName, formatJobDateTime } = useJobPresentation(() => jobsStore.jobs)
const jobsStore = useJobsStore()
const toast = useToast()
const { confirm } = useConfirm()

const filter = ref<'all' | 'completed' | 'failed'>('all')
const expandedJobId = ref<string | null>(null)
const historyPage = ref(1)
const HISTORY_PAGE_SIZE = 10
const reportLogs = ref<Record<string, string[]>>({})
const reportLogsLoading = ref<Record<string, boolean>>({})

const filterTabs = computed(() => {
  void i18nVersion.value
  return [
    { key: 'all', label: t('history.filter.all') },
    { key: 'completed', label: t('history.filter.completed') },
    { key: 'failed', label: t('history.filter.failed') },
  ]
})

onMounted(() => {
  jobsStore.fetchJobs()
})

const failedStatuses = ['failed', 'cancelled', 'skipped'] as const

const filteredJobs = computed(() => {
  const jobs = filter.value === 'all'
    ? jobsStore.jobs.filter(j => j.status === 'completed' || failedStatuses.includes(j.status as any))
    : filter.value === 'failed'
      ? jobsStore.jobs.filter(j => failedStatuses.includes(j.status as any))
      : jobsStore.jobs.filter(j => j.status === filter.value)

  return sortJobsForList(jobs)
})

const historyTotalPages = computed(() => Math.max(1, Math.ceil(filteredJobs.value.length / HISTORY_PAGE_SIZE)))
const paginatedJobs = computed(() => {
  const start = (historyPage.value - 1) * HISTORY_PAGE_SIZE
  return filteredJobs.value.slice(start, start + HISTORY_PAGE_SIZE)
})
watch([filter, () => filteredJobs.value.length], () => {
  historyPage.value = 1
  expandedJobId.value = null
})
function goHistoryPage(page: number) {
  historyPage.value = page
  expandedJobId.value = null
}


const historyTitle = computed(() => {
  void i18nVersion.value
  return t('history.title')
})
const colName = computed(() => { void i18nVersion.value; return t('history.col.name') })
const colStatus = computed(() => { void i18nVersion.value; return t('history.col.status') })
const colCreated = computed(() => { void i18nVersion.value; return t('history.col.created') })
const colCompleted = computed(() => { void i18nVersion.value; return t('history.col.completed') })
const colActions = computed(() => { void i18nVersion.value; return t('history.col.actions') })

function getErrorDetail(error: unknown) {
  if (typeof error === 'object' && error !== null) {
    const maybeMessage = (error as { message?: string }).message
    const maybeResponse = (error as { response?: { data?: { detail?: string } } }).response
    return maybeResponse?.data?.detail || maybeMessage || ''
  }
  return String(error ?? '')
}

async function toggleReport(job: Job) {
  expandedJobId.value = expandedJobId.value === job.id ? null : job.id
  if (expandedJobId.value === job.id && !reportLogs.value[job.id]) {
    await loadReportLogs(job.id)
  }
}

async function loadReportLogs(jobId: string) {
  reportLogsLoading.value[jobId] = true
  try {
    const resp = await api.get(`/jobs/${jobId}/logs`)
    const logs = Array.isArray(resp.data) ? resp.data : Array.isArray(resp.data?.logs) ? resp.data.logs : []
    reportLogs.value[jobId] = logs.slice(-80).map((line: any) => String(line))
  } catch (error) {
    reportLogs.value[jobId] = [`日志读取失败：${getErrorDetail(error)}`]
  } finally {
    reportLogsLoading.value[jobId] = false
  }
}

function getDurationMs(job: Job) {
  if (!job.created_at || !job.completed_at) return 0
  const start = new Date(job.created_at).getTime()
  const end = new Date(job.completed_at).getTime()
  if (!Number.isFinite(start) || !Number.isFinite(end) || end < start) return 0
  return end - start
}

function formatDuration(ms: number) {
  if (!ms) return '—'
  const totalSeconds = Math.round(ms / 1000)
  const hours = Math.floor(totalSeconds / 3600)
  const minutes = Math.floor((totalSeconds % 3600) / 60)
  const seconds = totalSeconds % 60
  if (hours) return `${hours}h ${minutes}m ${seconds}s`
  if (minutes) return `${minutes}m ${seconds}s`
  return `${seconds}s`
}

function getDiagnostics(job: Job) {
  return job.result_metadata?.recommended_diagnostics as RecommendedDiagnostics | undefined
}

function getReportScore(job: Job) {
  const diagnostics = getDiagnostics(job)
  let score = job.status === 'completed' ? 100 : 48
  if (diagnostics) {
    const segmentCount = Math.max(1, Number(diagnostics.segment_count || 1))
    score -= Math.min(18, (diagnostics.large_v3_retry_segments || 0) / segmentCount * 18)
    score -= Math.min(16, (diagnostics.qwen_retry_segments || 0) / segmentCount * 16)
    score -= Math.min(14, (diagnostics.stepdown_segments || 0) / segmentCount * 14)
    score -= Math.min(20, (diagnostics.aligner_empty_segments || 0) / segmentCount * 20)
    score -= Math.min(8, (diagnostics.cleanup?.noise_only_segments || 0) / segmentCount * 8)
  }
  if (job.error_message) score -= 12
  return Math.max(0, Math.min(100, Math.round(score)))
}

function getScoreTone(score: number) {
  if (score >= 86) return '优秀'
  if (score >= 70) return '可用'
  if (score >= 55) return '需复核'
  return '低可信'
}

function getReportSummary(job: Job) {
  const metadata = job.result_metadata || {}
  const execution = metadata.whisper_execution as Record<string, any> | undefined
  return [
    execution?.summary,
    execution?.strategy ? `链路：${execution.strategy}` : '',
    execution?.executor_key ? `执行器：${execution.executor_key}` : '',
    execution?.model ? `模型：${execution.model}` : '',
    execution?.pipeline_mode ? `模式：${execution.pipeline_mode}` : '',
    execution?.language ? `语言：${execution.language}` : '',
    job.input_path ? `输入：${job.input_path}` : '',
    job.output_path ? `输出：${job.output_path}` : '',
    job.error_message ? `错误：${job.error_message}` : '',
  ].filter(Boolean)
}

function getReportMeta(job: Job) {
  return [
    ['任务 ID', job.id],
    ['链路 ID', job.chain_id || '—'],
    ['父任务', job.parent_task_id || '—'],
    ['依赖任务', job.depends_on_task_id || '—'],
    ['创建', formatJobDateTime.value(job.created_at)],
    ['完成', formatJobDateTime.value(job.completed_at)],
    ['阶段', job.phase_label || job.phase_key || '—'],
  ]
}

function formatJson(value: unknown) {
  if (!value) return '—'
  try { return JSON.stringify(value, null, 2) } catch { return String(value) }
}

function getLogInsights(job: Job) {
  const lines = reportLogs.value[job.id] || []
  const lower = lines.map(line => line.toLowerCase())
  const errors = lines.filter((line, index) => lower[index].includes('error') || lower[index].includes('failed') || lower[index].includes('exception') || line.includes('失败')).slice(-8)
  const warnings = lines.filter((line, index) => lower[index].includes('warn') || lower[index].includes('fallback') || lower[index].includes('retry') || line.includes('补救')).slice(-8)
  return {
    total: lines.length,
    errors,
    warnings,
    tail: lines.slice(-12),
  }
}

function getDiagnosticsSummary(job: Job) {
  const diagnostics = getDiagnostics(job)
  if (!diagnostics) return []
  return [
    `对齐 ${diagnostics.aligned_segments}/${diagnostics.segment_count}`,
    `large-v3 补救 ${diagnostics.large_v3_retry_segments}`,
    `Qwen 补救 ${diagnostics.qwen_retry_segments}`,
    `降级 ${diagnostics.stepdown_segments}`,
    `空对齐 ${diagnostics.aligner_empty_segments}`,
    diagnostics.cleanup ? `噪声 ${diagnostics.cleanup.noise_only_segments}` : '',
  ].filter(Boolean)
}

function getStatusLabel(job: any) {
  return getTerminalBadgeLabel.value(job)
}

function downloadOutput(job: any) {
  if (job.output_path) {
    window.open(`/api/jobs/${job.id}/download`, '_blank')
  }
}

async function deleteJob(jobId: string) {
  if (!await confirm({ message: t('history.deleteConfirm'), danger: true })) return
  try {
    await jobsStore.deleteJob(jobId)
  } catch (e: any) {
    console.error('Delete failed:', e)
    toast.error(t('common.errorWithDetail', { detail: e?.response?.data?.detail || e.message }))
  }
}

</script>

<template>
  <div class="w-full space-y-6 animate-fade-in">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <VisionTabs v-model="filter" :tabs="filterTabs" />
    </div>

    <!-- Loading -->
    <div v-if="jobsStore.loading" class="flex items-center justify-center py-16">
      <div class="w-8 h-8 border-2 rounded-full animate-spin border-[#0075FF] border-t-transparent"></div>
    </div>

    <!-- Empty State -->
    <div v-else-if="filteredJobs.length === 0" class="empty-state-card flex flex-col items-center justify-center py-24 text-center">
      <div class="w-14 h-14 rounded-2xl flex items-center justify-center mb-4 empty-state-icon">
        <BaseIcon name="history" class="w-7 h-7 text-white/20" />
      </div>
      <h3 class="text-base font-medium mb-1 text-white font-display">{{ t('history.noHistory') }}</h3>
      <p class="text-sm text-white/30">{{ t('history.noHistoryDesc') }}</p>
    </div>

    <!-- Table Card -->
    <div v-else class="table-card ui-card">
      <!-- Table Header -->
      <div class="table-card__header">
        <div>
          <h2 class="table-card__title">{{ historyTitle }}</h2>
          <p class="table-card__subtitle">{{ t('history.recordCount', { n: filteredJobs.length }) }}</p>
        </div>
      </div>

      <!-- Table -->
      <div class="table-wrapper">
        <table class="w-full">
          <thead>
            <tr class="table-head-row">
              <th class="table-th">{{ colName }}</th>
              <th class="table-th">{{ colStatus }}</th>
              <th class="table-th">{{ colCreated }}</th>
              <th class="table-th">{{ colCompleted }}</th>
              <th class="table-th">{{ t('history.col.progress') }}</th>
              <th class="table-th text-right">{{ colActions }}</th>
            </tr>
          </thead>
          <tbody>
            <template v-for="job in paginatedJobs" :key="job.id">
              <tr
                class="table-row table-row--clickable"
                :class="{ 'table-row--expanded': expandedJobId === job.id }"
                @click="toggleReport(job)"
              >
                <td class="table-td">
                  <div class="table-name-cell">
                    <div class="table-avatar">
                      <BaseIcon name="jobs" class="w-4 h-4" />
                    </div>
                    <div>
                      <p class="table-name">{{ getJobDisplayName(job) }}</p>
                      <p class="table-path">{{ job.input_path }}</p>
                      <p v-if="getActivityDetailLine(job)" class="table-detail">{{ getActivityDetailLine(job) }}</p>
                    </div>
                  </div>
                </td>
                <td class="table-td">
                  <VuiBadge
                    :color="getStatusTone(job)"
                    :variant="getTerminalBadgeVariant(job.status)"
                    size="sm"
                  >
                    {{ getStatusLabel(job) }}
                  </VuiBadge>
                </td>
                <td class="table-td text-sm text-white/50">{{ formatJobDateTime(job.created_at) }}</td>
                <td class="table-td text-sm text-white/50">{{ formatJobDateTime(job.completed_at) }}</td>
                <td class="table-td">
                  <div class="table-progress">
                    <VuiProgress
                      :value="getHistoryProgressValue(job)"
                      :color="getHistoryProgressTone(job)"
                      variant="gradient"
                      class="table-progress__bar"
                    />
                    <span class="table-progress__text">{{ getHistoryProgressValue(job) }}%</span>
                  </div>
                </td>
                <td class="table-td text-right">
                  <div class="flex items-center justify-end gap-2" @click.stop>
                    <VuiButton
                      v-if="job.output_path"
                      variant="outlined"
                      color="secondary"
                      size="small"
                      @click="downloadOutput(job)"
                    >
                      {{ t('common.download') }}
                    </VuiButton>
                    <VuiButton
                      variant="outlined"
                      color="error"
                      size="small"
                      @click="deleteJob(job.id)"
                    >
                      {{ t('common.delete') }}
                    </VuiButton>
                  </div>
                </td>
              </tr>
              <tr v-if="expandedJobId === job.id" class="history-report-row">
                <td colspan="6" class="history-report-cell">
                  <div class="history-report">
                    <div class="history-report__score">
                      <strong>{{ getReportScore(job) }}</strong>
                      <span>{{ getScoreTone(getReportScore(job)) }}</span>
                    </div>
                    <div class="history-report__body">
                      <div class="history-report__metrics">
                        <span>总耗时：{{ formatDuration(getDurationMs(job)) }}</span>
                        <span>任务类型：{{ job.job_type || '—' }}</span>
                        <span>最终进度：{{ getHistoryProgressValue(job) }}%</span>
                        <span>日志采样：{{ getLogInsights(job).total }} 行</span>
                      </div>
                      <div v-if="getDiagnosticsSummary(job).length" class="history-report__chips">
                        <span v-for="item in getDiagnosticsSummary(job)" :key="item">{{ item }}</span>
                      </div>
                      <div class="history-report__grid">
                        <div class="history-report__block">
                          <h5>任务信息</h5>
                          <dl>
                            <template v-for="([label, value]) in getReportMeta(job)" :key="label">
                              <dt>{{ label }}</dt>
                              <dd>{{ value }}</dd>
                            </template>
                          </dl>
                        </div>
                        <div class="history-report__block">
                          <h5>执行摘要</h5>
                          <div class="history-report__lines">
                            <p v-for="line in getReportSummary(job)" :key="line">{{ line }}</p>
                            <p v-if="!getReportSummary(job).length && !getDiagnosticsSummary(job).length">暂无详细链路记录，仅展示基础任务信息。</p>
                          </div>
                        </div>
                        <div class="history-report__block">
                          <h5>日志分析</h5>
                          <div v-if="reportLogsLoading[job.id]" class="history-report__lines"><p>日志读取中…</p></div>
                          <div v-else class="history-report__lines">
                            <p v-if="getLogInsights(job).errors.length">错误/失败：{{ getLogInsights(job).errors.length }} 条</p>
                            <p v-if="getLogInsights(job).warnings.length">补救/警告：{{ getLogInsights(job).warnings.length }} 条</p>
                            <p v-if="!getLogInsights(job).errors.length && !getLogInsights(job).warnings.length">未从最近日志中识别到明显错误或补救信号。</p>
                          </div>
                        </div>
                      </div>
                      <details class="history-report__details">
                        <summary>查看最近日志</summary>
                        <pre>{{ (reportLogs[job.id] || []).slice(-30).join('\n') || '暂无日志' }}</pre>
                      </details>
                      <details class="history-report__details">
                        <summary>查看原始设置 / 结果元数据</summary>
                        <pre>settings = {{ formatJson(job.settings) }}

result_metadata = {{ formatJson(job.result_metadata) }}</pre>
                      </details>
                    </div>
                  </div>
                </td>
              </tr>
            </template>
          </tbody>
        </table>
      </div>
      <NoorPagination
        :page="historyPage"
        :total-pages="historyTotalPages"
        @page="goHistoryPage"
      />
    </div>
  </div>
</template>

<style scoped>
.table-card {
  overflow: hidden;
}

.table-card__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1.5rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

.table-card__title {
  font-family: var(--font-display);
  font-size: 1rem;
  font-weight: 700;
  color: #FFFFFF;
  margin-bottom: 0.25rem;
}

.table-card__subtitle {
  font-family: var(--font-display);
  font-size: 0.75rem;
  color: rgba(255, 255, 255, 0.4);
}

.table-wrapper {
  overflow-x: auto;
}

.table-head-row {
  background: rgba(255, 255, 255, 0.02);
}

.table-th {
  text-align: left;
  padding: 1rem 1.5rem;
  font-family: var(--font-display);
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: rgba(255, 255, 255, 0.4);
  white-space: nowrap;
}

.table-th.text-right {
  text-align: right;
}

.table-row {
  border-bottom: 1px solid rgba(255, 255, 255, 0.04);
  transition: background var(--transition-fast);
}

.table-row:hover {
  background: rgba(255, 255, 255, 0.02);
}

.table-row:last-child {
  border-bottom: none;
}

.table-td {
  padding: 1.25rem 1.5rem;
  vertical-align: middle;
}

.table-name-cell {
  display: flex;
  align-items: center;
  gap: 0.875rem;
}

.table-avatar {
  width: 2.5rem;
  height: 2.5rem;
  border-radius: var(--radius-md);
  background: #0075FF;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #FFFFFF;
  flex-shrink: 0;
}

.table-name {
  font-family: var(--font-display);
  font-size: 0.875rem;
  font-weight: 600;
  color: #FFFFFF;
  margin-bottom: 0.25rem;
  max-width: 250px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.table-path {
  font-family: var(--font-display);
  font-size: 0.75rem;
  color: rgba(255, 255, 255, 0.3);
  max-width: 300px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.table-detail {
  margin-top: 0.32rem;
  font-family: var(--font-display);
  font-size: 0.7rem;
  color: rgba(255, 255, 255, 0.46);
  max-width: 300px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.table-progress {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  min-width: 120px;
}

.table-progress__bar {
  flex: 1;
}

.table-progress__text {
  font-family: var(--font-display);
  font-size: 0.75rem;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.5);
  min-width: 2.5rem;
  text-align: right;
}

.text-right {
  text-align: right;
}

.table-row--clickable {
  cursor: pointer;
}

.table-row--expanded {
  background: rgba(0, 117, 255, 0.045);
}

.history-report-row {
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
}

.history-report-cell {
  padding: 0 1.5rem 1.25rem;
}

.history-report {
  display: flex;
  gap: 1rem;
  padding: 1rem;
  border-radius: var(--radius-lg);
  background: rgba(7, 12, 28, 0.56);
  border: 1px solid rgba(255, 255, 255, 0.06);
  animation: report-enter 180ms ease-out;
}

.history-report__score {
  width: 5rem;
  min-height: 5rem;
  display: grid;
  place-items: center;
  align-content: center;
  border-radius: var(--radius-md);
  background: linear-gradient(135deg, rgba(0,117,255,.26), rgba(0,212,255,.1));
  color: #fff;
  flex: none;
}

.history-report__score strong {
  font-size: 1.65rem;
  line-height: 1;
}

.history-report__score span {
  margin-top: .35rem;
  font-size: .72rem;
  color: rgba(255,255,255,.62);
}

.history-report__body {
  min-width: 0;
  display: grid;
  gap: .65rem;
}

.history-report__metrics,
.history-report__chips {
  display: flex;
  flex-wrap: wrap;
  gap: .5rem;
}

.history-report__metrics span,
.history-report__chips span {
  display: inline-flex;
  align-items: center;
  min-height: 1.6rem;
  padding: 0 .65rem;
  border-radius: 999px;
  background: rgba(255,255,255,.055);
  border: 1px solid rgba(255,255,255,.07);
  color: rgba(255,255,255,.62);
  font-size: .72rem;
}

.history-report__chips span {
  color: rgba(0,212,255,.82);
  background: rgba(0,212,255,.08);
  border-color: rgba(0,212,255,.16);
}

.history-report__lines {
  display: grid;
  gap: .3rem;
  color: rgba(255,255,255,.45);
  font-size: .76rem;
  line-height: 1.5;
  word-break: break-all;
}


.history-report__grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: .75rem;
}

.history-report__block {
  min-width: 0;
  padding: .78rem;
  border-radius: var(--radius-md);
  background: rgba(255,255,255,.035);
  border: 1px solid rgba(255,255,255,.055);
}

.history-report__block h5 {
  margin-bottom: .55rem;
  color: rgba(255,255,255,.8);
  font-size: .76rem;
  font-weight: 800;
}

.history-report__block dl {
  display: grid;
  grid-template-columns: 4.2rem minmax(0, 1fr);
  gap: .35rem .55rem;
  font-size: .72rem;
}

.history-report__block dt {
  color: rgba(255,255,255,.34);
}

.history-report__block dd {
  color: rgba(255,255,255,.58);
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.history-report__details {
  border-radius: var(--radius-md);
  border: 1px solid rgba(255,255,255,.055);
  background: rgba(255,255,255,.028);
  overflow: hidden;
}

.history-report__details summary {
  cursor: pointer;
  padding: .65rem .78rem;
  color: rgba(255,255,255,.62);
  font-size: .74rem;
  font-weight: 800;
}

.history-report__details pre {
  max-height: 18rem;
  overflow: auto;
  padding: .78rem;
  border-top: 1px solid rgba(255,255,255,.055);
  color: rgba(255,255,255,.54);
  font-size: .7rem;
  line-height: 1.55;
  white-space: pre-wrap;
  word-break: break-word;
}

@media (max-width: 980px) {
  .history-report__grid {
    grid-template-columns: 1fr;
  }
}

@keyframes report-enter {
  from { opacity: 0; transform: translateY(-4px); }
  to { opacity: 1; transform: translateY(0); }
}

@media (max-width: 768px) {
  .history-report {
    flex-direction: column;
  }
  .history-report__score {
    width: 100%;
    min-height: 4rem;
  }
}

</style>
