import { defineStore } from 'pinia'
import { ref } from 'vue'
import api from '../api'
import { useI18n } from '../composables/useI18n'
import type { Job, JobCreate, SSEEvent } from '../api/types'

// Module-level cache for fire-and-forget preload
const _jobsCache: { data: Job[]; loaded: boolean } = { data: [], loaded: false }
let _jobsFetchPromise: Promise<void> | null = null

export const useJobsStore = defineStore('jobs', () => {
  const { t } = useI18n()
  const jobs = ref<Job[]>([])
  const currentJob = ref<Job | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)
  const eventSource = ref<EventSource | null>(null)
  const eventSources = ref<Map<string, EventSource>>(new Map())
  const MAX_BUFFERED_LOGS = 1000
  const logs = ref<{ jobId: string; line: string }[]>([])
  let externalPollTimer: number | null = null

  function hasActiveExternalJobs(list: Job[] = jobs.value) {
    return list.some(job => (job.job_type === 'external_task' || !!job.result_metadata?.external_task) && ['pending', 'queued', 'blocked', 'running'].includes(job.status))
  }

  function syncExternalPolling() {
    if (hasActiveExternalJobs()) {
      if (externalPollTimer == null) {
        externalPollTimer = window.setInterval(() => {
          void fetchJobs()
        }, 10000)
      }
      return
    }
    if (externalPollTimer != null) {
      window.clearInterval(externalPollTimer)
      externalPollTimer = null
    }
  }

  async function _fetchJobsBg() {
    try {
      const resp = await api.get('/jobs', { params: {} })
      jobs.value = resp.data.jobs
      _jobsCache.data = resp.data.jobs
      _jobsCache.loaded = true
    } catch {
      // Silently fail - background refresh
    }
  }

  async function fetchJobs(status?: string) {
    if (_jobsCache.loaded && !status) {
      jobs.value = _jobsCache.data
    }

    if (!status && _jobsFetchPromise) {
      await _jobsFetchPromise
      return
    }

    loading.value = true
    error.value = null

    const run = async () => {
      try {
        const params = status ? { status } : {}
        const resp = await api.get('/jobs', { params })
        jobs.value = resp.data.jobs
        if (!status) {
          _jobsCache.data = resp.data.jobs
          _jobsCache.loaded = true
          syncExternalPolling()
        }
      } catch (e: any) {
        error.value = e.message || t('jobs.fetchFailed')
      } finally {
        loading.value = false
      }
    }

    if (!status) {
      _jobsFetchPromise = run().finally(() => {
        _jobsFetchPromise = null
      })
      await _jobsFetchPromise
      return
    }

    await run()
  }

  // Fire-and-forget preload
  if (!_jobsCache.loaded) {
    _fetchJobsBg()
  } else {
    jobs.value = _jobsCache.data
  }

  function updateJobProgress(jobId: string, progress: number, status?: string, patch: Partial<Job> = {}) {
    const job = jobs.value.find(j => j.id === jobId)
    if (job) {
      const next = Math.max(0, Math.min(100, Number(progress || 0)))
      if ((status ?? job.status) === 'running') {
        job.progress = Math.max(job.progress || 0, next)
      } else {
        job.progress = next
      }
      Object.assign(job, patch)
      if (status) job.status = status as Job['status']
    }
  }

  function currentJobProgress(jobId: string) {
    return jobs.value.find(j => j.id === jobId)?.progress ?? 0
  }

  function createPhasePatch(data: any): Partial<Job> {
    return {
      phase_key: data.phase_key,
      phase_group: data.phase_group,
      phase_label: data.phase_label,
      phase_progress: data.phase_progress,
      detail: data.detail,
    }
  }

  function emitStructuredEvent(onMessage: (event: SSEEvent) => void, type: SSEEvent['type'], data: any) {
    onMessage({
      type,
      job_id: data.job_id,
      success: data.success,
      progress: data.progress,
      phase_key: data.phase_key,
      phase_group: data.phase_group,
      phase_label: data.phase_label,
      phase_progress: data.phase_progress,
      detail: data.detail,
      line: data.line,
    })
  }

  async function createJob(jobData: JobCreate): Promise<Job> {
    loading.value = true
    error.value = null
    try {
      const resp = await api.post('/jobs', jobData)
      const job = resp.data as Job
      upsertJob(job)
      return job
    } catch (e: any) {
      error.value = e.message || t('jobs.createFailed')
      throw e
    } finally {
      loading.value = false
    }
  }

  async function getJob(jobId: string) {
    try {
      const resp = await api.get(`/jobs/${jobId}`)
      return resp.data as Job
    } catch (e: any) {
      return null
    }
  }

  function upsertJob(job: Job) {
    const idx = jobs.value.findIndex(j => j.id === job.id)
    if (idx >= 0) {
      jobs.value[idx] = { ...jobs.value[idx], ...job }
    } else {
      jobs.value.unshift(job)
    }
    if (_jobsCache.loaded) {
      const cacheIdx = _jobsCache.data.findIndex(j => j.id === job.id)
      if (cacheIdx >= 0) {
        _jobsCache.data[cacheIdx] = { ..._jobsCache.data[cacheIdx], ...job }
      } else {
        _jobsCache.data = [job, ..._jobsCache.data]
      }
    }
    syncExternalPolling()
  }

  async function deleteJob(jobId: string) {
    try {
      await api.delete(`/jobs/${jobId}`)
      jobs.value = jobs.value.filter(j => j.id !== jobId)
      syncExternalPolling()
    } catch (e: any) {
      error.value = e.message || t('jobs.deleteFailed')
    }
  }

  function pruneJobs(jobIds: string[]) {
    if (!jobIds.length) return
    const ids = new Set(jobIds)
    jobs.value = jobs.value.filter(j => !ids.has(j.id))
    if (_jobsCache.loaded) {
      _jobsCache.data = _jobsCache.data.filter(j => !ids.has(j.id))
    }
    syncExternalPolling()
  }

  function connectToEvents(jobId: string, onMessage: (event: SSEEvent) => void) {
    // Close existing connection for this job if any
    if (eventSources.value.has(jobId)) {
      eventSources.value.get(jobId)!.close()
      eventSources.value.delete(jobId)
    }

    const es = new EventSource(`/api/jobs/${jobId}/events`)
    eventSources.value.set(jobId, es)

    es.addEventListener('connected', () => {})

    es.addEventListener('progress', (e) => {
      const data = JSON.parse(e.data)
      updateJobProgress(jobId, Number(data.progress ?? currentJobProgress(jobId)), 'running', createPhasePatch(data))
      emitStructuredEvent(onMessage, 'progress', data)
    })

    es.addEventListener('log', (e) => {
      const data = JSON.parse(e.data)
      logs.value.push({ jobId, line: data.line })
      if (logs.value.length > MAX_BUFFERED_LOGS) {
        logs.value.splice(0, logs.value.length - MAX_BUFFERED_LOGS)
      }
      emitStructuredEvent(onMessage, 'log', data)
    })

    es.addEventListener('queued', (e) => {
      const data = JSON.parse(e.data)
      updateJobProgress(jobId, currentJobProgress(jobId), 'queued', createPhasePatch(data))
      emitStructuredEvent(onMessage, 'queued', data)
    })

    es.addEventListener('blocked', (e) => {
      const data = JSON.parse(e.data)
      updateJobProgress(jobId, currentJobProgress(jobId), 'blocked', createPhasePatch(data))
      emitStructuredEvent(onMessage, 'blocked', data)
    })

    es.addEventListener('done', async (e) => {
      const data = JSON.parse(e.data)
      updateJobProgress(jobId, Number(data.progress ?? currentJobProgress(jobId)), data.type, {
        ...createPhasePatch(data),
        detail: data.detail || data.error,
      })
      emitStructuredEvent(onMessage, data.type, { ...data, detail: data.detail || data.error })
      es.close()
      eventSources.value.delete(jobId)
      void fetchJobs()
    })

    es.addEventListener('keepalive', () => {
      // ignore
    })
  }

  function disconnectFromEvents() {
    if (eventSource.value) {
      eventSource.value.close()
      eventSource.value = null
    }
    eventSources.value.forEach(es => es.close())
    eventSources.value.clear()
    if (externalPollTimer != null) {
      window.clearInterval(externalPollTimer)
      externalPollTimer = null
    }
  }

  function clearLogs() {
    logs.value = []
  }

  return {
    jobs,
    currentJob,
    loading,
    error,
    logs,
    fetchJobs,
    createJob,
    getJob,
    upsertJob,
    deleteJob,
    pruneJobs,
    connectToEvents,
    disconnectFromEvents,
    clearLogs,
    updateJobProgress,
  }
})
