<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useJobsStore } from '../stores/jobs'
import { useMediaStore } from '../stores/media'
import { useI18n } from '../composables/useI18n'
import { formatDate, formatDuration, jobTitle, statusLabel, statusTone } from '../app/format'
import type { Job, JobStatus } from '../api/types'

const { t } = useI18n()
const jobs = useJobsStore()
const media = useMediaStore()
let metricsTimer: number | undefined

const welcomeGreeting = computed(() => t('dashboard.welcome.greeting'))
const recentJobs = computed(() => jobs.jobs.slice(0, 6))
const runningCount = computed(() => jobs.activeJobs.length)

// GPU metrics
const gpuMetrics = computed(() => {
  const gpu = jobs.metrics?.gpu
  if (!gpu) return null
  return {
    util: gpu.gpu_util || 0,
    memoryUsed: gpu.mem_used || 0,
    memoryTotal: gpu.mem_total || 1,
    temp: gpu.temp,
    power: gpu.power,
  }
})

// CPU/Memory metrics
const cpuMetrics = computed(() => {
  const cpu = jobs.metrics?.cpu_mem
  if (!cpu) return null
  return {
    util: cpu.cpu_util || 0,
    memUsed: cpu.mem_used || 0,
    memTotal: cpu.mem_total || 1,
    temp: cpu.cpu_temp,
  }
})

function formatMemory(used: number, total: number) {
  const u = used / (1024 ** 3)
  const t = total / (1024 ** 3)
  return `${u.toFixed(1)} / ${t.toFixed(1)} GB`
}

function getMetricColor(value: number) {
  if (value > 85) return 'error'
  if (value > 60) return 'warning'
  return 'success'
}

function getStatusColor(status: string) {
  const tone = statusTone(status as JobStatus)
  if (tone === 'success') return 'success'
  if (tone === 'warning') return 'warning'
  if (tone === 'danger') return 'error'
  if (tone === 'info') return 'info'
  return 'neutral'
}

function getDashboardStatusColor(job: Job) {
  if (job.status === 'running') return 'primary'
  return getStatusColor(job.status)
}

function formatRelativeTime(dateStr?: string) {
  if (!dateStr) return t('dashboard.unknown')
  const date = new Date(dateStr)
  const now = new Date()
  const diff = now.getTime() - date.getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return t('dashboard.justNow')
  if (mins < 60) return t('dashboard.minsAgo', { n: mins })
  const hours = Math.floor(mins / 60)
  if (hours < 24) return t('dashboard.hoursAgo', { n: hours })
  return formatDate(dateStr)
}

// Library tag counts
const tagCounts = ref<Record<string, number>>({})
async function fetchTagCounts() {
  try {
    const { api } = await import('../api/client')
    const data = await api.get<Record<string, unknown>>('/media-library/tag-counts')
    if (data && typeof data === 'object') {
      for (const [key, val] of Object.entries(data as Record<string, number>)) {
        tagCounts.value[key] = val
      }
    }
  } catch {
    // Tag counts API may not be available - that's fine
  }
}

// Plugin dashboard widgets
const pluginWidgets = ref<Array<{
  id: string
  pluginName: string
  title: string
  html: string
}>>([])

async function fetchPluginWidgets() {
  try {
    const { api } = await import('../api/client')
    const data = await api.get<{ widgets: Array<{ id: string; plugin_name: string; title: string; html: string }> }>('/plugins/dashboard-widgets')
    if (data?.widgets) pluginWidgets.value = data.widgets as any
  } catch {
    // Plugin dashboard may not be available
  }
}

onMounted(async () => {
  await Promise.all([
    jobs.fetchJobs(),
    jobs.fetchMetrics(),
    fetchTagCounts(),
    fetchPluginWidgets(),
  ])
  metricsTimer = window.setInterval(() => jobs.fetchMetrics(), 5000)
})

onUnmounted(() => {
  if (metricsTimer) window.clearInterval(metricsTimer)
})
</script>

