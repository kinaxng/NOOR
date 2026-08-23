<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, watch, computed, defineAsyncComponent, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useMediaLibraryStore } from '../stores/mediaLibrary'
import { useI18n } from '../composables/useI18n'
import MediaCard from '../components/noor/MediaCard.vue'
import BaseIcon from '../components/noor/BaseIcon.vue'
import VisionTabs from '../components/ui/Tabs.vue'
import VuiButton from '../components/ui/Button/VuiButton.vue'
import NoorPagination from '../components/ui/Pagination.vue'

// Lazy-load panels that are only shown on demand
const AsyncMediaDetailPanel = defineAsyncComponent(() => import('../components/noor/MediaDetailPanel.vue'))
const AsyncLadaPanel = defineAsyncComponent(() => import('../components/noor/LadaPanel.vue'))
const AsyncSubtitlePanel = defineAsyncComponent(() => import('../components/noor/SubtitlePanel.vue'))
import type { MediaItem } from '../api/types'

const { t, i18nVersion } = useI18n()
const mediaLibraryStore = useMediaLibraryStore()
const route = useRoute()
const router = useRouter()

const activeFilter = ref((route.query.filter as string) || '')
const filters = computed(() => {
  void i18nVersion.value
  return [
    { key: '', label: t('library.filter.all') },
    { key: 'cracked', label: t('library.filter.cracked') },
    { key: 'chinese', label: t('library.filter.chinese') },
    { key: 'leaked', label: t('library.filter.leaked') },
    { key: 'uncensored', label: t('library.filter.uncensored') },
  ]
})

const activeFilterStr = computed({
  get: () => activeFilter.value,
  set: (v: string) => { activeFilter.value = v },
})

const searchQuery = ref(mediaLibraryStore.searchQuery)
const searchPlaceholder = computed(() => {
  void i18nVersion.value
  return t('library.search.placeholder')
})

const visibleItems = computed(() => mediaLibraryStore.filteredItems)

type LibraryImageMode = 'cover' | 'backdrop'
const IMAGE_MODE_KEY = 'noor-library-image-mode'
const imageMode = ref<LibraryImageMode>((localStorage.getItem(IMAGE_MODE_KEY) as LibraryImageMode) || 'cover')
const gridEl = ref<HTMLElement | null>(null)
let resizeObserver: ResizeObserver | null = null
let resizeTimer: ReturnType<typeof setTimeout> | null = null

const gridMinWidth = computed(() => imageMode.value === 'backdrop' ? 320 : 160)
const gridTemplateColumns = computed(() => `repeat(auto-fill, minmax(${gridMinWidth.value}px, 1fr))`)
const imageModeTitle = computed(() => imageMode.value === 'backdrop' ? '切换为封面图' : '切换为背景图')

function toggleImageMode() {
  imageMode.value = imageMode.value === 'cover' ? 'backdrop' : 'cover'
  localStorage.setItem(IMAGE_MODE_KEY, imageMode.value)
  schedulePageSizeUpdate(true)
}

function estimatePageSize() {
  const el = gridEl.value
  if (!el) return 18
  const width = el.clientWidth || window.innerWidth
  const top = el.getBoundingClientRect().top
  const availableHeight = Math.max(360, window.innerHeight - top - 88)
  const gap = 16
  const minWidth = gridMinWidth.value
  const columns = Math.max(1, Math.floor((width + gap) / (minWidth + gap)))
  const cardWidth = Math.max(minWidth, (width - gap * Math.max(0, columns - 1)) / columns)
  const imageHeight = imageMode.value === 'backdrop' ? cardWidth * 1468 / 2184 : cardWidth * 3 / 2
  const cardHeight = imageHeight + (imageMode.value === 'backdrop' ? 64 : 74)
  const measuredRows = Math.max(1, Math.floor((availableHeight + gap) / (cardHeight + gap)))
  const rows = imageMode.value === 'cover' ? Math.max(3, measuredRows) : measuredRows
  const maxItems = imageMode.value === 'backdrop' ? 96 : 144
  return Math.max(imageMode.value === 'cover' ? columns * 3 : columns, Math.min(maxItems, columns * rows))
}

