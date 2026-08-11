<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import VuiButton from '../ui/Button/VuiButton.vue'
import VuiSubmitButton from '../ui/SubmitButton.vue'
import VuiBadge from '../ui/Badge/VuiBadge.vue'
import VisionTabs from '../ui/Tabs.vue'
import { buildWhisperProfileWithTranslation, formatWhisperTranslationSummary, getWhisperModelBackendMeta, getWhisperSelectableStrategyPresentation, isDirectWhisperTranslationBackend, resolveWhisperEditableDefaults, type WhisperModelBackend, type WhisperRuntimeTier } from '../../composables/useWhisperProfiles'
import PanelHeader from './panels/PanelHeader.vue'
import FilePathSelector from './panels/FilePathSelector.vue'
import { useSubtitles } from '../../composables/useSubtitles'
import { useWhisper } from '../../composables/useWhisper'
import { useI18n } from '../../composables/useI18n'
import { useToast } from '../../composables/useToast'
import { useJobNavigation } from '../../composables/useJobNavigation'
import SubtitlePreview from './SubtitlePreview.vue'
import api from '../../api'
import type { TranslateSrtTaskCreateResponse } from '../../api/types'
import { useJobsStore } from '../../stores/jobs'

const { t, i18nVersion } = useI18n()
const toast = useToast()
const jobsStore = useJobsStore()
const { openJobsFocus } = useJobNavigation()
const panelTitle = computed(() => t('detail.openSubtitle'))

const props = defineProps<{
  open: boolean
  detail: import('../../api/types').MediaItemDetail | null
  loading?: boolean
  initialSelectedPath?: string
}>()

// Convenience ref to detail
const detail = computed(() => props.detail)

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
  closeSubtitlePreview,
} = useSubtitles()

// Whisper composable
const {
  whisperTaskId,
  whisperStatus,
  whisperQueuedHint,
  whisperProgress,
  whisperRunning,
  whisperFeedbackVisible,
  whisperFeedbackKind,
  startWhisperTask,
  openQueuedJob,
} = useWhisper()

// Whisper settings
const whisperDefaultsLoaded = ref(false)
const whisperDefaultRuntimeTier = ref<WhisperRuntimeTier>('gpu_standard')
const whisperDefaultModelBackend = ref<WhisperModelBackend>('chickenrice-zh')
const whisperDefaultVadBackend = ref('energy')
const whisperDefaultTimingRefiner = ref('none')

// Translate settings (for local SRT translation feature)
const whisperTranslateEnabled = ref(true)
const whisperTranslateTo = ref('zh')
const whisperTranslateModel = ref('gpt-4o-mini')
const whisperTranslateStyle = ref('adult_explicit')
const whisperTranslateBaseUrl = ref('https://api.openai.com/v1')
const whisperTranslateApiKey = ref('')
const whisperSavedTranslateEnabled = ref(true)
const whisperSavedTranslateTo = ref('zh')
const whisperSavedTranslateModel = ref('gpt-4o-mini')
const whisperSavedTranslateStyle = ref('adult_explicit')
const whisperSavedTranslateBaseUrl = ref('https://api.openai.com/v1')
const whisperSavedTranslateApiKey = ref('')

// Local SRT translation loading state
const translatingSubtitle = ref('')


// Tabs
const subtitleTab = ref<'local' | 'search' | 'whisper'>('local')

