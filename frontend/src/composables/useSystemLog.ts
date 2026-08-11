import { ref, onUnmounted } from 'vue'
import api from '../api'

export interface LogEntry {
  seq?: number
  time: string
  level: string
  source?: string
  line: string
}

const logs = ref<LogEntry[]>([])
const connected = ref(false)
const show = ref(false) // 默认隐藏
let pollTimer: ReturnType<typeof setInterval> | null = null
let cursor: number | null = null
let requestSeq = 0
let fetching = false
const seenSeq = new Set<number>()

export function useSystemLog() {
  async function fetchLogs(mode: 'init' | 'poll' = 'poll') {
    if (fetching) return
    fetching = true
    const seq = requestSeq
    try {
      const params = mode === 'init'
        ? { tail: 0 }
        : cursor == null
          ? { tail: 0 }
          : { since: cursor }
      const resp = await api.get('/system/logs', { params })
      if (seq !== requestSeq) return
      const data = resp.data
      if (typeof data.next_index === 'number') {
        cursor = data.next_index
      }
      if (mode === 'init') {
        logs.value = []
        seenSeq.clear()
      } else if (data.logs && Array.isArray(data.logs) && data.logs.length) {
        const fresh: LogEntry[] = []
        for (const item of data.logs as LogEntry[]) {
          if (typeof item.seq === 'number') {
            if (seenSeq.has(item.seq)) continue
            seenSeq.add(item.seq)
          }
          fresh.push(item)
        }
        if (fresh.length) logs.value.push(...fresh)
        if (logs.value.length > 500) {
          const removed = logs.value.splice(0, logs.value.length - 500)
          for (const item of removed) {
            if (typeof item.seq === 'number') seenSeq.delete(item.seq)
          }
        }
      }
      connected.value = true
    } catch {
      if (seq !== requestSeq) return
      connected.value = false
    } finally {
      if (seq === requestSeq) fetching = false
    }
  }

  function startPolling() {
    if (pollTimer) return
    requestSeq += 1
    cursor = null
    logs.value = []
    seenSeq.clear()
    fetching = false
    fetchLogs('init') // 只建立游标，不读取历史日志
    pollTimer = setInterval(() => fetchLogs('poll'), 2000) // 仅打开面板时轮询
  }

  function stopPolling() {
    requestSeq += 1
    if (pollTimer) {
      clearInterval(pollTimer)
      pollTimer = null
    }
    logs.value = []
    seenSeq.clear()
    fetching = false
    cursor = null
    connected.value = false
  }

  function toggle() {
    show.value = !show.value
    if (show.value) {
      // Only start polling when panel is opened
      startPolling()
    } else {
      stopPolling()
    }
  }

  onUnmounted(() => {
    stopPolling()
  })

  return { logs, connected, show, startPolling, stopPolling, toggle }
}
