import { ref, onUnmounted } from 'vue'
import api from '../api'

export interface LogEntry {
  time: string
  level: string
  line: string
}

const logs = ref<LogEntry[]>([])
const connected = ref(false)
const show = ref(false) // 默认隐藏
let pollTimer: ReturnType<typeof setInterval> | null = null

export function useSystemLog() {
  async function fetchLogs() {
    try {
      const resp = await api.get('/system/logs')
      const data = resp.data
      if (data.logs && Array.isArray(data.logs)) {
        // 用服务器返回的全部日志替换本地（服务器是最新的）
        logs.value = data.logs
        connected.value = true
      }
    } catch {
      connected.value = false
    }
  }

  function startPolling() {
    fetchLogs() // 立即获取一次
    pollTimer = setInterval(fetchLogs, 2000) // 每 2 秒轮询
  }

  function stopPolling() {
    if (pollTimer) {
      clearInterval(pollTimer)
      pollTimer = null
    }
    connected.value = false
  }

  function toggle() {
    if (show.value) {
      stopPolling()
    } else {
      startPolling()
    }
    show.value = !show.value
  }

  onUnmounted(() => {
    stopPolling()
  })

  return { logs, connected, show, startPolling, stopPolling, toggle }
}