// Translation strings as computed (reactive to currentLang)
const tabLabels = computed(() => {
  void i18nVersion.value
  return {
    local: t('subtitle.local'),
    search: t('subtitle.search'),
    whisper: t('subtitle.whisper'),
  }
})
const noResultsLabel = computed(() => {
  void i18nVersion.value
  return t('subtitle.noResults')
})
const previewLabel = computed(() => {
  void i18nVersion.value
  return t('subtitle.preview')
})
const deleteLabel = computed(() => {
  void i18nVersion.value
  return t('common.delete')
})
const loadingLabel = computed(() => {
  void i18nVersion.value
  return t('common.loading')
})
const downloadLabel = computed(() => {
  void i18nVersion.value
  return t('subtitle.download')
})
const rescanLabel = computed(() => {
  void i18nVersion.value
  return t('subtitle.rescan')
})
const sourceLabel = computed(() => {
  void i18nVersion.value
  return t('subtitle.source')
})
function displaySubtitleSource(sub: { source?: string; source_key?: string }) {
  if (sub.source_key === 'local-subtitle-library' || sub.source_key === 'local_library') {
    return t('subtitle.sourceName.localSubtitleLibrary')
  }
  if (sub.source_key === 'xunlei-subtitle' || sub.source_key === 'xunlei') {
    return t('subtitle.sourceName.xunlei')
  }
  if (sub.source_key === 'mteam-plugin' || sub.source_key === 'mteam') {
    return t('subtitle.sourceName.mteam')
  }
  return sub.source || ''
}
const whisperLangLabel = computed(() => {
  void i18nVersion.value
  return t('whisper.language')
})
const whisperSubmitButtonLabel = computed(() => {
  if (whisperFeedbackKind.value === 'queued') return t('whisper.status.queued')
  if (whisperFeedbackKind.value === 'error') return whisperStatus.value
  return whisperStatus.value || t('whisper.status.submitting')
})
const whisperSubmitStatus = computed<'idle' | 'running' | 'success' | 'error'>(() => {
  if (!whisperFeedbackVisible.value) return 'idle'
  if (whisperFeedbackKind.value === 'queued') return 'success'
  if (whisperFeedbackKind.value === 'error') return 'error'
  return 'running'
})

const whisperDefaultMeta = computed(() => getWhisperModelBackendMeta(whisperDefaultModelBackend.value))
const whisperTranslationSummary = computed(() => formatWhisperTranslationSummary(t, {
  translateEnabled: whisperTranslateEnabled.value,
  translateTo: whisperTranslateTo.value,
  translateModel: whisperTranslateModel.value,
  directTranslate: isDirectWhisperTranslationBackend(whisperDefaultModelBackend.value),
}))
const whisperHasRunOverrides = computed(() => (
  whisperTranslateEnabled.value !== whisperSavedTranslateEnabled.value
))
const whisperStrategyPresentation = computed(() => getWhisperSelectableStrategyPresentation(t, whisperDefaultModelBackend.value))
const whisperDefaultSummaryClass = computed(() => whisperStrategyPresentation.value.summaryClass)
const whisperOpenJobsLabel = computed(() => t('whisper.status.viewJobs'))
const whisperTranslateRunningLabel = computed(() => t('subtitle.translateRunning'))
const whisperTranslateActionLabel = computed(() => t('subtitle.aiTranslate'))
const whisperFlowSteps = computed(() => {
  if (whisperDefaultModelBackend.value === 'anime-whisper') {
    return [
      { title: 'Smart VAD 分块', desc: '按语音活动切分音频，控制每段长度，降低长音频污染。' },
      { title: 'Anime-Whisper 转写', desc: '使用 Anime-Whisper 生成日语字幕，适合作为对照模型。' },
      { title: '字幕安全整理', desc: '整理空段、重叠时间轴与过长片段，生成 ja.srt。' },
      { title: '可选翻译', desc: '如开启翻译，再提交 OpenAI-Compatible 翻译任务生成中文。' },
    ]
  }
  if (whisperDefaultModelBackend.value === 'large-v3') {
    return [
      { title: 'Smart VAD 分块', desc: '按语音活动切分音频，控制每段长度，降低长音频污染。' },
      { title: 'Faster-Whisper large-v3 转写', desc: '使用 large-v3 生成日语字幕，可再衔接翻译任务。' },
      { title: '字幕安全整理', desc: '整理空段、重叠时间轴与过长片段，生成 ja.srt。' },
      { title: '可选翻译', desc: '如开启翻译，再提交 OpenAI-Compatible 翻译任务生成中文。' },
    ]
  }
  return [
    { title: 'Smart VAD 分块', desc: '先按语音活动切段，目标约 30 秒，避免整段长音频直接进模型。' },
    { title: 'ChickenRice 日中直出', desc: '使用 faster-whisper 直译模型从日语音频生成中文字幕。' },
    { title: '字幕安全整理', desc: '整理空段、重叠时间轴、相邻短段与过长片段，生成 zh.srt。' },
  ]
})
// whisperTranslateProviderOptions removed — unified OpenAI-compatible API, no provider concept (translate fields kept for local SRT translation feature)

