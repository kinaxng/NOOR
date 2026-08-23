<script setup lang="ts">
import { computed } from 'vue'
import type { MediaItemDetail } from '../../api/types'

interface VariantRow {
  id: string
  path: string
  name: string
  dir: string
  tags?: import('../../api/types').MediaItem['tags']
}

const props = defineProps<{
  open: boolean
  detail: MediaItemDetail | null
  loading: boolean
  error: string | null
  variantRows: VariantRow[]
  selectedVariantPath: string
  previewVideoPath: string
}>()

const emit = defineEmits<{
  close: []
  'select-variant': [path: string]
  'open-preview': [path?: string]
  'update:previewVideoPath': [path: string]
}>()

const previewVideoName = computed(() => props.previewVideoPath.split('/').pop() || props.previewVideoPath)
const previewVideoUrl = computed(() => {
  if (!props.previewVideoPath) return ''
  return `/api/media-library/hardlinks/preview-file?path=${encodeURIComponent(props.previewVideoPath)}`
})

function formatBytes(value?: number | null) {
  const size = Number(value || 0)
  if (!size) return '-'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let n = size; let i = 0
  while (n >= 1024 && i < units.length - 1) { n /= 1024; i += 1 }
  return `${n.toFixed(i === 0 ? 0 : 1)} ${units[i]}`
}
</script>

<template>
  <Teleport to="body">
    <Transition enter-active-class="transition-opacity duration-200" enter-from-class="opacity-0" leave-active-class="transition-opacity duration-200" leave-to-class="opacity-0">
      <div v-if="open" class="fixed inset-0 z-50 flex justify-end">
        <div class="absolute inset-0 bg-black/80 backdrop-blur-sm" @click="emit('close')" />
        <div class="relative bg-(--ui-bg) border-l border-(--ui-border) flex flex-col overflow-hidden shadow-2xl h-full w-full max-w-md">
          <!-- Loading -->
          <div v-if="loading" class="flex items-center justify-center flex-1">
            <UIcon name="i-heroicons-arrow-path-20-solid" class="w-8 h-8 animate-spin text-(--ui-text-muted)" />
          </div>
          <!-- Error -->
          <div v-else-if="error" class="flex flex-col items-center justify-center flex-1 p-8 text-center">
            <p class="text-(--ui-error) text-lg mb-2">错误</p>
            <p class="text-(--ui-text-muted) text-sm max-w-md">{{ error }}</p>
            <UButton color="neutral" variant="ghost" size="sm" class="mt-4" @click="emit('close')">关闭</UButton>
          </div>
          <!-- Content -->
          <template v-else-if="detail">
            <div class="flex-1 overflow-y-auto p-4 space-y-4 relative">
              <!-- Hero -->
              <div class="detail-hero shrink-0 -mx-4 -mt-4">
                <img v-if="detail.backdrop_path || detail.poster_path" :src="detail.backdrop_path || detail.poster_path" :alt="detail.name" />
                <div class="detail-hero__actions">
                  <UButton color="white" variant="ghost" icon="i-heroicons-x-mark-20-solid" class="detail-close" @click="emit('close')" />
                </div>
                <div class="absolute bottom-4 left-4 right-4 z-10 flex items-end justify-between">
                  <div class="min-w-0 pr-4">
                    <h2 class="text-2xl font-bold text-white truncate">{{ detail.name }}</h2>
                  </div>
                  <UButton color="primary" size="lg" icon="i-heroicons-play-20-solid" class="shrink-0 shadow-lg" @click="emit('open-preview')">播放</UButton>
                </div>
              </div>
              <!-- File path -->
              <div>
                <div class="font-mono text-xs break-all p-2 rounded bg-(--ui-bg-elevated) border border-(--ui-border)">{{ detail.file_path || detail.path }}</div>
              </div>
              <!-- Meta -->
              <div class="detail-meta">
                <span :title="detail.studios?.join('、') || '-'">片商: {{ detail.studios?.join('、') || '-' }}</span>
                <span>发行: {{ detail.premiered || '-' }}</span>
                <span :title="detail.actors?.map(a => a.name).join('、') || '-'">演员: {{ detail.actors?.map(a => a.name).join('、') || '-' }}</span>
              </div>
              <!-- Genres -->
              <div v-if="detail.genres?.length" class="flex flex-wrap gap-1.5">
                <UBadge v-for="genre in detail.genres.slice(0, 20)" :key="genre" color="neutral" variant="soft" size="xs">{{ genre }}</UBadge>
              </div>
              <!-- Versions -->
              <div class="versions">
                <h3>文件版本</h3>
                <button
                  v-for="variant in variantRows"
                  :key="variant.path"
                  class="version-row"
                  :class="{ 'is-active': selectedVariantPath === variant.path }"
                  @click="emit('select-variant', variant.path)"
                >
                  <strong>{{ variant.name }}</strong>
                  <span>{{ variant.path }}</span>
                </button>
              </div>
            </div>
          </template>
        </div>

        <!-- Video Preview (inline within detail panel) -->
        <div v-if="previewVideoPath" class="fixed inset-0 z-[51] flex items-center justify-center bg-black/90" @click.self="emit('update:previewVideoPath', '')">
          <div class="relative w-full max-w-3xl mx-4">
            <UButton color="white" variant="ghost" icon="i-heroicons-x-mark-20-solid" class="absolute top-2 right-2 z-10" @click="emit('update:previewVideoPath', '')" />
            <video
              :key="previewVideoUrl"
              class="w-full max-h-[70vh] bg-black rounded-lg"
              :src="previewVideoUrl"
              controls
              autoplay
              preload="metadata"
            />
            <p class="text-xs text-white/60 mt-2 truncate">{{ previewVideoName }}</p>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>
