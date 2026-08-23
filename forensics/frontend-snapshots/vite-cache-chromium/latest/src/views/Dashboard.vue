<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useMediaLibraryStore } from '../stores/mediaLibrary'
import { useJobsStore } from '../stores/jobs'
import { RouterLink } from 'vue-router'
import BaseIcon from '../components/noor/BaseIcon.vue'
import VuiBadge from '../components/ui/Badge/VuiBadge.vue'
import SystemMetricsCard from '../components/ui/SystemMetricsCard.vue'
import WelcomeMark from '../components/ui/WelcomeMark.vue'
import ActivityCard from '../components/ui/ActivityCard.vue'
import api from '../api'
import { useI18n } from '../composables/useI18n'
import { useJobPresentation } from '../composables/useJobPresentation'
import { sortRunningJobsForList, sortJobsForList } from '../composables/jobOrdering'

const { t, i18nVersion } = useI18n()
const { getActivityDetailLine, getRunningBadgeLabel, getJobDisplayName, getDashboardJobMetaTokens, getDashboardJobChips, getDashboardStatusTone, getDashboardIconName, formatDashboardRelativeTime } = useJobPresentation(() => jobsStore.jobs)
const mediaLibraryStore = useMediaLibraryStore()
const jobsStore = useJobsStore()

const DASHBOARD_COUNTS_CACHE_TTL = 60_000
const dashboardCountsCache = {
  key: '',
  fetchedAt: 0,
  data: null as null | { total: number; cracked: number; chinese: number; leaked: number; uncensored: number },
  promise: null as null | Promise<{ total: number; cracked: number; chinese: number; leaked: number; uncensored: number }>,
}

// System metrics
const sysMetrics = ref({
  gpu: { gpu_util: 0, mem_used: 0, mem_total: 0, temp: 0, power: 0 },
  cpu_mem: { cpu_util: 0, mem_used: 0, mem_total: 0, cpu_temp: 0, disk_read: 0 },
})
let metricsInterval: ReturnType<typeof setInterval> | null = null

async function fetchMetrics() {
  try {
    const resp = await api.get('/system/metrics')
    sysMetrics.value = resp.data
  } catch (e) {
    // ignore
  }
}

const formatCount = computed(() => {
  void i18nVersion.value
  const formatter = new Intl.NumberFormat('zh-CN')
  return (value: number) => formatter.format(value)
})

// Full library tag counts (fetched separately to get accurate totals)
const fullTagCounts = ref({ total: 0, cracked: 0, chinese: 0, leaked: 0, uncensored: 0 })
const countsLoaded = ref(false)

async function fetchDashboardCounts() {
  const libraryKey = mediaLibraryStore.enabledLibraryIds.length > 0 ? mediaLibraryStore.enabledLibraryIds[0] : 'all'
  const cacheKey = `counts:${libraryKey}`
  const now = Date.now()

  if (dashboardCountsCache.data && dashboardCountsCache.key === cacheKey && now - dashboardCountsCache.fetchedAt < DASHBOARD_COUNTS_CACHE_TTL) {
    return dashboardCountsCache.data
  }

  if (dashboardCountsCache.promise && dashboardCountsCache.key === cacheKey) {
    return await dashboardCountsCache.promise
  }

  const params: any = { limit: 200, offset: 0 }
  if (mediaLibraryStore.enabledLibraryIds.length > 0) {
    params.library_id = mediaLibraryStore.enabledLibraryIds[0]
  }

  dashboardCountsCache.key = cacheKey
  dashboardCountsCache.promise = (async () => {
    const allItems: any[] = []
    let fetched = 0
    let total = 0
    do {
      const resp = await api.get('/media-library/items', { params: { ...params, offset: fetched } })
      const items: any[] = resp.data.items
      allItems.push(...items)
      total = resp.data.total
      fetched += items.length
    } while (fetched < total && fetched < 2000)

    const data = {
      total: allItems.length,
      cracked: allItems.filter(i => i.tags?.is_cracked).length,
      chinese: allItems.filter(i => i.tags?.has_chinese).length,
      leaked: allItems.filter(i => i.tags?.release_type_key === 'leaked').length,
      uncensored: allItems.filter(i => i.tags?.release_type_key === 'uncensored').length,
    }

    dashboardCountsCache.data = data
    dashboardCountsCache.fetchedAt = Date.now()
    return data
  })()

  try {
    return await dashboardCountsCache.promise
  } finally {
    dashboardCountsCache.promise = null
  }
}

