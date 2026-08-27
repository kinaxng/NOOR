<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useMediaLibraryStore } from '../stores/mediaLibrary'
import { useJobsStore } from '../stores/jobs'
import { RouterLink } from 'vue-router'
import BaseIcon from '../components/noor/BaseIcon.vue'
import VuiBadge from '../components/ui/Badge/VuiBadge.vue'
import WelcomeMark from '../components/ui/WelcomeMark.vue'
import ActivityCard from '../components/ui/ActivityCard.vue'
import api from '../api'
import { useI18n } from '../composables/useI18n'
import { useJobPresentation } from '../composables/useJobPresentation'
import { sortRunningJobsForList, sortJobsForList } from '../composables/jobOrdering'
import { useToast } from '../composables/useToast'

const { t, i18nVersion } = useI18n()
const toast = useToast()
const { getActivityDetailLine, getRunningBadgeLabel, getJobDisplayName, getDashboardJobMetaTokens, getDashboardJobChips, getDashboardStatusTone, getDashboardIconName, formatDashboardRelativeTime } = useJobPresentation(() => jobsStore.jobs)
const mediaLibraryStore = useMediaLibraryStore()
const jobsStore = useJobsStore()
const dashboardWidgets = ref<any[]>([])
const intelligenceOverview = ref<any>(null)
const intelligenceLoading = ref(false)
const javdbWidgetPage = ref(0)
const javdbWidgetPageSize = ref(1)

type DashboardLayoutItem = {
  id: string
  x: number
  y: number
  w: number
  h: number
  minW?: number
  minH?: number
}

const DASHBOARD_LAYOUT_STORAGE_KEY = 'noor-dashboard-grid-layout-v1'
const DASHBOARD_HIDDEN_STORAGE_KEY = 'noor-dashboard-hidden-cards-v1'
const dashboardGridRef = ref<HTMLElement | null>(null)
const dashboardGridWidth = ref(0)
const dashboardGridCols = computed(() => {
  const width = dashboardGridWidth.value || window.innerWidth
  if (width >= 1180) return 12
  if (width >= 860) return 8
  if (width >= 620) return 4
  return 1
})
const dashboardGridRowHeight = 88
const dashboardGridGap = 16
const isDashboardInteracting = ref(false)
const isDashboardEditMode = ref(false)
const defaultDashboardLayout: DashboardLayoutItem[] = [
  { id: 'welcome', x: 0, y: 0, w: 6, h: 4, minW: 3, minH: 3 },
  { id: 'stats', x: 6, y: 0, w: 6, h: 4, minW: 4, minH: 3 },
  { id: 'javdb-recommend', x: 0, y: 4, w: 12, h: 4, minW: 4, minH: 3 },
  { id: 'intelligence-core', x: 0, y: 8, w: 12, h: 3, minW: 4, minH: 3 },
  { id: 'system-cpu', x: 0, y: 11, w: 4, h: 4, minW: 3, minH: 3 },
  { id: 'system-gpu', x: 4, y: 11, w: 4, h: 4, minW: 3, minH: 3 },
  { id: 'recent-jobs', x: 8, y: 11, w: 4, h: 4, minW: 3, minH: 3 },
]
const dashboardCardOptions = [
  { id: 'welcome', label: '欢迎' },
  { id: 'stats', label: '媒体统计' },
  { id: 'javdb-recommend', label: 'JAVDB 推荐' },
  { id: 'intelligence-core', label: 'Intelligence Core' },
  { id: 'system-cpu', label: 'CPU / 内存' },
  { id: 'system-gpu', label: 'GPU / 显存' },
  { id: 'recent-jobs', label: '任务动态' },
]
const dashboardCardIds = dashboardCardOptions.map(card => card.id)
const dashboardWidgetPluginByCard: Record<string, string> = {
  'javdb-recommend': 'javdb',
  'system-cpu': 'widget-system',
  'system-gpu': 'widget-system',
}
const dashboardLayout = ref<DashboardLayoutItem[]>(loadDashboardLayout())
const hiddenDashboardCards = ref<string[]>(loadHiddenDashboardCards())
let dashboardResizeObserver: ResizeObserver | null = null
let dashboardInteraction:
  | null
  | {
      type: 'drag' | 'resize'
      id: string
      startX: number
      startY: number
      startItem: DashboardLayoutItem
    } = null

const DASHBOARD_COUNTS_CACHE_TTL = 60_000
const dashboardCountsCache = {
  key: '',
  fetchedAt: 0,
  data: null as null | { total: number; cracked: number; chinese: number; leaked: number; uncensored: number },
  promise: null as null | Promise<{ total: number; cracked: number; chinese: number; leaked: number; uncensored: number }>,
}

function cloneLayout(layout: DashboardLayoutItem[]) {
  return layout.map(item => ({ ...item }))
}

function loadDashboardLayout() {
  if (typeof localStorage === 'undefined') return cloneLayout(defaultDashboardLayout)
  try {
    const raw = localStorage.getItem(DASHBOARD_LAYOUT_STORAGE_KEY)
    if (!raw) return cloneLayout(defaultDashboardLayout)
    const parsed = JSON.parse(raw)
    if (!Array.isArray(parsed)) return cloneLayout(defaultDashboardLayout)
    const defaults = new Map(defaultDashboardLayout.map(item => [item.id, item]))
    return defaultDashboardLayout.map((fallback) => {
      const saved = parsed.find((item: DashboardLayoutItem) => item?.id === fallback.id)
      return {
        ...fallback,
        ...(saved || {}),
        minW: fallback.minW,
        minH: fallback.minH,
      }
    }).filter(item => defaults.has(item.id))
  } catch {
    return cloneLayout(defaultDashboardLayout)
  }
}


