<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useMediaStore } from '../../stores/media'
import type { MediaItem } from '../../api/types'

const props = withDefaults(defineProps<{
  coverMode: 'cover' | 'fanart'
  blurEnabled: boolean
  gridMinCardWidth: number
  selectedItemId?: string | null
}>(), {
  selectedItemId: null,
})

const emit = defineEmits<{
  'open-detail': [item: MediaItem]
  'open-lada': [item: MediaItem]
  'open-subtitle': [item: MediaItem]
  'page-change': [page: number]
}>()

const media = useMediaStore()

const GRID_GAP = 16
const FALLBACK_CARD_HEIGHT = 316
const PAGE_CHROME_OFFSET = 28
const MIN_PAGE_SIZE = 6
const MAX_PAGE_SIZE = 60

const pageRootRef = ref<HTMLElement | null>(null)
const gridRef = ref<HTMLElement | null>(null)
const paginationRef = ref<HTMLElement | null>(null)
const fanartFailures = ref<Set<string>>(new Set())

let resizeObserver: ResizeObserver | null = null
let responsiveSyncTimer: ReturnType<typeof setTimeout> | null = null

function handleResize() { scheduleResponsiveSync() }

function estimateResponsivePageSize() {
  const gridEl = gridRef.value || pageRootRef.value
  if (!gridEl) return media.pageSize
  const gridWidth = gridEl.clientWidth || pageRootRef.value?.clientWidth || window.innerWidth
  const columns = Math.max(1, Math.floor((gridWidth + GRID_GAP) / (props.gridMinCardWidth + GRID_GAP)))
  const firstCard = gridRef.value?.querySelector('.media-card') as HTMLElement | null
  const cardHeight = firstCard?.offsetHeight || FALLBACK_CARD_HEIGHT
  const gridTop = gridRef.value?.getBoundingClientRect().top ?? gridEl.getBoundingClientRect().top
  const paginationHeight = paginationRef.value?.offsetHeight || 52
  const availableHeight = Math.max(cardHeight, window.innerHeight - gridTop - paginationHeight - PAGE_CHROME_OFFSET)
  const measuredRows = Math.max(1, Math.floor((availableHeight + GRID_GAP) / (cardHeight + GRID_GAP)))
  let minRows = 1
  if (window.innerHeight >= 1200) minRows = 3
  else if (window.innerHeight >= 900) minRows = 2
  return Math.min(MAX_PAGE_SIZE, Math.max(MIN_PAGE_SIZE, columns * Math.max(measuredRows, minRows)))
}

async function syncResponsivePageSize(force = false) {
  const nextSize = estimateResponsivePageSize()
  if (!force && nextSize === media.pageSize) return
  const offset = Math.max(0, (media.page - 1) * media.pageSize)
  media.pageSize = nextSize
  const nextPage = Math.max(1, Math.floor(offset / nextSize) + 1)
  media.page = nextPage
  await media.fetchItems(nextPage)
}

function scheduleResponsiveSync(force = false) {
  if (responsiveSyncTimer) clearTimeout(responsiveSyncTimer)
  responsiveSyncTimer = setTimeout(() => { void syncResponsivePageSize(force) }, force ? 0 : 120)
}

function imageSrc(item: MediaItem) {
  if (props.coverMode === 'fanart' && item.fanart_path && !fanartFailures.value.has(item.id)) {
    return item.fanart_path
  }
  return item.poster_path
}

function imageWrapClass() {
  return props.coverMode === 'fanart' ? 'aspect-[2184/1468]' : 'aspect-[2/3]'
}

function handleImageError(item: MediaItem) {
  if (props.coverMode === 'fanart' && item.fanart_path) {
    const s = new Set(fanartFailures.value); s.add(item.id); fanartFailures.value = s
  }
}

watch(() => props.coverMode, () => {
  fanartFailures.value = new Set()
  scheduleResponsiveSync(true)
})

onMounted(async () => {
  const { nextTick } = await import('vue')
  await nextTick()
  scheduleResponsiveSync(true)
  if (typeof ResizeObserver !== 'undefined') {
    resizeObserver = new ResizeObserver(() => scheduleResponsiveSync())
    if (pageRootRef.value) resizeObserver.observe(pageRootRef.value)
    if (gridRef.value) resizeObserver.observe(gridRef.value)
    if (paginationRef.value) resizeObserver.observe(paginationRef.value)
  }
  window.addEventListener('resize', handleResize, { passive: true })
})

onBeforeUnmount(() => {
  if (responsiveSyncTimer) clearTimeout(responsiveSyncTimer)
  resizeObserver?.disconnect()
  resizeObserver = null
  window.removeEventListener('resize', handleResize)
})

const loadingLabel = computed(() => '加载中...')
const emptyTitle = computed(() => '还没有内容')
const emptyDesc = computed(() => '前往设置连接媒体库')
</script>

