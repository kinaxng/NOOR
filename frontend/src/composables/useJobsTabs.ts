import { computed, type Ref } from 'vue'
import type { Job } from '../api/types'
import { useI18n } from './useI18n'
import type { JobTabKey } from './useJobRuntimePresentation'
import { sortChainJobs, sortJobsForList, sortRunningJobsForList } from './jobOrdering'

export function useJobsTabs(allJobs: () => Job[], activeTab: Ref<JobTabKey>) {
  const { t } = useI18n()

  const tabRunningLabel = computed(() => t('jobs.running'))
  const tabCompletedLabel = computed(() => t('history.filter.completed'))
  const tabFailedLabel = computed(() => t('history.filter.failed'))
  const emptyRunningLabel = computed(() => t('jobs.noRunning'))
  const emptyCompletedLabel = computed(() => t('jobs.noCompleted'))
  const emptyFailedLabel = computed(() => t('jobs.noFailed'))

  const runningTabJobs = computed(() => sortRunningJobsForList(allJobs().filter(j => j.status === 'running' || j.status === 'queued' || j.status === 'blocked' || j.status === 'pending')))
  const completedTabJobs = computed(() => sortJobsForList(allJobs().filter(j => j.status === 'completed')))
  const failedTabJobs = computed(() => sortJobsForList(allJobs().filter(j => j.status === 'failed' || j.status === 'cancelled' || j.status === 'skipped')))

  const filterTabs = computed(() => [
    { key: 'running', label: `${tabRunningLabel.value} ${runningTabJobs.value.length}` },
    { key: 'completed', label: `${tabCompletedLabel.value} ${completedTabJobs.value.length}` },
    { key: 'failed', label: `${tabFailedLabel.value} ${failedTabJobs.value.length}` },
  ])

  const currentTabJobs = computed(() => {
    if (activeTab.value === 'running') return runningTabJobs.value
    if (activeTab.value === 'completed') return completedTabJobs.value
    if (activeTab.value === 'background') return []
    return failedTabJobs.value
  })

  const currentTabTitle = computed(() => {
    if (activeTab.value === 'running') return tabRunningLabel.value
    if (activeTab.value === 'completed') return tabCompletedLabel.value
    if (activeTab.value === 'background') return t('jobs.background')
    return tabFailedLabel.value
  })

  const currentEmptyLabel = computed(() => {
    if (activeTab.value === 'running') return emptyRunningLabel.value
    if (activeTab.value === 'completed') return emptyCompletedLabel.value
    if (activeTab.value === 'background') return t('jobs.noBackground')
    return emptyFailedLabel.value
  })

  return {
    sortChainJobs,
    filterTabs,
    currentTabJobs,
    currentTabTitle,
    currentEmptyLabel,
  }
}