function loadHiddenDashboardCards() {
  if (typeof localStorage === 'undefined') return []
  try {
    const raw = localStorage.getItem(DASHBOARD_HIDDEN_STORAGE_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    if (!Array.isArray(parsed)) return []
    return parsed.filter((id: string) => dashboardCardIds.includes(id))
  } catch {
    return []
  }
}

function saveHiddenDashboardCards() {
  try {
    localStorage.setItem(DASHBOARD_HIDDEN_STORAGE_KEY, JSON.stringify(hiddenDashboardCards.value))
  } catch {
    // local-only enhancement; ignore persistence failures
  }
}

function isDashboardCardHidden(id: string) {
  return hiddenDashboardCards.value.includes(id)
}

function activeDashboardWidgetPluginIds() {
  return [...new Set(
    dashboardCardIds
      .filter(id => !isDashboardCardHidden(id))
      .map(id => dashboardWidgetPluginByCard[id])
      .filter(Boolean)
  )]
}

function pruneDashboardWidgetsForMountedCards() {
  const active = new Set(activeDashboardWidgetPluginIds())
  dashboardWidgets.value = dashboardWidgets.value.filter(widget => active.has(String(widget?.plugin_id || '')))
}

async function toggleDashboardCardVisibility(id: string) {
  if (!dashboardCardIds.includes(id)) return
  if (isDashboardCardHidden(id)) {
    hiddenDashboardCards.value = hiddenDashboardCards.value.filter(cardId => cardId !== id)
    await ensureDashboardDataForCard(id)
  } else {
    hiddenDashboardCards.value = [...hiddenDashboardCards.value, id]
    pruneDashboardWidgetsForMountedCards()
  }
}

function saveDashboardLayout() {
  try {
    localStorage.setItem(DASHBOARD_LAYOUT_STORAGE_KEY, JSON.stringify(dashboardLayout.value))
  } catch {
    // local-only enhancement; ignore persistence failures
  }
}

function resetDashboardLayout() {
  dashboardLayout.value = cloneLayout(defaultDashboardLayout)
  hiddenDashboardCards.value = []
  void ensureDashboardDataForVisibleCards()
}

function enterDashboardEditMode() {
  isDashboardEditMode.value = true
}

function saveDashboardLayoutAndExit() {
  saveDashboardLayout()
  saveHiddenDashboardCards()
  isDashboardEditMode.value = false
  toast.success('布局已保存')
}

function updateDashboardGridWidth() {
  dashboardGridWidth.value = dashboardGridRef.value?.clientWidth || window.innerWidth
}

function getDashboardLayoutItem(id: string) {
  let item = dashboardLayout.value.find(entry => entry.id === id)
  if (!item) {
    const fallback = defaultDashboardLayout.find(entry => entry.id === id)
    if (!fallback) return null
    item = { ...fallback }
    dashboardLayout.value.push(item)
  }
  return item
}

function normalizeDashboardItem(item: DashboardLayoutItem, cols = dashboardGridCols.value) {
  const minW = Math.min(item.minW || 1, cols)
  item.w = Math.max(minW, Math.min(item.w, cols))
  item.h = Math.max(item.minH || 1, item.h)
  item.x = Math.max(0, Math.min(item.x, Math.max(0, cols - item.w)))
  item.y = Math.max(0, item.y)
}

function dashboardItemsOverlap(a: DashboardLayoutItem, b: DashboardLayoutItem) {
  return a.x < b.x + b.w && a.x + a.w > b.x && a.y < b.y + b.h && a.y + a.h > b.y
}

function resolveDashboardCollisions(activeId: string) {
  const active = getDashboardLayoutItem(activeId)
  if (!active) return
  const visible = new Set(visibleDashboardItems.value)
  const items = dashboardLayout.value
    .filter(item => item.id !== activeId && visible.has(item.id))
    .sort((a, b) => a.y - b.y || a.x - b.x)

  let guard = 0
  let changed = true
  while (changed && guard < 24) {
    changed = false
    guard += 1
    for (const item of items) {
      if (dashboardItemsOverlap(active, item)) {
        item.y = active.y + active.h
        normalizeDashboardItem(item)
        changed = true
      }
      for (const other of items) {
        if (other.id === item.id) continue
        if (dashboardItemsOverlap(item, other)) {
          other.y = item.y + item.h
          normalizeDashboardItem(other)
          changed = true
        }
      }
    }
  }
}

function dashboardItemStyle(id: string) {
  const item = getDashboardLayoutItem(id)
  if (!item) return {}
  const cols = dashboardGridCols.value
  if (cols <= 1) {
    return {
      gridColumn: '1 / -1',
      gridRow: 'auto',
      minHeight: `${Math.max(3, item.minH || 3) * dashboardGridRowHeight}px`,
    }
  }
  const scale = cols >= 12 ? 1 : cols / 12
  const width = Math.max(item.minW || 1, Math.round(item.w * scale))
  const x = Math.min(Math.round(item.x * scale), Math.max(0, cols - width))
  const normalized = {
    ...item,
    x,
    w: Math.min(width, cols),
  }
  normalizeDashboardItem(normalized, cols)
  return {
    gridColumn: `${normalized.x + 1} / span ${normalized.w}`,
    gridRow: `${normalized.y + 1} / span ${normalized.h}`,
  }
}

function dashboardGridStyle() {
  if (dashboardGridCols.value <= 1) {
    return {
      gridTemplateColumns: '1fr',
      gridAutoRows: 'auto',
      gap: `${dashboardGridGap}px`,
      minHeight: '0px',
    }
  }
  const visibleItems = visibleDashboardItems.value
    .map(id => getDashboardLayoutItem(id))
    .filter(Boolean) as DashboardLayoutItem[]
  const rows = visibleItems.length
    ? Math.max(...visibleItems.map(item => item.y + item.h))
    : 1
  return {
    '--dashboard-grid-cols': dashboardGridCols.value,
    gridTemplateColumns: `repeat(${dashboardGridCols.value}, minmax(0, 1fr))`,
    gridAutoRows: `${dashboardGridRowHeight}px`,
    gap: `${dashboardGridGap}px`,
    minHeight: `${rows * dashboardGridRowHeight + Math.max(0, rows - 1) * dashboardGridGap}px`,
  }
}

function startDashboardInteraction(event: PointerEvent, id: string, type: 'drag' | 'resize') {
  if (!isDashboardEditMode.value || dashboardGridCols.value <= 1) return
  const target = event.target as HTMLElement | null
  if (type === 'drag' && target?.closest('a, button, input, select, textarea, .dashboard-grid-card__resize')) return
  const item = getDashboardLayoutItem(id)
  if (!item) return
  event.preventDefault()
  ;(event.currentTarget as HTMLElement)?.setPointerCapture?.(event.pointerId)
  dashboardInteraction = {
    type,
    id,
    startX: event.clientX,
    startY: event.clientY,
    startItem: { ...item },
  }
  isDashboardInteracting.value = true
  window.addEventListener('pointermove', handleDashboardPointerMove)
  window.addEventListener('pointerup', endDashboardInteraction)
}

function handleDashboardPointerMove(event: PointerEvent) {
  if (!dashboardInteraction) return
  const item = getDashboardLayoutItem(dashboardInteraction.id)
  if (!item || !dashboardGridRef.value) return
  const cols = dashboardGridCols.value
  const colWidth = (dashboardGridRef.value.clientWidth - dashboardGridGap * (cols - 1)) / cols
  const stepX = colWidth + dashboardGridGap
  const stepY = dashboardGridRowHeight + dashboardGridGap
  const dx = Math.round((event.clientX - dashboardInteraction.startX) / stepX)
  const dy = Math.round((event.clientY - dashboardInteraction.startY) / stepY)

  if (dashboardInteraction.type === 'drag') {
    item.x = dashboardInteraction.startItem.x + dx
    item.y = dashboardInteraction.startItem.y + dy
  } else {
    item.w = dashboardInteraction.startItem.w + dx
    item.h = dashboardInteraction.startItem.h + dy
  }
  normalizeDashboardItem(item, cols)
  resolveDashboardCollisions(item.id)
}

function endDashboardInteraction() {
  if (dashboardInteraction) {
    dashboardInteraction = null
  }
  isDashboardInteracting.value = false
  window.removeEventListener('pointermove', handleDashboardPointerMove)
  window.removeEventListener('pointerup', endDashboardInteraction)
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

async function fetchDashboardWidgets() {
  const pluginIds = activeDashboardWidgetPluginIds()
  if (!pluginIds.length) {
    dashboardWidgets.value = []
    return
  }
  try {
    const resp = await api.get('/plugins/dashboard/widgets', { params: { plugin_ids: pluginIds.join(',') } })
    dashboardWidgets.value = Array.isArray(resp.data) ? resp.data : []
  } catch {
    dashboardWidgets.value = []
  }
}

async function ensureDashboardDataForCard(id: string) {
  if (id === 'recent-jobs') {
    await jobsStore.fetchJobs()
    return
  }
  if (id === 'stats') {
    if (!mediaLibraryStore.libraries.length) await mediaLibraryStore.fetchLibraries()
    try {
      fullTagCounts.value = await fetchDashboardCounts()
    } finally {
      countsLoaded.value = true
    }
    return
  }
  if (id === 'intelligence-core') {
    await fetchIntelligenceOverview()
    return
  }
  if (dashboardWidgetPluginByCard[id]) {
    await fetchDashboardWidgets()
  }
}

async function ensureDashboardDataForVisibleCards() {
  const visible = new Set(dashboardCardIds.filter(id => !isDashboardCardHidden(id)))
  if (visible.has('stats')) {
    await mediaLibraryStore.fetchLibraries()
  }
  const tasks: Promise<unknown>[] = []
  if (visible.has('recent-jobs')) tasks.push(jobsStore.fetchJobs())
  if (visible.has('intelligence-core')) tasks.push(fetchIntelligenceOverview())
  if (dashboardCardIds.some(id => visible.has(id) && dashboardWidgetPluginByCard[id])) tasks.push(fetchDashboardWidgets())
  await Promise.allSettled(tasks)
  if (visible.has('stats')) {
    try {
      fullTagCounts.value = await fetchDashboardCounts()
    } catch {
      // ignore counting errors
    } finally {
      countsLoaded.value = true
    }
  } else {
    countsLoaded.value = true
  }
}

function updateJavdbWidgetPageSize() {
  javdbWidgetPageSize.value = 1
}

onMounted(async () => {
  updateDashboardGridWidth()
  if (dashboardGridRef.value) {
    dashboardResizeObserver = new ResizeObserver(updateDashboardGridWidth)
    dashboardResizeObserver.observe(dashboardGridRef.value)
  }
  await ensureDashboardDataForVisibleCards()
  updateJavdbWidgetPageSize()
  window.addEventListener('resize', updateJavdbWidgetPageSize)
  window.addEventListener('resize', updateDashboardGridWidth)
})

const javdbRecommendWidget = computed(() => {
  return dashboardWidgets.value.find(widget => widget?.plugin_id === 'javdb' && widget?.key === 'javdb-recommend') || null
})

const systemMetricsWidget = computed(() => {
  return dashboardWidgets.value.find(widget => widget?.payload?.kind === 'system_metrics') || null
})

const visibleDashboardItems = computed(() => {
  return [
    'welcome',
    'stats',
    javdbRecommendItems.value.length ? 'javdb-recommend' : null,
    'intelligence-core',
    systemMetricsWidget.value ? 'system-cpu' : null,
    systemMetricsWidget.value ? 'system-gpu' : null,
    'recent-jobs',
  ].filter((id): id is string => Boolean(id) && !isDashboardCardHidden(id as string))
})

async function fetchIntelligenceOverview() {
  intelligenceLoading.value = true
  try {
    const [stats, refresh] = await Promise.all([
      api.get('/knowledge/stats'),
      api.get('/knowledge/resources/refresh/status'),
    ])
    intelligenceOverview.value = {
      ...stats.data,
      refresh: refresh.data,
    }
  } catch {
    intelligenceOverview.value = null
  } finally {
    intelligenceLoading.value = false
  }
}

const intelligenceStats = computed(() => intelligenceOverview.value || {})
const intelligenceRefreshCounts = computed(() => intelligenceStats.value.refresh?.counts || {})
const intelligenceActiveTasks = computed(() => Number(intelligenceRefreshCounts.value.queued || 0) + Number(intelligenceRefreshCounts.value.running || 0))
const intelligenceEntityTotal = computed<number>(() => (Object.values(intelligenceStats.value.entities || {}) as unknown[]).reduce<number>((sum, value) => sum + Number(value || 0), 0))

const systemMetricsPayload = computed(() => {
  return systemMetricsWidget.value?.payload?.data || systemMetricsWidget.value?.payload || {}
})

const systemCpu = computed(() => systemMetricsPayload.value?.cpu_mem || {})
const systemGpu = computed(() => systemMetricsPayload.value?.gpu || {})

function metricPercent(value: unknown) {
  const n = Math.round(Number(value || 0))
  return Math.max(0, Math.min(100, n))
}

function metricMemoryLine(used: unknown, total: unknown) {
  const totalNumber = Number(total || 0)
  if (!totalNumber) return '0 / 0 GB'
  return `${Number(used || 0).toFixed(1)} / ${totalNumber.toFixed(0)} GB`
}

function metricRingStyle(value: unknown, color: string) {
  const safe = metricPercent(value)
  return {
    background: `conic-gradient(${color} ${safe * 3.6}deg, rgba(255,255,255,.08) 0deg)`,
  }
}

const javdbRecommendItems = computed(() => {
  const items = javdbRecommendWidget.value?.payload?.items
  return Array.isArray(items) ? items : []
})

const javdbRecommendPages = computed(() => {
  const size = Math.max(1, javdbWidgetPageSize.value)
  const pages: any[][] = []
  for (let i = 0; i < javdbRecommendItems.value.length; i += size) {
    pages.push(javdbRecommendItems.value.slice(i, i + size))
  }
  if (javdbWidgetPage.value >= pages.length) {
    javdbWidgetPage.value = Math.max(0, pages.length - 1)
  }
  return pages
})

const formatJavdbWidgetTitle = computed(() => {
  return (item: any) => [item?.code || '', item?.title || ''].filter(Boolean).join(' ')
})

function prevJavdbWidgetPage() {
  if (!javdbRecommendPages.value.length) return
  javdbWidgetPage.value = javdbWidgetPage.value <= 0
    ? javdbRecommendPages.value.length - 1
    : javdbWidgetPage.value - 1
}

function nextJavdbWidgetPage() {
  if (!javdbRecommendPages.value.length) return
  javdbWidgetPage.value = javdbWidgetPage.value >= javdbRecommendPages.value.length - 1
    ? 0
    : javdbWidgetPage.value + 1
}

onUnmounted(() => {
  window.removeEventListener('resize', updateJavdbWidgetPageSize)
  window.removeEventListener('resize', updateDashboardGridWidth)
  dashboardResizeObserver?.disconnect()
  dashboardResizeObserver = null
  endDashboardInteraction()
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

const statsRingItems = computed(() => {
  const radii = [58, 47, 36, 25]
  return statsCards.value.map((stat, index) => {
    const radius = radii[index] || 24
    const circumference = 2 * Math.PI * radius
    const ratio = Math.max(0, Math.min(100, stat.ratio))
    return {
      ...stat,
      radius,
      circumference,
      dashOffset: circumference * (1 - ratio / 100),
      percentLabel: `${ratio}%`,
    }
  })
})


</script>

<template>
  <div class="w-full animate-fade-in">
    <div v-if="isDashboardEditMode" class="dashboard-grid-toolbar">
      <div class="dashboard-grid-toolbar__meta">
        <span class="dashboard-grid-toolbar__dot" />
        <span>栅格布局 · {{ dashboardGridCols }} 列</span>
      </div>
      <div class="dashboard-grid-toolbar__actions">
        <button type="button" class="dashboard-grid-toolbar__reset" @click="resetDashboardLayout">重置布局</button>
        <button type="button" class="dashboard-grid-toolbar__save" @click="saveDashboardLayoutAndExit">保存布局</button>
      </div>
    </div>
    <div v-if="isDashboardEditMode" class="dashboard-card-visibility" aria-label="卡片显示控制">
      <button
        v-for="card in dashboardCardOptions"
        :key="card.id"
        type="button"
        class="dashboard-card-visibility__item"
        :class="{ 'dashboard-card-visibility__item--hidden': isDashboardCardHidden(card.id) }"
        @click="toggleDashboardCardVisibility(card.id)"
      >
        <BaseIcon :name="isDashboardCardHidden(card.id) ? 'eye-off' : 'eye'" class="w-3.5 h-3.5" />
        <span>{{ card.label }}</span>
      </button>
    </div>

    <div
      ref="dashboardGridRef"
      class="dashboard-grid"
      :class="{ 'dashboard-grid--editing': isDashboardEditMode, 'dashboard-grid--active': isDashboardInteracting }"
      :style="dashboardGridStyle()"
    >
      <section
        v-if="visibleDashboardItems.includes('welcome')"
        class="dashboard-grid-card dashboard-grid-card--welcome"
        :style="dashboardItemStyle('welcome')"
      >
        <div class="dashboard-grid-card__chrome" @pointerdown.stop="startDashboardInteraction($event, 'welcome', 'drag')">
          <span class="dashboard-grid-card__grip"><BaseIcon name="grid" class="w-3.5 h-3.5" /></span>
          <span class="dashboard-grid-card__label">欢迎</span>
        </div>
        <div class="dashboard-grid-card__body dashboard-grid-card__body--flush">
          <WelcomeMark :greeting="t('dashboard.welcome.greeting')" :username="t('dashboard.user')" :message="t('dashboard.welcome.message')" />
        </div>
        <button v-if="isDashboardEditMode" type="button" class="dashboard-grid-card__resize" @pointerdown.stop="startDashboardInteraction($event, 'welcome', 'resize')" aria-label="调整尺寸" />
      </section>

      <section
        v-if="visibleDashboardItems.includes('stats')"
        class="dashboard-grid-card dashboard-grid-card--stats"
        :style="dashboardItemStyle('stats')"
      >
        <div class="dashboard-grid-card__chrome" @pointerdown.stop="startDashboardInteraction($event, 'stats', 'drag')">
          <span class="dashboard-grid-card__grip"><BaseIcon name="grid" class="w-3.5 h-3.5" /></span>
          <span class="dashboard-grid-card__label">统计</span>
        </div>
        <div class="dashboard-grid-card__body dashboard-grid-card__body--flush">
          <div class="dashboard-stats-card">
            <RouterLink to="/library" class="dashboard-stats-orbit" aria-label="媒体库统计">
              <svg class="dashboard-stats-orbit__svg" viewBox="0 0 128 128" role="img">
                <circle
                  v-for="ring in statsRingItems"
                  :key="`track-${ring.filter}`"
                  class="dashboard-stats-orbit__track"
                  cx="64"
                  cy="64"
                  :r="ring.radius"
                />
                <circle
                  v-for="ring in statsRingItems"
                  :key="ring.filter"
                  class="dashboard-stats-orbit__ring"
                  :class="`dashboard-stats-orbit__ring--${ring.tone}`"
                  cx="64"
                  cy="64"
                  :r="ring.radius"
                  :stroke-dasharray="ring.circumference"
                  :stroke-dashoffset="ring.dashOffset"
                  :aria-label="`${ring.label} ${ring.percentLabel}`"
                />
              </svg>
              <div class="dashboard-stats-orbit__center">
                <strong :class="{ 'dashboard-stats-card__value--pending': !countsLoaded }">{{ formatCount(fullTagCounts.total) }}</strong>
                <span>{{ t('dashboard.stats.total') }}</span>
              </div>
            </RouterLink>

            <div class="dashboard-stats-legend">
              <RouterLink
                v-for="stat in statsCards"
                :key="stat.filter"
                :to="'/library?filter=' + stat.filter"
                class="dashboard-stats-legend__item"
                :class="`dashboard-stats-legend__item--${stat.tone}`"
              >
                <span class="dashboard-stats-legend__color" />
                <span class="dashboard-stats-legend__label">{{ stat.label }}</span>
                <span class="dashboard-stats-legend__value">
                  <strong>{{ stat.displayValue }}</strong>
                  <small>{{ stat.ratio }}%</small>
                </span>
              </RouterLink>
            </div>
          </div>
        </div>
        <button v-if="isDashboardEditMode" type="button" class="dashboard-grid-card__resize" @pointerdown.stop="startDashboardInteraction($event, 'stats', 'resize')" aria-label="调整尺寸" />
      </section>

      <section
        v-if="visibleDashboardItems.includes('javdb-recommend')"
        class="dashboard-grid-card dashboard-grid-card--javdb"
        :style="dashboardItemStyle('javdb-recommend')"
      >
        <div class="dashboard-grid-card__chrome" @pointerdown.stop="startDashboardInteraction($event, 'javdb-recommend', 'drag')">
          <span class="dashboard-grid-card__grip"><BaseIcon name="grid" class="w-3.5 h-3.5" /></span>
          <span class="dashboard-grid-card__label">JAVDB 推荐</span>
        </div>
        <div class="dashboard-grid-card__body">
          <section class="dashboard-widget-card dashboard-widget-card--hero">
            <div class="dashboard-widget-carousel">
              <button
                v-if="javdbRecommendPages.length > 1"
                type="button"
                class="dashboard-widget-card__pager-btn dashboard-widget-card__pager-btn--overlay dashboard-widget-card__pager-btn--left"
                @click="prevJavdbWidgetPage"
              >
                <BaseIcon name="chevronLeft" class="w-4 h-4" />
              </button>
              <button
                v-if="javdbRecommendPages.length > 1"
                type="button"
                class="dashboard-widget-card__pager-btn dashboard-widget-card__pager-btn--overlay dashboard-widget-card__pager-btn--right"
                @click="nextJavdbWidgetPage"
              >
                <BaseIcon name="chevronRight" class="w-4 h-4" />
              </button>
              <div class="dashboard-widget-carousel__track" :style="{ transform: `translateX(-${javdbWidgetPage * 100}%)` }">
                <div
                  v-for="(pageItems, pageIndex) in javdbRecommendPages"
                  :key="`javdb-page-${pageIndex}`"
                  class="dashboard-widget-carousel__page"
                  :style="{ gridTemplateColumns: `repeat(${pageItems.length}, minmax(0, 1fr))` }"
                >
                  <RouterLink
                    v-for="item in pageItems"
                    :key="item.code || item.title"
                    :to="{ path: '/plugins/javdb', query: { code: item.code || '' } }"
                    class="dashboard-widget-media"
                  >
                    <div class="dashboard-widget-media__cover">
                      <img :src="item.cover_url" :alt="formatJavdbWidgetTitle(item)" loading="lazy" />
                      <div class="dashboard-widget-media__overlay">
                        <p class="dashboard-widget-media__title">{{ formatJavdbWidgetTitle(item) }}</p>
                        <div class="dashboard-widget-media__meta">
                          <span v-if="item.release_date">{{ item.release_date }}</span>
                        </div>
                        <div class="dashboard-widget-media__badges">
                          <VuiBadge v-if="item.magnets_count" color="info" variant="contained" size="xs">{{ item.magnets_count }} 磁链</VuiBadge>
                          <VuiBadge v-if="item.has_cnsub" color="success" variant="contained" size="xs">中字</VuiBadge>
                          <VuiBadge v-if="item.is_cracked" color="danger" variant="contained" size="xs">破解</VuiBadge>
                        </div>
                      </div>
                    </div>
                  </RouterLink>
                </div>
              </div>
            </div>
          </section>
        </div>
        <button v-if="isDashboardEditMode" type="button" class="dashboard-grid-card__resize" @pointerdown.stop="startDashboardInteraction($event, 'javdb-recommend', 'resize')" aria-label="调整尺寸" />
      </section>

      <section
        v-if="visibleDashboardItems.includes('intelligence-core')"
        class="dashboard-grid-card dashboard-grid-card--intelligence"
        :style="dashboardItemStyle('intelligence-core')"
      >
        <div class="dashboard-grid-card__chrome" @pointerdown.stop="startDashboardInteraction($event, 'intelligence-core', 'drag')">
          <span class="dashboard-grid-card__grip"><BaseIcon name="grid" class="w-3.5 h-3.5" /></span>
          <span class="dashboard-grid-card__label">Intelligence Core</span>
        </div>
        <div class="dashboard-grid-card__body">
          <div class="intelligence-card" :class="{ 'is-loading': intelligenceLoading }">
            <div class="intelligence-card__identity">
              <span class="intelligence-card__mark"><BaseIcon name="sparkles" /></span>
              <div>
                <span class="intelligence-card__eyebrow">NOOR PERSONAL INTELLIGENCE</span>
                <h3>正在持续理解你的媒体世界</h3>
                <p>统一汇集媒体库、作品详情与各资源源站的长期情报。</p>
              </div>
            </div>
            <div class="intelligence-card__metrics">
              <div>
                <strong>{{ formatCount(intelligenceStats.work_profiles || 0) }}</strong>
                <span>作品画像</span>
              </div>
              <div>
                <strong>{{ formatCount(intelligenceStats.resource_observations || 0) }}</strong>
                <span>资源观测</span>
              </div>
              <div>
                <strong>{{ formatCount(intelligenceEntityTotal) }}</strong>
                <span>知识实体</span>
              </div>
            </div>
            <div class="intelligence-card__state">
              <span class="intelligence-card__pulse" :class="{ 'is-active': intelligenceActiveTasks > 0 }" />
              <div>
                <strong>{{ intelligenceActiveTasks > 0 ? `后台确认 ${intelligenceActiveTasks} 项` : '情报已同步' }}</strong>
                <span>{{ intelligenceActiveTasks > 0 ? '慢速源站不会阻塞页面' : '新发现会自动进入统一画像' }}</span>
              </div>
              <button type="button" :disabled="intelligenceLoading" @click="fetchIntelligenceOverview">
                <BaseIcon name="refresh" />
                刷新
              </button>
            </div>
          </div>
        </div>
        <button v-if="isDashboardEditMode" type="button" class="dashboard-grid-card__resize" @pointerdown.stop="startDashboardInteraction($event, 'intelligence-core', 'resize')" aria-label="调整尺寸" />
      </section>

      <section
        v-if="visibleDashboardItems.includes('system-cpu')"
        class="dashboard-grid-card dashboard-grid-card--system"
        :style="dashboardItemStyle('system-cpu')"
      >
        <div class="dashboard-grid-card__chrome" @pointerdown.stop="startDashboardInteraction($event, 'system-cpu', 'drag')">
          <span class="dashboard-grid-card__grip"><BaseIcon name="grid" class="w-3.5 h-3.5" /></span>
          <span class="dashboard-grid-card__label">CPU / 内存</span>
        </div>
        <div class="dashboard-grid-card__body">
          <div class="dashboard-system-card dashboard-system-card--cpu">
            <div class="dashboard-system-card__head">
              <h3>CPU / Memory</h3>
              <span>CPU</span>
            </div>
            <div class="dashboard-system-card__body">
              <div class="dashboard-system-card__rows">
                <div class="dashboard-system-card__row"><span>利用率</span><strong>{{ metricPercent(systemCpu.cpu_util) }}<small>%</small></strong></div>
                <div class="dashboard-system-card__row"><span>内存</span><strong>{{ metricMemoryLine(systemCpu.mem_used, systemCpu.mem_total) }}</strong></div>
                <div class="dashboard-system-card__row"><span>温度</span><strong>{{ Number(systemCpu.cpu_temp || 0).toFixed(0) }}<small>°C</small></strong></div>
                <div class="dashboard-system-card__row"><span>磁盘读取</span><strong>{{ Number(systemCpu.disk_read || 0).toFixed(0) }}<small>MB/s</small></strong></div>
              </div>
              <div class="dashboard-system-card__ring" :style="metricRingStyle(systemCpu.cpu_util, '#01B574')">
                <div><strong>{{ metricPercent(systemCpu.cpu_util) }}%</strong><span>CPU</span></div>
              </div>
            </div>
          </div>
        </div>
        <button v-if="isDashboardEditMode" type="button" class="dashboard-grid-card__resize" @pointerdown.stop="startDashboardInteraction($event, 'system-cpu', 'resize')" aria-label="调整尺寸" />
      </section>

      <section
        v-if="visibleDashboardItems.includes('system-gpu')"
        class="dashboard-grid-card dashboard-grid-card--system"
        :style="dashboardItemStyle('system-gpu')"
      >
        <div class="dashboard-grid-card__chrome" @pointerdown.stop="startDashboardInteraction($event, 'system-gpu', 'drag')">
          <span class="dashboard-grid-card__grip"><BaseIcon name="grid" class="w-3.5 h-3.5" /></span>
          <span class="dashboard-grid-card__label">GPU / 显存</span>
        </div>
        <div class="dashboard-grid-card__body">
          <div class="dashboard-system-card dashboard-system-card--gpu">
            <div class="dashboard-system-card__head">
              <h3>GPU Metrics</h3>
              <span>GPU</span>
            </div>
            <div class="dashboard-system-card__body">
              <div class="dashboard-system-card__rows">
                <div class="dashboard-system-card__row"><span>利用率</span><strong>{{ metricPercent(systemGpu.gpu_util) }}<small>%</small></strong></div>
                <div class="dashboard-system-card__row"><span>显存</span><strong>{{ metricMemoryLine(systemGpu.mem_used, systemGpu.mem_total) }}</strong></div>
                <div class="dashboard-system-card__row"><span>温度</span><strong>{{ Number(systemGpu.temp || 0).toFixed(0) }}<small>°C</small></strong></div>
                <div class="dashboard-system-card__row"><span>功耗</span><strong>{{ Number(systemGpu.power || 0).toFixed(0) }}<small>W</small></strong></div>
              </div>
              <div class="dashboard-system-card__ring" :style="metricRingStyle(systemGpu.gpu_util, '#0075FF')">
                <div><strong>{{ metricPercent(systemGpu.gpu_util) }}%</strong><span>GPU</span></div>
              </div>
            </div>
          </div>
        </div>
        <button v-if="isDashboardEditMode" type="button" class="dashboard-grid-card__resize" @pointerdown.stop="startDashboardInteraction($event, 'system-gpu', 'resize')" aria-label="调整尺寸" />
      </section>

      <section
        v-if="visibleDashboardItems.includes('recent-jobs')"
        class="dashboard-grid-card dashboard-grid-card--activity"
        :style="dashboardItemStyle('recent-jobs')"
      >
        <div class="dashboard-grid-card__chrome" @pointerdown.stop="startDashboardInteraction($event, 'recent-jobs', 'drag')">
          <span class="dashboard-grid-card__grip"><BaseIcon name="grid" class="w-3.5 h-3.5" /></span>
          <span class="dashboard-grid-card__label">任务动态</span>
        </div>
        <div class="dashboard-grid-card__body">
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
        <button v-if="isDashboardEditMode" type="button" class="dashboard-grid-card__resize" @pointerdown.stop="startDashboardInteraction($event, 'recent-jobs', 'resize')" aria-label="调整尺寸" />
      </section>
    </div>

    <button
      v-if="!isDashboardEditMode"
      type="button"
      class="dashboard-edit-fab"
      aria-label="编辑仪表盘布局"
      title="编辑布局"
      @click="enterDashboardEditMode"
    >
      <BaseIcon name="grid" class="w-5 h-5" />
    </button>
  </div>
</template>

<style scoped>
.dashboard-grid-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  margin-bottom: 0.85rem;
  color: var(--color-text-muted);
  font-family: var(--font-display);
  font-size: 11px;
}

.dashboard-grid-toolbar__meta {
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
}

.dashboard-grid-toolbar__dot {
  width: 0.42rem;
  height: 0.42rem;
  border-radius: 999px;
  background: var(--color-brand);
  box-shadow: 0 0 12px rgba(0, 117, 255, 0.42);
}

.dashboard-grid-toolbar__reset {
  border-radius: 999px;
  border: 1px solid var(--color-border-subtle);
  background: rgba(255, 255, 255, 0.028);
  padding: 0.34rem 0.72rem;
  color: var(--color-text-secondary);
  transition: var(--transition-fast);
}

.dashboard-grid-toolbar__actions {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
}

.dashboard-grid-toolbar__save {
  border-radius: 999px;
  border: 1px solid rgba(0, 117, 255, 0.42);
  background: rgba(0, 117, 255, 0.82);
  box-shadow: 0 10px 24px rgba(0, 117, 255, 0.18);
  padding: 0.34rem 0.78rem;
  color: #fff;
  font-weight: 700;
  transition: var(--transition-fast);
}

.dashboard-grid-toolbar__reset:hover,
.dashboard-grid-toolbar__save:hover {
  border-color: rgba(255, 255, 255, 0.12);
  color: var(--color-text-primary);
}

.dashboard-grid-toolbar__reset:hover {
  background: rgba(255, 255, 255, 0.052);
}

.dashboard-grid-toolbar__save:hover {
  background: rgba(0, 117, 255, 0.94);
  color: #fff;
}

.dashboard-card-visibility {
  display: flex;
  flex-wrap: wrap;
  gap: 0.46rem;
  margin: -0.2rem 0 0.9rem;
}

.dashboard-card-visibility__item {
  display: inline-flex;
  align-items: center;
  gap: 0.38rem;
  min-height: 1.9rem;
  border-radius: 999px;
  border: 1px solid rgba(255, 255, 255, 0.105);
  background: rgba(255, 255, 255, 0.045);
  padding: 0 0.68rem;
  color: var(--color-text-secondary);
  font-family: var(--font-display);
  font-size: 11px;
  font-weight: 700;
  transition: background-color var(--transition-fast), border-color var(--transition-fast), color var(--transition-fast), opacity var(--transition-fast);
}

.dashboard-card-visibility__item:hover {
  border-color: rgba(255, 255, 255, 0.16);
  background: rgba(255, 255, 255, 0.065);
  color: var(--color-text-primary);
}

.dashboard-card-visibility__item--hidden {
  border-color: rgba(255, 255, 255, 0.06);
  background: rgba(255, 255, 255, 0.02);
  color: rgba(255, 255, 255, 0.34);
}

.dashboard-grid {
  position: relative;
  display: grid;
  align-items: stretch;
  border-radius: var(--radius-xl);
  transition: min-height var(--transition-fast);
}

.dashboard-grid--editing,
.dashboard-grid--active {
  background-image:
    linear-gradient(rgba(0, 117, 255, 0.18) 1px, transparent 1px),
    linear-gradient(90deg, rgba(0, 117, 255, 0.18) 1px, transparent 1px);
  background-size: calc((100% - (var(--dashboard-grid-cols, 12) - 1) * 16px) / var(--dashboard-grid-cols, 12) + 16px) 104px, calc((100% - (var(--dashboard-grid-cols, 12) - 1) * 16px) / var(--dashboard-grid-cols, 12) + 16px) 104px;
  background-position: 0 0;
  box-shadow: inset 0 0 0 1px rgba(0, 117, 255, 0.08);
}

.dashboard-grid--active {
  background-image:
    linear-gradient(rgba(0, 117, 255, 0.26) 1px, transparent 1px),
    linear-gradient(90deg, rgba(0, 117, 255, 0.26) 1px, transparent 1px);
  box-shadow: inset 0 0 0 1px rgba(0, 117, 255, 0.12);
}

.dashboard-grid-card {
  position: relative;
  display: flex;
  min-width: 0;
  min-height: 0;
  overflow: hidden;
  border-radius: var(--radius-xl);
  user-select: none;
  touch-action: none;
}

.dashboard-grid-card__chrome {
  position: absolute;
  top: 0.42rem;
  left: 50%;
  transform: translateX(-50%);
  z-index: 8;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.4rem;
  max-width: calc(100% - 2.2rem);
  height: 1.62rem;
  border-radius: 999px;
  border: 1px solid rgba(255, 255, 255, 0.105);
  background: rgba(7, 10, 18, 0.62);
  color: rgba(255, 255, 255, 0.68);
  padding: 0 0.62rem;
  opacity: 0;
  pointer-events: none;
  backdrop-filter: blur(12px);
  cursor: grab;
  box-shadow: 0 10px 24px rgba(0, 0, 0, 0.18);
  transition: opacity var(--transition-fast), background-color var(--transition-fast), color var(--transition-fast), transform var(--transition-fast);
}

.dashboard-grid--editing .dashboard-grid-card__chrome {
  opacity: 0.72;
  pointer-events: auto;
}

.dashboard-grid--editing .dashboard-grid-card:hover .dashboard-grid-card__chrome {
  opacity: 1;
  transform: translateX(-50%) translateY(-1px);
}

.dashboard-grid-card__grip {
  display: inline-flex;
  opacity: 0.72;
  cursor: grab;
}

.dashboard-grid-card__label {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-family: var(--font-display);
  font-size: 10.5px;
  font-weight: 700;
}

.dashboard-grid-card__body {
  display: flex;
  flex: 1;
  min-width: 0;
  min-height: 0;
  padding: 0;
  overflow: hidden;
}

.dashboard-grid-card__body--flush {
  border-radius: inherit;
}

.dashboard-grid-card__resize {
  position: absolute;
  right: 0.2rem;
  bottom: 0.2rem;
  z-index: 9;
  width: 2.05rem;
  height: 2.05rem;
  border: 0;
  border-radius: 0;
  background:
    radial-gradient(circle, rgba(255, 255, 255, 0.74) 0 1.35px, transparent 1.55px) right 0.34rem bottom 0.34rem / 0.42rem 0.42rem no-repeat,
    radial-gradient(circle, rgba(255, 255, 255, 0.58) 0 1.25px, transparent 1.45px) right 0.78rem bottom 0.34rem / 0.42rem 0.42rem no-repeat,
    radial-gradient(circle, rgba(255, 255, 255, 0.58) 0 1.25px, transparent 1.45px) right 0.34rem bottom 0.78rem / 0.42rem 0.42rem no-repeat,
    radial-gradient(circle, rgba(255, 255, 255, 0.38) 0 1.15px, transparent 1.35px) right 1.22rem bottom 0.34rem / 0.42rem 0.42rem no-repeat,
    radial-gradient(circle, rgba(255, 255, 255, 0.38) 0 1.15px, transparent 1.35px) right 0.78rem bottom 0.78rem / 0.42rem 0.42rem no-repeat,
    radial-gradient(circle, rgba(255, 255, 255, 0.38) 0 1.15px, transparent 1.35px) right 0.34rem bottom 1.22rem / 0.42rem 0.42rem no-repeat;
  cursor: nwse-resize;
  opacity: 0.72;
  transition: opacity var(--transition-fast), transform var(--transition-fast), filter var(--transition-fast);
}

.dashboard-grid-card__resize::after {
  content: none;
}

.dashboard-grid-card__resize:hover {
  opacity: 1;
  filter: drop-shadow(0 0 10px rgba(0, 117, 255, 0.28));
  transform: translate(-0.5px, -0.5px);
}

.dashboard-edit-fab {
  position: fixed;
  right: clamp(1.25rem, 2.6vw, 2.2rem);
  bottom: clamp(1.25rem, 2.6vw, 2.2rem);
  z-index: 40;
  display: grid;
  width: 3.15rem;
  height: 3.15rem;
  place-items: center;
  border-radius: 999px;
  border: 1px solid rgba(0, 117, 255, 0.4);
  background: rgba(0, 117, 255, 0.88);
  color: #fff;
  box-shadow: 0 18px 48px rgba(0, 117, 255, 0.32), 0 10px 28px rgba(0, 0, 0, 0.24);
  transition: transform var(--transition-fast), box-shadow var(--transition-fast), filter var(--transition-fast);
}

.dashboard-edit-fab:hover {
  transform: translateY(-2px);
  filter: brightness(1.05);
  box-shadow: 0 22px 58px rgba(0, 117, 255, 0.38), 0 12px 30px rgba(0, 0, 0, 0.28);
}

.dashboard-grid-card :deep(.welcome-mark) {
  width: 100%;
  min-height: 0;
  height: 100%;
}

.dashboard-grid-card :deep(.activity-card) {
  width: 100%;
  overflow: hidden;
}

.dashboard-grid-card :deep(.activity-card__body) {
  min-height: 0;
  overflow: auto;
  padding-right: 0.15rem;
}

.dashboard-grid-card :deep(.plugin-widget),
.dashboard-grid-card :deep(.plugin-widget-renderer) {
  width: 100%;
  height: 100%;
}

.dashboard-grid-card--stats .dashboard-stats-card,
.dashboard-grid-card--javdb .dashboard-widget-card {
  width: 100%;
  height: 100%;
}

.dashboard-grid-card--javdb .dashboard-grid-card__body,
.dashboard-grid-card--javdb .dashboard-widget-card,
.dashboard-grid-card--javdb .dashboard-widget-card--hero {
  padding: 0;
}

.dashboard-grid-card--system .dashboard-grid-card__body > * {
  flex: 1;
  min-width: 0;
  min-height: 0;
}

.dashboard-system-card {
  display: flex;
  flex: 1;
  min-width: 0;
  min-height: 0;
  flex-direction: column;
  padding: 1.2rem;
  border-radius: var(--radius-xl);
  border: 1px solid var(--color-border-default);
  background:
    linear-gradient(180deg, rgba(255,255,255,.018) 0%, rgba(255,255,255,0) 100%),
    var(--color-bg-surface);
  box-shadow: var(--shadow-md);
}

.dashboard-system-card__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  margin-bottom: 1rem;
  padding-bottom: 0.82rem;
  border-bottom: 1px solid var(--color-border-subtle);
}

.dashboard-system-card__head h3 {
  margin: 0;
  font-family: var(--font-display);
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-semibold);
  color: var(--color-text-primary);
}

.dashboard-system-card__head span {
  font-family: var(--font-display);
  font-size: 11px;
  font-weight: 800;
  color: var(--dashboard-system-color);
}

.intelligence-card {
  position: relative;
  display: grid;
  grid-template-columns: minmax(280px, 1.35fr) minmax(320px, 1fr) minmax(220px, 0.7fr);
  align-items: center;
  gap: clamp(1rem, 2vw, 2rem);
  width: 100%;
  height: 100%;
  padding: clamp(1rem, 2vw, 1.55rem);
  overflow: hidden;
  border: 1px solid rgba(95, 178, 255, 0.18);
  border-radius: inherit;
  background:
    radial-gradient(circle at 12% 22%, rgba(0, 117, 255, 0.16), transparent 35%),
    radial-gradient(circle at 78% 80%, rgba(113, 84, 255, 0.12), transparent 42%),
    rgba(11, 17, 29, 0.86);
}

.intelligence-card.is-loading { opacity: 0.68; }

.intelligence-card__identity,
.intelligence-card__metrics,
.intelligence-card__state {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: center;
}

.intelligence-card__identity { gap: 1rem; min-width: 0; }
.intelligence-card__mark {
  display: grid;
  flex: 0 0 auto;
  width: 3.35rem;
  height: 3.35rem;
  place-items: center;
  border-radius: 1rem;
  color: #8fceff;
  background: linear-gradient(145deg, rgba(0, 117, 255, 0.2), rgba(115, 87, 255, 0.15));
  box-shadow: inset 0 0 0 1px rgba(126, 205, 255, 0.2), 0 14px 36px rgba(0, 80, 210, 0.14);
}
.intelligence-card__mark :deep(svg) { width: 1.6rem; height: 1.6rem; }
.intelligence-card__eyebrow { color: rgba(126, 205, 255, 0.66); font: 650 0.61rem/1 var(--font-display); letter-spacing: 0.14em; }
.intelligence-card h3 { margin: 0.38rem 0 0; color: rgba(255,255,255,.94); font: 600 clamp(.98rem, 1.35vw, 1.18rem)/1.2 var(--font-display); letter-spacing: -.02em; }
.intelligence-card p { margin: 0.42rem 0 0; color: rgba(255,255,255,.43); font: 400 .72rem/1.45 var(--font-display); }

.intelligence-card__metrics { justify-content: center; gap: clamp(.8rem, 1.7vw, 1.5rem); }
.intelligence-card__metrics div { min-width: 5.4rem; }
.intelligence-card__metrics strong { display: block; color: rgba(255,255,255,.94); font: 650 1.35rem/1 var(--font-display); letter-spacing: -.035em; }
.intelligence-card__metrics span { display: block; margin-top: .42rem; color: rgba(255,255,255,.42); font: 500 .66rem/1 var(--font-display); }

.intelligence-card__state { justify-content: flex-end; gap: .65rem; }
.intelligence-card__pulse { width: .48rem; height: .48rem; flex: 0 0 auto; border-radius: 999px; background: #55d69b; box-shadow: 0 0 0 5px rgba(85,214,155,.08), 0 0 16px rgba(85,214,155,.36); }
.intelligence-card__pulse.is-active { background: #64b5ff; box-shadow: 0 0 0 5px rgba(100,181,255,.08), 0 0 16px rgba(100,181,255,.36); animation: intelligence-pulse 1.4s ease-in-out infinite; }
@keyframes intelligence-pulse { 50% { opacity: .48; transform: scale(.82); } }
.intelligence-card__state div { min-width: 0; margin-right: auto; }
.intelligence-card__state strong,
.intelligence-card__state span { display: block; white-space: nowrap; }
.intelligence-card__state strong { color: rgba(255,255,255,.82); font: 550 .75rem/1.15 var(--font-display); }
.intelligence-card__state span { margin-top: .32rem; color: rgba(255,255,255,.38); font: 400 .63rem/1.15 var(--font-display); }
.intelligence-card__state button { display: inline-flex; align-items: center; gap: .35rem; padding: .48rem .62rem; border: 1px solid rgba(255,255,255,.09); border-radius: .65rem; color: rgba(255,255,255,.58); background: rgba(255,255,255,.035); font: 500 .66rem/1 var(--font-display); }
.intelligence-card__state button :deep(svg) { width: .78rem; height: .78rem; }

@media (max-width: 980px) {
  .intelligence-card { grid-template-columns: 1fr 1fr; }
  .intelligence-card__state { grid-column: 1 / -1; justify-content: flex-start; }
}

@media (max-width: 640px) {
  .intelligence-card { grid-template-columns: 1fr; }
  .intelligence-card__metrics { justify-content: flex-start; }
  .intelligence-card__state { grid-column: auto; }
}

.dashboard-system-card--cpu {
  --dashboard-system-color: #01B574;
}

.dashboard-system-card--gpu {
  --dashboard-system-color: #0075FF;
}

.dashboard-system-card__body {
  display: flex;
  flex: 1;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  min-height: 0;
}

.dashboard-system-card__rows {
  display: flex;
  min-width: 0;
  flex: 1;
  flex-direction: column;
  gap: 0.68rem;
}

.dashboard-system-card__row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.8rem;
  min-width: 0;
}

.dashboard-system-card__row span {
  font-family: var(--font-display);
  font-size: 11px;
  color: rgba(255,255,255,.46);
}

.dashboard-system-card__row strong {
  min-width: 0;
  overflow: hidden;
  text-align: right;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-family: var(--font-display);
  font-size: 0.9rem;
  font-weight: var(--font-weight-semibold);
  color: var(--color-text-primary);
}

.dashboard-system-card__row small {
  margin-left: 0.24rem;
  font-size: 11px;
  color: rgba(255,255,255,.38);
}

.dashboard-system-card__ring {
  position: relative;
  display: grid;
  width: clamp(82px, 7.4vw, 108px);
  height: clamp(82px, 7.4vw, 108px);
  flex: 0 0 auto;
  place-items: center;
  border-radius: 999px;
}

.dashboard-system-card__ring::before {
  content: '';
  position: absolute;
  inset: 10px;
  border-radius: inherit;
  background: var(--color-bg-surface);
  box-shadow: inset 0 0 0 1px rgba(255,255,255,.04);
}

.dashboard-system-card__ring div {
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.15rem;
}

.dashboard-system-card__ring strong {
  font-family: var(--font-display);
  font-size: clamp(1.2rem, 2vw, 1.75rem);
  font-weight: var(--font-weight-bold);
  color: var(--color-text-primary);
}

.dashboard-system-card__ring span {
  font-family: var(--font-display);
  font-size: 10px;
  color: rgba(255,255,255,.42);
}

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

.dashboard-widget-card {
  display: flex;
  flex-direction: column;
  gap: 0;
  padding: 0.85rem;
  border-radius: var(--radius-xl);
  border: 1px solid var(--color-border-default);
  background:
    linear-gradient(180deg, rgba(255,255,255,0.028) 0%, rgba(255,255,255,0.012) 100%),
    var(--color-bg-surface);
  box-shadow: var(--shadow-md);
  height: 18rem;
}

.dashboard-widget-card--hero {
  height: 18rem;
}


.dashboard-widget-carousel {
  position: relative;
  overflow: hidden;
  flex: 1;
  min-height: 0;
  height: 100%;
}

.dashboard-widget-carousel__track {
  display: flex;
  height: 100%;
  transition: transform var(--transition-fast);
}

.dashboard-widget-carousel__page {
  min-width: 100%;
  display: grid;
  gap: 0.85rem;
  min-height: 0;
  align-items: stretch;
}

.dashboard-widget-media {
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border-radius: var(--radius-lg);
  border: 1px solid rgba(255,255,255,0.08);
  background: rgba(255,255,255,0.03);
  color: inherit;
  text-decoration: none;
  transition: var(--transition-fast);
  min-width: 0;
  height: 100%;
}

.dashboard-widget-media:hover {
  transform: translateY(-1px);
  border-color: rgba(255,255,255,0.14);
  background: rgba(255,255,255,0.05);
}

.dashboard-widget-media__cover {
  position: relative;
  overflow: hidden;
  background: rgba(255,255,255,0.04);
  width: 100%;
  height: 100%;
}

.dashboard-widget-media__cover img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  background: rgba(10,14,24,0.72);
}

.dashboard-widget-media__overlay {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  justify-content: flex-end;
  gap: 0.35rem;
  padding: 0.8rem;
  background: linear-gradient(180deg, rgba(7,10,18,0.04) 20%, rgba(7,10,18,0.82) 100%);
  opacity: 0;
  transition: opacity var(--transition-fast);
  pointer-events: none;
}

.dashboard-widget-media:hover .dashboard-widget-media__overlay,
.dashboard-widget-media:focus-visible .dashboard-widget-media__overlay,
.dashboard-widget-media:focus-within .dashboard-widget-media__overlay {
  opacity: 1;
}

.dashboard-widget-media__title {
  margin: 0;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  font-size: 0.82rem;
  line-height: 1.36;
  color: #fff;
  text-shadow: 0 2px 10px rgba(0,0,0,0.45);
}

.dashboard-widget-media__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem 0.55rem;
  font-size: 10px;
  color: rgba(255,255,255,0.72);
}

