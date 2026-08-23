<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import api from '../../api'
import BaseIcon from './BaseIcon.vue'

type SearchBadge = { label: string; tone?: string }
type SearchAction = { type: string; route?: string; payload?: Record<string, any> }
type SearchItem = {
  id: string
  source: string
  source_label: string
  type: string
  title: string
  subtitle?: string
  description?: string
  image?: string | null
  icon?: string
  badges?: SearchBadge[]
  action?: SearchAction
}
type SearchScope = { key: string; label: string; count: number; error?: string | null; items: SearchItem[] }

const props = defineProps<{ open: boolean }>()
const emit = defineEmits<{ close: [] }>()
const router = useRouter()
const query = ref('')
const loading = ref(false)
const error = ref('')
const scopes = ref<SearchScope[]>([])
const inputEl = ref<HTMLInputElement | null>(null)
const selectedFlatIndex = ref(0)
let timer: number | null = null
let seq = 0

const flatItems = computed(() => scopes.value.flatMap(scope => scope.items.map(item => ({ scope, item }))))
const hasSearched = computed(() => query.value.trim().length > 0)


function close() {
  emit('close')
}

async function runSearch() {
  const q = query.value.trim()
  const current = ++seq
  if (!q) {
    scopes.value = []
    error.value = ''
    loading.value = false
    return
  }
  loading.value = true
  error.value = ''
  try {
    const resp = await api.get('/search', { params: { q, limit: 8 } })
    if (current !== seq) return
    scopes.value = resp.data?.scopes || []
    selectedFlatIndex.value = 0
  } catch (e: any) {
    if (current !== seq) return
    error.value = e?.response?.data?.detail || e?.message || '搜索失败'
    scopes.value = []
  } finally {
    if (current === seq) loading.value = false
  }
}

watch(query, () => {
  if (timer != null) window.clearTimeout(timer)
  timer = window.setTimeout(runSearch, 220)
})

watch(() => props.open, async value => {
  if (value) {
    await nextTick()
    inputEl.value?.focus()
    inputEl.value?.select()
  } else {
    if (timer != null) window.clearTimeout(timer)
    timer = null
  }
})

function iconFor(item: SearchItem) {
  if (item.icon) return item.icon
  if (item.type === 'media') return 'library'
  if (item.type === 'hardlink') return 'hardlink'
  if (item.type === 'task') return 'jobs'
  return 'search'
}

function toneClass(tone?: string) {
  return `global-search-badge--${tone || 'info'}`
}

function resultTypeLabel(type: string) {
  if (type === 'media') return '作品'
  if (type === 'hardlink') return '硬链接'
  if (type === 'task') return '任务'
  if (type === 'resource') return '资源'
  if (type === 'subtitle') return '字幕'
  if (type === 'person') return '演员'
  return type
}

function moreRoute(scope: SearchScope) {
  const q = encodeURIComponent(query.value.trim())
  if (!q) return ''
  if (scope.key === 'media') return `/library?q=${q}`
  if (scope.key === 'resources') return `/search/resources?q=${q}`
  if (scope.key === 'jobs') return `/jobs?q=${q}`
  return ''
}

async function openMore(scope: SearchScope) {
  const route = moreRoute(scope)
  if (!route) return
  await router.push(route)
  close()
}

async function openItem(item: SearchItem) {
  const route = item.action?.route
  if (route) await router.push(route)
  close()
}

function move(delta: number) {
  const total = flatItems.value.length
  if (!total) return
  selectedFlatIndex.value = (selectedFlatIndex.value + delta + total) % total
}

function openSelected() {
  const entry = flatItems.value[selectedFlatIndex.value]
  if (entry) void openItem(entry.item)
}

function onKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape') {
    event.preventDefault()
    close()
    return
  }
  if (event.key === 'ArrowDown') {
    event.preventDefault()
    move(1)
    return
  }
  if (event.key === 'ArrowUp') {
    event.preventDefault()
    move(-1)
    return
  }
  if (event.key === 'Enter') {
    event.preventDefault()
    openSelected()
  }
}

function isSelected(scopeIndex: number, itemIndex: number) {
  let index = 0
  for (let s = 0; s < scopes.value.length; s += 1) {
    const count = scopes.value[s].items.length
    if (s === scopeIndex) return selectedFlatIndex.value === index + itemIndex
    index += count
  }
  return false
}

function visibleScopeItems(scope: SearchScope) {
  return (scope.items || []).slice(0, 3)
}
</script>