// Selected file path (for multi-file work: current + siblings)
const selectedPath = ref('')

// When selected path changes, re-fetch subtitles
watch(selectedPath, async (newPath) => {
  if (newPath && props.open) {
    await fetchSubtitles(newPath)
  }
})

// Sibling paths from detail
const siblingPaths = computed(() => {
  return props.detail?.siblings?.filter(s => s.file_path) || undefined
})

function resetWhisperRunOverrides() {
  whisperTranslateEnabled.value = whisperSavedTranslateEnabled.value
  whisperTranslateTo.value = whisperSavedTranslateTo.value
  whisperTranslateModel.value = whisperSavedTranslateModel.value
  whisperTranslateStyle.value = whisperSavedTranslateStyle.value
  whisperTranslateBaseUrl.value = whisperSavedTranslateBaseUrl.value
  whisperTranslateApiKey.value = whisperSavedTranslateApiKey.value
}

// Load whisper defaults
async function loadWhisperDefaults() {
  if (whisperDefaultsLoaded.value) {
    resetWhisperRunOverrides()
    return
  }
  try {
    const resp = await api.get('/settings')
    if (resp.data.whisper) {
      const defaults = resolveWhisperEditableDefaults(resp.data.whisper)
      whisperDefaultRuntimeTier.value = defaults.runtime_tier
      whisperDefaultModelBackend.value = defaults.model_backend
      whisperDefaultVadBackend.value = defaults.vad_backend
      whisperDefaultTimingRefiner.value = defaults.timing_refiner
      whisperTranslateEnabled.value = defaults.translate_enabled
      whisperTranslateTo.value = defaults.translate_to
      whisperTranslateModel.value = defaults.translate_model
      whisperTranslateStyle.value = defaults.translate_style
      whisperTranslateBaseUrl.value = defaults.translate_base_url
      whisperTranslateApiKey.value = defaults.translate_api_key
      whisperSavedTranslateEnabled.value = whisperTranslateEnabled.value
      whisperSavedTranslateTo.value = whisperTranslateTo.value
      whisperSavedTranslateModel.value = whisperTranslateModel.value
      whisperSavedTranslateStyle.value = whisperTranslateStyle.value
      whisperSavedTranslateBaseUrl.value = whisperTranslateBaseUrl.value
      whisperSavedTranslateApiKey.value = whisperTranslateApiKey.value
      resetWhisperRunOverrides()
      whisperDefaultsLoaded.value = true
    }
  } catch (e) {
    console.error('Failed to load Whisper defaults:', e)
  }
}

// Watch for panel open AND detail arriving
watch([() => props.open, () => props.detail, () => props.initialSelectedPath], async ([isOpen, detail, initialSelectedPath]) => {
  if (isOpen && detail?.file_path) {
    const targetPath = initialSelectedPath || detail.file_path
    selectedPath.value = targetPath
    await Promise.all([
      loadWhisperDefaults(),
      fetchSubtitles(targetPath),
    ])
    subtitleTab.value = 'local'
  } else if (!isOpen) {
    clearSubtitles()
  }
}, { immediate: true })

// Trigger search when switching to search tab
watch(subtitleTab, (tab) => {
  if (tab === 'search') {
    handleSearchOnline()
  }
})