.dashboard-widget-media__badges {
  display: flex;
  flex-wrap: wrap;
  gap: 0.25rem;
}

.dashboard-widget-card__pager-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 2.2rem;
  height: 2.2rem;
  border-radius: 999px;
  border: 1px solid rgba(255,255,255,0.1);
  background: rgba(10,14,24,0.48);
  backdrop-filter: blur(10px);
  color: rgba(255,255,255,0.72);
  transition: var(--transition-fast);
  z-index: 2;
}

.dashboard-widget-card__pager-btn:hover {
  border-color: rgba(255,255,255,0.18);
  background: rgba(10,14,24,0.68);
  color: #fff;
}

.dashboard-widget-card__pager-btn--overlay {
  position: absolute;
  top: 50%;
  transform: translateY(-50%);
}

.dashboard-widget-card__pager-btn--left {
  left: 0.4rem;
}

.dashboard-widget-card__pager-btn--right {
  right: 0.4rem;
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

  .dashboard-widget-card,
  .dashboard-widget-card--hero {
    height: 21.25rem;
  }
}

@media (max-width: 699px) {
  .dashboard-widget-card {
    padding: 0.65rem;
  }

  .dashboard-widget-card__pager-btn--left {
    left: 0.18rem;
  }

  .dashboard-widget-card__pager-btn--right {
    right: 0.18rem;
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
  gap: clamp(0.55rem, 1.2vw, 0.9rem);
  height: 100%;
  min-height: 0;
  padding: clamp(0.78rem, 1.45vw, 1.15rem);
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

.dashboard-stats-card__header {
  position: relative;
  z-index: 1;
  display: flex;
  flex-shrink: 0;
  align-items: center;
  justify-content: space-between;
  gap: 0.8rem;
  min-width: 0;
}

.dashboard-stats-card__identity {
  display: inline-flex;
  align-items: center;
  gap: 0.65rem;
  min-width: 0;
}

.dashboard-stats-card__dot {
  width: 0.55rem;
  height: 0.55rem;
  flex: 0 0 auto;
  border-radius: 999px;
  background: var(--color-brand);
  box-shadow: 0 0 0 4px rgba(0, 117, 255, 0.12), 0 0 18px rgba(0, 117, 255, 0.3);
}

.dashboard-stats-card__title {
  margin: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-family: var(--font-display);
  font-size: clamp(0.9rem, 1.45vw, 1.05rem);
  font-weight: var(--font-weight-semibold);
  color: var(--color-text-primary);
}

.dashboard-stats-card__main {
  position: relative;
  z-index: 1;
  display: grid;
  container-type: inline-size;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 11rem), 1fr));
  gap: clamp(0.65rem, 1.5vw, 1rem);
  min-height: 0;
}

