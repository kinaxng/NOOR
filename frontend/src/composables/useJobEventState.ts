import { ref } from 'vue'
import type { Job, SSEEvent } from '../api/types'
import type { useJobsStore } from '../stores/jobs'

export type JobRuntimeStatus = {
  status: string
  progress: number
  phaseKey?: string
  phaseGroup?: string
  phaseLabel?: string
  detail?: string
  phaseProgress?: number
}

type JobsStore = ReturnType<typeof useJobsStore>

type UseJobEventStateOptions = {
  allJobs: () => Job[]
  jobsStore: JobsStore
}

export function useJobEventState(options: UseJobEventStateOptions) {
  const { allJobs, jobsStore } = options

  const jobStatuses = ref<Record<string, JobRuntimeStatus>>({})
  const sseConnected = ref<Set<string>>(new Set())
  const watchedJobIds = ref<Set<string>>(new Set())

  function getJobById(jobId: string) {
    return allJobs().find(job => job.id === jobId) || null
  }

  function clampJobProgress(jobId: string, incoming: number | null | undefined) {
    const next = Math.max(0, Math.min(100, Number(incoming ?? 0)))
    const current = jobStatuses.value[jobId]?.progress ?? getJobById(jobId)?.progress ?? 0
    return Math.max(current, next)
  }

  function seedJobStatus(job: Job, fallbackStatus: string) {
    jobStatuses.value[job.id] = {
      status: fallbackStatus,
      progress: job.progress || 0,
      phaseKey: job.phase_key,
      phaseGroup: job.phase_group,
      phaseLabel: job.phase_label,
      detail: job.detail,
      phaseProgress: job.phase_progress,
    }
  }

  function refreshJobStatus(job: Job, runtimeStatus: string) {
    const progress = job.progress || jobStatuses.value[job.id]?.progress || 0
    jobStatuses.value[job.id] = {
      status: runtimeStatus,
      progress,
      phaseKey: job.phase_key,
      phaseGroup: job.phase_group,
      phaseLabel: job.phase_label,
      detail: job.detail,
      phaseProgress: job.phase_progress,
    }
  }

  function ensureJobStatus(jobId: string): JobRuntimeStatus {
    if (!jobStatuses.value[jobId]) {
      jobStatuses.value[jobId] = { status: '', progress: 0, phaseKey: '', phaseLabel: '', detail: '', phaseProgress: 0 }
    }
    return jobStatuses.value[jobId]
  }

  function applyStructuredEvent(
    jobId: string,
    event: SSEEvent,
    options: {
      status?: string
      progress?: number
      phaseProgress?: number
      keepPhaseProgressMonotonic?: boolean
    } = {},
  ) {
    const current = ensureJobStatus(jobId)
    jobStatuses.value[jobId] = {
      ...current,
      status: options.status ?? current.status,
      progress: options.progress ?? current.progress,
      phaseKey: event.phase_key ?? current.phaseKey,
      phaseGroup: event.phase_group ?? current.phaseGroup,
      phaseLabel: event.phase_label ?? current.phaseLabel,
      detail: event.detail ?? current.detail,
      phaseProgress: options.keepPhaseProgressMonotonic
        ? Math.max(current.phaseProgress ?? 0, options.phaseProgress ?? event.phase_progress ?? 0)
        : options.phaseProgress ?? event.phase_progress ?? current.phaseProgress,
    }
    sseConnected.value.add(jobId)
  }

  function updateStorePhaseState(jobId: string, progress: number, status?: Job['status'], event?: SSEEvent, phaseLabelOverride?: string) {
    jobsStore.updateJobProgress(jobId, progress, status, {
      phase_key: event?.phase_key,
      phase_group: event?.phase_group,
      phase_label: phaseLabelOverride ?? event?.phase_label,
      phase_progress: event?.phase_progress,
      detail: event?.detail,
    })
  }

  function applyTerminalEvent(jobId: string, event: SSEEvent, status: Extract<Job['status'], 'completed' | 'failed' | 'cancelled' | 'skipped'>, fallbackLabel: string, defaultProgress: number, phaseProgress?: number) {
    const progress = Number(event.progress ?? ensureJobStatus(jobId).progress ?? defaultProgress)
    applyStructuredEvent(jobId, event, {
      status: fallbackLabel,
      progress,
      phaseProgress,
    })
    updateStorePhaseState(jobId, progress, status, event, event.phase_label || fallbackLabel)
  }

  function applyQueuedLikeEvent(jobId: string, event: SSEEvent, statusLabel: string) {
    applyStructuredEvent(jobId, event, {
      status: statusLabel,
      phaseProgress: event.phase_progress ?? 0,
    })
  }

  function pruneJobStatuses(jobIds: string[]) {
    for (const jobId of jobIds) {
      delete jobStatuses.value[jobId]
    }
  }

  return {
    jobStatuses,
    sseConnected,
    watchedJobIds,
    getJobById,
    clampJobProgress,
    seedJobStatus,
    refreshJobStatus,
    ensureJobStatus,
    applyStructuredEvent,
    updateStorePhaseState,
    applyTerminalEvent,
    applyQueuedLikeEvent,
    pruneJobStatuses,
  }
}