function handleClose() {
  clearSubtitles()
  emit('close')
}

async function handleSearchOnline() {
  if (!selectedPath.value) return
  await searchOnlineSubtitles(selectedPath.value)
}

async function handleDownloadSubtitle(url: string, _filename: string, source?: string) {
  const matchedSubtitle = onlineSubtitles.value.find(sub => sub.url === url && sub.name === _filename)
  const sourceType = matchedSubtitle?.source_type
  const sourceKey = matchedSubtitle?.source_key
  const success = await downloadOnlineSubtitle(url, selectedPath.value, source, sourceType, sourceKey)
  if (success) {
    subtitleTab.value = 'local'
    emit('refreshLocal')
  }
}

async function handlePreviewOnline(url: string, filename: string) {
  const matchedSubtitle = onlineSubtitles.value.find(sub => sub.url === url && sub.name === filename)
  await previewOnlineSubtitle(url, filename, matchedSubtitle?.source_key)
}

async function handlePreviewLocal(path: string, filename: string) {
  await previewLocalSubtitle(path, filename)
}

function isLocalLibrarySubtitle(sub: { source?: string; source_type?: string; source_key?: string }) {
  return sub.source_type === 'local_library' || sub.source_key === 'local-subtitle-library' || sub.source_key === 'local_library'
}

async function handleTranslateLocal(path: string, filename: string) {
  translatingSubtitle.value = filename
  try {
    const resp = await api.post<TranslateSrtTaskCreateResponse>('/whisper/translate/srt', {
      srt_path: path,
      target_lang: whisperTranslateTo.value || 'zh',
      model: whisperTranslateModel.value || 'gpt-4o-mini',
      style: whisperTranslateStyle.value || 'adult_explicit',
      base_url: whisperTranslateBaseUrl.value || 'https://api.openai.com/v1',
      api_key: whisperTranslateApiKey.value || '',
    })
    await jobsStore.fetchJobs()
    toast.success(t('subtitle.translateTaskCreated'))
    await openJobsFocus({ jobId: resp.data?.task_id })
    emit('refreshLocal')
  } catch (e: any) {
    console.error('Translation failed', e)
    toast.error(t('common.errorWithDetail', { detail: e?.response?.data?.detail || e.message || t('common.error') }))
  } finally {
    translatingSubtitle.value = ''
  }
}

async function handleDeleteSubtitle(path: string, filename: string) {
  await deleteSubtitle(path, filename)
}