.dashboard-stats-card__total {
  display: flex;
  min-width: 0;
  flex-direction: column;
  justify-content: center;
  gap: 0.24rem;
  border-radius: var(--radius-lg);
  border: 1px solid rgba(255,255,255,0.06);
  background: rgba(255,255,255,0.028);
  padding: clamp(0.65rem, 1.35vw, 0.95rem);
}

.dashboard-stats-card__total-label {
  font-family: var(--font-display);
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--color-text-muted);
}

.dashboard-stats-card__total strong {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-family: var(--font-display);
  font-size: clamp(1.75rem, 5vw, 3.3rem);
  font-weight: var(--font-weight-bold);
  line-height: 0.96;
  letter-spacing: -0.055em;
  color: var(--color-text-primary);
}

.dashboard-stats-card__rings {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.48rem;
  min-width: 0;
}

.dashboard-stat-ring {
  --stat-color: var(--color-brand);
  display: grid;
  min-width: 0;
  place-items: center;
  gap: 0.15rem;
  min-height: 4.4rem;
  border-radius: var(--radius-lg);
  border: 1px solid rgba(255,255,255,0.055);
  background:
    radial-gradient(circle at center, var(--color-bg-surface) 0 48%, transparent 49%),
    conic-gradient(var(--stat-color) var(--stat-ratio), rgba(255,255,255,0.075) 0deg);
  color: inherit;
  text-decoration: none;
}