function schedulePageSizeUpdate(refetch = false) {
  if (resizeTimer) clearTimeout(resizeTimer)
  resizeTimer = setTimeout(async () => {
    await nextTick()
    const changed = mediaLibraryStore.setPageSize(estimatePageSize())
    if ((changed || refetch) && mediaLibraryStore.selectedLibrary?.id) {
      await mediaLibraryStore.fetchItems(mediaLibraryStore.selectedLibrary.id, 1, activeFilter.value || null, searchQuery.value)
    } else if ((changed || refetch) && mediaLibraryStore.enabledLibraryIds.length === 0) {
      await mediaLibraryStore.fetchAllItems(1, searchQuery.value)
    }
  }, 120)
}




const showDetailPanel = ref(false)
const showLadaPanel = ref(false)
const selectedVideo = ref<MediaItem | null>(null)
const videoDetail = ref<any>(null)
const loadingDetail = ref(false)
const detailError = ref<string | null>(null)

const showSubtitlePanel = ref(false)
const subtitleVideoPath = ref('')
const subtitleVideoId = ref('')
const subtitleFolderPaths = ref<string[]>([])
let detailRequestToken = 0

function resetPanelState(options: { keepSelectedVideo?: boolean } = {}) {
  showDetailPanel.value = false
  showLadaPanel.value = false
  showSubtitlePanel.value = false
  loadingDetail.value = false
  videoDetail.value = null
  detailError.value = null
  subtitleVideoPath.value = ''
  subtitleVideoId.value = ''
  subtitleFolderPaths.value = []
  if (!options.keepSelectedVideo) {
    selectedVideo.value = null
  }
}

async function loadItemDetail(item: MediaItem) {
  const token = ++detailRequestToken
  loadingDetail.value = true
  videoDetail.value = null
  detailError.value = null
  try {
    const detail = await mediaLibraryStore.fetchItemDetail(item.id)
    if (token !== detailRequestToken || selectedVideo.value?.id !== item.id) return null
    videoDetail.value = detail
    return detail
  } catch (e: any) {
    if (token === detailRequestToken && selectedVideo.value?.id === item.id) {
      detailError.value = e?.message || t('common.loadFailed')
    }
    return null
  } finally {
    if (token === detailRequestToken && selectedVideo.value?.id === item.id) {
      loadingDetail.value = false
    }
  }
}

onMounted(async () => {
  await ensureLibraryReady()
  await nextTick()
  schedulePageSizeUpdate(true)
  if (gridEl.value) {
    resizeObserver = new ResizeObserver(() => schedulePageSizeUpdate())
    resizeObserver.observe(gridEl.value)
  }
  window.addEventListener('resize', handleResize)
})

onBeforeUnmount(() => {
  resizeObserver?.disconnect()
  resizeObserver = null
  if (resizeTimer) clearTimeout(resizeTimer)
  window.removeEventListener('resize', handleResize)
})

function handleResize() {
  schedulePageSizeUpdate()
}

watch(activeFilter, (key) => {
  mediaLibraryStore.setFilter(key || null)
  router.replace({ query: key ? { filter: key } : {} })
}, { flush: 'post' })



let searchDebounce: ReturnType<typeof setTimeout> | null = null
watch(searchQuery, (value) => {
  if (searchDebounce) clearTimeout(searchDebounce)
  searchDebounce = setTimeout(() => {
    mediaLibraryStore.setSearch(value)
  }, 220)
})

function autoSelectLibrary(_filter: string | null) {
  const preferredId = mediaLibraryStore.enabledLibraryIds[0]
  const lib = (preferredId
    ? mediaLibraryStore.allLibraries.find(l => l.id === preferredId)
    : null) || mediaLibraryStore.libraries[0] || null
  if (!lib) {
    mediaLibraryStore.selectLibrary(null)
    return null
  }
  mediaLibraryStore.selectLibrary(lib)
  return lib
}

async function ensureLibraryReady() {
  await mediaLibraryStore.fetchLibraries()
  mediaLibraryStore.filterTag = activeFilter.value || null
  const lib = autoSelectLibrary(activeFilter.value || null)
  if (!lib) return

  const selectedId = mediaLibraryStore.selectedLibrary?.id
  const shouldFetchDirectly = selectedId === lib.id || mediaLibraryStore.items.length === 0
  if (shouldFetchDirectly) {
    await mediaLibraryStore.fetchItems(lib.id, 1, activeFilter.value || null, searchQuery.value)
  }
}