onMounted(async () => {
  await mediaLibraryStore.fetchLibraries()
  await jobsStore.fetchJobs()
  await fetchMetrics()
  metricsInterval = setInterval(fetchMetrics, 5000)

  try {
    fullTagCounts.value = await fetchDashboardCounts()
  } catch (e) {
    // ignore counting errors
  } finally {
    countsLoaded.value = true
  }
})

onUnmounted(() => {
  if (metricsInterval) clearInterval(metricsInterval)
})


// Recent jobs
const recentJobs = computed(() => {
  const seen = new Set<string>()
  const runningJobs = jobsStore.jobs.filter(job => job.status === 'running' || job.status === 'queued' || job.status === 'blocked' || job.status === 'pending')
  const terminalJobs = jobsStore.jobs.filter(job => job.status !== 'running' && job.status !== 'queued' && job.status !== 'blocked' && job.status !== 'pending')

  return [...sortRunningJobsForList(runningJobs), ...sortJobsForList(terminalJobs)]
    .filter((job) => {
      const dateKey = (job.created_at || '').slice(0, 10)
      const itemKey = job.emby_item_name || job.input_path?.split('/').pop() || job.id
      const key = `${itemKey}::${job.job_type}::${job.status}::${dateKey}`
      if (seen.has(key)) return false
      seen.add(key)
      return true
    })
    .slice(0, 6)
})

const getDashboardJobMetaLine = computed(() => {
  void i18nVersion.value
  return (job: any) => getDashboardJobMetaTokens.value(job, formatDashboardRelativeTime.value(job.created_at)).join(' · ')
})

const statsCards = computed(() => {
  void i18nVersion.value
  const total = Math.max(fullTagCounts.value.total, 1)
  return [
    {
      label: t('dashboard.stats.cracked'),
      subtitle: `${Math.round((fullTagCounts.value.cracked / total) * 100)}% ${t('dashboard.stats.total')}`,
      displayValue: formatCount.value(fullTagCounts.value.cracked),
      value: fullTagCounts.value.cracked,
      filter: 'cracked',
      group: 1,
      tone: 'brand',
      ratio: Math.round((fullTagCounts.value.cracked / total) * 100),
    },
    {
      label: t('dashboard.stats.chinese'),
      subtitle: `${Math.round((fullTagCounts.value.chinese / total) * 100)}% ${t('dashboard.stats.total')}`,
      displayValue: formatCount.value(fullTagCounts.value.chinese),
      value: fullTagCounts.value.chinese,
      filter: 'chinese',
      group: 2,
      tone: 'success',
      ratio: Math.round((fullTagCounts.value.chinese / total) * 100),
    },
    {
      label: t('dashboard.stats.leaked'),
      subtitle: `${Math.round((fullTagCounts.value.leaked / total) * 100)}% ${t('dashboard.stats.total')}`,
      displayValue: formatCount.value(fullTagCounts.value.leaked),
      value: fullTagCounts.value.leaked,
      filter: 'leaked',
      group: 3,
      tone: 'warning',
      ratio: Math.round((fullTagCounts.value.leaked / total) * 100),
    },
    {
      label: t('dashboard.stats.uncensored'),
      subtitle: `${Math.round((fullTagCounts.value.uncensored / total) * 100)}% ${t('dashboard.stats.total')}`,
      displayValue: formatCount.value(fullTagCounts.value.uncensored),
      value: fullTagCounts.value.uncensored,
      filter: 'uncensored',
      group: 4,
      tone: 'neutral',
      ratio: Math.round((fullTagCounts.value.uncensored / total) * 100),
    },
  ]
})