<template>
  <UDashboardPanel id="home" grow>
    <template #header>
      <UDashboardNavbar :title="t('nav.overview')">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #right>
          <UButton color="neutral" variant="ghost" to="/jobs">{{ t('dashboard.viewAll') }}</UButton>
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <!-- Welcome -->
      <div class="mb-8">
        <h1 class="text-2xl font-bold">{{ welcomeGreeting }} <span class="text-(--color-noor-400)">NOOR</span></h1>
        <p class="mt-1 text-sm text-(--ui-text-muted)">{{ t('status.connected') }}</p>
      </div>

      <!-- KPI stat cards -->
      <div class="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <UCard>
          <div class="flex items-center gap-3">
            <div class="w-10 h-10 rounded-lg bg-(--color-noor-600)/20 flex items-center justify-center">
              <UIcon name="i-heroicons-play-20-solid" class="w-5 h-5 text-(--color-noor-400)" />
            </div>
            <div>
              <div class="text-sm font-medium text-(--ui-text-muted)">{{ t('dashboard.job.running') }}</div>
              <div class="text-2xl font-bold">{{ runningCount }}</div>
            </div>
          </div>
        </UCard>

        <UCard>
          <div class="flex items-center gap-3">
            <div class="w-10 h-10 rounded-lg bg-green-500/20 flex items-center justify-center">
              <UIcon name="i-heroicons-check-circle-20-solid" class="w-5 h-5 text-green-400" />
            </div>
            <div>
              <div class="text-sm font-medium text-(--ui-text-muted)">{{ t('dashboard.job.completed') }}</div>
              <div class="text-2xl font-bold">{{ jobs.completedJobs.length }}</div>
            </div>
          </div>
        </UCard>

        <UCard>
          <div class="flex items-center gap-3">
            <div class="w-10 h-10 rounded-lg bg-blue-500/20 flex items-center justify-center">
              <UIcon name="i-heroicons-cpu-chip-20-solid" class="w-5 h-5 text-blue-400" />
            </div>
            <div>
              <div class="text-sm font-medium text-(--ui-text-muted)">GPU</div>
              <div class="text-2xl font-bold">{{ gpuMetrics ? `${gpuMetrics.util}%` : '-' }}</div>
            </div>
          </div>
        </UCard>

        <UCard>
          <div class="flex items-center gap-3">
            <div class="w-10 h-10 rounded-lg bg-amber-500/20 flex items-center justify-center">
              <UIcon name="i-heroicons-server-20-solid" class="w-5 h-5 text-amber-400" />
            </div>
            <div>
              <div class="text-sm font-medium text-(--ui-text-muted)">CPU</div>
              <div class="text-2xl font-bold">{{ cpuMetrics ? `${cpuMetrics.util}%` : '-' }}</div>
            </div>
          </div>
        </UCard>
      </div>

      <!-- Library tag distribution -->
      <div v-if="Object.keys(tagCounts).length" class="grid grid-cols-2 sm:grid-cols-5 gap-3 mb-6">
        <UCard v-for="(count, tag) in tagCounts" :key="tag" class="text-center">
          <div class="text-xs text-(--ui-text-muted) uppercase tracking-wider mb-1">{{ t(`dashboard.stats.${tag}`) || tag }}</div>
          <div class="text-xl font-bold">{{ count }}</div>
        </UCard>
      </div>

      <!-- System metrics row -->
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6">
        <!-- GPU card -->
        <UCard v-if="gpuMetrics">
          <template #header>
            <h3 class="text-sm font-semibold">{{ t('dashboard.gpu.title') }}</h3>
          </template>
          <div class="space-y-4">
            <div>
              <div class="flex justify-between text-xs mb-1">
                <span class="text-(--ui-text-muted)">{{ t('dashboard.gpu.util') }}</span>
                <span class="font-medium">{{ gpuMetrics.util }}%</span>
              </div>
              <UProgress :value="gpuMetrics.util" :color="getMetricColor(gpuMetrics.util)" size="sm" />
            </div>
            <div>
              <div class="flex justify-between text-xs mb-1">
                <span class="text-(--ui-text-muted)">{{ t('dashboard.gpu.memory') }}</span>
                <span class="font-medium">{{ formatMemory(gpuMetrics.memoryUsed, gpuMetrics.memoryTotal) }}</span>
              </div>
              <UProgress :value="(gpuMetrics.memoryUsed / gpuMetrics.memoryTotal) * 100" :color="getMetricColor((gpuMetrics.memoryUsed / gpuMetrics.memoryTotal) * 100)" size="sm" />
            </div>
            <div class="grid grid-cols-2 gap-3">
              <div v-if="gpuMetrics.temp != null" class="p-2 rounded bg-(--ui-bg-elevated)/50">
                <div class="text-xs text-(--ui-text-muted)">{{ t('dashboard.gpu.temp') }}</div>
                <div class="font-medium">{{ gpuMetrics.temp }}°C</div>
              </div>
              <div v-if="gpuMetrics.power != null" class="p-2 rounded bg-(--ui-bg-elevated)/50">
                <div class="text-xs text-(--ui-text-muted)">{{ t('dashboard.gpu.power') }}</div>
                <div class="font-medium">{{ gpuMetrics.power }}W</div>
              </div>
            </div>
          </div>
        </UCard>

        <!-- CPU card -->
        <UCard v-if="cpuMetrics">
          <template #header>
            <h3 class="text-sm font-semibold">{{ t('dashboard.cpu.title') }}</h3>
          </template>
          <div class="space-y-4">
            <div>
              <div class="flex justify-between text-xs mb-1">
                <span class="text-(--ui-text-muted)">{{ t('dashboard.cpu.util') }}</span>
                <span class="font-medium">{{ cpuMetrics.util }}%</span>
              </div>
              <UProgress :value="cpuMetrics.util" :color="getMetricColor(cpuMetrics.util)" size="sm" />
            </div>
            <div>
              <div class="flex justify-between text-xs mb-1">
                <span class="text-(--ui-text-muted)">{{ t('dashboard.cpu.memory') }}</span>
                <span class="font-medium">{{ formatMemory(cpuMetrics.memUsed, cpuMetrics.memTotal) }}</span>
              </div>
              <UProgress :value="(cpuMetrics.memUsed / cpuMetrics.memTotal) * 100" :color="getMetricColor((cpuMetrics.memUsed / cpuMetrics.memTotal) * 100)" size="sm" />
            </div>
            <div v-if="cpuMetrics.temp != null" class="p-2 rounded bg-(--ui-bg-elevated)/50">
              <div class="text-xs text-(--ui-text-muted)">{{ t('dashboard.cpu.temp') }}</div>
              <div class="font-medium">{{ cpuMetrics.temp }}°C</div>
            </div>
          </div>
        </UCard>
      </div>

      <!-- Plugin dashboard widgets -->
      <div v-if="pluginWidgets.length" class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 mb-6">
        <UCard v-for="widget in pluginWidgets" :key="widget.id">
          <template #header>
            <div class="flex items-center justify-between">
              <h3 class="text-sm font-semibold">{{ widget.title }}</h3>
              <UBadge color="neutral" variant="subtle" size="xs">{{ widget.pluginName }}</UBadge>
            </div>
          </template>
          <div v-html="widget.html" class="plugin-widget-content text-sm" />
        </UCard>
      </div>

      <!-- Recent jobs -->
      <UCard v-if="!jobs.loading && !jobs.error">
        <template #header>
          <div class="flex items-center justify-between">
            <h2 class="text-base font-semibold">{{ t('dashboard.recentJobs') }}</h2>
            <UButton color="neutral" variant="ghost" size="sm" to="/jobs">{{ t('dashboard.viewAll') }}</UButton>
          </div>
        </template>

        <div v-if="!recentJobs.length" class="text-center py-8">
          <UIcon name="i-heroicons-inbox-20-solid" class="w-8 h-8 mb-2 opacity-50" />
          <p class="text-sm text-(--ui-text-muted)">{{ t('dashboard.noJobs') }}</p>
        </div>

        <div v-else class="divide-y divide-(--ui-border)">
          <div
            v-for="job in recentJobs"
            :key="job.id"
            class="flex items-center justify-between p-4 hover:bg-(--ui-bg-elevated)/50 transition-colors cursor-pointer"
          >
            <div class="flex items-center gap-3 min-w-0">
              <div class="w-9 h-9 rounded-lg flex items-center justify-center shrink-0"
                :class="job.status === 'running' ? 'bg-(--color-noor-600)/20 text-(--color-noor-400)' : job.status === 'completed' ? 'bg-green-500/20 text-green-400' : 'bg-(--ui-bg-elevated) text-(--ui-text-muted)'">
                <UIcon v-if="job.status === 'running'" name="i-heroicons-play-20-solid" class="w-4 h-4" />
                <UIcon v-else-if="job.status === 'completed'" name="i-heroicons-check-20-solid" class="w-4 h-4" />
                <UIcon v-else-if="job.status === 'failed'" name="i-heroicons-x-mark-20-solid" class="w-4 h-4" />
                <UIcon v-else name="i-heroicons-clock-20-solid" class="w-4 h-4" />
              </div>
              <div class="min-w-0">
                <div class="text-sm font-medium truncate">{{ jobTitle(job) }}</div>
                <div class="text-xs text-(--ui-text-muted) mt-0.5">{{ formatRelativeTime(job.created_at) }}</div>
                <div v-if="job.status === 'running' && job.detail" class="text-xs text-(--ui-text-muted) mt-0.5 truncate">{{ job.detail }}</div>
              </div>
            </div>
            <div class="flex items-center gap-3 shrink-0">
              <div v-if="job.status === 'running'" class="hidden sm:block w-24">
                <UProgress :value="Math.max(0, Math.min(100, job.progress || 0))" size="xs" color="primary" />
              </div>
              <UBadge :color="getDashboardStatusColor(job)" variant="subtle">{{ statusLabel(job.status) }}</UBadge>
            </div>
          </div>
        </div>
      </UCard>

      <!-- Loading / Error -->
      <div v-else-if="jobs.loading" class="flex flex-col items-center justify-center py-12 text-(--ui-text-muted)">
        <UIcon name="i-heroicons-arrow-path-20-solid" class="w-8 h-8 animate-spin mb-4" />
        <p>{{ t('common.loading') }}</p>
      </div>

      <div v-else-if="jobs.error" class="flex flex-col items-center justify-center py-12">
        <UIcon name="i-heroicons-exclamation-triangle-20-solid" class="w-12 h-12 text-(--ui-error) mb-4" />
        <p class="text-(--ui-error) font-medium">{{ jobs.error }}</p>
      </div>
    </template>
  </UDashboardPanel>
</template>
