<script setup lang="ts">
import { ref, watch } from 'vue'
import BaseButton from './BaseButton.vue'
import BaseProgress from './BaseProgress.vue'
import { useSubtitles } from '../composables/useSubtitles'
import { useWhisper } from '../composables/useWhisper'
import { useI18n } from '../composables/useI18n'
import SubtitlePreview from './SubtitlePreview.vue'
import api from '../api'

const { t } = useI18n()

const props = defineProps<{
  open: boolean
  videoPath: string
  videoId: string
}>()

const emit = defineEmits<{
  close: []
  refreshLocal: []
}>()

// Subtitle composable
const {
  subtitles,
  onlineSubtitles,
  loadingSubtitles,
  searchingOnline,
  subtitleError,
  videoCodeForSearch,
  subtitlePreviewContent,
  subtitlePreviewFilename,
  loadingSubtitlePreview,
  fetchSubtitles,
  searchOnlineSubtitles,
  downloadOnlineSubtitle,
  previewOnlineSubtitle,
  previewLocalSubtitle,
  deleteSubtitle,
  clearSubtitles,
  formatFileSize,
} = useSubtitles()

// Whisper composable
const {
  whisperStatus,
  whisperProgress,
  whisperRunning,
  startWhisperTask,
} = useWhisper()

// Whisper settings
const whisperModel = ref('anime-whisper')
const whisperPipeline = ref('ensemble')
const whisperMergeStrategy = ref('smart_merge')
const whisperLanguage = ref('ja')
const whisperSensitivity = ref('balanced')
const whisperDefaultsLoaded = ref(false)

// Tabs
const subtitleTab = ref<'local' | 'search' | 'whisper'>('local')

// Load whisper defaults
async function loadWhisperDefaults() {
  if (whisperDefaultsLoaded.value) return
  try {
    const resp = await fetch('/api/settings')
    const data = await resp.json()
    if (data.whisper) {
      whisperModel.value = data.whisper.model || 'anime-whisper'
      whisperPipeline.value = data.whisper.pipeline_mode || 'ensemble'
      whisperMergeStrategy.value = data.whisper.merge_strategy || 'smart_merge'
      whisperLanguage.value = data.whisper.language || 'ja'
      whisperSensitivity.value = data.whisper.sensitivity || 'balanced'
      whisperDefaultsLoaded.value = true
    }
  } catch (e) {
    console.error('Failed to load Whisper defaults:', e)
  }
}

// Watch for panel open
watch(() => props.open, async (isOpen) => {
  if (isOpen && props.videoPath) {
    await Promise.all([
      loadWhisperDefaults(),
      fetchSubtitles(props.videoPath),
    ])
    subtitleTab.value = 'local'
  } else {
    clearSubtitles()
  }
})

// Watch video path change
watch(() => props.videoPath, async (newPath) => {
  if (newPath && props.open) {
    await fetchSubtitles(newPath)
  }
})

function handleClose() {
  clearSubtitles()
  emit('close')
}

async function handleSearchOnline() {
  if (!props.videoPath) return
  await searchOnlineSubtitles(props.videoPath)
}

async function handleDownloadSubtitle(url: string, filename: string) {
  const success = await downloadOnlineSubtitle(url, props.videoPath)
  if (success) {
    subtitleTab.value = 'local'
    emit('refreshLocal')
  }
}

async function handlePreviewOnline(url: string, filename: string) {
  await previewOnlineSubtitle(url, filename)
}

async function handlePreviewLocal(path: string, filename: string) {
  await previewLocalSubtitle(path, filename)
}

async function handleDeleteSubtitle(path: string, filename: string) {
  await deleteSubtitle(path, filename)
}

async function handleStartWhisper() {
  await startWhisperTask({
    video_path: props.videoPath,
    model: whisperModel.value,
    pipeline_mode: whisperPipeline.value,
    merge_strategy: whisperMergeStrategy.value,
    language: whisperLanguage.value,
    sensitivity: whisperSensitivity.value,
  })
  emit('refreshLocal')
}
</script>

