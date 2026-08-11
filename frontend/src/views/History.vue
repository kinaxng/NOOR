
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

const { t, i18nVersion } = useI18n()
const { getStatusTone, getTerminalBadgeVariant, getTerminalBadgeLabel, getHistoryProgressValue, getHistoryProgressTone, getActivityDetailLine, getJobDisplayName, formatJobDateTime } = useJobPresentation(() => jobsStore.jobs)
const jobsStore = useJobsStore()
const toast = useToast()
const { confirm } = useConfirm()

const filter = ref<'all' | 'completed' | 'failed'>('all')
const currentPage = ref(1)
const PAGE_SIZE = 20

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

const totalPages = computed(() => Math.max(1, Math.ceil(filteredJobs.value.length / PAGE_SIZE)))
const pagedJobs = computed(() => {
  const start = (currentPage.value - 1) * PAGE_SIZE
  return filteredJobs.value.slice(start, start + PAGE_SIZE)
})

watch(filter, () => { currentPage.value = 1 })
watch(filteredJobs, () => {
  if (currentPage.value > totalPages.value) currentPage.value = totalPages.value
})

const historyTitle = computed(() => {
  void i18nVersion.value
  return t('history.title')
})
const colName = computed(() => { void i18nVersion.value; return t('history.col.name') })
const colStatus = computed(() => { void i18nVersion.value; return t('history.col.status') })
const colCreated = computed(() => { void i18nVersion.value; return t('history.col.created') })
const colCompleted = computed(() => { void i18nVersion.value; return t('history.col.completed') })
const colActions = computed(() => { void i18nVersion.value; return t('history.col.actions') })
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
            <tr
              v-for="job in pagedJobs"
              :key="job.id"
              class="table-row"
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
                <div class="flex items-center justify-end gap-2">
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
          </tbody>
        </table>
      </div>
      <NoorPagination
        v-model:page="currentPage"
        :total-pages="totalPages"
        class="table-card__pagination"
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

.table-card__pagination {
  padding: 0.9rem 1.5rem 1rem;
  border-top: 1px solid rgba(255, 255, 255, 0.055);
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
</style>