.dashboard-stat-ring span {
  font-family: var(--font-display);
  font-size: clamp(0.9rem, 2vw, 1.15rem);
  font-weight: 800;
  color: var(--color-text-primary);
}

.dashboard-stat-ring small {
  max-width: 80%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-family: var(--font-display);
  font-size: 10px;
  color: rgba(255,255,255,0.52);
}

.dashboard-stat-ring--brand,
.dashboard-stat-row--brand {
  --stat-color: var(--color-brand);
}

.dashboard-stat-ring--success,
.dashboard-stat-row--success {
  --stat-color: var(--color-success);
}

.dashboard-stat-ring--warning,
.dashboard-stat-row--warning {
  --stat-color: var(--color-warning);
}

.dashboard-stat-ring--neutral,
.dashboard-stat-row--neutral {
  --stat-color: rgba(255,255,255,0.72);
}

.dashboard-stats-card__list {
  position: relative;
  z-index: 1;
  display: grid;
  min-height: 0;
  flex: 1;
  grid-template-columns: repeat(auto-fit, minmax(11rem, 1fr));
  gap: 0.48rem;
  overflow: auto;
  padding-right: 0.1rem;
}

.dashboard-stat-row {
  --stat-color: var(--color-brand);
  display: flex;
  min-width: 0;
  flex-direction: column;
  justify-content: center;
  gap: 0.45rem;
  border-radius: var(--radius-lg);
  border: 1px solid rgba(255,255,255,0.052);
  background: rgba(255,255,255,0.024);
  padding: 0.62rem 0.72rem;
  color: inherit;
  text-decoration: none;
  transition: var(--transition-fast);
}