// Sync filter from URL changes (e.g., browser back/forward)
watch(() => route.query.filter, (f) => {
  const filter = (f as string) || ''
  if (filter !== activeFilter.value) {
    activeFilter.value = filter
  }
})

watch(() => route.path, async (path) => {
  if (path === '/library') {
    await ensureLibraryReady()
  }
})

function handleSelectVideo(item: MediaItem) {
  resetPanelState({ keepSelectedVideo: true })
  selectedVideo.value = item
  showDetailPanel.value = true
  void loadItemDetail(item)
}

function handleQuickAction(item: MediaItem) {
  resetPanelState({ keepSelectedVideo: true })
  selectedVideo.value = item
  showLadaPanel.value = true
  void loadItemDetail(item)
}

async function handleSubtitleAction(item: MediaItem) {
  resetPanelState({ keepSelectedVideo: true })
  selectedVideo.value = item
  subtitleVideoId.value = item.id
  const detail = await loadItemDetail(item)
  if (!detail) return
  subtitleVideoPath.value = detail.file_path || item.path || ''
  const allPaths = [subtitleVideoPath.value]
  if (detail.siblings) {
    for (const s of detail.siblings) {
      if (s.file_path && !allPaths.includes(s.file_path)) {
        allPaths.push(s.file_path)
      }
    }
  }
  subtitleFolderPaths.value = allPaths
  showSubtitlePanel.value = true
}

function handleCloseDetail() {
  detailRequestToken += 1
  resetPanelState()
}

function handleCloseSubtitle() {
  detailRequestToken += 1
  resetPanelState()
}

function goPage(page: number) {
  if (mediaLibraryStore.enabledLibraryIds.length === 0) {
    mediaLibraryStore.fetchAllItems(page)
    return
  }
  if (mediaLibraryStore.selectedLibrary?.id) mediaLibraryStore.fetchItems(mediaLibraryStore.selectedLibrary.id, page)
}

</script>

<template>
  <div class="w-full space-y-6 animate-fade-in">
    <div class="library-toolbar">
      <div class="library-toolbar__row">
        <VisionTabs v-model="activeFilterStr" :tabs="filters" />
        <div class="library-toolbar__search-wrap">
          <button
            type="button"
            class="library-toolbar__icon-btn"
            :aria-label="imageModeTitle"
            :title="imageModeTitle"
            @click="toggleImageMode"
          >
            <BaseIcon :name="imageMode === 'backdrop' ? 'grid' : 'library'" class="h-4 w-4" />
          </button>
          <div class="library-toolbar__search">
            <BaseIcon name="search" class="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-white/25" />
            <input
              v-model="searchQuery"
              type="search"
              :placeholder="searchPlaceholder"
              class="library-toolbar__search-input"
            />
          </div>
        </div>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="mediaLibraryStore.loading" class="flex flex-col items-center justify-center py-24">
      <div class="w-10 h-10 border-2 rounded-full animate-spin mb-4 border-[#0075FF] border-t-transparent"></div>
      <span class="text-sm text-white/30">{{ t('common.loading') }}</span>
    </div>

    <!-- Empty content -->
    <div
      v-else-if="visibleItems.length === 0 && !mediaLibraryStore.error"
      class="library-state-card ui-card flex flex-col items-center justify-center text-center"
    >
      <div class="w-16 h-16 rounded-2xl flex items-center justify-center mb-5 empty-state-icon">
        <BaseIcon name="folder" class="w-8 h-8 text-white/20" />
      </div>
      <h2 class="text-lg font-semibold mb-2 text-white font-display">{{ t('library.emptyTitle') }}</h2>
      <p class="text-sm text-white/30">{{ t('library.emptyDesc') }}</p>
    </div>

    <!-- Media library not configured / disabled -->
    <div
      v-else-if="mediaLibraryStore.error"
      class="library-state-card ui-card flex flex-col items-center justify-center text-center"
    >
      <div class="w-16 h-16 rounded-2xl flex items-center justify-center mb-5 empty-state-icon">
        <BaseIcon name="folder" class="w-8 h-8 text-white/20" />
      </div>
      <h2 class="text-lg font-semibold mb-2 text-white font-display">{{ t('library.noLibraryTitle') }}</h2>
      <p class="text-sm text-white/30 mb-5">{{ mediaLibraryStore.error }}</p>
      <VuiButton variant="gradient" color="info" size="small" @click="router.push('/settings')">
        {{ t('library.goToSettings') }} →
      </VuiButton>
    </div>

    <!-- Grid -->
    <div
      v-else
      ref="gridEl"
      class="grid gap-4"
      :class="imageMode === 'backdrop' ? 'library-grid--backdrop' : 'library-grid--cover'"
      :style="{ gridTemplateColumns }"
    >
      <MediaCard
        v-for="(item, i) in visibleItems"
        :key="item.id"
        :item="item"
        :image-mode="imageMode"
        :selected="selectedVideo?.id === item.id"
        class="stagger-item"
        :style="{ animationDelay: `${(i % 18) * 50}ms` }"
        @click="handleSelectVideo"
        @quick-action="handleQuickAction"
        @subtitle-action="handleSubtitleAction"
      />
    </div>

    <!-- Pagination -->
    <NoorPagination
      :page="mediaLibraryStore.currentPage"
      :total-pages="mediaLibraryStore.totalPages"
      @page="goPage"
    />

    <AsyncMediaDetailPanel
      v-if="showDetailPanel"
      :open="showDetailPanel"
      :item="selectedVideo"
      :detail="videoDetail"
      :loading="loadingDetail"
      :error="detailError"
      @close="handleCloseDetail"
    />

    <AsyncLadaPanel
      v-if="showLadaPanel"
      :open="showLadaPanel"
      :item="selectedVideo"
      :detail="videoDetail"
      @close="handleCloseDetail"
    />

    <AsyncSubtitlePanel
      v-if="showSubtitlePanel"
      :open="showSubtitlePanel"
      :detail="videoDetail"
      :loading="loadingDetail"
      :initial-selected-path="subtitleVideoPath"
      @close="handleCloseSubtitle"
    />
  </div>