// GPU metrics (reactive)
const gpuMetrics = computed(() => {
  void i18nVersion.value
  return [
    { label: t('dashboard.gpu.util'), value: String(sysMetrics.value.gpu.gpu_util), unit: '%' },
    { label: t('dashboard.gpu.memory'), value: sysMetrics.value.gpu.mem_used.toFixed(1), unit: 'GB / ' + sysMetrics.value.gpu.mem_total.toFixed(0) + ' GB' },
    { label: t('dashboard.gpu.temp'), value: String(sysMetrics.value.gpu.temp), unit: '°C' },
    { label: t('dashboard.gpu.power'), value: sysMetrics.value.gpu.power.toFixed(0), unit: 'W' },
  ]
})

// CPU metrics (reactive)
const cpuMetrics = computed(() => {
  void i18nVersion.value
  return [
    { label: t('dashboard.cpu.util'), value: String(sysMetrics.value.cpu_mem.cpu_util), unit: '%' },
    { label: t('dashboard.cpu.memory'), value: sysMetrics.value.cpu_mem.mem_used.toFixed(1), unit: 'GB / ' + sysMetrics.value.cpu_mem.mem_total.toFixed(0) + ' GB' },
    { label: t('dashboard.cpu.temp'), value: String(sysMetrics.value.cpu_mem.cpu_temp), unit: '°C' },
    { label: t('dashboard.cpu.disk'), value: String(sysMetrics.value.cpu_mem.disk_read), unit: 'MB/s' },
  ]
})
</script>

