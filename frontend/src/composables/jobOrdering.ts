import type { Job } from '../api/types'

export const RUNNING_PHASE_ORDER: Record<string, number> = {
  prepare: 10,
  analyze: 20,
  transcribe: 30,
  retry: 40,
  align: 50,
  translate: 60,
  process: 70,
  encode: 80,
  output: 90,
}

export const RUNNING_STATUS_ORDER: Record<Job['status'], number> = {
  running: 0,
  queued: 1,
  blocked: 2,
  pending: 3,
  completed: 9,
  failed: 9,
  cancelled: 9,
  skipped: 9,
}

export function getCreatedAt(job: Job) {
  return new Date(job.created_at || 0).getTime()
}

export function getChainSortOrder(job: Job) {
  if (job.depends_on_task_id) return 1
  if (job.parent_task_id) return 1
  return 0
}

export function getRunningStatusSortOrder(job: Job) {
  return RUNNING_STATUS_ORDER[job.status] ?? 99
}

export function getRunningPhaseSortOrder(job: Job) {
  return RUNNING_PHASE_ORDER[job.phase_group || job.phase_key || ''] ?? 999
}

export function sortChainJobs(a: Job, b: Job) {
  const orderDiff = getChainSortOrder(a) - getChainSortOrder(b)
  if (orderDiff !== 0) return orderDiff
  return getCreatedAt(a) - getCreatedAt(b)
}

export function sortJobsForList(jobs: Job[]) {
  return [...jobs].sort((a, b) => {
    if (a.chain_id && b.chain_id && a.chain_id === b.chain_id) {
      const orderDiff = getChainSortOrder(a) - getChainSortOrder(b)
      if (orderDiff !== 0) return orderDiff
    }
    return getCreatedAt(b) - getCreatedAt(a)
  })
}

export function sortRunningJobsForList(jobs: Job[]) {
  return [...jobs].sort((a, b) => {
    const statusDiff = getRunningStatusSortOrder(a) - getRunningStatusSortOrder(b)
    if (statusDiff !== 0) return statusDiff

    const phaseDiff = getRunningPhaseSortOrder(a) - getRunningPhaseSortOrder(b)
    if (phaseDiff !== 0) return phaseDiff

    if (a.chain_id && b.chain_id && a.chain_id === b.chain_id) {
      const chainDiff = getChainSortOrder(a) - getChainSortOrder(b)
      if (chainDiff !== 0) return chainDiff
    }

    return getCreatedAt(b) - getCreatedAt(a)
  })
}