async function handleStartWhisper(modelBackend: WhisperModelBackend = whisperDefaultModelBackend.value) {
  const payload = buildWhisperProfileWithTranslation(modelBackend, {
    runtime_tier: whisperDefaultRuntimeTier.value,
    vad_backend: whisperDefaultVadBackend.value,
    timing_refiner: whisperDefaultTimingRefiner.value,
    translate_enabled: whisperTranslateEnabled.value,
    translate_to: whisperTranslateTo.value,
    translate_base_url: whisperTranslateBaseUrl.value,
    translate_api_key: whisperTranslateApiKey.value,
    translate_model: whisperTranslateModel.value,
    translate_style: whisperTranslateStyle.value,
  })

  await startWhisperTask({
    video_path: selectedPath.value,
    ...payload,
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
        <div class="relative bg-bg-surface border-l border-border-default flex flex-col overflow-hidden shadow-2xl h-full w-full lg:w-[min(50vw,960px)]">
          <!-- Loading overlay -->
          <div v-if="loading" class="absolute inset-0 z-10 flex items-center justify-center bg-bg-surface/80 backdrop-blur-sm">
            <div class="animate-spin w-8 h-8 border-2 border-accent-cyan border-t-transparent rounded-full"></div>
          </div>

          <!-- Scrollable wrapper -->
          <div class="flex-1 overflow-y-auto p-4 space-y-4 relative">

            <div class="panel-topbar">
              <span class="panel-topbar__title">{{ panelTitle }}</span>
              <button
                @click="handleClose"
                :title="t('common.close')"
                :aria-label="t('common.close')"
                class="panel-topbar__close"
              >
                <svg xmlns="http://www.w3.org/2000/svg" class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            <!-- Shared Header: backdrop + title + tagline + actors -->
            <PanelHeader :detail="detail" :show-play="false" />

            <!-- Video Path / Folder Selector -->
            <FilePathSelector
              :file-path="props.detail?.file_path"
              :sibling-paths="siblingPaths"
              v-model="selectedPath"
            />

            <!-- Tabs -->
            <VisionTabs v-model="subtitleTab" :tabs="[
              { key: 'local', label: tabLabels.local },
              { key: 'search', label: tabLabels.search },
              { key: 'whisper', label: tabLabels.whisper },
            ]" :compact="true" />

            <!-- Content -->
            <div class="subtitle-panel-content pb-16">
            <!-- Local Tab -->
            <div v-if="subtitleTab === 'local'" class="subtitle-tab-pane">
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
                {{ noResultsLabel }}
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
                    <VuiButton size="small" variant="outlined" color="secondary" @click="handlePreviewLocal(sub.path, sub.filename)">
                      {{ previewLabel }}
                    </VuiButton>
                    <VuiButton
                      size="small"
                      variant="outlined"
                      color="warning"
                      :loading="translatingSubtitle === sub.filename"
                      :disabled="translatingSubtitle === sub.filename"
                      @click="handleTranslateLocal(sub.path, sub.filename)"
                    >
                      {{ translatingSubtitle === sub.filename ? whisperTranslateRunningLabel : whisperTranslateActionLabel }}
                    </VuiButton>
                    <VuiButton size="small" variant="outlined" color="error" @click="handleDeleteSubtitle(sub.path, sub.filename)">
                      {{ deleteLabel }}
                    </VuiButton>
                  </div>
                </div>
              </div>
            </div>

            <!-- Search Tab -->
            <div v-if="subtitleTab === 'search'" class="subtitle-tab-pane">
              <!-- Loading -->
              <div v-if="searchingOnline" class="flex items-center justify-center py-8">
                <div class="animate-spin w-8 h-8 border-2 border-accent-cyan border-t-transparent rounded-full"></div>
                <span class="ml-3 text-text-secondary">{{ loadingLabel }}</span>
              </div>

              <!-- Error -->
              <div v-else-if="subtitleError" class="text-status-error text-center py-4">
                {{ subtitleError }}
              </div>

              <!-- Empty -->
              <div v-else-if="onlineSubtitles.length === 0" class="text-text-muted text-center py-8">
                <p>{{ noResultsLabel }}</p>
                <VuiButton variant="outlined" color="secondary" size="small" @click="handleSearchOnline" class="mt-4">
                  {{ rescanLabel }}
                </VuiButton>
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
                    <p class="text-text-muted text-xs">{{ whisperLangLabel }}: {{ sub.language }} | {{ sourceLabel }}: {{ displaySubtitleSource(sub) }}</p>
                  </div>
                  <div class="flex gap-2 ml-4">
                    <VuiButton size="small" variant="outlined" color="secondary" @click="isLocalLibrarySubtitle(sub) ? handlePreviewLocal(sub.url, sub.name) : handlePreviewOnline(sub.url, sub.name)">
                      {{ previewLabel }}
                    </VuiButton>
                    <VuiButton size="small" variant="gradient" color="success" @click="handleDownloadSubtitle(sub.url, sub.name, sub.source)">
                      {{ downloadLabel }}
                    </VuiButton>
                  </div>
                </div>
              </div>
            </div>

            <!-- Whisper Tab -->
            <div v-if="subtitleTab === 'whisper'" class="subtitle-tab-pane">
              <div class="space-y-3">
                <div class="ui-card whisper-default-summary" :class="whisperDefaultSummaryClass">
                  <div class="whisper-default-summary__head">
                    <div>
                      <div class="whisper-default-summary__headline">
                        <span>{{ t(whisperDefaultMeta.titleKey) }}</span>
                        <VuiBadge :color="whisperStrategyPresentation.badgeColor" variant="gradient" size="xs">{{ t(whisperDefaultMeta.badgeKey) }}</VuiBadge>
                      </div>
                      <p class="whisper-default-summary__desc">实际执行链路按下列步骤提交；主流程固定启用，非直出模型可按本次任务追加翻译。</p>
                    </div>
                  </div>

                  <div class="whisper-todo-flow">
                    <div
                      v-for="step in whisperFlowSteps"
                      :key="step.title"
                      class="whisper-todo-step whisper-todo-step--fixed is-enabled"
                    >
                      <input type="checkbox" checked disabled />
                      <span class="whisper-todo-step__mark"></span>
                      <span class="whisper-todo-step__body">
                        <span class="whisper-todo-step__title">{{ step.title }}</span>
                        <span class="whisper-todo-step__desc">{{ step.desc }}</span>
                      </span>
                    </div>

                    <label class="whisper-todo-step whisper-todo-step--optional" :class="{ 'is-enabled': whisperTranslateEnabled && !isDirectWhisperTranslationBackend(whisperDefaultModelBackend) }">
                      <input v-model="whisperTranslateEnabled" type="checkbox" :disabled="whisperRunning || isDirectWhisperTranslationBackend(whisperDefaultModelBackend)" />
                      <span class="whisper-todo-step__mark"></span>
                      <span class="whisper-todo-step__body">
                        <span class="whisper-todo-step__title">{{ isDirectWhisperTranslationBackend(whisperDefaultModelBackend) ? '直出中文字幕' : '翻译成中文' }}</span>
                        <span class="whisper-todo-step__desc">{{ isDirectWhisperTranslationBackend(whisperDefaultModelBackend) ? 'ChickenRice 已在识别阶段直接输出中文，不再追加大模型翻译。' : '可选。生成 ja.srt 后继续提交翻译，当前：' + whisperTranslationSummary }}</span>
                      </span>
                    </label>
                  </div>

                  <div class="whisper-default-summary__meta">
                    <span v-if="whisperHasRunOverrides" class="whisper-default-summary__chip whisper-default-summary__chip--info">{{ t('subtitle.whisperRunOverrideActive') }}</span>
                  </div>
                  <p v-if="whisperQueuedHint" class="whisper-default-summary__hint">{{ whisperQueuedHint }}</p>

                  <div class="whisper-default-summary__action whisper-default-summary__action--bottom">
                    <VuiSubmitButton
                      full
                      size="lg"
                      :status="whisperSubmitStatus"
                      :progress="whisperFeedbackVisible ? whisperProgress : 0"
                      :disabled="whisperRunning"
                      idle-label="任务提交"
                      :running-label="whisperSubmitButtonLabel"
                      :success-label="whisperSubmitButtonLabel"
                      :error-label="whisperSubmitButtonLabel"
                      :title="whisperTaskId ? `#${whisperTaskId}` : whisperSubmitButtonLabel"
                      @click="handleStartWhisper(whisperDefaultModelBackend)"
                    />
                  </div>
                  <VuiButton
                    v-if="whisperFeedbackKind === 'queued' && whisperTaskId"
                    size="small"
                    variant="outlined"
                    color="secondary"
                    class="w-full whisper-open-jobs-button"
                    @click="openQueuedJob"
                  >
                    {{ whisperOpenJobsLabel }}
                  </VuiButton>
                </div>

              </div>
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
    @close="closeSubtitlePreview"
  />
</template>

<style scoped>
.panel-topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
}

.panel-topbar__title {
  display: inline-flex;
  align-items: center;
  min-height: 1.5rem;
  font-size: 0.72rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--color-text-muted);
}

