Chunk ID: b5c317
Wall time: 0.0001 seconds
Process exited with code 0
Original token count: 5950
Output:
<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '../api'
import BaseIcon from '../components/noor/BaseIcon.vue'
import { createDownloaderDialogContext } from '../composables/useDownloaderDialog'
import { useToast } from '../composables/useToast'

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

type ResourceGroup = {
  provider: string
  provider_label: string
  total: number
  items: ResourceItem[]
  has_more?: boolean
  next_page?: number
  max_items?: number
}

const route = useRoute()
const router = useRouter()
const toast = useToast()
const downloads = createDownloaderDialogContext('resource-search')
const query = ref(String(route.query.q || ''))
const loading = ref(false)
const error = ref('')
const groups = ref<ResourceGroup[]>([])
const activeProvider = ref('all')
const displayLimitPerProvider = 24
const providerLoading = ref<Record<string, boolean>>({})
const providerReachedEnd = ref<Record<string, boolean>>({})
let seq = 0

const total = computed(() => groups.value.reduce((sum, group) => sum + (group.items?.length || 0), 0))
const visibleGroups = computed(() => activeProvider.value === 'all'
  ? groups.value.map(group => ({ ...group, items: (group.items || []).slice(0, displayLimitPerProvider) }))
  : groups.value.filter(group => group.provider === activeProvider.value))
const visibleTotal = computed(() => visibleGroups.value.reduce((sum, group) => sum + (group.items?.length || 0), 0))
const providerOptions = computed(() => [
  { id: 'all', label: '全部来源', count: total.value },
  ...groups.value.map(group => ({ id: group.provider, label: group.provider_label || group.provider, count: group.items?.length || 0 })),
])
const subtitleCount = computed(() => groups.value.flatMap(group => group.items || []).filter(item => item.features?.has_subtitle).length)
const ptCount = computed(() => groups.value.flatMap(group => group.items || []).filter(item => item.features?.is_private_tracker || item.requirements?.accepts_private_tracker).length)
const directCount = computed(() => groups.value.flatMap(group => group.items || []).filter(item => item.url).length)
const codeHint = computed(() => extractCode(query.value))

function normalizeGroup(raw: any): ResourceGroup {
  const provider = String(raw?.provider || '')
  const providerLabel = String(raw?.provider_label || provider)
  return {
    ...raw,
    provider,
    provider_label: providerLabel,
    items: (Array.isArray(raw?.items) ? raw.items : []).map((item: any) => ({
      ...item,
      provider: String(item?.provider || provider),
      provider_label: String(item?.provider_label || providerLabel),
    })),
  }
}

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

function toneClass(tone: string) {
  return `resource-search-badge--${tone || 'info'}`
}

function targetRoute(item: ResourceItem) {
  const key = item.query_key || extractCode(`${item.title} ${item.subtitle || ''}`)
  if ((item.provider === 'javdb' || item.provider === 'avdb') && key) return `/plugins/javdb?code=${encodeURIComponent(key)}`
  if (item.provider) return `/plugins/${item.provider}`
  return '/plugins'
}

function itemSourceText(item: ResourceItem) {
  const pieces = []
  if (item.file_count) pieces.push(`${item.file_count} 文件`)
  if (item.compatible_downloaders?.length) pieces.push(`可用下载器 ${item.compatible_downloaders.length}`)
  if (item.query_key) pieces.push(item.query_key)
  return pieces.join(' · ')
}

async function openItem(item: ResourceItem) {
  await router.push(targetRoute(item))
}

