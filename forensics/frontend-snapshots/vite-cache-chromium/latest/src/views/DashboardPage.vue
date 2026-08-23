<script setup lang="ts">
import { computed, onMounted, onUnmounted } from 'vue'
import { RouterLink } from 'vue-router'
import { useJobsStore } from '../stores/jobs'
import NoorBadge from '../noor-kit/NoorBadge.vue'
import NoorState from '../noor-kit/NoorState.vue'
import { formatDate, jobTitle, statusLabel, statusTone } from '../app/format'

const jobs = useJobsStore()
let metricsTimer: number | undefined

const recentJobs = computed(() => jobs.jobs.slice(0, 6))
const runningCount = computed(() => jobs.activeJobs.length)

onMounted(async () => {
  await Promise.all([jobs.fetchJobs(), jobs.fetchMetrics()])
  metricsTimer = window.setInterval(() => jobs.fetchMetrics(), 5000)
})

onUnmounted(() => {
  if (metricsTimer) window.clearInterval(metricsTimer)
})
</script>

<template>
  <section class="page stack">
    <div class="page-heading">
      <div>
        <h1>概览</h1>
        <p>系统状态、任务队列与最近活动。</p>
      </div>
      <RouterLink class="link-button" to="/jobs">查看任务</RouterLink>
    </div>

    <div class="metric-grid">
      <div class="metric-card">
        <span>运行任务</span>
        <strong>{{ runningCount }}</strong>
      </div>
      <div class="metric-card">
        <span>历史记录</span>
        <strong>{{ jobs.historyJobs.length }}</strong>
      </div>
      <div class="metric-card">
        <span>GPU</span>
        <strong>{{ jobs.metrics?.gpu ? `${jobs.metrics.gpu.gpu_util}%` : '-' }}</strong>
      </div>
      <div class="metric-card">
        <span>CPU</span>
        <strong>{{ jobs.metrics?.cpu_mem ? `${jobs.metrics.cpu_mem.cpu_util}%` : '-' }}</strong>
      </div>
    </div>

    <NoorState v-if="jobs.loading" type="loading" title="加载任务" />
    <NoorState v-else-if="jobs.error" type="error" :title="jobs.error" />

    <div v-else class="panel">
      <div class="panel-title">
        <h2>最近任务</h2>
      </div>
      <div v-if="!recentJobs.length" class="muted">暂无任务</div>
      <div v-else class="list">
        <RouterLink v-for="job in recentJobs" :key="job.id" class="list-row" :to="{ path: '/jobs', query: { job: job.id } }">
          <div>
            <strong>{{ jobTitle(job) }}</strong>
            <span>{{ formatDate(job.created_at) }}</span>
          </div>
          <NoorBadge :tone="statusTone(job.status)">{{ statusLabel(job.status) }}</NoorBadge>
        </RouterLink>
      </div>
    </div>
  </section>
</template>
