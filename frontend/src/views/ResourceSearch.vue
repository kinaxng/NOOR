<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '../api'
import BaseIcon from '../components/noor/BaseIcon.vue'
import { useToast } from '../composables/useToast'
import { createDownloaderDialogContext } from '../composables/useDownloaderDialog'
import { openSubscriptionDialog } from '../composables/useSubscriptionDialog'

type ResourceItem = {
  provider: string
  provider_label: string
  id: string
  title: string
  subtitle?: string
  url?: string
  cover_url?: string
  source_url?: string
  size_bytes?: number
  file_count?: number
  tags?: string[]
  features?: Record<string, any>
  requirements?: Record<string, any>
  preferred_downloader?: string
  compatible_downloaders?: string[]
  query_key?: string
}

type CatalogSearchItem = {
  id: string
  source?: string
  source_label?: string
  type?: string
  title: string
  subtitle?: string
  description?: string
  image?: string | null
  badges?: { label: string, tone?: string }[]
  action?: { route?: string, payload?: Record<string, any> }
}

type MediaLibraryItem = {
  id?: string
  name?: string
  path?: string
  poster_path?: string
  fanart_path?: string
  backdrop_path?: string
  date_created?: string
  nfo?: Record<string, any>
  tags?: Record<string, any>
  subtitle_count?: number
}

type ResourceGroup = {
  provider: string
  provider_label: string
  total: number
  items: ResourceItem[]
  has_more?: boolean
  next_page?: number
  max_items?: number
}

type WorkResult = {
  code: string
  title: string
  cover_url?: string
  fanart_url?: string
  resources: ResourceItem[]
  providers: ResourceGroup[]
  media_item?: MediaLibraryItem
  catalog_item?: CatalogSearchItem
  in_library: boolean
  features: {
    has_subtitle: boolean
    is_cracked: boolean
    is_private_tracker: boolean
    has_direct_url: boolean
  }
}

const route = useRoute()
const router = useRouter()
const toast = useToast()
const query = ref(String(route.query.q || ''))
const loading = ref(false)
const error = ref('')
const groups = ref<ResourceGroup[]>([])
const mediaItems = ref<MediaLibraryItem[]>([])
const catalogItems = ref<CatalogSearchItem[]>([])
const activeProvider = ref('all')
const displayLimitPerProvider = 24
const providerLoading = ref<Record<string, boolean>>({})
const providerReachedEnd = ref<Record<string, boolean>>({})
const pushingResources = ref<Record<string, boolean>>({})
let seq = 0

const total = computed(() => groups.value.reduce((sum, group) => sum + (group.items?.length || 0), 0))
const works = computed(() => aggregateWorks(groups.value, mediaItems.value, catalogItems.value))
const visibleWorks = computed(() => {
  if (activeProvider.value === 'all') return works.value
  if (activeProvider.value === 'library') return works.value.filter(work => work.in_library)
  return works.value.filter(work => work.providers.some(provider => provider.provider === activeProvider.value))
})
const visibleTotal = computed(() => visibleWorks.value.length)
const providerSummary = computed(() => groups.value
  .filter(group => (group.items?.length || 0) > 0)
  .map(group => `${group.provider_label || group.provider} ${group.items?.length || 0}`)
  .join(' · '))
const providerOptions = computed(() => [
  { id: 'all', label: '全部作品', count: works.value.length },
  ...(mediaItems.value.length ? [{ id: 'library', label: '已入库', count: mediaItems.value.length }] : []),
  ...groups.value.map(group => ({ id: group.provider, label: group.provider_label || group.provider, count: group.items?.length || 0 })),
])
const subtitleCount = computed(() => groups.value.flatMap(group => group.items || []).filter(item => item.features?.has_subtitle).length)
const ptCount = computed(() => groups.value.flatMap(group => group.items || []).filter(item => item.features?.is_private_tracker || item.requirements?.accepts_private_tracker).length)
const directCount = computed(() => groups.value.flatMap(group => group.items || []).filter(item => item.url).length)
const codeHint = computed(() => extractCode(query.value))

function extractCode(value: string) {
  const match = String(value || '').match(/\b(FC2[-_ ]?(?:PPV[-_ ]?)?\d{4,9}|[A-Z]{2,8}[-_ ]?\d{2,7}|\d{6}[-_]\d{2,5})\b/i)
  if (!match) return ''
  const raw = match[1].toUpperCase().replace(/[_ ]+/g, '-')
  const fc2 = raw.match(/^FC2-?(?:PPV-?)?(\d{4,9})$/i)
  if (fc2) return `FC2-PPV-${fc2[1]}`
  const compact = raw.match(/^([A-Z]{2,8})(\d{2,7})$/)
  if (compact) return `${compact[1]}-${compact[2]}`
  return raw
}


function mediaCode(item: MediaLibraryItem) {
  const nfo = item.nfo || {}
  return extractCode(`${nfo.num || ''} ${item.name || ''} ${nfo.title || ''} ${nfo.originaltitle || ''}`) || String(nfo.num || item.name || item.id || '媒体')
}

function mediaTitle(item: MediaLibraryItem) {
  const nfo = item.nfo || {}
  return String(nfo.title || item.name || nfo.originaltitle || mediaCode(item))
}

function mediaCover(item: MediaLibraryItem) {
  return item.backdrop_path || item.fanart_path || item.poster_path || ''
}

function catalogCode(item: CatalogSearchItem) {
  const payload = item.action?.payload || {}
  const declared = String(payload.query_key || payload.code || '').trim()
  return extractCode(declared) || declared || extractCode(`${item.title || ''} ${item.subtitle || ''} ${item.id || ''}`) || item.title
}