async function downloadItem(item: ResourceItem) {
  try {
    const response = await api.post('/plugins/resources/resolve-download', {
      provider_id: item.provider,
      item,
    })
    const resolved = response.data || {}
    const resolvedItem = resolved.item || item
    const resolvedUrl = resolved.url || resolvedItem.url
    const downloaderIds = Array.isArray(resolvedItem.compatible_downloaders)
      ? resolvedItem.compatible_downloaders.filter(Boolean)
      : []
    const downloaderId = resolvedItem.preferred_downloader || downloaderIds[0]
    if (!downloaderId) throw new Error('没有兼容的下载器')
    if (!resolvedUrl) throw new Error('资源链接解析失败')
    await downloads.open({
      downloaderId,
      downloaderIds,
      url: resolvedUrl,
      title: item.title,
      rename: item.title,
      itemTitle: item.title,
    })
  } catch (error: any) {
    toast.error(error?.response?.data?.detail || error?.message || '推送失败')
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
    })
    const nextGroup = normalizeGroup((resp.data?.groups || [])[0] || {})
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
    const resp = await api.post('/plugins/resources/search', {
      query: payload,
      limit_per_plugin: displayLimitPerProvider,
    })
    if (current !== seq) return
    groups.value = (resp.data?.groups || []).map(normalizeGroup)
    if (activeProvider.value !== 'all' && !groups.value.some(group => group.provider === activeProvider.value)) {
      activeProvider.value = 'all'
    }
  } catch (e: any) {
    if (current !== seq) return
    error.value = e?.response?.data?.detail || e?.message || '资源搜索失败'
    groups.value = []
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
        <h1>资源结果</h1>
        <p>主程序统一聚合资源类插件，结果按来源拆分，点击后进入对应作品或插件页面。</p>
      </div>
      <form class="resource-search-box" @submit.prevent="submit">
        <BaseIcon name="search" class="resource-search-box__icon" />
        <input v-model="query" placeholder="输入番号或标题，例如 DASS-927" />
        <button type="submit">搜索</button>
      </form>
    </header>

    <section class="resource-search-summary">
      <div class="resource-search-stat">
        <span>资源</span>
        <strong>{{ total }}</strong>
      </div>
      <div class="resource-search-stat">
        <span>来源</span>
        <strong>{{ groups.length }}</strong>
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
        <span v-else-if="query">{{ codeHint || query }} · 当前 {{ visibleTotal }} 条</span>
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

    <section v-for="group in visibleGroups" :key="group.provider" class="resource-search-group">
      <div class="resource-search-group__head">
        <div>
          <strong>{{ group.provider_label || group.provider }}</strong>
          <span>{{ group.provider }}</span>
        </div>
        <em>{{ group.items.length }} 条</em>
      </div>
      <div class="resource-search-grid">
        <article v-for="item in group.items" :key="`${group.provider}:${item.id}`" class="resource-search-card" tabindex="0" @click="openItem(item)" @keydown.enter="openItem(item)">
          <div class="resource-search-cover" :class="{ 'has-image': !!item.cover_url }">
            <img v-if="item.cover_url" :src="item.cover_url" alt="" loading="lazy" />
            <BaseIcon v-else name="download" />
          </div>
          <div class="resource-search-main">
            <strong>{{ item.title }}</strong>
            <span v-if="item.subtitle">{{ item.subtitle }}</span>
            <small>{{ itemSourceText(item) || item.source_url || item.url || '资源插件结果' }}</small>
          </div>
          <div class="resource-search-badges">
            <span v-for="badge in badges(item)" :key="badge.label" class="resource-search-badge" :class="toneClass(badge.tone)">{{ badge.label }}</span>
          </div>
          <div class="resource-search-card__actions">
            <button v-if="item.url || item.source_url" type="button" class="resource-search-download" @click.stop="downloadItem(item)">
              <BaseIcon name="download" />
              <span>推送下载</span>
            </button>
            <button type="button" class="resource-search-open" @click.stop="openItem(item)" title="打开来源">
              <BaseIcon name="chevronRight" />
            </button>
          </div>
        </article>
      </div>
      <button v-if="hasMoreForGroup(group)" type="button" class="resource-search-more-row" @click="loadMoreProvider(group)">
        <BaseIcon v-if="providerLoading[group.provider]" name="loading" class="resource-search-spin" />
        <BaseIcon v-else name="chevronRight" />
        <span>{{ activeProvider === 'all' ? '更多结果' : ((group.items?.length || 0) >= 100 ? '已加载 100 条' : '加载更多') }}</span>
        <em v-if="activeProvider !== 'all'">{{ group.items.length }} / 100</em>
      </button>
    </section>
  </div>
</template>

<style scoped>
.resource-search-page { display: grid; gap: 1rem; }
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
.resource-search-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(31rem, 1fr)); gap: .65rem; }
.resource-search-more-row { min-height: 42px; display: inline-flex; align-items: center; justify-content: center; gap: .45rem; border: 1px solid rgba(255,255,255,.08); background: rgba(255,255,255,.035); color: var(--color-text-secondary); font-size: .8rem; font-weight: 750; }
.resource-search-more-row:hover { border-color: rgba(0,117,255,.24); background: rgba(0,117,255,.1); color: #fff; }
.resource-search-more-row svg, .resource-search-more-row :deep(svg) { width: 1rem; height: 1rem; }
.resource-search-more-row em { color: var(--color-text-muted); font-style: normal; font-weight: 650; }
.resource-search-card { position: relative; min-width: 0; display: grid; grid-template-columns: 9rem minmax(0, 1fr); gap: .8rem; align-items: stretch; padding: .65rem; border: 1px solid var(--color-glass-border); background: var(--color-bg-surface); color: inherit; text-align: left; box-shadow: 0 1px 0 rgba(255,255,255,.02) inset, 0 8px 18px rgba(0,0,0,.14); transition: transform var(--transition-fast), border-color var(--transition-fast), background var(--transition-fast); cursor: pointer; }
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
.resource-search-card__actions { grid-column: 2 / 3; display: flex; align-items: center; justify-content: flex-end; gap: .4rem; }
.resource-search-download,.resource-search-open { min-height: 30px; display: inline-flex; align-items: center; justify-content: center; gap: .35rem; border: 1px solid rgba(0,117,255,.25); border-radius: var(--radius-button); background: rgba(0,117,255,.12); color: #dbeafe; font-size: .72rem; font-weight: 750; }
.resource-search-download { padding: 0 .7rem; }
.resource-search-open { width: 30px; }
.resource-search-download:hover,.resource-search-open:hover { border-color: rgba(0,117,255,.5); background: rgba(0,117,255,.22); color: #fff; }
.resource-search-download svg,.resource-search-open svg,.resource-search-download :deep(svg),.resource-search-open :deep(svg) { width: .9rem; height: .9rem; }
.resource-search-skeleton-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(31rem, 1fr)); gap: .65rem; }
.resource-search-card.is-skeleton { pointer-events: none; }
.resource-search-card.is-skeleton .resource-search-cover, .resource-search-card.is-skeleton strong, .resource-search-card.is-skeleton span, .resource-search-card.is-skeleton small { position: relative; overflow: hidden; color: transparent; background: rgba(255,255,255,.055); }
.resource-search-card.is-skeleton strong { width: 88%; height: 2.4rem; }
.resource-search-card.is-skeleton span { width: 62%; height: .85rem; }
.resource-search-card.is-skeleton small { width: 44%; height: .75rem; }
.resource-search-card.is-skeleton .resource-search-cover::after, .resource-search-card.is-skeleton strong::after, .resource-search-card.is-skeleton span::after, .resource-search-card.is-skeleton small::after { content: ''; position: absolute; inset: 0; transform: translateX(-100%); background: linear-gradient(90deg, transparent, rgba(255,255,255,.08), transparent); animation: resource-search-shimmer 1.2s infinite; }
@keyframes resource-search-shimmer { to { transform: translateX(100%); } }
@media (max-width: 1100px) { .resource-search-summary { grid-template-columns: repeat(3, minmax(0, 1fr)); } .resource-search-toolbar, .resource-search-hero { grid-template-columns: 1fr; } .resource-search-status { justify-content: flex-start; white-space: normal; } }
@media (max-width: 760px) { .resource-search-summary { grid-template-columns: repeat(2, minmax(0, 1fr)); } .resource-search-grid, .resource-search-skeleton-grid { grid-template-columns: 1fr; } .resource-search-card { grid-template-columns: 7rem minmax(0,1fr); } }
@media (max-width: 560px) { .resource-search-hero { padding: .8rem; } .resource-search-card { grid-template-columns: 1fr; } .resource-search-badges,.resource-search-card__actions { grid-column: 1 / -1; } }
</style>
