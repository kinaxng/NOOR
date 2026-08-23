<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useJobsStore } from '../stores/jobs'
import NoorBadge from '../noor-kit/NoorBadge.vue'
import NoorButton from '../noor-kit/NoorButton.vue'
import NoorPagination from '../noor-kit/NoorPagination.vue'
import NoorState from '../noor-kit/NoorState.vue'
import NoorTabs from '../noor-kit/NoorTabs.vue'
import { formatBytes, formatDate, formatDuration, jobQualityScore, jobTitle, metadataValue, pipelineLabel, statusLabel, statusTone } from '../app/format'
import type { Job } from '../api/types'

const jobs = useJobsStore()
const tab = ref('active')
const page = ref(1)
const pageSize = 10
const expandedJobId = ref('')

const tabs = computed(() => [
  { key: 'active', label: `进行中 ${jobs.activeJobs.length}` },
  { key: 'completed', label: `已完成 ${jobs.completedJobs.length}` },
  { key: 'failed', label: `失败 ${jobs.failedJobs.length}` },
])

const visibleJobs = computed(() => {
  if (tab.value === 'completed') return jobs.completedJobs
  if (tab.value === 'failed') return jobs.failedJobs
  return jobs.activeJobs
})

const pagedJobs = computed(() => visibleJobs.value.slice((page.value - 1) * pageSize, page.value * pageSize))

watch(tab, () => {
  page.value = 1
  expandedJobId.value = ''
})

async function toggleReport(job: Job) {
  expandedJobId.value = expandedJobId.value === job.id ? '' : job.id
  if (expandedJobId.value && !jobs.jobLogs[job.id]) {
    await jobs.fetchJobLogs(job.id).catch(() => [])
  }
}

function meta(job: Job, keys: string[]) {
  return metadataValue(job.result_metadata, keys)
}

onMounted(() => jobs.fetchJobs())
</script>

<template>
  <section class="page stack">
    <div class="page-heading">
      <div>
        <h1>任务</h1>
        <p>运行队列、终态任务与清理操作。</p>
      </div>
      <div class="actions">
        <NoorButton @click="jobs.cleanupJobs()">清理孤立任务</NoorButton>
        <NoorButton tone="primary" @click="jobs.fetchJobs()">刷新</NoorButton>
      </div>
    </div>

    <NoorTabs v-model="tab" :tabs="tabs" />
    <NoorState v-if="jobs.loading" type="loading" title="加载任务" />
    <NoorState v-else-if="jobs.error" type="error" :title="jobs.error" />
    <NoorState v-else-if="!visibleJobs.length" type="empty" title="暂无任务" />

    <div v-else class="job-grid">
      <article v-for="job in pagedJobs" :key="job.id" class="job-card">
        <div class="job-card__head">
          <div>
            <h2>{{ jobTitle(job) }}</h2>
            <p>{{ job.input_path }}</p>
          </div>
          <NoorBadge :tone="statusTone(job.status)">{{ statusLabel(job.status) }}</NoorBadge>
        </div>
        <div class="progress"><i :style="{ width: `${Math.max(0, Math.min(100, job.progress || 0))}%` }" /></div>
        <div class="job-meta">
          <span>{{ Math.round(job.progress || 0) }}%</span>
          <span>{{ job.phase_label || job.detail || job.job_type || '任务' }}</span>
          <span>{{ formatDate(job.created_at) }}</span>
        </div>
        <div class="actions">
          <NoorButton tone="ghost" @click="toggleReport(job)">{{ expandedJobId === job.id ? '收起报告' : '报告' }}</NoorButton>
          <NoorButton v-if="['pending', 'queued', 'running', 'blocked'].includes(job.status)" tone="danger" @click="jobs.cancelJob(job.id)">取消</NoorButton>
          <NoorButton v-if="job.status === 'completed' && job.output_path" @click="window.open(`/api/jobs/${job.id}/download`, '_blank')">下载</NoorButton>
          <NoorButton tone="ghost" @click="jobs.deleteJob(job.id)">删除</NoorButton>
        </div>
        <section v-if="expandedJobId === job.id" class="job-report">
          <div class="report-grid">
            <div><span>总耗时</span><strong>{{ formatDuration(job.created_at, job.completed_at) }}</strong></div>
            <div><span>质量评分</span><strong>{{ jobQualityScore(job) }}</strong></div>
            <div><span>输出大小</span><strong>{{ formatBytes(meta(job, ['output_size', 'output_bytes', 'file_size']) as any) }}</strong></div>
            <div><span>阶段</span><strong>{{ job.phase_label || job.phase_key || '-' }}</strong></div>
          </div>
          <dl>
            <template v-if="job.error_message">
              <dt>错误</dt><dd>{{ job.error_message }}</dd>
            </template>
            <dt>输入</dt><dd>{{ job.input_path }}</dd>
            <dt>输出</dt><dd>{{ job.output_path || '-' }}</dd>
            <dt>链路</dt><dd>{{ pipelineLabel(job.settings?.strategy || job.settings?.pipeline_mode || job.job_type) }}</dd>
            <dt>日志</dt>
            <dd>
              <span v-if="jobs.logsLoading[job.id]">加载中</span>
              <span v-else>{{ (jobs.jobLogs[job.id] || job.logs || []).length }} 条</span>
            </dd>
          </dl>
        </section>
      </article>
    </div>
    <NoorPagination v-if="visibleJobs.length > pageSize" v-model:page="page" :total="visibleJobs.length" :page-size="pageSize" />
  </section>
</template>