function catalogRoute(item: CatalogSearchItem) {
  return item.action?.route || ''
}

function mediaWorkBadges(work: WorkResult) {
  const tags = work.media_item?.tags || {}
  const out = [{ label: '已入库', tone: 'success' }]
  if (tags.has_chinese) out.push({ label: '中字', tone: 'success' })
  if (tags.is_cracked) out.push({ label: '破解', tone: 'warning' })
  if (tags.release_type) out.push({ label: String(tags.release_type), tone: 'info' })
  const subtitles = Number(work.media_item?.subtitle_count || 0)
  if (subtitles) out.push({ label: `字幕 ${subtitles}`, tone: 'info' })
  return out
}

function formatSize(value?: number) {
  let size = Number(value || 0)
  if (!Number.isFinite(size) || size <= 0) return ''
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let index = 0
  while (size >= 1024 && index < units.length - 1) {
    size /= 1024
    index += 1
  }
  return index >= 2 ? `${size.toFixed(1)} ${units[index]}` : `${Math.round(size)} ${units[index]}`
}

function resourceKey(item: ResourceItem) {
  return `${item.provider}:${item.id || ''}:${item.url || ''}:${item.title || ''}`
}

function providerLabel(provider: string) {
  return groups.value.find(group => group.provider === provider)?.provider_label || provider
}

function workKeyFromItem(item: ResourceItem) {
  const declared = String(item.query_key || '').trim()
  return extractCode(declared) || declared || extractCode(`${item.title || ''} ${item.subtitle || ''} ${item.id || ''}`) || `${item.provider}:${item.id || item.title}`
}

function cleanWorkTitle(item: ResourceItem, code: string) {
  const title = String(item.title || '').trim()
  if (!title) return code || '未知作品'
  if (code && title.toUpperCase() === code.toUpperCase()) return code
  if (item.provider === 'javdb' && code && title.toUpperCase().startsWith(`${code.toUpperCase()} `)) return title
  if (item.provider === 'javdb' && !/\.(torrent|mp4|mkv|avi|torrent)$/i.test(title)) return title
  return code || title
}

function aggregateWorks(sourceGroups: ResourceGroup[], libraryItems: MediaLibraryItem[], catalogSourceItems: CatalogSearchItem[]) {
  const map = new Map<string, WorkResult>()
  for (const media of libraryItems || []) {
    const code = mediaCode(media)
    const key = code || String(media.id || media.name || '')
    if (!key) continue
    map.set(key, {
      code,
      title: mediaTitle(media),
      cover_url: mediaCover(media),
      fanart_url: mediaCover(media),
      resources: [],
      providers: [],
      media_item: media,
      in_library: true,
      features: {
        has_subtitle: !!media.tags?.has_chinese,
        is_cracked: !!media.tags?.is_cracked,
        is_private_tracker: false,
        has_direct_url: false,
      },
    })
  }

  for (const catalog of catalogSourceItems || []) {
    const code = catalogCode(catalog)
    const key = code || String(catalog.id || catalog.title || '')
    if (!key) continue
    const existing = map.get(key)
    if (existing) {
      existing.catalog_item = catalog
      if (!existing.cover_url && catalog.image) existing.cover_url = catalog.image
      if (!existing.fanart_url && catalog.image) existing.fanart_url = catalog.image
      continue
    }
    map.set(key, {
      code,
      title: catalog.title || code,
      cover_url: catalog.image || '',
      fanart_url: catalog.image || '',
      resources: [],
      providers: [],
      catalog_item: catalog,
      in_library: (catalog.badges || []).some(badge => badge.label === '已入库'),
      features: {
        has_subtitle: (catalog.badges || []).some(badge => badge.label === '中字'),
        is_cracked: (catalog.badges || []).some(badge => badge.label === '破解'),
        is_private_tracker: false,
        has_direct_url: false,
      },
    })
  }

  for (const group of sourceGroups) {
    for (const item of group.items || []) {
      const code = workKeyFromItem(item)
      const key = code || resourceKey(item)
      const existing = map.get(key) || {
        code,
        title: cleanWorkTitle(item, code),
        cover_url: item.cover_url,
        fanart_url: item.cover_url,
        resources: [],
        providers: [],
        in_library: false,
        features: {
          has_subtitle: false,
          is_cracked: false,
          is_private_tracker: false,
          has_direct_url: false,
        },
      }
      if (!existing.cover_url && item.cover_url) existing.cover_url = item.cover_url
      if (item.provider === 'javdb' && existing.title === existing.code && item.title && !/\.(torrent|mp4|mkv|avi|torrent)$/i.test(item.title)) {
        existing.title = cleanWorkTitle(item, code)
      }
      existing.resources.push(item)
      existing.features.has_subtitle = existing.features.has_subtitle || !!item.features?.has_subtitle
      existing.features.is_cracked = existing.features.is_cracked || !!item.features?.is_cracked
      existing.features.is_private_tracker = existing.features.is_private_tracker || !!(item.features?.is_private_tracker || item.requirements?.accepts_private_tracker)
      existing.features.has_direct_url = existing.features.has_direct_url || !!item.url
      map.set(key, existing)
    }
  }
  for (const work of map.values()) {
    const providerMap = new Map<string, ResourceGroup>()
    for (const item of work.resources) {
      const provider = item.provider || 'unknown'
      const group = providerMap.get(provider) || {
        provider,
        provider_label: providerLabel(provider),
        total: 0,
        items: [],
      }
      group.items.push(item)
      group.total = group.items.length
      providerMap.set(provider, group)
    }
    work.providers = [...providerMap.values()].sort((a, b) => providerOrder(a.provider) - providerOrder(b.provider))
    work.resources.sort((a, b) => providerOrder(a.provider) - providerOrder(b.provider) || Number(b.size_bytes || 0) - Number(a.size_bytes || 0))
  }
  return [...map.values()].sort((a, b) => {
    const aExact = a.code && a.code === codeHint.value
    const bExact = b.code && b.code === codeHint.value
    if (aExact !== bExact) return aExact ? -1 : 1
    return b.resources.length - a.resources.length || a.code.localeCompare(b.code, 'zh-CN')
  })
}