</template>


<style scoped>
.library-toolbar {
  display: flex;
  flex-direction: column;
  gap: 0.55rem;
  padding: 0;
}

.library-toolbar__row {
  display: flex;
  align-items: center;
  gap: 0.7rem;
  justify-content: space-between;
}

.library-toolbar__search-wrap {
  display: flex;
  flex: 0 0 20rem;
  justify-content: flex-end;
  align-items: center;
  gap: 0.5rem;
}

.library-toolbar__icon-btn {
  height: 38px;
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  border-radius: var(--radius-lg);
  border: 1px solid var(--color-border-default);
  background: rgba(255,255,255,0.04);
  color: rgba(255,255,255,0.68);
  justify-content: center;
  width: 38px;
  padding: 0;
  font-family: var(--font-display);
  font-size: 0.75rem;
  font-weight: 700;
  transition: var(--transition-fast);
  white-space: nowrap;
}

.library-toolbar__icon-btn:hover {
  border-color: rgba(0,117,255,0.36);
  background: rgba(255,255,255,0.07);
  color: #fff;
}

.library-toolbar__search {
  position: relative;
  width: 100%;
  max-width: 20rem;
}

.library-toolbar__search-input {
  width: 100%;
  border-radius: var(--radius-lg);
  border: 1px solid var(--color-border-default);
  background: rgba(255,255,255,0.04);
  padding: 0.56rem 0.8rem 0.56rem 2.2rem;
  font-size: var(--font-size-sm);
  color: var(--color-text-primary);
  outline: none;
  transition: var(--transition-fast);
}

.library-toolbar__search-input::placeholder {
  color: rgba(255,255,255,0.25);
}

.library-toolbar__search-input:focus {
  border-color: rgba(0,117,255,0.42);
  background: rgba(255,255,255,0.055);
}

.library-pagination {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.65rem;
}

@media (max-width: 1100px) {
  .library-toolbar__row {
    flex-direction: column;
    align-items: stretch;
  }

  .library-toolbar__search-wrap {
    flex: none;
    width: 100%;
  }

  .library-toolbar__search {
    max-width: none;
  }
}

@media (max-width: 640px) {
    .library-toolbar__meta {
    flex-direction: column;
    align-items: flex-start;
    gap: 0.2rem;
  }

  .library-pagination {
    gap: 0.45rem;
  }

  .library-pagination__btn {
    min-width: 0;
  }

  .library-state-card {
    min-height: 14rem;
    padding: 1.75rem 1rem;
  }
}
</style>
