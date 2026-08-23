<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useJobsStore } from '../stores/jobs'
import { useI18n } from '../composables/useI18n'
import BaseIcon from '../components/BaseIcon.vue'
import VuiBadge from '../components/vision/VuiBadge/VuiBadge.vue'
import VuiButton from '../components/vision/VuiButton/VuiButton.vue'
import VuiProgress from '../components/vision/VuiProgress/VuiProgress.vue'

const { t } = useI18n()
const jobsStore = useJobsStore()

const filter = ref<'all' | 'completed' | 'failed'>('all')

const filterButtons = computed(() => [
  { key: 'all', labelKey: 'history.filter.all' },
  { key: 'completed', labelKey: 'history.filter.completed' },
  { key: 'failed', labelKey: 'history.filter.failed' }
] as const)

onMounted(() => {
  jobsStore.fetchJobs()
})

const filteredJobs = computed(() => {
  if (filter.value === 'all') {
    return jobsStore.jobs.filter(j => j.status === 'completed' || j.status === 'failed')
  }
  return jobsStore.jobs.filter(j => j.status === filter.value)
})

function formatDate(dateStr?: string) {
  if (!dateStr) return 'N/A'
  return new Date(dateStr).toLocaleString('zh-CN')
}

function downloadOutput(job: any) {
  if (job.output_path) {
    window.open(`/api/jobs/${job.id}/download`, '_blank')
  }
}

async function deleteJob(jobId: string) {
  if (confirm(t('history.deleteConfirm'))) {
    try {
      await jobsStore.deleteJob(jobId)
      await jobsStore.fetchJobs()
    } catch (e: any) {
      console.error('Delete failed:', e)
      alert(t('common.error') + ': ' + (e?.response?.data?.detail || e.message))
    }
  }
}

function getStatusInfo(status: string) {
  switch (status) {
    case 'completed':
      return { label: '完成', color: 'success' as const, variant: 'gradient' as const }
    case 'failed':
      return { label: '失败', color: 'error' as const, variant: 'gradient' as const }
    default:
      return { label: status, color: 'secondary' as const, variant: 'standard' as const }
  }
}

function getJobProgress(job: any) {
  if (job.status === 'completed') return 100
  if (job.status === 'failed') return 0
  return job.progress || 0
}
</script>

<template>
  <div class="max-w-[1400px] mx-auto space-y-6 animate-fade-in">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <div class="flex items-center gap-2">
        <button
          v-for="btn in filterButtons"
          :key="btn.key"
          @click="filter = btn.key"
          class="filter-btn"
          :class="{ 'filter-btn--active': filter === btn.key }"
        >
          {{ t(btn.labelKey) }}
        </button>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="jobsStore.loading" class="flex items-center justify-center py-16">
      <div class="w-8 h-8 border-2 rounded-full animate-spin border-[#0075FF] border-t-transparent"></div>
    </div>

    <!-- Empty State -->
    <div v-else-if="filteredJobs.length === 0" class="empty-state-card flex flex-col items-center justify-center py-24 text-center">
      <div class="w-14 h-14 rounded-2xl flex items-center justify-center mb-4" style="background: rgba(255,255,255,0.04);">
        <BaseIcon name="history" class="w-7 h-7 text-white/20" />
      </div>
      <h3 class="text-base font-medium mb-1 text-white font-display">暂无历史记录</h3>
      <p class="text-sm text-white/30">{{ t('history.noHistory') }}</p>
    </div>

    <!-- Table Card -->
    <div v-else class="table-card vision-card">
      <!-- Table Header -->
      <div class="table-card__header">
        <div>
          <h2 class="table-card__title">任务记录</h2>
          <p class="table-card__subtitle">共 {{ filteredJobs.length }} 条记录</p>
        </div>
      </div>

      <!-- Table -->
      <div class="table-wrapper">
        <table class="w-full">
          <thead>
            <tr class="table-head-row">
              <th class="table-th">名称</th>
              <th class="table-th">状态</th>
              <th class="table-th">创建时间</th>
              <th class="table-th">完成时间</th>
              <th class="table-th">进度</th>
              <th class="table-th text-right">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="job in filteredJobs"
              :key="job.id"
              class="table-row"
            >
              <td class="table-td">
                <div class="table-name-cell">
                  <div class="table-avatar">
                    <BaseIcon name="jobs" class="w-4 h-4" />
                  </div>
                  <div>
                    <p class="table-name">{{ job.emby_item_name || '未知任务' }}</p>
                    <p class="table-path">{{ job.input_path }}</p>
                  </div>
                </div>
              </td>
              <td class="table-td">
                <VuiBadge
                  :color="getStatusInfo(job.status).color"
                  :variant="getStatusInfo(job.status).variant"
                  size="sm"
                >
                  {{ getStatusInfo(job.status).label }}
                </VuiBadge>
              </td>
              <td class="table-td text-sm" style="color: rgba(255,255,255,0.5);">{{ formatDate(job.created_at) }}</td>
              <td class="table-td text-sm" style="color: rgba(255,255,255,0.5);">{{ formatDate(job.completed_at) }}</td>
              <td class="table-td">
                <div class="table-progress">
                  <VuiProgress
                    :value="getJobProgress(job)"
                    :color="job.status === 'completed' ? 'success' : job.status === 'failed' ? 'error' : 'info'"
                    variant="gradient"
                    class="table-progress__bar"
                  />
                  <span class="table-progress__text">{{ getJobProgress(job) }}%</span>
                </div>
              </td>
              <td class="table-td text-right">
                <div class="flex items-center justify-end gap-2">
                  <VuiButton
                    v-if="job.output_path"
                    variant="outlined"
                    color="secondary"
                    size="small"
                    @click="downloadOutput(job)"
                  >
                    下载
                  </VuiButton>
                  <VuiButton
                    variant="outlined"
                    color="error"
                    size="small"
                    @click="deleteJob(job.id)"
                  >
                    删除
                  </VuiButton>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<style scoped>
.filter-btn {
  padding: 0.5rem 1rem;
  border-radius: var(--radius-button);
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  font-family: var(--font-display);
  transition: all var(--transition-fast);
  background: rgba(255,255,255,0.03);
  border: 1px solid rgba(255,255,255,0.06);
  color: rgba(255,255,255,0.5);
  cursor: pointer;
}

.filter-btn:hover {
  background: rgba(255,255,255,0.06);
  color: rgba(255,255,255,0.7);
}

.filter-btn--active {
  background: #0075FF;
  color: white;
  box-shadow: 0 4px 12px rgba(0, 117, 255, 0.3);
  border-color: transparent;
}

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
</style>