function providerOrder(provider: string) {
  if (provider === 'avdb') return 0
  if (provider === 'mteam-plugin') return 1
  if (provider === 'javdb') return 2
  return 9
}

function badges(item: ResourceItem) {
  const out = [{ label: item.provider_label || item.provider, tone: 'primary' }]
  if (item.features?.has_subtitle) out.push({ label: '中字', tone: 'success' })
  if (item.features?.is_cracked) out.push({ label: '破解', tone: 'warning' })
  if (item.features?.is_private_tracker || item.requirements?.accepts_private_tracker) out.push({ label: 'PT', tone: 'danger' })
  const size = formatSize(item.size_bytes)
  if (size) out.push({ label: size, tone: 'info' })
  if (item.preferred_downloader) out.push({ label: item.preferred_downloader, tone: 'info' })
  return out
}

function dedupeBadges(items: Array<{ label: string, tone: string }>) {
  const seen = new Set<string>()
  const out: Array<{ label: string, tone: string }> = []
  for (const item of items) {
    const key = item.label
    if (!key || seen.has(key)) continue
    seen.add(key)
    out.push(item)
  }
  return out
}

function workBadges(work: WorkResult) {
  const out = work.in_library ? mediaWorkBadges(work) : []
  if (work.catalog_item && !work.in_library) out.push(...(work.catalog_item.badges || []).filter(badge => ['JavDB', '已入库', '中字', '破解'].includes(badge.label)).map(badge => ({ label: badge.label, tone: badge.tone || 'info' })))
  if (work.in_library && work.catalog_item) out.push({ label: 'JavDB', tone: 'primary' })
  if (work.resources.length) out.push({ label: `${work.resources.length} 资源`, tone: 'primary' })
  if (work.features.has_subtitle) out.push({ label: '中字', tone: 'success' })
  if (work.features.is_cracked) out.push({ label: '破解', tone: 'warning' })
  if (work.features.is_private_tracker) out.push({ label: 'PT', tone: 'danger' })
  if (work.features.has_direct_url) out.push({ label: '可推送', tone: 'info' })
  return dedupeBadges(out)
}

function toneClass(tone: string) {
  return `resource-search-badge--${tone || 'info'}`
}

function targetRoute(itemOrWork: ResourceItem | WorkResult) {
  const key = 'resources' in itemOrWork
    ? itemOrWork.code
    : itemOrWork.query_key || extractCode(`${itemOrWork.title} ${itemOrWork.subtitle || ''}`)
  if ('resources' in itemOrWork && itemOrWork.in_library) return `/library?q=${encodeURIComponent(key || itemOrWork.code)}`
  if ('resources' in itemOrWork && itemOrWork.catalog_item && catalogRoute(itemOrWork.catalog_item)) return catalogRoute(itemOrWork.catalog_item)
  if (key) return `/plugins/javdb?code=${encodeURIComponent(key)}`
  if (!('resources' in itemOrWork) && itemOrWork.provider) return `/plugins/${itemOrWork.provider}`
  return '/plugins'
}

function itemSourceText(item: ResourceItem | null) {
  if (!item) return ''
  const pieces = []
  if (item.file_count) pieces.push(`${item.file_count} 文件`)
  if (item.compatible_downloaders?.length) pieces.push(`可用下载器 ${item.compatible_downloaders.length}`)
  if (item.query_key) pieces.push(item.query_key)
  return pieces.join(' · ')
}

function libraryRoute(work: WorkResult) {
  return `/library?q=${encodeURIComponent(work.code)}`
}

function javdbRoute(work: WorkResult) {
  return catalogRoute(work.catalog_item || {} as CatalogSearchItem) || `/plugins/javdb?code=${encodeURIComponent(work.code)}`
}

async function openWork(work: WorkResult) {
  await router.push(targetRoute(work))
}

async function openLibrary(work: WorkResult) {
  await router.push(libraryRoute(work))
}

async function openJavdb(work: WorkResult) {
  await router.push(javdbRoute(work))
}

async function subscribeWork(work: WorkResult) {
  try {
    await openSubscriptionDialog({
      code: work.code,
      title: work.title || work.code,
      cover_url: work.cover_url || work.fanart_url || '',
      fanart_url: work.fanart_url || work.cover_url || '',
      sourcePlugin: 'global-resource-search',
      sourceLabel: '全局资源搜索',
      sourceRoute: route.fullPath,
      sourceContext: 'resource-search',
      defaultMode: 'loose',
      requireCracked: false,
      requireSubtitle: false,
      onSuccess: result => toast.success(result?.created ? '订阅已创建' : '订阅已存在'),
    })
  } catch (e: any) {
    toast.error(e?.response?.data?.detail || e?.message || '订阅失败')
  }
}