<template>
  <Teleport to="body">
    <Transition name="panel">
      <div
        v-if="open"
        class="fixed inset-0 z-50 flex justify-end"
      >
        <!-- Backdrop -->
        <div
          class="absolute inset-0 bg-bg-void/80 backdrop-blur-sm"
          @click="handleClose"
        ></div>

        <!-- Panel -->
        <div class="relative bg-bg-surface border-l border-border-default flex flex-col overflow-hidden shadow-2xl h-full w-full max-w-md">
          <!-- Header -->
          <div class="flex items-center justify-between px-6 py-4 border-b border-border-subtle flex-shrink-0">
            <h2 class="font-display font-semibold text-lg text-text-primary">
              {{ t('subtitle.local') }}
            </h2>
            <button
              @click="handleClose"
              class="text-text-muted hover:text-text-primary transition-colors p-1"
            >
              <svg xmlns="http://www.w3.org/2000/svg" class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          <!-- Video Path -->
          <div class="px-6 py-2 bg-bg-elevated text-xs text-text-muted truncate border-b border-border-subtle flex-shrink-0">
            {{ videoPath }}
          </div>

          <!-- Tabs -->
          <div class="flex border-b border-border-subtle px-6 flex-shrink-0">
            <button
              v-for="tab in ['local', 'search', 'whisper'] as const"
              :key="tab"
              @click="subtitleTab = tab; tab === 'search' && handleSearchOnline()"
              :class="[
                'px-4 py-3 text-sm font-medium transition-colors border-b-2 -mb-px',
                subtitleTab === tab
                  ? 'text-accent-cyan border-accent-cyan'
                  : 'text-text-secondary hover:text-text-primary border-transparent'
              ]"
            >
              {{ t(`subtitle.${tab}`) }}
              <span v-if="tab === 'local'">({{ subtitles.length }})</span>
            </button>
          </div>

          <!-- Content -->
          <div class="flex-1 overflow-y-auto p-6">
            <!-- Local Tab -->
            <div v-if="subtitleTab === 'local'">
              <!-- Loading -->
              <div v-if="loadingSubtitles" class="flex items-center justify-center py-8">
                <div class="animate-spin w-8 h-8 border-2 border-accent-cyan border-t-transparent rounded-full"></div>
              </div>

              <!-- Error -->
              <div v-else-if="subtitleError" class="text-status-error text-center py-4">
                {{ subtitleError }}
              </div>

              <!-- Empty -->
              <div v-else-if="subtitles.length === 0" class="text-text-muted text-center py-8">
                {{ t('subtitle.noResults') }}
              </div>

              <!-- List -->
              <div v-else class="space-y-2">
                <div
                  v-for="sub in subtitles"
                  :key="sub.path"
                  class="flex items-center justify-between bg-bg-elevated rounded-lg p-3 hover:bg-bg-hover transition-colors"
                >
                  <div class="flex-1 min-w-0">
                    <p class="text-text-primary text-sm font-medium truncate">{{ sub.filename }}</p>
                    <p class="text-text-muted text-xs truncate">{{ sub.path }}</p>
                    <p class="text-text-muted text-xs">{{ formatFileSize(sub.size) }}</p>
                  </div>
                  <div class="flex gap-2 ml-4">
                    <BaseButton size="sm" variant="secondary" @click="handlePreviewLocal(sub.path, sub.filename)">
                      {{ t('subtitle.preview') }}
                    </BaseButton>
                    <BaseButton size="sm" variant="danger" @click="handleDeleteSubtitle(sub.path, sub.filename)">
                      {{ t('common.delete') }}
                    </BaseButton>
                  </div>
                </div>
              </div>
            </div>

            <!-- Search Tab -->
            <div v-if="subtitleTab === 'search'">
              <!-- Loading -->
              <div v-if="searchingOnline" class="flex items-center justify-center py-8">
                <div class="animate-spin w-8 h-8 border-2 border-accent-cyan border-t-transparent rounded-full"></div>
                <span class="ml-3 text-text-secondary">{{ t('common.loading') }}</span>
              </div>

              <!-- Error -->
              <div v-else-if="subtitleError" class="text-status-error text-center py-4">
                {{ subtitleError }}
              </div>

              <!-- Empty -->
              <div v-else-if="onlineSubtitles.length === 0" class="text-text-muted text-center py-8">
                <p>{{ t('subtitle.noResults') }}</p>
                <BaseButton variant="secondary" size="sm" @click="handleSearchOnline" class="mt-4">
                  重新搜索
                </BaseButton>
              </div>

              <!-- Results -->
              <div v-else class="space-y-2">
                <div
                  v-for="(sub, index) in onlineSubtitles"
                  :key="index"
                  class="flex items-center justify-between bg-bg-elevated rounded-lg p-3 hover:bg-bg-hover transition-colors"
                >
                  <div class="flex-1 min-w-0">
                    <p class="text-text-primary text-sm font-medium truncate">{{ sub.name }}</p>
                    <p class="text-text-muted text-xs">{{ t('whisper.language') }}: {{ sub.language }} | 来源: {{ sub.source }}</p>
                  </div>
                  <div class="flex gap-2 ml-4">
                    <BaseButton size="sm" variant="secondary" @click="handlePreviewOnline(sub.url, sub.name)">
                      {{ t('subtitle.preview') }}
                    </BaseButton>
                    <BaseButton size="sm" variant="success" @click="handleDownloadSubtitle(sub.url, sub.name)">
                      {{ t('subtitle.download') }}
                    </BaseButton>
                  </div>
                </div>
              </div>
            </div>

            <!-- Whisper Tab -->
            <div v-if="subtitleTab === 'whisper'">
              <div class="space-y-4">
                <!-- Model -->
                <div>
                  <label class="block text-sm font-medium text-text-secondary mb-2">{{ t('whisper.model') }}</label>
                  <select
                    v-model="whisperModel"
                    :disabled="whisperRunning"
                    class="w-full bg-bg-elevated border border-border-subtle text-text-primary rounded-lg px-3 py-2 focus:ring-2 focus:ring-accent-cyan focus:border-transparent"
                  >
                    <option value="anime-whisper">Anime-Whisper (推荐JAV)</option>
                    <option value="large-v3">Faster-Whisper Large v3</option>
                    <option value="large-v3-turbo">Faster-Whisper Large v3 Turbo</option>
                    <option value="medium">Faster-Whisper Medium</option>
                    <option value="small">Faster-Whisper Small</option>
                    <option value="base">Faster-Whisper Base</option>
                    <option value="tiny">Faster-Whisper Tiny</option>
                  </select>
                </div>

                <!-- Pipeline -->
                <div>
                  <label class="block text-sm font-medium text-text-secondary mb-2">{{ t('whisper.pipeline') }}</label>
                  <select
                    v-model="whisperPipeline"
                    :disabled="whisperRunning"
                    class="w-full bg-bg-elevated border border-border-subtle text-text-primary rounded-lg px-3 py-2 focus:ring-2 focus:ring-accent-cyan focus:border-transparent"
                  >
                    <option value="ensemble">两遍处理 + 智能合并 (推荐)</option>
                    <option value="single">单遍处理</option>
                  </select>
                </div>

                <!-- Merge Strategy -->
                <div v-if="whisperPipeline === 'ensemble'">
                  <label class="block text-sm font-medium text-text-secondary mb-2">{{ t('whisper.mergeStrategy') }}</label>
                  <select
                    v-model="whisperMergeStrategy"
                    :disabled="whisperRunning"
                    class="w-full bg-bg-elevated border border-border-subtle text-text-primary rounded-lg px-3 py-2 focus:ring-2 focus:ring-accent-cyan focus:border-transparent"
                  >
                    <option value="smart_merge">智能合并 (推荐)</option>
                    <option value="full_merge">合并所有</option>
                    <option value="pass1_primary">Pass1 为主</option>
                    <option value="pass2_primary">Pass2 为主</option>
                    <option value="longest">选择最长文本</option>
                  </select>
                </div>

                <!-- Language -->
                <div>
                  <label class="block text-sm font-medium text-text-secondary mb-2">{{ t('whisper.language') }}</label>
                  <select
                    v-model="whisperLanguage"
                    :disabled="whisperRunning"
                    class="w-full bg-bg-elevated border border-border-subtle text-text-primary rounded-lg px-3 py-2 focus:ring-2 focus:ring-accent-cyan focus:border-transparent"
                  >
                    <option value="ja">日语</option>
                    <option value="auto">自动检测</option>
                    <option value="en">英语</option>
                    <option value="zh">中文</option>
                  </select>
                </div>

                <!-- Sensitivity -->
                <div>
                  <label class="block text-sm font-medium text-text-secondary mb-2">{{ t('whisper.sensitivity') }}</label>
                  <select
                    v-model="whisperSensitivity"
                    :disabled="whisperRunning"
                    class="w-full bg-bg-elevated border border-border-subtle text-text-primary rounded-lg px-3 py-2 focus:ring-2 focus:ring-accent-cyan focus:border-transparent"
                  >
                    <option value="conservative">保守 (减少误识别)</option>
                    <option value="balanced">平衡 (推荐)</option>
                    <option value="aggressive">激进 (更多检测)</option>
                  </select>
                </div>

                <!-- Status -->
                <div v-if="whisperStatus" class="text-center py-2 rounded" :class="{
                  'text-accent-cyan': whisperStatus.includes('提交') || whisperStatus.includes('创建'),
                  'text-status-success': whisperStatus.includes('完成'),
                  'text-status-error': whisperStatus.includes('失败') || whisperStatus.includes('错误')
                }">
                  {{ whisperStatus }}
                </div>

                <!-- Progress -->
                <BaseProgress
                  v-if="whisperRunning || whisperProgress > 0"
                  :value="whisperProgress"
                  variant="cyan"
                  :show-label="true"
                />

                <!-- Start Button -->
                <BaseButton
                  v-if="!whisperRunning"
                  variant="primary"
                  class="w-full"
                  @click="handleStartWhisper"
                >
                  {{ t('whisper.start') }}
                </BaseButton>
              </div>
            </div>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>

  <!-- Subtitle Preview -->
  <SubtitlePreview
    :filename="subtitlePreviewFilename"
    :content="subtitlePreviewContent"
    :loading="loadingSubtitlePreview"
    @close="() => {}"
  />
</template>

<style scoped>
.panel-enter-active {
  transition: opacity 0.25s ease;
}
.panel-enter-active .bg-bg-surface {
  transition: transform 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}
.panel-enter-from {
  opacity: 0;
}
.panel-enter-from .bg-bg-surface {
  transform: translateX(100%);
}
.panel-leave-active {
  transition: opacity 0.2s ease;
}
.panel-leave-to {
  opacity: 0;
}
.panel-leave-from .bg-bg-surface {
  transform: translateX(100%);
}
</style>