<template>
  <div ref="pageRootRef">
    <!-- Loading -->
    <div v-if="media.loading" class="flex flex-col items-center justify-center py-12 text-(--ui-text-muted)">
      <UIcon name="i-heroicons-arrow-path-20-solid" class="w-8 h-8 animate-spin mb-4" />
      <p>{{ loadingLabel }}</p>
    </div>

    <!-- Error -->
    <div v-else-if="media.error" class="flex flex-col items-center justify-center py-12">
      <UIcon name="i-heroicons-exclamation-triangle-20-solid" class="w-12 h-12 text-(--ui-error) mb-4" />
      <p class="text-(--ui-error) font-medium">{{ media.error }}</p>
      <UButton color="primary" size="sm" class="mt-4" to="/settings">前往设置</UButton>
    </div>

    <!-- Empty -->
    <div v-else-if="!media.items.length" class="flex flex-col items-center justify-center py-12 text-(--ui-text-muted)">
      <UIcon name="i-heroicons-film-20-solid" class="w-12 h-12 mb-4 opacity-50" />
      <p>{{ emptyTitle }}</p>
      <p class="text-xs mt-1">{{ emptyDesc }}</p>
    </div>

    <template v-else>
      <!-- Grid -->
      <div
        ref="gridRef"
        class="grid gap-4"
        :style="{ gridTemplateColumns: `repeat(auto-fill, minmax(${gridMinCardWidth}px, 1fr))` }"
      >
        <UCard
          v-for="(item, i) in media.items"
          :key="item.id"
          class="media-card stagger-item cursor-pointer group overflow-hidden flex flex-col"
          :class="selectedItemId === item.id ? 'ring-1 ring-(--color-noor-500)' : ''"
          :style="{ animationDelay: `${(i % 18) * 50}ms` }"
          :ui="{ body: { padding: 'p-0' } }"
        >
          <!-- Cover -->
          <div
            :class="imageWrapClass()"
            class="bg-(--ui-bg-elevated) relative overflow-hidden"
            @click="emit('open-detail', item)"
          >
            <img
              v-if="imageSrc(item)"
              :src="imageSrc(item)"
              :alt="item.name"
              :class="blurEnabled ? 'blur-xl' : ''"
              class="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
              loading="lazy"
              @error="handleImageError(item)"
            />
            <div v-else class="w-full h-full flex items-center justify-center text-(--ui-text-muted) text-xs font-medium tracking-wider">
              无封面
            </div>
          </div>

          <!-- Info -->
          <div class="p-3 border-t border-(--ui-border)">
            <p
              class="text-xs line-clamp-2 h-8 text-(--ui-text) mb-1.5 cursor-pointer hover:text-white transition-colors"
              :title="item.name"
              @click="emit('open-detail', item)"
            >{{ item.name }}</p>

            <!-- Tags -->
            <div class="flex flex-wrap gap-1">
              <span
                class="text-xs px-1.5 py-0.5 rounded border cursor-pointer transition-colors"
                :class="(item.tags?.has_chinese || (item.subtitle_count ?? 0) > 0) ? 'border-(--color-noor-500)/40 bg-(--color-noor-600)/15 text-(--color-noor-200)' : 'border-(--ui-border) bg-(--ui-bg-elevated) text-(--ui-text-muted)'"
                @click.stop="emit('open-subtitle', item)"
              >中字</span>

              <span
                v-if="!item.tags?.release_type"
                class="text-xs px-1.5 py-0.5 rounded border cursor-pointer transition-colors"
                :class="item.tags?.is_cracked ? 'border-(--color-noor-500)/40 bg-(--color-noor-600)/15 text-(--color-noor-200)' : 'border-(--ui-border) bg-(--ui-bg-elevated) text-(--ui-text-muted)'"
                @click.stop="emit('open-lada', item)"
              >{{ item.tags?.is_cracked ? '破解' : '破解?' }}</span>

              <span
                v-if="item.tags?.release_type"
                class="text-xs px-1.5 py-0.5 rounded border"
                :class="item.tags.release_type_key === 'leaked' ? 'border-amber-400/40 bg-amber-400/10 text-amber-300' : 'border-emerald-400/40 bg-emerald-400/10 text-emerald-300'"
              >{{ item.tags.release_type_key === 'leaked' ? '流出' : '无码' }}</span>
            </div>
          </div>
        </UCard>
      </div>

      <!-- Pagination -->
      <div v-if="media.pageCount > 1" ref="paginationRef" class="mt-6 flex justify-center pb-8">
        <UPagination v-model="media.page" :total="media.total" :items-per-page="media.pageSize" @update:model-value="emit('page-change', $event)" />
      </div>
    </template>
  </div>
</template>