async function pushResource(item: ResourceItem) {
  const key = resourceKey(item)
  if (pushingResources.value[key]) return
  pushingResources.value = { ...pushingResources.value, [key]: true }
  try {
    const resolved = await api.post('/plugins/resources/resolve-download', {
      provider_id: item.provider,
      item,
    }).then(resp => resp.data)
    const resolvedItem = resolved?.item || item
    const url = resolved?.url || resolvedItem?.url
    const downloaderIds = Array.from(new Set([
      resolvedItem?.preferred_downloader,
      ...(Array.isArray(resolvedItem?.compatible_downloaders) ? resolvedItem.compatible_downloaders : []),
    ].filter(Boolean).map(String)))
    if (!downloaderIds.length) throw new Error('没有兼容的下载器')
    if (!url) throw new Error('资源链接解析失败')
    const workTitle = resolvedItem.query_key || extractCode(`${resolvedItem.title || ''} ${resolvedItem.subtitle || ''}`) || query.value
    await createDownloaderDialogContext(item.provider).open({
      downloaderId: resolvedItem?.preferred_downloader || downloaderIds[0],
      downloaderIds,
      url,
      magnet: url,
      title: workTitle,
      itemTitle: workTitle,
      name: workTitle,
      rename: workTitle,
      titleOptions: [
        { key: 'work', label: '作品番号', value: workTitle, hint: '优先使用作品番号，避免资源文件名污染标题。' },
        resolvedItem.title && resolvedItem.title !== workTitle ? { key: 'resource', label: '资源原名', value: resolvedItem.title, hint: '使用资源插件返回的原始资源名。' } : null,
      ].filter(Boolean),
      titleMode: 'work',
      sourcePluginId: item.provider,
    })
  } catch (e: any) {
    toast.error(e?.response?.data?.detail || e?.message || '打开推送卡片失败')
  } finally {
    pushingResources.value = { ...pushingResources.value, [key]: false }
  }
}

function switchProvider(provider: string) {
  activeProvider.value = provider
}

function hasMoreForGroup(group: ResourceGroup) {
  if (activeProvider.value === 'all') return Boolean(group.has_more)
  return Boolean(group.has_more) && (group.items?.length || 0) < 100 && !providerReachedEnd.value[group.provider]
}

function nextProviderPage(group: ResourceGroup) {
  const loaded = group.items?.length || 0
  return group.next_page || Math.floor(loaded / displayLimitPerProvider) + 1
}

async function loadMoreProvider(group: ResourceGroup) {
  if (activeProvider.value === 'all') {
    switchProvider(group.provider)
    return
  }
  if (providerLoading.value[group.provider] || !hasMoreForGroup(group)) return
  const q = query.value.trim()
  if (!q) return
  providerLoading.value = { ...providerLoading.value, [group.provider]: true }
  try {
    const code = extractCode(q)
    const payload: Record<string, any> = {
      keyword: q,
      q,
      limit: displayLimitPerProvider,
      mode: 'deep',
      page: nextProviderPage(group),
      max_items: 100,
    }
    if (code) {
      payload.code = code
      payload.number = code
    }
    const resp = await api.post('/plugins/resources/search', {
      query: payload,
      providers: [group.provider],
      limit_per_plugin: displayLimitPerProvider,
      track_intent: false,
    })
    const nextGroup = (resp.data?.groups || [])[0]
    const incoming = Array.isArray(nextGroup?.items) ? nextGroup.items : []
    const target = groups.value.find(item => item.provider === group.provider)
    if (!target) return
    const seen = new Set((target.items || []).map(item => `${item.provider}:${item.id}:${item.url || ''}`))
    for (const item of incoming) {
      const key = `${item.provider}:${item.id}:${item.url || ''}`
      if (seen.has(key)) continue
      seen.add(key)
      target.items.push(item)
    }
    target.has_more = Boolean(nextGroup?.has_more) && target.items.length < 100
    target.next_page = nextGroup?.next_page
    target.max_items = nextGroup?.max_items
    if (!target.has_more || target.items.length >= 100) {
      providerReachedEnd.value = { ...providerReachedEnd.value, [group.provider]: true }
    }
  } catch (e: any) {
    error.value = e?.response?.data?.detail || e?.message || '加载更多资源失败'
  } finally {
    providerLoading.value = { ...providerLoading.value, [group.provider]: false }
  }
}

async function search() {
  const q = query.value.trim()
  const current = ++seq
  if (!q) {
    groups.value = []
    mediaItems.value = []
    catalogItems.value = []
    error.value = ''
    activeProvider.value = 'all'
    return
  }
  // A resource search is a fresh aggregation across all resource providers.
  // Keep provider tabs as a local view filter only; every explicit search
  // resets to “全部来源” so a previous AVDB/M-Team filter cannot hide JavDB.
  activeProvider.value = 'all'
  loading.value = true
  error.value = ''
  providerLoading.value = {}
  providerReachedEnd.value = {}
  try {
    const code = extractCode(q)
    const payload: Record<string, any> = { keyword: q, q, limit: displayLimitPerProvider, mode: 'deep', page: 1, max_items: 100 }
    if (code) {
      payload.code = code
      payload.number = code
    }
    const [resourceResp, mediaResp, catalogResp] = await Promise.all([
      api.post('/plugins/resources/search', {
        query: payload,
        limit_per_plugin: displayLimitPerProvider,
      }),
      api.get('/media-library/items', { params: { q, limit: 24, offset: 0 } }).catch(() => ({ data: { items: [] } })),
      api.get('/search', { params: { q, scope: 'catalog', limit: 24 } }).catch(() => ({ data: { scopes: [] } })),
    ])
    if (current !== seq) return
    groups.value = resourceResp.data?.groups || []
    mediaItems.value = Array.isArray(mediaResp.data?.items) ? mediaResp.data.items : []
    const catalogScope = Array.isArray(catalogResp.data?.scopes) ? catalogResp.data.scopes.find((scope: any) => scope?.key === 'catalog') : null
    catalogItems.value = Array.isArray(catalogScope?.items) ? catalogScope.items : []
    if (activeProvider.value !== 'all' && !groups.value.some(group => group.provider === activeProvider.value)) {
      activeProvider.value = 'all'
    }
  } catch (e: any) {
    if (current !== seq) return
    error.value = e?.response?.data?.detail || e?.message || '资源搜索失败'
    groups.value = []
    mediaItems.value = []
    catalogItems.value = []
  } finally {
    if (current === seq) loading.value = false
  }
}