.dashboard-stat-row:hover {
  border-color: color-mix(in srgb, var(--stat-color) 28%, rgba(255,255,255,0.08));
  background: color-mix(in srgb, var(--stat-color) 8%, rgba(255,255,255,0.028));
}

.dashboard-stat-row__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  min-width: 0;
}

.dashboard-stat-row__label {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-family: var(--font-display);
  font-size: 11px;
  color: rgba(255,255,255,0.58);
}

.dashboard-stat-row strong {
  flex: 0 0 auto;
  font-family: var(--font-display);
  font-size: 0.92rem;
  font-weight: 750;
  color: var(--color-text-primary);
}

.dashboard-stat-row small {
  margin-left: 0.35rem;
  font-size: 10px;
  color: var(--stat-color);
}

.dashboard-stat-row__bar {
  height: 0.22rem;
  overflow: hidden;
  border-radius: 999px;
  background: rgba(255,255,255,0.08);
}

.dashboard-stat-row__bar span {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: var(--stat-color);
  box-shadow: 0 0 12px color-mix(in srgb, var(--stat-color) 32%, transparent);
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

/* Media library stats: coaxial rings + compact legend */
.dashboard-stats-card {
  --stats-brand: var(--color-brand);
  --stats-success: var(--color-success);
  --stats-warning: var(--color-warning);
  --stats-neutral: rgba(255,255,255,0.78);
  display: grid;
  container: dashboard-stats / inline-size;
  grid-template-columns: minmax(12rem, 1.18fr) minmax(9.5rem, 0.82fr);
  align-items: center;
  gap: clamp(0.65rem, 1.45vw, 1.05rem);
  min-height: 0;
  overflow: hidden;
  padding: clamp(0.62rem, 1.15vw, 0.95rem);
  background:
    radial-gradient(circle at 31% 50%, rgba(0,117,255,0.12), transparent 34%),
    linear-gradient(145deg, rgba(255,255,255,0.04), rgba(255,255,255,0.012)),
    var(--color-bg-surface);
}

.dashboard-stats-orbit {
  position: relative;
  display: grid;
  width: min(100%, 16.5rem);
  aspect-ratio: 1;
  place-items: center;
  justify-self: center;
  color: inherit;
  text-decoration: none;
  filter: drop-shadow(0 18px 30px rgba(0,0,0,0.22));
}

.dashboard-stats-orbit__svg {
  width: 100%;
  height: 100%;
  overflow: visible;
  transform: rotate(-90deg);
}

.dashboard-stats-orbit__track,
.dashboard-stats-orbit__ring {
  fill: none;
  stroke-width: 5.8;
}

.dashboard-stats-orbit__track {
  stroke: rgba(255,255,255,0.055);
}

.dashboard-stats-orbit__ring {
  stroke-linecap: round;
  transition: stroke-dashoffset var(--transition-fast), opacity var(--transition-fast);
}

.dashboard-stats-orbit:hover .dashboard-stats-orbit__ring {
  opacity: 0.92;
}

.dashboard-stats-orbit__ring--brand { stroke: var(--stats-brand); }
.dashboard-stats-orbit__ring--success { stroke: var(--stats-success); }
.dashboard-stats-orbit__ring--warning { stroke: var(--stats-warning); }
.dashboard-stats-orbit__ring--neutral { stroke: var(--stats-neutral); }

.dashboard-stats-orbit__center {
  position: absolute;
  inset: 38%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.18rem;
  border-radius: 999px;
  background:
    radial-gradient(circle at 50% 0%, rgba(255,255,255,0.045), transparent 58%),
    color-mix(in srgb, var(--color-bg-surface) 90%, transparent);
  box-shadow:
    inset 0 0 0 1px rgba(255,255,255,0.055),
    0 12px 28px rgba(0,0,0,0.22);
}

.dashboard-stats-orbit__center strong {
  max-width: 92%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-family: var(--font-display);
  font-size: clamp(0.95rem, 2.28vw, 1.68rem);
  font-weight: var(--font-weight-bold);
  line-height: 0.95;
  letter-spacing: -0.055em;
  color: var(--color-text-primary);
}

.dashboard-stats-orbit__center span {
  max-width: 82%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-family: var(--font-display);
  font-size: 9px;
  font-weight: 700;
  color: rgba(255,255,255,0.45);
}

.dashboard-stats-legend {
  display: grid;
  align-content: center;
  gap: clamp(0.34rem, 0.8vw, 0.54rem);
  min-width: 0;
  min-height: 0;
  overflow: auto;
}

.dashboard-stats-legend__item {
  --stat-color: var(--stats-brand);
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  gap: 0.6rem;
  min-width: 0;
  border-radius: var(--radius-md);
  padding: 0.42rem 0.5rem;
  color: inherit;
  text-decoration: none;
  transition: background-color var(--transition-fast), transform var(--transition-fast);
}

.dashboard-stats-legend__item:hover {
  background: color-mix(in srgb, var(--stat-color) 8%, rgba(255,255,255,0.025));
  transform: translateX(1px);
}

.dashboard-stats-legend__item--brand { --stat-color: var(--stats-brand); }
.dashboard-stats-legend__item--success { --stat-color: var(--stats-success); }
.dashboard-stats-legend__item--warning { --stat-color: var(--stats-warning); }
.dashboard-stats-legend__item--neutral { --stat-color: var(--stats-neutral); }

.dashboard-stats-legend__color {
  width: 0.64rem;
  height: 0.64rem;
  border-radius: 999px;
  background: var(--stat-color);
  box-shadow: 0 0 12px color-mix(in srgb, var(--stat-color) 38%, transparent);
}

.dashboard-stats-legend__label {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-family: var(--font-display);
  font-size: 11px;
  font-weight: 650;
  color: rgba(255,255,255,0.52);
}

.dashboard-stats-legend__value {
  display: flex;
  min-width: 0;
  flex-direction: column;
  align-items: flex-end;
  gap: 0.05rem;
}

.dashboard-stats-legend__value strong {
  overflow: hidden;
  text-align: right;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-family: var(--font-display);
  font-size: clamp(0.95rem, 1.65vw, 1.18rem);
  font-weight: var(--font-weight-bold);
  line-height: 1;
  color: var(--stat-color);
}

.dashboard-stats-legend__value small {
  font-family: var(--font-display);
  font-size: 10px;
  font-weight: 750;
  color: rgba(255,255,255,0.34);
}

@container dashboard-stats (max-width: 430px) {
  .dashboard-stats-card {
    grid-template-columns: 1fr;
    align-content: center;
  }

  .dashboard-stats-orbit {
    width: min(100%, 13rem);
  }

  .dashboard-stats-legend {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    align-content: start;
  }

  .dashboard-stats-legend__item {
    padding: 0.36rem 0.38rem;
  }

  .dashboard-stats-legend__value {
    gap: 0;
  }
}

@media (max-width: 720px) {
  .dashboard-grid {
    grid-template-columns: 1fr !important;
    grid-auto-rows: auto !important;
    gap: 0.85rem !important;
    min-height: 0 !important;
    border-radius: 0;
  }

  .dashboard-grid-card {
    grid-column: 1 / -1 !important;
    grid-row: auto !important;
    width: 100%;
    min-width: 0;
    min-height: auto !important;
    touch-action: auto;
  }

  .dashboard-grid-card__body {
    min-height: auto;
    overflow: visible;
  }

  .dashboard-grid-card__chrome,
  .dashboard-grid-card__resize {
    display: none;
  }

  .dashboard-grid-card--welcome .dashboard-grid-card__body {
    min-height: 15rem;
  }

  .dashboard-grid-card--javdb .dashboard-grid-card__body,
  .dashboard-grid-card--system .dashboard-grid-card__body,
  .dashboard-grid-card--activity .dashboard-grid-card__body {
    min-height: 0;
  }

  .dashboard-grid-card--stats .dashboard-stats-card,
  .dashboard-grid-card--javdb .dashboard-widget-card {
    height: auto;
    min-height: 0;
  }

  .dashboard-grid-card :deep(.activity-card),
  .dashboard-grid-card :deep(.plugin-widget),
  .dashboard-grid-card :deep(.plugin-widget-renderer) {
    height: auto;
    min-height: 0;
  }

  .dashboard-system-card {
    padding: 0.9rem;
  }

  .dashboard-system-card__body {
    align-items: stretch;
  }

  .dashboard-system-card__ring {
    width: 82px;
    height: 82px;
  }

  .dashboard-stats-card {
    grid-template-columns: 1fr;
  }

  .dashboard-stats-orbit {
    width: min(100%, 13rem);
  }

  .dashboard-stats-legend {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 460px) {
  .dashboard-system-card__body {
    flex-direction: column-reverse;
  }

  .dashboard-system-card__ring {
    align-self: center;
  }

  .dashboard-stats-legend {
    grid-template-columns: 1fr;
  }
}

</style>