<template>
  <div class="w-full space-y-6 animate-fade-in">

    <!-- Welcome + Stats Row -->
    <div class="dashboard-top-grid grid grid-cols-1 lg:grid-cols-4 gap-6">
      <!-- Welcome Card -->
      <div class="lg:col-span-2 dashboard-top-grid__panel">
        <WelcomeMark :greeting="t('dashboard.welcome.greeting')" :username="t('dashboard.user')" :message="t('dashboard.welcome.message')" />
      </div>

      <!-- Stats Card -->
      <div class="lg:col-span-2 dashboard-stats-card dashboard-top-grid__panel">
        <div class="dashboard-stats-card__hero">
          <div class="dashboard-stats-card__hero-copy">
            <p class="dashboard-stats-card__eyebrow">{{ t('dashboard.stats.total') }}</p>
            <div class="dashboard-stats-card__value" :class="{ 'dashboard-stats-card__value--pending': !countsLoaded }">
              <span class="dashboard-stats-card__number">{{ formatCount(fullTagCounts.total) }}</span>
            </div>
            <div class="dashboard-stats-card__summary-row">
              <p class="dashboard-stats-card__summary">关键分布</p>
              <span class="dashboard-stats-card__summary-dot" />
            </div>
          </div>
          <RouterLink to="/library" class="dashboard-stats-card__hero-link">
            {{ t('dashboard.viewAll') }}
          </RouterLink>
        </div>

        <div class="dashboard-stats-card__grid">
          <RouterLink
            v-for="stat in statsCards"
            :key="stat.filter"
            :to="'/library?filter=' + stat.filter"
            class="dashboard-stat-tile"
            :class="`dashboard-stat-tile--${stat.tone}`"
          >
            <span class="dashboard-stat-tile__glow" />
            <div class="dashboard-stat-tile__topline">
              <div class="dashboard-stat-tile__title-group">
                <span class="dashboard-stat-tile__dot" />
                <span class="dashboard-stat-tile__label">{{ stat.label }}</span>
              </div>
              <span class="dashboard-stat-tile__ratio">{{ stat.ratio }}%</span>
            </div>
            <div class="dashboard-stat-tile__body">
              <div class="dashboard-stat-tile__value" :class="{ 'dashboard-stat-tile__value--pending': !countsLoaded }">
                <span class="dashboard-stat-tile__number">{{ stat.displayValue }}</span>
              </div>
              <div class="dashboard-stat-tile__meter">
                <div class="dashboard-stat-tile__bar">
                  <span class="dashboard-stat-tile__bar-fill" :style="{ width: `${stat.ratio}%` }" />
                </div>
              </div>
            </div>
          </RouterLink>
        </div>
      </div>
    </div>

    <!-- Activity Card -->
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <div class="lg:col-span-2">
        <!-- GPU Metrics -->
        <SystemMetricsCard
          :title="t('dashboard.gpu.title')"
          :metrics="gpuMetrics"
          :progress-value="sysMetrics.gpu.gpu_util"
          progress-label="GPU"
          class="dashboard-metric-card dashboard-metric-card--gpu mb-5"
        />

        <!-- CPU / Memory Metrics -->
        <SystemMetricsCard
          class="dashboard-metric-card dashboard-metric-card--cpu"
          :title="t('dashboard.cpu.title')"
          :metrics="cpuMetrics"
          :progress-value="Math.round(sysMetrics.cpu_mem.cpu_util)"
          progress-label="CPU"
          progress-color="#01B574"
        />
      </div>

      <!-- Recent Activity -->
      <div>
        <ActivityCard :title="t('dashboard.recentJobs')">
          <template #action>
            <RouterLink to="/jobs" class="dashboard-link">
              {{ t('dashboard.viewAll') }}
            </RouterLink>
          </template>

          <div v-if="recentJobs.length === 0" class="py-8 text-center">
            <p class="text-sm text-white/30">{{ t('dashboard.noJobs') }}</p>
          </div>

          <RouterLink
            v-for="job in recentJobs"
            :key="job.id"
            :to="{ path: '/jobs', query: { job: job.id } }"
            class="activity-item dashboard-activity-item"
          >
            <div class="activity-item__icon" :class="`activity-item__icon--${getDashboardStatusTone(job)}`">
              <BaseIcon
                :name="getDashboardIconName(job)"
                class="w-3.5 h-3.5"
              />
            </div>
            <div class="activity-item__content">
              <p class="activity-item__name">{{ getJobDisplayName(job) }}</p>
              <p class="activity-item__meta">{{ getDashboardJobMetaLine(job) }}</p>
              <p v-if="getActivityDetailLine(job)" class="activity-item__meta activity-item__meta--secondary">{{ getActivityDetailLine(job) }}</p>
              <div v-if="getDashboardJobChips(job).length" class="activity-item__chain">
                <span v-for="chip in getDashboardJobChips(job)" :key="`${job.id}-${chip}`" class="activity-item__chip">{{ chip }}</span>
              </div>
            </div>
            <VuiBadge
              :color="getDashboardStatusTone(job)"
              variant="contained"
              size="xs"
            >
              {{ getRunningBadgeLabel(job) }}
            </VuiBadge>
          </RouterLink>
        </ActivityCard>
      </div>
    </div>
  </div>
</template>

<style scoped>
.dashboard-top-grid {
  align-items: stretch;
}

.dashboard-top-grid__panel {
  height: 18rem;
}

.dashboard-top-grid__panel.dashboard-stats-card {
  height: 18rem;
  min-height: 0;
}

.dashboard-top-grid__panel :deep(.welcome-mark) {
  min-height: 100%;
  height: 100%;
}

@media (min-width: 1024px) {
  .dashboard-top-grid__panel {
    height: 21.25rem;
  }

  .dashboard-top-grid__panel.dashboard-stats-card {
    height: 21.25rem;
  }
}

.activity-item__meta--secondary {
  opacity: 0.72;
  margin-top: 0.2rem;
}

.activity-item__chain {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
  margin-top: 0.32rem;
}

.activity-item__chip {
  display: inline-flex;
  align-items: center;
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 9999px;
  padding: 0.1rem 0.45rem;
  font-size: 11px;
  color: rgba(255,255,255,0.48);
}