.panel-topbar__close {
  width: 2.1rem;
  height: 2.1rem;
  flex: none;
  border-radius: 0.7rem;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: var(--color-text-secondary);
  background: var(--color-bg-elevated);
  border: 1px solid var(--color-border-default);
  transition: color 0.16s ease, background 0.16s ease, border-color 0.16s ease, transform 0.16s ease;
}

.panel-topbar__close:hover {
  color: var(--color-text-primary);
  background: var(--color-bg-hover);
  border-color: var(--color-border-strong);
  transform: translateY(-1px);
}

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

.subtitle-panel-content {
  display: flex;
  flex-direction: column;
  gap: 0.875rem;
}

.subtitle-tab-pane {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.whisper-submit-button {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  min-height: 2.5rem;
  padding: 0.5rem 1rem;
  border-radius: var(--radius-button);
  overflow: hidden;
  border: 1px solid rgba(0, 117, 255, 0.32);
  background: rgba(0, 117, 255, 0.16);
  box-shadow: 0 4px 6px -1px rgba(0, 117, 255, 0.2), 0 2px 4px -1px rgba(0, 117, 255, 0.12);
}

.whisper-submit-button--queued {
  border-color: rgba(34, 197, 94, 0.28);
  background: rgba(34, 197, 94, 0.16);
  box-shadow: 0 4px 6px -1px rgba(34, 197, 94, 0.18), 0 2px 4px -1px rgba(34, 197, 94, 0.1);
}

.whisper-submit-button--queued {
  border-color: rgba(34, 197, 94, 0.28);
  background: rgba(34, 197, 94, 0.16);
  box-shadow: 0 4px 6px -1px rgba(34, 197, 94, 0.18), 0 2px 4px -1px rgba(34, 197, 94, 0.1);
}

.whisper-submit-button--error {
  border-color: rgba(239, 68, 68, 0.3);
  background: rgba(239, 68, 68, 0.14);
  box-shadow: 0 4px 6px -1px rgba(239, 68, 68, 0.14), 0 2px 4px -1px rgba(239, 68, 68, 0.08);
}

.whisper-submit-button__fill {
  position: absolute;
  inset: 0 auto 0 0;
  background: linear-gradient(90deg, rgba(0, 117, 255, 0.96), rgba(57, 147, 254, 0.92));
  transition: width 0.22s ease;
}

.whisper-submit-button--queued .whisper-submit-button__fill {
  width: 100% !important;
  background: linear-gradient(90deg, rgba(34, 197, 94, 0.96), rgba(74, 222, 128, 0.92));
}

.whisper-submit-button__label {
  position: relative;
  z-index: 1;
  display: block;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-family: var(--font-display);
  font-size: 0.75rem;
  font-weight: var(--font-weight-bold);
  line-height: 1;
  letter-spacing: 0.5px;
  text-transform: uppercase;
  color: #fff;
}

.whisper-submit-button--error .whisper-submit-button__label {
  text-transform: none;
  letter-spacing: 0;
  font-size: 0.8125rem;
}

.whisper-todo-flow {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 0.16rem;
}

.whisper-todo-flow::before {
  content: '';
  position: absolute;
  left: 1.035rem;
  top: 2rem;
  bottom: 2rem;
  width: 1px;
  background: rgba(255, 255, 255, 0.09);
}

.whisper-todo-step {
  --node-color: rgba(255, 255, 255, 0.26);
  --node-bg: rgb(31, 36, 62);
  --node-ring: rgba(255, 255, 255, 0.08);
  position: relative;
  display: grid;
  grid-template-columns: 2.05rem minmax(0, 1fr);
  align-items: start;
  gap: 0.48rem;
  padding: 0.42rem 0.25rem;
  border: 1px solid transparent;
  border-radius: 0.7rem;
  background: transparent;
}

.whisper-todo-step::before,
.whisper-todo-step::after {
  content: '';
  position: absolute;
  left: 1.035rem;
  width: 1px;
  background: rgba(255, 255, 255, 0.09);
  transform: translateX(-0.5px);
}

.whisper-todo-step::before {
  top: 0;
  height: 0.64rem;
}

.whisper-todo-step::after {
  top: 1.78rem;
  bottom: 0;
}

.whisper-todo-step:first-child::before,
.whisper-todo-step:last-child::after {
  display: none;
}

.whisper-todo-step input[type='checkbox'] {
  position: absolute;
  opacity: 0;
  pointer-events: none;
}

.whisper-todo-step__mark {
  position: relative;
  z-index: 1;
  box-sizing: border-box;
  width: 1.12rem;
  height: 1.12rem;
  margin: 0.22rem auto 0;
  border-radius: 9999px;
  border: 1px solid var(--node-color);
  background: var(--node-bg);
  box-shadow: 0 0 0 4px var(--node-ring);
}

.whisper-todo-step.is-enabled .whisper-todo-step__mark::after {
  content: '';
  display: block;
  width: 0.34rem;
  height: 0.54rem;
  margin: 0.15rem 0 0 0.36rem;
  border: solid var(--node-color);
  border-width: 0 2px 2px 0;
  transform: rotate(45deg);
}

.whisper-todo-step--fixed.is-enabled {
  --node-color: rgba(255, 255, 255, 0.38);
  --node-bg: rgba(255, 255, 255, 0.055);
  --node-ring: rgba(255, 255, 255, 0.045);
}

.whisper-todo-step--optional.is-enabled {
  --node-color: rgba(145, 213, 255, 0.95);
  --node-bg: rgba(0, 117, 255, 0.18);
  --node-ring: rgba(0, 117, 255, 0.1);
}

.whisper-todo-step--optional {
  cursor: pointer;
}

.whisper-todo-step--optional:hover {
  background: rgba(0, 117, 255, 0.035);
}

.whisper-todo-step__body {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 0.18rem;
}

.whisper-todo-step__title {
  font-size: 0.78rem;
  font-weight: 750;
  color: var(--color-text-primary);
}

.whisper-todo-step--fixed .whisper-todo-step__title {
  color: rgba(255, 255, 255, 0.72);
}

.whisper-todo-step__desc {
  font-size: 0.7rem;
  line-height: 1.45;
  color: var(--color-text-secondary);
}

.whisper-todo-step--fixed .whisper-todo-step__desc {
  color: rgba(255, 255, 255, 0.42);
}

.whisper-default-summary {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.whisper-default-summary__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.75rem;
}

.whisper-default-summary__headline {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
  font-size: 0.875rem;
  font-weight: 700;
  color: var(--color-text-primary);
}

.whisper-default-summary__desc {
  margin: 0.18rem 0 0;
  font-size: 0.71875rem;
  color: var(--color-text-secondary);
}

.whisper-default-summary__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 0.45rem;
}

.whisper-default-summary__chip {
  display: inline-flex;
  align-items: center;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 9999px;
  padding: 0.14rem 0.48rem;
  font-size: 0.6875rem;
  color: var(--color-text-secondary);
}

.whisper-default-summary__chip--info {
  border-color: rgba(0, 117, 255, 0.24);
  background: rgba(0, 117, 255, 0.08);
  color: rgba(191, 227, 255, 0.96);
}

.whisper-default-summary__action {
  width: min(100%, 11.5rem);
}

.whisper-default-summary__action--bottom {
  width: 100%;
  margin-top: 0.15rem;
}

.whisper-default-summary__hint {
  margin-top: 0.25rem;
  font-size: 0.75rem;
  line-height: 1.45;
  color: var(--color-text-muted);
}

.whisper-open-jobs-button {
  margin-top: -0.25rem;
}

@media (max-width: 720px) {
  .whisper-default-summary__head {
    flex-direction: column;
  }
}
</style>