function submit() {
  const q = query.value.trim()
  router.replace({ path: '/search/resources', query: q ? { q } : {} })
  void search()
}

watch(() => route.query.q, value => {
  query.value = String(value || '')
  void search()
})

function handleScrollLoadMore() {
  if (activeProvider.value === 'all' || loading.value) return
  const group = groups.value.find(item => item.provider === activeProvider.value)
  if (!group || !hasMoreForGroup(group)) return
  const distance = document.documentElement.scrollHeight - window.scrollY - window.innerHeight
  if (distance < 420) void loadMoreProvider(group)
}

onMounted(() => {
  void search()
  window.addEventListener('scroll', handleScrollLoadMore, { passive: true })
})

onUnmounted(() => {
  window.removeEventListener('scroll', handleScrollLoadMore)
})
</script>

<template>
  <div class="resource-search-page">
    <header class="resource-search-hero">
      <div class="resource-search-hero__main">
        <p class="resource-search-eyebrow">全局资源搜索</p>
        <h1>作品资源结果</h1>
        <p>主程序统一聚合资源类插件，先按作品归并，再在作品下展示可推送资源。</p>
      </div>
      <form class="resource-search-box" @submit.prevent="submit">
        <BaseIcon name="search" class="resource-search-box__icon" />
        <input v-model="query" placeholder="输入番号或标题，例如 TEST-001" />
        <button type="submit">搜索</button>
      </form>
    </header>

    <section class="resource-search-summary">
      <div class="resource-search-stat">
        <span>作品</span>
        <strong>{{ works.length }}</strong>
      </div>
      <div class="resource-search-stat">
        <span>资源</span>
        <strong>{{ total }}</strong>
      </div>
      <div class="resource-search-stat">
        <span>中字</span>
        <strong>{{ subtitleCount }}</strong>
      </div>
      <div class="resource-search-stat">
        <span>PT 资源</span>
        <strong>{{ ptCount }}</strong>
      </div>
      <div class="resource-search-stat">
        <span>直链/磁链</span>
        <strong>{{ directCount }}</strong>
      </div>
    </section>

    <div class="resource-search-toolbar">
      <div class="resource-search-provider-tabs">
        <button
          v-for="provider in providerOptions"
          :key="provider.id"
          type="button"
          class="resource-search-provider"
          :class="{ 'is-active': activeProvider === provider.id }"
          @click="switchProvider(provider.id)"
        >
          <span>{{ provider.label }}</span>
          <em>{{ provider.count }}</em>
        </button>
      </div>
      <div class="resource-search-status">
        <span v-if="loading"><BaseIcon name="loading" class="resource-search-spin" /> 搜索中…</span>
        <span v-else-if="error" class="is-error">{{ error }}</span>
        <span v-else-if="query">{{ codeHint || query }} · 当前 {{ visibleTotal }} 部作品<span v-if="providerSummary"> · {{ providerSummary }}</span></span>
        <span v-else>输入关键词开始搜索资源插件。</span>
      </div>
    </div>

    <div v-if="loading && !total" class="resource-search-skeleton-grid">
      <div v-for="i in 8" :key="i" class="resource-search-card is-skeleton">
        <div class="resource-search-cover"></div>
        <div class="resource-search-main">
          <strong></strong>
          <span></span>
          <small></small>
        </div>
      </div>
    </div>

    <div v-else-if="!loading && query && visibleTotal === 0 && !error" class="resource-search-empty">
      <BaseIcon name="search" />
      <strong>没有资源结果</strong>
      <span>可以尝试输入完整番号，或确认对应资源插件已启用。</span>
    </div>

    <section v-else class="resource-search-group">
      <div class="resource-search-grid">
        <article v-for="work in visibleWorks" :key="work.code" class="resource-search-work-card">
          <div class="resource-search-work-card__media">
            <button type="button" class="resource-search-cover resource-search-work-cover" :class="{ 'has-image': !!work.cover_url }" @click="openWork(work)">
              <img v-if="work.cover_url" :src="work.cover_url" alt="" loading="lazy" />
              <BaseIcon v-else name="download" />
            </button>
            <div class="resource-search-work-info">
              <button type="button" class="resource-search-work-title" @click="openWork(work)">
                <strong>{{ work.code }}</strong>
              </button>
              <div class="resource-search-badges">
                <span v-for="badge in workBadges(work)" :key="badge.label" class="resource-search-badge" :class="toneClass(badge.tone)">{{ badge.label }}</span>
              </div>
              <div class="resource-search-work-actions" :class="{ 'resource-search-work-actions--triple': work.in_library, 'resource-search-work-actions--split': !work.in_library }">
                <button type="button" class="resource-search-inline-action" @click="openJavdb(work)">JavDB</button>
                <button type="button" class="resource-search-inline-action" @click="subscribeWork(work)">{{ work.in_library ? '洗版' : '订阅' }}</button>
                <button v-if="work.in_library" type="button" class="resource-search-inline-action" @click="openLibrary(work)">媒体库</button>
              </div>
            </div>
          </div>

          <div v-if="work.resources.length" class="resource-search-resource-list resource-search-resource-list--mixed">
            <div
              v-for="item in work.resources"
              :key="resourceKey(item)"
              class="resource-search-resource-row"
            >
              <div class="resource-search-resource-row__main">
                <strong>{{ item.title }}</strong>
                <span>{{ item.subtitle || itemSourceText(item) || item.url || '资源插件结果' }}</span>
                <div class="resource-search-badges">
                  <span v-for="badge in badges(item)" :key="badge.label" class="resource-search-badge" :class="toneClass(badge.tone)">{{ badge.label }}</span>
                </div>
              </div>
              <button
                type="button"
                class="resource-search-push-btn"
                :disabled="pushingResources[resourceKey(item)]"
                :title="pushingResources[resourceKey(item)] ? '推送中' : '推送下载'"
                @click="pushResource(item)"
              >
                <BaseIcon v-if="pushingResources[resourceKey(item)]" name="loading" class="resource-search-spin" />
                <BaseIcon v-else name="download" />
                <span>{{ pushingResources[resourceKey(item)] ? '推送中' : '推送' }}</span>
              </button>
            </div>
          </div>
          <div v-else class="resource-search-library-only">
            <BaseIcon name="library" />
            <span>该作品已在媒体库中，点击左侧封面或标题进入媒体库。</span>
          </div>
        </article>
      </div>
    </section>

    <section v-for="group in groups.filter(group => hasMoreForGroup(group))" :key="`more:${group.provider}`" class="resource-search-more-section">
      <button type="button" class="resource-search-more-row" @click="loadMoreProvider(group)">
        <BaseIcon v-if="providerLoading[group.provider]" name="loading" class="resource-search-spin" />
        <BaseIcon v-else name="chevronRight" />
        <span>{{ activeProvider === 'all' ? `更多 ${group.provider_label || group.provider} 结果` : ((group.items?.length || 0) >= 100 ? '已加载 100 条' : '加载更多') }}</span>
        <em v-if="activeProvider !== 'all'">{{ group.items.length }} / 100</em>
      </button>
    </section>

  </div>