.dashboard-stats-card {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 0.65rem;
  height: 100%;
  min-height: 0;
  padding: 1rem;
  overflow: hidden;
  border-radius: var(--radius-xl);
  border: 1px solid var(--color-border-default);
  background:
    radial-gradient(circle at 78% 18%, rgba(0, 117, 255, 0.14), transparent 28%),
    linear-gradient(135deg, rgba(255, 255, 255, 0.03) 0%, rgba(255, 255, 255, 0) 44%),
    linear-gradient(180deg, rgba(255, 255, 255, 0.015) 0%, rgba(255, 255, 255, 0) 100%),
    var(--color-bg-surface);
  box-shadow: var(--shadow-md);
}

.dashboard-stats-card::before {
  content: '';
  position: absolute;
  inset: -34% auto auto 60%;
  width: 14rem;
  height: 14rem;
  border-radius: 999px;
  background: rgba(0, 117, 255, 0.12);
  filter: blur(56px);
  pointer-events: none;
}

.dashboard-stats-card__hero {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
  padding: 0 0 0.65rem;
  border-bottom: 1px solid var(--color-border-subtle);
}

.dashboard-stats-card__hero-copy {
  display: flex;
  flex-direction: column;
  gap: 0.12rem;
}

.dashboard-stats-card__eyebrow {
  margin: 0 0 0.3rem;
  font-family: var(--font-display);
  font-size: var(--font-size-xs);
  font-weight: var(--font-weight-medium);
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--color-text-muted);
}

.dashboard-stats-card__value {
  display: flex;
  align-items: center;
  overflow: hidden;
  transition: opacity var(--transition-fast), transform var(--transition-fast);
}

.dashboard-stats-card__value--pending {
  opacity: 0.72;
}

.dashboard-stats-card__number {
  font-family: var(--font-display);
  font-size: clamp(2.35rem, 4.8vw, 3.5rem);
  font-weight: var(--font-weight-bold);
  line-height: 0.94;
  letter-spacing: -0.05em;
  color: var(--color-text-primary);
  text-shadow: 0 10px 30px rgba(0, 0, 0, 0.28);
}

.dashboard-stats-card__summary-row {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
}

.dashboard-stats-card__summary {
  margin: 0;
  font-size: 11px;
  color: var(--color-text-secondary);
}

.dashboard-stats-card__summary-dot {
  width: 0.28rem;
  height: 0.28rem;
  border-radius: 999px;
  background: rgba(0, 117, 255, 0.7);
  box-shadow: 0 0 10px rgba(0, 117, 255, 0.32);
}

.dashboard-stats-card__hero-link {
  position: relative;
  z-index: 1;
  flex-shrink: 0;
  padding: 0.38rem 0.64rem;
  border-radius: var(--radius-button);
  border: 1px solid rgba(0, 117, 255, 0.16);
  background: rgba(0, 117, 255, 0.08);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.05);
  font-family: var(--font-display);
  font-size: 11px;
  font-weight: var(--font-weight-semibold);
  color: var(--color-text-primary);
  transition: var(--transition-fast);
}

.dashboard-stats-card__hero-link:hover {
  transform: translateY(-1px);
  border-color: rgba(0, 117, 255, 0.32);
  background: rgba(0, 117, 255, 0.14);
  box-shadow: 0 8px 20px rgba(0, 117, 255, 0.16);
}

.dashboard-stats-card__grid {
  position: relative;
  z-index: 1;
  display: grid;
  flex: 1;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.58rem;
}

.dashboard-stat-tile {
  --dashboard-stat-bg: rgba(255, 255, 255, 0.028);
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 0.9rem;
  min-height: 0;
  padding: 0.68rem 0.78rem;
  overflow: hidden;
  border-radius: calc(var(--radius-lg) + 2px);
  border: 1px solid rgba(255, 255, 255, 0.05);
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.03) 0%, rgba(255, 255, 255, 0) 100%),
    var(--dashboard-stat-bg);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.03);
  transition: var(--transition-fast);
}

.dashboard-stat-tile:hover {
  transform: translateY(-1px);
  border-color: rgba(255, 255, 255, 0.075);
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.035) 0%, rgba(255, 255, 255, 0.01) 100%),
    var(--dashboard-stat-bg);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.03),
    0 10px 20px rgba(0, 0, 0, 0.14);
}

