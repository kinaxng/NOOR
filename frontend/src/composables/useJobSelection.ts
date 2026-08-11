import { ref } from 'vue'
import type { RouteLocationNormalizedLoaded, Router } from 'vue-router'
import type { Job } from '../api/types'
import api from '../api'
import type { JobTabKey } from './useJobRuntimePresentation'

export type JobLogEntry = { time: string; line: string }

type UseJobSelectionOptions = {
  route: RouteLocationNormalizedLoaded
  router: Router
  maxVisibleLogLines: number
  shouldWatchJob: (job: { status: string }) => boolean
  watchJob: (jobId: string) => Promise<void> | void
  getJobById: (jobId: string) => Job | null
  findJobByChainId: (chainId: string) => Job | null
  onFocusTab: (status: JobTabKey) => void
}

export function useJobSelection(options: UseJobSelectionOptions) {
  const {
    route,
    router,
    maxVisibleLogLines,
    shouldWatchJob,
    watchJob,
    getJobById,
    findJobByChainId,
    onFocusTab,
  } = options

  const logs = ref<JobLogEntry[]>([])
  const selectedJobId = ref<string | null>(null)
  const flashJobId = ref<string | null>(null)
  let flashTimer: ReturnType<typeof setTimeout> | null = null

  function dispose() {
    if (flashTimer) clearTimeout(flashTimer)
  }

  function flashFocusedJob(jobId: string) {
    flashJobId.value = jobId
    if (flashTimer) clearTimeout(flashTimer)
    flashTimer = setTimeout(() => {
      if (flashJobId.value === jobId) flashJobId.value = null
    }, 2200)
  }

  function tabForJobStatus(status: string): 'running' | 'completed' | 'failed' {
    if (status === 'completed') return 'completed'
    if (status === 'failed' || status === 'cancelled' || status === 'skipped') return 'failed'
    return 'running'
  }

  async function loadHistoricalLogs(jobId: string) {
    logs.value = []
    const resp = await api.get(`/jobs/${jobId}/logs`)
    const historicalLogs = Array.isArray(resp.data)
      ? resp.data
      : Array.isArray(resp.data?.logs)
        ? resp.data.logs
        : []
    for (const line of historicalLogs.slice(-maxVisibleLogLines)) {
      logs.value.push({ time: '', line })
    }
  }

  async function selectJob(job: Job) {
    selectedJobId.value = job.id
    await loadHistoricalLogs(job.id)
    if (shouldWatchJob(job)) {
      await watchJob(job.id)
    }
  }

  async function selectJobById(jobId: string) {
    const job = getJobById(jobId)
    if (job) await selectJob(job)
  }

  function appendVisibleLog(entry: JobLogEntry) {
    logs.value.push(entry)
    if (logs.value.length > maxVisibleLogLines) {
      logs.value.splice(0, logs.value.length - maxVisibleLogLines)
    }
  }

  async function applyRouteFocus() {
    const focusJobId = typeof route.query.job === 'string' ? route.query.job : ''
    const focusChainId = typeof route.query.chain === 'string' ? route.query.chain : ''
    if (!focusJobId && !focusChainId) return

    let target = focusJobId ? getJobById(focusJobId) : null
    if (!target && focusChainId) {
      target = findJobByChainId(focusChainId)
    }
    if (!target) return

    onFocusTab(tabForJobStatus(target.status))
    flashFocusedJob(target.id)
    await selectJob(target)

    const nextQuery = { ...route.query }
    delete nextQuery.job
    delete nextQuery.chain
    await router.replace({ query: nextQuery })
  }

  return {
    logs,
    selectedJobId,
    flashJobId,
    appendVisibleLog,
    selectJob,
    selectJobById,
    applyRouteFocus,
    dispose,
  }
}