</template>

<style scoped>
.resource-search-page { display: grid; gap: 1rem; min-width: 0; }
.resource-search-hero { display: grid; grid-template-columns: minmax(0, 1fr) minmax(22rem, 38rem); gap: 1rem; align-items: end; padding: 1rem; border: 1px solid var(--color-glass-border); background: linear-gradient(135deg, rgba(255,255,255,.045), rgba(255,255,255,.018)); box-shadow: 0 1px 0 rgba(255,255,255,.02) inset, 0 14px 32px rgba(0,0,0,.18); }
.resource-search-eyebrow { margin: 0 0 .35rem; color: var(--color-text-muted); font-size: .74rem; letter-spacing: .08em; text-transform: uppercase; font-weight: 750; }
.resource-search-hero h1 { margin: 0; color: #fff; font-size: clamp(1.45rem, 2.2vw, 2rem); line-height: 1.15; }
.resource-search-hero p { max-width: 46rem; margin: .45rem 0 0; color: var(--color-text-secondary); font-size: .9rem; line-height: 1.65; }
.resource-search-box { height: 44px; display: grid; grid-template-columns: auto minmax(0, 1fr) auto; align-items: center; gap: .65rem; padding: 0 .45rem 0 .85rem; border: 1px solid var(--color-border-default); background: var(--color-bg-surface); }
.resource-search-box__icon { width: 1rem; height: 1rem; color: var(--color-text-muted); }
.resource-search-box input { min-width: 0; height: 100%; border: 0; outline: 0; background: transparent; color: #fff; font: inherit; }
.resource-search-box button { height: 31px; padding: 0 1rem; border-radius: var(--radius-button); background: var(--color-brand); color: #fff; font-size: .8rem; font-weight: 750; }
.resource-search-summary { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: .65rem; }
.resource-search-stat { min-height: 64px; display: grid; align-content: center; gap: .25rem; padding: .65rem .8rem; border: 1px solid var(--color-glass-border); background: var(--color-bg-surface); }
.resource-search-stat span { color: var(--color-text-muted); font-size: .74rem; }
.resource-search-stat strong { color: #fff; font-size: 1.25rem; line-height: 1; }
.resource-search-toolbar { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: .75rem; align-items: center; }
.resource-search-provider-tabs { min-width: 0; display: flex; flex-wrap: wrap; gap: .45rem; }
.resource-search-provider { min-height: 30px; display: inline-flex; align-items: center; gap: .4rem; padding: .25rem .65rem; border-radius: var(--radius-pill); border: 1px solid rgba(255,255,255,.08); background: rgba(255,255,255,.04); color: var(--color-text-secondary); font-size: .76rem; font-weight: 750; }
.resource-search-provider em { color: var(--color-text-muted); font-style: normal; }
.resource-search-provider.is-active { border-color: rgba(0,117,255,.42); background: rgba(0,117,255,.16); color: #fff; }
.resource-search-status { min-height: 32px; display: flex; align-items: center; gap: .5rem; padding: 0 .8rem; border: 1px solid rgba(255,255,255,.065); background: rgba(255,255,255,.026); color: var(--color-text-secondary); font-size: .78rem; font-weight: 650; white-space: nowrap; }
.resource-search-status span { display: inline-flex; align-items: center; gap: .45rem; }
.resource-search-status .is-error { color: #fca5a5; }
.resource-search-spin { width: 1rem; height: 1rem; }
.resource-search-empty { min-height: 12rem; display: grid; place-items: center; align-content: center; gap: .5rem; padding: 2rem; text-align: center; border: 1px solid var(--color-border-default); background: var(--color-bg-surface); color: var(--color-text-muted); }
.resource-search-empty svg, .resource-search-empty :deep(svg) { width: 1.6rem; height: 1.6rem; }
.resource-search-empty strong { color: #fff; }
.resource-search-group { display: grid; gap: .7rem; }
.resource-search-group + .resource-search-group { padding-top: 1rem; border-top: 1px solid rgba(255,255,255,.085); }
.resource-search-group__head { display: flex; align-items: flex-end; justify-content: space-between; gap: 1rem; padding: 0 .1rem; }
.resource-search-group__head div { display: grid; gap: .12rem; }
.resource-search-group__head strong { color: #fff; font-size: 1rem; }
.resource-search-group__head span, .resource-search-group__head em { color: var(--color-text-muted); font-size: .74rem; font-style: normal; font-weight: 750; }
.resource-search-grid { display: grid; grid-template-columns: 1fr; gap: .8rem; }
.resource-search-work-card { width: 100%; min-width: 0; display: grid; grid-template-columns: minmax(24rem, 36rem) minmax(0, 1fr); gap: .9rem; padding: .75rem; border: 1px solid var(--color-glass-border); background: rgba(255,255,255,.018); box-shadow: 0 1px 0 rgba(255,255,255,.02) inset, 0 8px 18px rgba(0,0,0,.12); }
.resource-search-work-card__media { min-width: 0; display: grid; gap: .7rem; align-content: start; }
.resource-search-work-cover { width: 100%; border: 0; padding: 0; color: var(--color-text-muted); }
.resource-search-work-cover img { width: 100%; height: 100%; object-fit: cover; }
.resource-search-work-title { min-width: 0; display: grid; gap: .2rem; text-align: left; color: inherit; }
.resource-search-work-title strong { color: #fff; font-size: 1rem; line-height: 1.2; }
.resource-search-work-title span { color: rgba(255,255,255,.78); font-size: .82rem; line-height: 1.38; display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; }
.resource-search-work-info { min-width: 0; display: flex; flex-direction: column; gap: .5rem; }
.resource-search-work-source { color: var(--color-text-muted); font-size: .74rem; line-height: 1.45; }
.resource-search-work-actions { display: grid; grid-template-columns: 1fr; align-items: center; gap: .45rem; margin-top: .15rem; }
.resource-search-work-actions--split { grid-template-columns: repeat(2, minmax(0, 1fr)); }
.resource-search-work-actions--triple { grid-template-columns: repeat(3, minmax(0, 1fr)); }
.resource-search-inline-action { height: 30px; padding: 0 .75rem; border-radius: var(--radius-button); border: 1px solid rgba(255,255,255,.08); background: rgba(255,255,255,.04); color: var(--color-text-secondary); font-size: .74rem; font-weight: 750; }
.resource-search-inline-action:hover { border-color: rgba(0,117,255,.28); background: rgba(0,117,255,.11); color: #fff; }
.resource-search-resource-list { min-width: 0; display: grid; gap: .6rem; align-content: start; }
.resource-search-resource-list--mixed { grid-template-columns: repeat(4, minmax(0, 1fr)); gap: .5rem; }
.resource-search-library-only { min-height: 7rem; display: flex; align-items: center; justify-content: center; gap: .55rem; padding: 1rem; border: 1px solid rgba(34,197,94,.16); border-radius: .85rem; background: rgba(34,197,94,.06); color: var(--color-text-secondary); font-size: .82rem; font-weight: 700; }
.resource-search-library-only svg, .resource-search-library-only :deep(svg) { width: 1.1rem; height: 1.1rem; color: #86efac; }
.resource-search-provider-block { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: .5rem; }
.resource-search-provider-block + .resource-search-provider-block { padding-top: .55rem; border-top: 1px solid rgba(255,255,255,.07); }
.resource-search-provider-block__head { grid-column: 1 / -1; display: flex; align-items: center; justify-content: space-between; gap: .75rem; color: var(--color-text-muted); font-size: .72rem; }
.resource-search-provider-block__head strong { color: rgba(255,255,255,.78); font-size: .78rem; }
.resource-search-resource-row { position: relative; min-width: 0; min-height: 6.4rem; display: grid; align-items: stretch; gap: .55rem; padding: .65rem .65rem 2.75rem .65rem; border: 1px solid rgba(255,255,255,.055); border-radius: .8rem; background: rgba(255,255,255,.035); }
.resource-search-resource-row__main { min-width: 0; display: grid; gap: .28rem; align-content: start; }
.resource-search-resource-row__main strong { color: rgba(255,255,255,.92); font-size: .78rem; line-height: 1.32; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.resource-search-resource-row__main span { color: var(--color-text-muted); font-size: .72rem; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.resource-search-resource-row .resource-search-badges { grid-column: auto; min-height: 0; }
.resource-search-push-btn { position: absolute; right: .55rem; bottom: .55rem; min-width: 3.45rem; height: 1.85rem; display: inline-flex; align-items: center; justify-content: center; gap: .3rem; padding: 0 .55rem; border-radius: .55rem; border: 1px solid rgba(0,117,255,.28); background: rgba(0,117,255,.16); color: #fff; font-size: .72rem; font-weight: 800; white-space: nowrap; overflow: hidden; }
.resource-search-push-btn svg, .resource-search-push-btn :deep(svg) { width: .88rem; height: .88rem; flex: 0 0 auto; }
.resource-search-push-btn span { display: inline; }
.resource-search-push-btn:disabled { opacity: .6; cursor: wait; }

.resource-search-more-section { display: grid; }
.resource-search-more-row { min-height: 42px; display: inline-flex; align-items: center; justify-content: center; gap: .45rem; border: 1px solid rgba(255,255,255,.08); background: rgba(255,255,255,.035); color: var(--color-text-secondary); font-size: .8rem; font-weight: 750; }
.resource-search-more-row:hover { border-color: rgba(0,117,255,.24); background: rgba(0,117,255,.1); color: #fff; }
.resource-search-more-row svg, .resource-search-more-row :deep(svg) { width: 1rem; height: 1rem; }
.resource-search-more-row em { color: var(--color-text-muted); font-style: normal; font-weight: 650; }
.resource-search-card { position: relative; min-width: 0; display: grid; grid-template-columns: 9rem minmax(0, 1fr); gap: .8rem; align-items: stretch; padding: .65rem 2.35rem .65rem .65rem; border: 1px solid var(--color-glass-border); background: var(--color-bg-surface); color: inherit; text-align: left; box-shadow: 0 1px 0 rgba(255,255,255,.02) inset, 0 8px 18px rgba(0,0,0,.14); transition: transform var(--transition-fast), border-color var(--transition-fast), background var(--transition-fast); }
.resource-search-card:hover { transform: translateY(-1px); border-color: rgba(0,117,255,.28); background: var(--color-bg-elevated); }
.resource-search-cover { aspect-ratio: 2184 / 1468; display: flex; align-items: center; justify-content: center; overflow: hidden; background: rgba(255,255,255,.05); color: var(--color-text-muted); }
.resource-search-cover img { width: 100%; height: 100%; object-fit: cover; }
.resource-search-cover svg, .resource-search-cover :deep(svg) { width: 1.25rem; height: 1.25rem; }
.resource-search-main { min-width: 0; display: grid; align-content: start; gap: .24rem; }
.resource-search-main strong { color: #fff; font-size: .9rem; line-height: 1.35; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.resource-search-main span { color: var(--color-text-secondary); font-size: .76rem; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.resource-search-main small { color: var(--color-text-muted); font-size: .7rem; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.resource-search-badges { grid-column: 2 / 3; display: flex; align-items: center; flex-wrap: wrap; gap: .3rem; min-height: 22px; }
.resource-search-badge { padding: .18rem .48rem; border-radius: 999px; background: rgba(255,255,255,.06); color: rgba(255,255,255,.65); font-size: .67rem; font-weight: 700; white-space: nowrap; }
.resource-search-badge--primary { background: rgba(0,117,255,.18); color: #bfdbfe; }
.resource-search-badge--success { background: rgba(34,197,94,.15); color: #86efac; }
.resource-search-badge--warning { background: rgba(245,158,11,.16); color: #fcd34d; }
.resource-search-badge--danger { background: rgba(239,68,68,.15); color: #fca5a5; }
.resource-search-badge--info { background: rgba(148,163,184,.12); color: #cbd5e1; }
.resource-search-card__arrow { position: absolute; right: .75rem; top: 50%; width: 1rem; height: 1rem; color: var(--color-text-muted); transform: translateY(-50%); }
.resource-search-skeleton-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(31rem, 1fr)); gap: .65rem; }
.resource-search-card.is-skeleton { pointer-events: none; }
.resource-search-card.is-skeleton .resource-search-cover, .resource-search-card.is-skeleton strong, .resource-search-card.is-skeleton span, .resource-search-card.is-skeleton small { position: relative; overflow: hidden; color: transparent; background: rgba(255,255,255,.055); }
.resource-search-card.is-skeleton strong { width: 88%; height: 2.4rem; }
.resource-search-card.is-skeleton span { width: 62%; height: .85rem; }
.resource-search-card.is-skeleton small { width: 44%; height: .75rem; }
.resource-search-card.is-skeleton .resource-search-cover::after, .resource-search-card.is-skeleton strong::after, .resource-search-card.is-skeleton span::after, .resource-search-card.is-skeleton small::after { content: ''; position: absolute; inset: 0; transform: translateX(-100%); background: linear-gradient(90deg, transparent, rgba(255,255,255,.08), transparent); animation: resource-search-shimmer 1.2s infinite; }
@keyframes resource-search-shimmer { to { transform: translateX(100%); } }
@media (max-width: 1280px) { .resource-search-work-card { grid-template-columns: minmax(18rem, 26rem) minmax(0, 1fr); } }
@media (max-width: 1100px) { .resource-search-summary { grid-template-columns: repeat(3, minmax(0, 1fr)); } .resource-search-toolbar, .resource-search-hero { grid-template-columns: 1fr; } .resource-search-status { justify-content: flex-start; white-space: normal; } }
@media (max-width: 980px) { .resource-search-work-card { grid-template-columns: 1fr; } .resource-search-provider-block { grid-template-columns: repeat(3, minmax(0, 1fr)); } .resource-search-resource-list--mixed { grid-template-columns: 1fr; } }
@media (max-width: 760px) { .resource-search-summary { grid-template-columns: repeat(2, minmax(0, 1fr)); } .resource-search-skeleton-grid { grid-template-columns: 1fr; } .resource-search-card { grid-template-columns: 7rem minmax(0,1fr); } .resource-search-provider-block { grid-template-columns: repeat(2, minmax(0, 1fr)); } .resource-search-resource-list--mixed { grid-template-columns: 1fr; } .resource-search-resource-row { grid-template-columns: 1fr; } }
@media (max-width: 560px) { .resource-search-hero { padding: .8rem; } .resource-search-box { grid-template-columns: auto minmax(0, 1fr); height: auto; min-height: 44px; padding: .38rem .45rem .38rem .85rem; } .resource-search-box button { grid-column: 1 / -1; width: 100%; } .resource-search-work-card { padding: .6rem; } .resource-search-work-card__media { grid-template-columns: 1fr; } .resource-search-work-actions, .resource-search-work-actions--split, .resource-search-work-actions--triple { grid-template-columns: 1fr; } .resource-search-card { grid-template-columns: 1fr; padding-right: .65rem; } .resource-search-provider-block, .resource-search-resource-list--mixed { grid-template-columns: 1fr; } .resource-search-badges { grid-column: 1 / -1; } .resource-search-card__arrow { display: none; } }
</style>
