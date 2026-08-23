<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useJobsStore } from '../stores/jobs'
import NoorBadge from '../noor-kit/NoorBadge.vue'
import NoorButton from '../noor-kit/NoorButton.vue'
import NoorPagination from '../noor-kit/NoorPagination.vue'
import NoorState from '../noor-kit/NoorState.vue'
import NoorTabs from '../noor-kit/NoorTabs.vue'
import { formatDate, jobTitle, statusLabel, statusTone } from '../app/format'

const jobs = useJobsStore()
const filter = ref('all')
const page = ref(1)
const pageSize = 10

const tabs = computed(() => [
  { key: 'all', label: '全部' },
  { key: 'completed', label: '已完成' },
  { key: 'failed', label: '失败' },
])

const filteredJobs = computed(() => {
  if (filter.value === 'completed') return jobs.completedJobs
  if (filter.value === 'failed') return jobs.failedJobs
  return jobs.historyJobs
})

const pagedJobs = computed(() => filteredJobs.value.slice((page.value - 1) * pageSize, page.value * pageSize))

onMounted(() => jobs.fetchJobs())
</script>

<template>
  <section class="page stack">
    <div class="page-heading">
      <div>
        <h1>历史</h1>
        <p>已完成、失败和取消的任务记录。</p>
      </div>
      <NoorButton tone="primary" @click="jobs.fetchJobs()">刷新</NoorButton>
    </div>

    <NoorTabs v-model="filter" :tabs="tabs" />
    <NoorState v-if="jobs.loading" type="loading" title="加载历史" />
    <NoorState v-else-if="jobs.error" type="error" :title="jobs.error" />
    <NoorState v-else-if="!filteredJobs.length" type="empty" title="暂无历史" />

    <div v-else class="table-panel">
      <table>
        <thead>
          <tr>
            <th>名称</th>
            <th>状态</th>
            <th>进度</th>
            <th>创建时间</th>
            <th>完成时间</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="job in pagedJobs" :key="job.id">
            <td>
              <strong>{{ jobTitle(job) }}</strong>
              <span>{{ job.input_path }}</span>
            </td>
            <td><NoorBadge :tone="statusTone(job.status)">{{ statusLabel(job.status) }}</NoorBadge></td>
            <td>{{ Math.round(job.progress || 0) }}%</td>
            <td>{{ formatDate(job.created_at) }}</td>
            <td>{{ formatDate(job.completed_at) }}</td>
            <td class="actions">
              <NoorButton v-if="job.status === 'completed' && job.output_path" @click="window.open(`/api/jobs/${job.id}/download`, '_blank')">下载</NoorButton>
              <NoorButton tone="ghost" @click="jobs.deleteJob(job.id)">删除</NoorButton>
            </td>
          </tr>
        </tbody>
      </table>
      <NoorPagination v-model:page="page" :total="filteredJobs.length" :page-size="pageSize" />
    </div>
  </section>
</template>
