<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useJobsStore } from '../stores/jobs'
import NoorBadge from '../noor-kit/NoorBadge.vue'
import NoorButton from '../noor-kit/NoorButton.vue'
import NoorState from '../noor-kit/NoorState.vue'
import NoorTabs from '../noor-kit/NoorTabs.vue'
import { formatDate, jobTitle, statusLabel, statusTone } from '../app/format'

const jobs = useJobsStore()
const tab = ref('active')

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
      <article v-for="job in visibleJobs" :key="job.id" class="job-card">
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
          <NoorButton v-if="['pending', 'queued', 'running', 'blocked'].includes(job.status)" tone="danger" @click="jobs.cancelJob(job.id)">取消</NoorButton>
          <NoorButton v-if="job.status === 'completed' && job.output_path" @click="window.open(`/api/jobs/${job.id}/download`, '_blank')">下载</NoorButton>
          <NoorButton tone="ghost" @click="jobs.deleteJob(job.id)">删除</NoorButton>
        </div>
      </article>
    </div>
  </section>
</template>