.dashboard-stat-tile--brand {
  --dashboard-stat-color: var(--color-brand);
  --dashboard-stat-glow: rgba(0, 117, 255, 0.18);
  --dashboard-stat-bg: rgba(0, 117, 255, 0.042);
}

.dashboard-stat-tile--success {
  --dashboard-stat-color: var(--color-success);
  --dashboard-stat-glow: rgba(1, 181, 116, 0.16);
  --dashboard-stat-bg: rgba(1, 181, 116, 0.04);
}

.dashboard-stat-tile--warning {
  --dashboard-stat-color: var(--color-warning);
  --dashboard-stat-glow: rgba(255, 181, 71, 0.16);
  --dashboard-stat-bg: rgba(255, 181, 71, 0.038);
}

.dashboard-stat-tile--neutral {
  --dashboard-stat-color: var(--color-text-primary);
  --dashboard-stat-glow: rgba(255, 255, 255, 0.1);
  --dashboard-stat-bg: rgba(255, 255, 255, 0.028);
}

.dashboard-stat-tile__glow {
  position: absolute;
  top: -1.75rem;
  right: -1.8rem;
  width: 5rem;
  height: 5rem;
  border-radius: 999px;
  background: var(--dashboard-stat-glow);
  filter: blur(26px);
  pointer-events: none;
  opacity: 0.9;
}

.dashboard-stat-tile__topline {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.6rem;
}

.dashboard-stat-tile__title-group {
  display: inline-flex;
  align-items: center;
  gap: 0.55rem;
  min-width: 0;
}

.dashboard-stat-tile__dot {
  width: 0.55rem;
  height: 0.55rem;
  flex-shrink: 0;
  border-radius: 999px;
  background: var(--dashboard-stat-color);
  box-shadow: 0 0 0 4px color-mix(in srgb, var(--dashboard-stat-color) 18%, transparent);
}

.dashboard-stat-tile__label,
.dashboard-stat-tile__ratio {
  font-family: var(--font-display);
  font-size: var(--font-size-xs);
}

.dashboard-stat-tile__label {
  overflow: hidden;
  color: var(--color-text-secondary);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.dashboard-stat-tile__ratio {
  color: rgba(255, 255, 255, 0.42);
}

.dashboard-stat-tile__body {
  position: relative;
  z-index: 1;
  display: flex;
  flex: 1;
  flex-direction: column;
  justify-content: space-between;
  gap: 0.45rem;
}

.dashboard-stat-tile__subtitle {
  margin: 0;
  font-size: 11px;
  color: var(--color-text-muted);
}

.dashboard-stat-tile__value {
  display: flex;
  align-items: flex-end;
  min-height: 0;
  transition: opacity var(--transition-fast), transform var(--transition-fast);
}

.dashboard-stat-tile__value--pending {
  opacity: 0.72;
}

.dashboard-stat-tile__number {
  font-family: var(--font-display);
  font-size: 1.2rem;
  font-weight: var(--font-weight-bold);
  line-height: 0.96;
  letter-spacing: -0.03em;
  color: var(--dashboard-stat-color);
}

.dashboard-stat-tile__meter {
  display: flex;
  align-items: center;
  gap: 0.35rem;
}

.dashboard-stat-tile__bar {
  flex: 1;
  height: 0.22rem;
  overflow: hidden;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.08);
}

.dashboard-stat-tile__bar-fill {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, color-mix(in srgb, var(--dashboard-stat-color) 80%, white), var(--dashboard-stat-color));
  box-shadow: 0 0 12px color-mix(in srgb, var(--dashboard-stat-color) 35%, transparent);
}

.dashboard-stat-tile__arrow {
  flex-shrink: 0;
  font-size: var(--font-size-xs);
  font-weight: var(--font-weight-semibold);
  color: color-mix(in srgb, var(--dashboard-stat-color) 70%, white);
  opacity: 0.9;
}

