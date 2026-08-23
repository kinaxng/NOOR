<script setup lang="ts">
import { computed } from 'vue'
import { useMediaStore } from '../../stores/media'
import type { MediaItemDetail } from '../../api/types'

interface VariantRow {
  id: string
  path: string
  name: string
  dir: string
}

const props = defineProps<{
  open: boolean
  detail: MediaItemDetail | null
  loading: boolean
  error: string | null
  variantRows: VariantRow[]
  selectedPath: string
  tab: 'local' | 'online' | 'whisper'
  whisperPreprocess: boolean
  whisperTranslate: boolean
  whisperSubmitting: boolean
}>()

const emit = defineEmits<{
  close: []
  'update:selectedPath': [path: string]
  'update:tab': [tab: 'local' | 'online' | 'whisper']
  'submit-whisper': []
}>()

const media = useMediaStore()

const subtitleTabs = computed(() => [
  { value: 'local', label: '本地字幕', icon: 'i-lucide-folder-open', badge: media.subtitles.length },
  { value: 'online', label: '在线字幕', icon: 'i-lucide-globe', badge: media.onlineSubtitles.length },
  { value: 'whisper', label: '生成字幕', icon: 'i-lucide-sparkles' },
])

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
        <div class="relative bg-(--ui-bg) border-l border-(--ui-border) flex flex-col overflow-hidden shadow-2xl h-full w-full max-w-xl">
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
                <div class="absolute bottom-4 left-4 right-4 z-10">
                  <h2 class="text-xl font-bold text-white truncate">{{ detail.name }}</h2>
                  <p class="text-xs text-white/70 mt-1">字幕管理</p>
                </div>
              </div>
              <!-- File selector -->
              <div v-if="variantRows.length > 1">
                <label class="text-xs text-(--ui-text-muted) uppercase tracking-wider mb-1.5 block">当前文件</label>
                <select
                  :value="selectedPath"
                  class="w-full h-9 px-3 rounded-lg border border-(--ui-border) bg-(--ui-bg) text-sm text-(--ui-text) outline-none focus:border-(--ui-border-accented)"
                  @change="emit('update:selectedPath', ($event.target as HTMLSelectElement).value)"
                >
                  <option v-for="v in variantRows" :key="v.path" :value="v.path">{{ v.name }}</option>
                </select>
              </div>
              <!-- Tabs -->
              <UTabs :model-value="tab" :items="subtitleTabs" class="-mx-1 flex-1" :content="false" @update:model-value="emit('update:tab', $event as 'local' | 'online' | 'whisper')" />
              <UAlert v-if="media.subtitleError" title="错误" :description="media.subtitleError" color="error" variant="soft" />
              <!-- Local tab -->
              <div v-if="tab === 'local'" class="min-h-[150px]">
                <div class="flex items-center justify-between mb-3">
                  <span class="text-xs text-(--ui-text-muted)">本地字幕</span>
                  <UButton color="neutral" variant="ghost" size="xs" icon="i-heroicons-arrow-path-20-solid" :loading="media.subtitleLoading" @click="media.fetchSubtitles()">扫描</UButton>
                </div>
                <div v-if="media.subtitleLoading" class="flex flex-col items-center justify-center py-8 text-(--ui-text-muted)">
                  <UIcon name="i-heroicons-arrow-path-20-solid" class="w-6 h-6 animate-spin mb-2" />
                  <span class="text-sm">扫描本地字幕中...</span>
                </div>
                <div v-else-if="!media.subtitles.length" class="flex flex-col items-center justify-center py-8 text-(--ui-text-muted)">
                  <UIcon name="i-heroicons-document-text-20-solid" class="w-8 h-8 mb-2 opacity-50" />
                  <span class="text-sm">未发现本地字幕</span>
                </div>
                <div v-else class="subtitle-list">
                  <div v-for="subtitle in media.subtitles" :key="subtitle.path" class="subtitle-row">
                    <div class="min-w-0 flex-1 pr-4">
                      <strong :title="subtitle.filename">{{ subtitle.filename }}</strong>
                      <span>{{ subtitle.ext }} · {{ formatBytes(subtitle.size) }}</span>
                    </div>
                    <div class="flex items-center gap-1 shrink-0">
                      <UButton color="neutral" variant="ghost" size="xs" :disabled="media.subtitleAction === subtitle.path" @click="media.previewLocalSubtitle(subtitle)">预览</UButton>
                      <UButton color="error" variant="ghost" size="xs" icon="i-heroicons-trash-20-solid" :disabled="media.subtitleAction === subtitle.path" @click="media.deleteLocalSubtitle(subtitle)" />
                    </div>
                  </div>
                </div>
              </div>
              <!-- Online tab -->
              <div v-else-if="tab === 'online'" class="min-h-[150px]">
                <div class="flex items-center justify-between mb-3">
                  <span class="text-xs text-(--ui-text-muted)">在线字幕</span>
                  <UButton color="neutral" variant="ghost" size="xs" icon="i-heroicons-magnifying-glass-20-solid" :loading="media.onlineSearching" @click="media.searchOnlineSubtitles()">搜索</UButton>
                </div>
                <div v-if="media.onlineSearching" class="flex flex-col items-center justify-center py-8 text-(--ui-text-muted)">
                  <UIcon name="i-heroicons-arrow-path-20-solid" class="w-6 h-6 animate-spin mb-2" />
                  <span class="text-sm">搜索字幕源中...</span>
                </div>
                <div v-else-if="!media.onlineSubtitles.length" class="flex flex-col items-center justify-center py-8 text-(--ui-text-muted)">
                  <UIcon name="i-heroicons-globe-alt-20-solid" class="w-8 h-8 mb-2 opacity-50" />
                  <span class="text-sm">暂无搜索结果，点击右上角搜索</span>
                </div>
                <div v-else class="subtitle-list">
                  <div v-for="subtitle in media.onlineSubtitles" :key="subtitle.url" class="subtitle-row">
                    <div class="min-w-0 flex-1 pr-4">
                      <strong :title="subtitle.name">{{ subtitle.name }}</strong>
                      <span class="flex items-center gap-2">
                        <UBadge color="neutral" variant="soft" size="xs">{{ subtitle.source || subtitle.source_key || '字幕源' }}</UBadge>
                        {{ subtitle.language || '-' }} · {{ subtitle.ext || '.srt' }}
                      </span>
                    </div>
                    <div class="flex items-center gap-1 shrink-0">
                      <UButton color="neutral" variant="ghost" size="xs" :disabled="media.subtitleAction === subtitle.url" @click="media.previewOnlineSubtitle(subtitle)">预览</UButton>
                      <UButton color="primary" variant="soft" size="xs" icon="i-heroicons-arrow-down-tray-20-solid" :disabled="media.subtitleAction === subtitle.url" @click="media.downloadOnlineSubtitle(subtitle)" />
                    </div>
                  </div>
                </div>
              </div>
              <!-- Whisper tab -->
              <div v-else class="p-4 rounded-lg bg-(--ui-bg-elevated) border border-(--ui-border)">
                <div class="space-y-3">
                  <ol class="text-xs text-(--ui-text-muted) space-y-1 list-decimal list-inside">
                    <li>切分音频 / VAD</li>
                    <li>Anime-Whisper 主转写</li>
                    <li>large-v3 fallback</li>
                    <li>Qwen fallback / 对齐补救</li>
                  </ol>
                  <div class="flex items-center justify-between">
                    <span class="text-sm">音频预处理</span>
                    <USwitch :model-value="whisperPreprocess" @update:model-value="media.whisperPreprocess = $event" />
                  </div>
                  <div class="flex items-center justify-between">
                    <span class="text-sm">生成后翻译中文</span>
                    <USwitch :model-value="whisperTranslate" @update:model-value="media.whisperTranslate = $event" />
                  </div>
                  <div class="flex justify-end pt-2">
                    <UButton color="primary" icon="i-heroicons-sparkles-20-solid" :loading="media.taskSubmitting === 'whisper' || whisperSubmitting" @click="emit('submit-whisper')">提交字幕生成任务</UButton>
                  </div>
                  <div v-if="media.taskMessage" class="text-xs text-emerald-400">{{ media.taskMessage }}</div>
                  <div v-if="media.taskError" class="text-xs text-red-400">{{ media.taskError }}</div>
                </div>
              </div>
            </div>
          </template>
        </div>

        <!-- Subtitle Preview (inline within subtitle panel) -->
        <div v-if="media.subtitlePreview" class="fixed inset-0 z-[51] flex items-center justify-center bg-black/90" @click.self="media.closeSubtitlePreview()">
          <div class="relative w-full max-w-2xl mx-4 bg-(--ui-bg) rounded-lg shadow-2xl overflow-hidden">
            <div class="flex items-center justify-between p-4 border-b border-(--ui-border)">
              <div class="min-w-0 pr-4">
                <h3 class="text-base font-semibold truncate" :title="media.subtitlePreview?.filename">{{ media.subtitlePreview?.filename }}</h3>
                <p class="text-sm text-(--ui-text-muted) mt-0.5">{{ media.subtitlePreview?.source === 'local' ? '本地字幕' : '在线字幕' }}</p>
              </div>
              <UButton color="neutral" variant="ghost" icon="i-heroicons-x-mark-20-solid" class="shrink-0" @click="media.closeSubtitlePreview()" />
            </div>
            <div class="max-h-[60vh] overflow-y-auto p-4 bg-(--ui-bg-elevated)">
              <pre class="text-xs font-mono whitespace-pre-wrap break-all">{{ media.subtitlePreview?.content }}</pre>
            </div>
            <div class="flex justify-end p-4 border-t border-(--ui-border)">
              <UButton color="primary" @click="media.closeSubtitlePreview()">关闭</UButton>
            </div>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>