<template>
  <Teleport to="body">
    <div v-if="open" class="global-search-overlay" @click.self="close">
      <div class="global-search" @keydown="onKeydown">
        <div class="global-search-input-row">
          <BaseIcon name="search" class="global-search-input-icon" />
          <input
            ref="inputEl"
            v-model="query"
            class="global-search-input"
            placeholder="搜索媒体、资源、任务..."
            autocomplete="off"
          />
          <div class="global-search-shortcut">ESC</div>
        </div>

        <div class="global-search-body">
          <div v-if="!hasSearched" class="global-search-empty">
            <BaseIcon name="command" class="global-search-empty-icon" />
            <div class="global-search-empty-title">输入关键词开始搜索</div>
            <div class="global-search-empty-desc">支持番号、标题、资源插件、任务名称与错误信息。</div>
          </div>
          <div v-else-if="loading" class="global-search-empty">
            <BaseIcon name="loading" class="global-search-empty-icon" />
            <div class="global-search-empty-title">搜索中...</div>
          </div>
          <div v-else-if="error" class="global-search-empty global-search-empty--error">
            <BaseIcon name="info" class="global-search-empty-icon" />
            <div class="global-search-empty-title">{{ error }}</div>
          </div>
          <div v-else-if="flatItems.length === 0" class="global-search-empty">
            <BaseIcon name="search" class="global-search-empty-icon" />
            <div class="global-search-empty-title">没有结果</div>
          </div>

          <div v-else class="global-search-scopes">
            <section v-for="(scope, scopeIndex) in scopes" :key="scope.key" v-show="scope.items.length || scope.error" class="global-search-scope">
              <div class="global-search-scope-head">
                <div class="global-search-scope-title">
                  <span>{{ scope.label }}</span>
                  <span v-if="scope.count" class="global-search-scope-count">{{ scope.count }}</span>
                </div>
                <span v-if="scope.error" class="global-search-scope-error">{{ scope.error }}</span>
              </div>
              <button
                v-for="(item, itemIndex) in visibleScopeItems(scope)"
                :key="`${scope.key}:${item.id}`"
                type="button"
                class="global-search-result"
                :class="{ 'is-selected': isSelected(scopeIndex, itemIndex) }"
                @mouseenter="selectedFlatIndex = flatItems.findIndex(entry => entry.item === item)"
                @click="openItem(item)"
              >
                <div class="global-search-thumb" :class="{ 'global-search-thumb--image': !!item.image }">
                  <img v-if="item.image" :src="item.image" alt="" loading="lazy" />
                  <BaseIcon v-else :name="iconFor(item)" class="global-search-thumb-icon" />
                </div>
                <div class="global-search-result-main">
                  <div class="global-search-title-row">
                    <strong class="global-search-title">{{ item.title }}</strong>
                    <span class="global-search-type">{{ resultTypeLabel(item.type) }}</span>
                  </div>
                  <div v-if="item.subtitle" class="global-search-subtitle">{{ item.subtitle }}</div>
                  <div v-if="item.description" class="global-search-desc">{{ item.description }}</div>
                </div>
                <div class="global-search-badges">
                  <span v-for="badge in item.badges || []" :key="badge.label" class="global-search-badge" :class="toneClass(badge.tone)">
                    {{ badge.label }}
                  </span>
                </div>
              </button>
              <button
                v-if="moreRoute(scope) && scope.items.length"
                type="button"
                class="global-search-result global-search-result--more"
                @click.stop="openMore(scope)"
              >
                <div class="global-search-thumb global-search-thumb--more">
                  <BaseIcon name="chevronRight" class="global-search-thumb-icon" />
                </div>
                <div class="global-search-result-main">
                  <strong class="global-search-title">获取更多结果</strong>
                  <div class="global-search-subtitle">进入{{ scope.label }}结果页查看完整内容</div>
                </div>
              </button>
            </section>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.global-search-overlay {
  position: fixed;
  inset: 0;
  z-index: 1000;
  display: flex;
  justify-content: center;
  align-items: flex-start;
  padding: min(10vh, 5rem) 1rem 1rem;
  background: rgba(0, 0, 0, 0.58);
  backdrop-filter: blur(10px);
}
.global-search {
  width: min(58rem, 100%);
  max-height: min(78vh, 48rem);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border: 1px solid rgba(255,255,255,.09);
  border-radius: 1.25rem;
  background: rgba(12, 17, 34, 0.96);
  box-shadow: 0 24px 80px rgba(0,0,0,.45);
}
.global-search-input-row {
  display: flex;
  align-items: center;
  gap: .75rem;
  padding: .95rem 1rem;
  border-bottom: 1px solid rgba(255,255,255,.07);
}
.global-search-input-icon { width: 1.15rem; height: 1.15rem; color: rgba(255,255,255,.42); }
.global-search-input {
  flex: 1;
  min-width: 0;
  border: 0;
  outline: 0;
  background: transparent;
  color: #fff;
  font-size: .98rem;
  font-family: var(--font-display);
}
.global-search-input::placeholder { color: rgba(255,255,255,.34); }
.global-search-shortcut {
  border: 1px solid rgba(255,255,255,.08);
  border-radius: .5rem;
  padding: .18rem .42rem;
  color: rgba(255,255,255,.38);
  font-size: .66rem;
}
.global-search-body { overflow: auto; padding: .7rem; }
.global-search-empty { min-height: 18rem; display: grid; place-items: center; align-content: center; gap: .5rem; color: rgba(255,255,255,.48); text-align: center; }
.global-search-empty-icon { width: 2rem; height: 2rem; color: rgba(255,255,255,.24); }
.global-search-empty-title { color: rgba(255,255,255,.74); font-weight: 700; }
.global-search-empty-desc { font-size: .78rem; }
.global-search-empty--error .global-search-empty-title { color: #fca5a5; }
.global-search-scopes { display: grid; gap: .8rem; }
.global-search-scope { display: grid; gap: .35rem; }
.global-search-scope-head { display: flex; align-items: center; justify-content: space-between; gap: .5rem; padding: .2rem .35rem; color: rgba(255,255,255,.42); font-size: .72rem; font-weight: 700; }
.global-search-scope-title { display: inline-flex; align-items: center; gap: .5rem; min-width: 0; }
.global-search-scope-count { color: rgba(255,255,255,.28); }
.global-search-scope-error { color: #fca5a5; font-weight: 500; }
.global-search-result {
  width: 100%;
  display: grid;
  grid-template-columns: 4.6rem minmax(0, 1fr) auto;
  gap: .75rem;
  align-items: center;
  padding: .62rem;
  border: 1px solid transparent;
  border-radius: .9rem;
  background: transparent;
  text-align: left;
  color: inherit;
  transition: background var(--transition-fast), border-color var(--transition-fast);
}
.global-search-result:hover,
.global-search-result.is-selected { background: rgba(255,255,255,.055); border-color: rgba(255,255,255,.075); }
.global-search-result--more { color: rgba(255,255,255,.62); }
.global-search-result--more .global-search-title { color: rgba(255,255,255,.74); }
.global-search-thumb { width: 4.6rem; aspect-ratio: 16 / 10; border-radius: .55rem; display: flex; align-items: center; justify-content: center; overflow: hidden; background: rgba(255,255,255,.055); color: rgba(255,255,255,.42); }
.global-search-thumb--more { background: rgba(0,117,255,.12); color: #93c5fd; }
.global-search-thumb img { width: 100%; height: 100%; object-fit: cover; }
.global-search-thumb-icon { width: 1.2rem; height: 1.2rem; }
.global-search-result-main { min-width: 0; display: grid; gap: .18rem; }
.global-search-title-row { display: flex; gap: .5rem; align-items: center; min-width: 0; }
.global-search-title { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: rgba(255,255,255,.9); font-size: .86rem; }
.global-search-type { flex: 0 0 auto; color: rgba(255,255,255,.34); font-size: .68rem; }
.global-search-subtitle { color: rgba(255,255,255,.48); font-size: .74rem; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.global-search-desc { color: rgba(255,255,255,.3); font-size: .7rem; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.global-search-badges { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: .28rem; max-width: 15rem; }
.global-search-badge { padding: .18rem .42rem; border-radius: 999px; background: rgba(255,255,255,.06); color: rgba(255,255,255,.6); font-size: .65rem; white-space: nowrap; }
.global-search-badge--primary { background: rgba(0,117,255,.18); color: #93c5fd; }
.global-search-badge--success { background: rgba(34,197,94,.15); color: #86efac; }
.global-search-badge--warning { background: rgba(245,158,11,.16); color: #fcd34d; }
.global-search-badge--danger { background: rgba(239,68,68,.15); color: #fca5a5; }
@media (max-width: 680px) {
  .global-search-overlay { padding-top: .75rem; }
  .global-search { max-height: calc(100vh - 1.5rem); }
  .global-search-result { grid-template-columns: 3.8rem minmax(0,1fr); }
  .global-search-badges { grid-column: 2; justify-content: flex-start; max-width: none; }
  .global-search-thumb { width: 3.8rem; }
}
</style>