@media (max-width: 768px) {
  .dashboard-stats-card {
    padding: 0.88rem;
  }

  .dashboard-stats-card__hero {
    align-items: center;
    flex-direction: row;
  }

  .dashboard-stats-card__hero-link {
    width: fit-content;
  }

  .dashboard-stats-card__grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 0.5rem;
  }
}


.dashboard-link {
  font-family: var(--font-display);
  font-size: 11px;
  font-weight: var(--font-weight-medium);
  color: var(--color-brand);
}

.activity-item {
  padding: 0.2rem 0;
}

.activity-item__chip {
  border-color: var(--color-border-subtle);
  padding: 0.08rem 0.4rem;
  font-size: 10px;
  color: rgba(255,255,255,0.42);
}


.dashboard-metric-card {
  border-radius: var(--radius-xl);
}

.dashboard-activity-item + .dashboard-activity-item {
  margin-top: 0.15rem;
}

.dashboard-activity-item {
  align-items: flex-start;
  padding: 0.28rem 0;
  border-radius: var(--radius-md);
  color: inherit;
  text-decoration: none;
  transition: background-color var(--transition-fast), transform var(--transition-fast);
}

.dashboard-activity-item:hover {
  background: rgba(255,255,255,0.02);
  transform: translateY(-1px);
}

.dashboard-activity-item .activity-item__icon {
  width: 1.8rem;
  height: 1.8rem;
  margin-top: 0.05rem;
  border-radius: var(--radius-sm);
}

.dashboard-activity-item .activity-item__name {
  font-size: 0.875rem;
}

.dashboard-activity-item .activity-item__meta {
  font-size: 11px;
  margin-top: 0.1rem;
}

.dashboard-activity-item .activity-item__chain {
  margin-top: 0.22rem;
  gap: 0.28rem;
}

.dashboard-activity-item :deep(.vui-badge) {
  margin-top: 0.1rem;
}


@media (max-width: 900px) {
  .dashboard-top-grid {
    gap: 0.85rem;
  }

  .dashboard-top-grid__panel {
    height: 17rem;
  }

  .dashboard-top-grid__panel.dashboard-stats-card {
    height: 17rem;
  }

  .dashboard-stats-card {
    gap: 0.5rem;
    padding: 0.8rem;
  }

  .dashboard-stats-card__hero {
    padding-bottom: 0.45rem;
  }

  .dashboard-stats-card__number {
    font-size: 2.15rem;
  }

  .dashboard-stats-card__summary-row {
    gap: 0.28rem;
  }

  .dashboard-stats-card__summary {
    font-size: 10px;
  }

  .dashboard-stats-card__hero-link {
    padding: 0.34rem 0.56rem;
    font-size: 10px;
  }

  .dashboard-stats-card__grid {
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 0.42rem;
  }

  .dashboard-stat-tile {
    gap: 0.38rem;
    padding: 0.55rem 0.5rem;
  }

  .dashboard-stat-tile__topline {
    align-items: flex-start;
    flex-direction: column;
    gap: 0.12rem;
  }

  .dashboard-stat-tile__title-group {
    gap: 0.32rem;
  }

  .dashboard-stat-tile__dot {
    width: 0.42rem;
    height: 0.42rem;
  }

  .dashboard-stat-tile__label,
  .dashboard-stat-tile__ratio {
    font-size: 10px;
  }

  .dashboard-stat-tile__number {
    font-size: 0.9rem;
  }

  .dashboard-stat-tile__bar {
    height: 0.18rem;
  }

  .dashboard-metric-card :deep(.system-metrics-card__body) {
    gap: 0.8rem;
  }

  .dashboard-metric-card :deep(.system-metrics-card__ring) {
    width: 86px;
    height: 86px;
  }

  .dashboard-metric-card :deep(.system-metrics-card__ring-value) {
    font-size: 1.45rem;
  }

  .dashboard-metric-card :deep(.system-metrics-card__metric-value) {
    font-size: 0.875rem;
  }
}

@media (max-width: 780px) {
  .dashboard-metric-card {
    margin-bottom: 0 !important;
  }
}

</style>
