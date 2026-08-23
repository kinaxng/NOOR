<script setup lang="ts">
import { ref, onMounted, watch, nextTick } from 'vue'
import { useEmbyStore } from '../stores/emby'
import { useJobsStore } from '../stores/jobs'
import type { EmbyItem, EmbyItemDetail, JobSettings } from '../api/types'
import api from '../api'
import { useI18n } from '../composables/useI18n'
import { useToast } from '../composables/useToast'
import MediaCard from '../components/MediaCard.vue'
import BasePanel from '../components/BasePanel.vue'
import BaseButton from '../components/BaseButton.vue'
import BaseBadge from '../components/BaseBadge.vue'
import BaseProgress from '../components/BaseProgress.vue'

const { t } = useI18n()
const toast = useToast()

const embyStore = useEmbyStore()
const jobsStore = useJobsStore()

const showModal = ref(false)
const selectedVideo = ref<EmbyItem | null>(null)
const videoDetail = ref<EmbyItemDetail | null>(null)
const loadingDetail = ref(false)
const submitting = ref(false)
const modalMode = ref<'view' | 'submit'>('view')

// Subtitle modal state
const showSubtitleModal = ref(false)
const subtitleVideoPath = ref('')
const subtitleVideoDir = ref('')
const subtitles = ref<{ filename: string; path: string; size: number; ext: string }[]>([])
const loadingSubtitles = ref(false)
const subtitleError = ref<string | null>(null)
const subtitleTab = ref<'local' | 'search' | 'whisper'>('local')
const onlineSubtitles = ref<{ name: string; url: string; ext: string; language: string; source: string }[]>([])
const searchingOnline = ref(false)
const videoCodeForSearch = ref('')

// Subtitle preview state
const showSubtitlePreview = ref(false)
const subtitlePreviewContent = ref('')
const subtitlePreviewFilename = ref('')
const loadingSubtitlePreview = ref(false)

// Whisper AI state
const whisperModel = ref('anime-whisper')
const whisperPipeline = ref('ensemble')
const whisperMergeStrategy = ref('smart_merge')
const whisperLanguage = ref('ja')
const whisperSensitivity = ref('balanced')
const whisperTaskId = ref('')
const whisperStatus = ref('')
const whisperLogs = ref<string[]>([])
const whisperProgress = ref(0)
const whisperRunning = ref(false)
const whisperEventSource = ref<EventSource | null>(null)
const whisperDefaultsLoaded = ref(false)

const settings = ref<JobSettings>({
  detection_model: 'v4-fast',
  restoration_model: 'basicvsrpp-v1.2',
  encoding_preset: 'hevc-nvidia-gpu-hq',
})

onMounted(async () => {
  await embyStore.fetchLibraries()
  jobsStore.fetchJobs()
  await loadWhisperDefaults()
  await nextTick()
  if (!embyStore.selectedLibrary && embyStore.libraries.length > 0) {
    embyStore.selectLibrary(embyStore.libraries[0])
  }
})

async function loadWhisperDefaults() {
  if (whisperDefaultsLoaded.value) return
  try {
    const resp = await api.get('/settings')
    if (resp.data.whisper) {
      whisperModel.value = resp.data.whisper.model || 'anime-whisper'
      whisperPipeline.value = resp.data.whisper.pipeline_mode || 'ensemble'
      whisperMergeStrategy.value = resp.data.whisper.merge_strategy || 'smart_merge'
      whisperLanguage.value = resp.data.whisper.language || 'ja'
      whisperSensitivity.value = resp.data.whisper.sensitivity || 'balanced'
      whisperDefaultsLoaded.value = true
    }
  } catch (e) {
    console.error('Failed to load Whisper defaults:', e)
  }
}

watch(() => embyStore.selectedLibrary, (library) => {
  if (library) {
    embyStore.fetchItems(library.id)
  }
}, { immediate: false })

function selectLibrary(library: any) {
  embyStore.selectLibrary(library)
}

const detailError = ref<string | null>(null)

function selectVideo(item: EmbyItem) {
  selectedVideo.value = item
  showModal.value = true
  loadingDetail.value = true
  videoDetail.value = null
  detailError.value = null
  modalMode.value = 'view'

  embyStore.fetchItemDetail(item.id).then(() => {
    videoDetail.value = embyStore.selectedItem
    if (!embyStore.selectedItem) {
      detailError.value = 'No details available for this item'
    }
  }).catch((e: any) => {
    console.error('Detail fetch error:', e)
    const msg = e?.response?.data?.detail || e?.message || 'Failed to load item details'
    detailError.value = msg
  }).finally(() => {
    loadingDetail.value = false
  })
}

function closeModal() {
  showModal.value = false
  selectedVideo.value = null
  videoDetail.value = null
}

function getDisplayTitle(item: EmbyItemDetail): string {
  return item.nfo?.title || item.nfo?.originaltitle || item.name
}

async function submitJob() {
  if (!selectedVideo.value || !videoDetail.value?.file_path) return

  submitting.value = true
  try {
    const displayName = getDisplayTitle(videoDetail.value)
    const job = await jobsStore.createJob({
      emby_item_id: selectedVideo.value.id,
      emby_item_name: displayName,
      input_path: videoDetail.value.file_path,
      settings: settings.value,
    })
    closeModal()
    toast.success(`Job submitted! Job ID: ${job.id}`)
  } catch (e) {
    console.error(e)
    toast.error('Failed to submit job')
  } finally {
    submitting.value = false
  }
}

function openSubmitModal(item: EmbyItem) {
  selectedVideo.value = item
  showModal.value = true
  loadingDetail.value = true
  videoDetail.value = null
  detailError.value = null
  modalMode.value = 'submit'

  embyStore.fetchItemDetail(item.id).then(() => {
    videoDetail.value = embyStore.selectedItem
    if (!embyStore.selectedItem) {
      detailError.value = 'No details available for this item'
    }
  }).catch((e: any) => {
    console.error('Detail fetch error:', e)
    const msg = e?.response?.data?.detail || e?.message || 'Failed to load item details'
    detailError.value = msg
  }).finally(() => {
    loadingDetail.value = false
  })
}

async function quickSubmit(item: EmbyItem) {
  if (item.tags?.is_cracked || hasCompletedJob(item.id)) {
    return
  }
  openSubmitModal(item)
}

function goNextPage() {
  embyStore.nextPage()
}

function goPrevPage() {
  embyStore.prevPage()
}

const filterButtons = [
  { key: 'all', labelKey: 'library.filter.all' },
  { key: 'cracked', labelKey: 'library.filter.破解' },
  { key: 'chinese', labelKey: 'library.filter.chinese' },
  { key: 'leaked', labelKey: 'library.filter.leaked' },
  { key: 'uncensored', labelKey: 'library.filter.uncensored' },
]

function setFilter(key: string) {
  embyStore.setFilter(key === 'all' ? null : key)
}

function hasCompletedJob(itemId: string): boolean {
  return jobsStore.jobs.some(job =>
    job.emby_item_id === itemId && job.status === 'completed'
  )
}

// Subtitle functions
async function showSubtitles(item: EmbyItem) {
  subtitleTab.value = 'local'
  subtitleVideoPath.value = item.path || ''
  subtitleVideoDir.value = item.path ? item.path.substring(0, item.path.lastIndexOf('/')) : ''
  subtitleError.value = null
  subtitles.value = []
  onlineSubtitles.value = []
  videoCodeForSearch.value = ''
  showSubtitleModal.value = true
  loadingSubtitles.value = true

  let videoPath = item.path
  if (!videoPath) {
    try {
      await embyStore.fetchItemDetail(item.id)
      videoPath = embyStore.selectedItem?.file_path || ''
      subtitleVideoPath.value = videoPath
      subtitleVideoDir.value = videoPath ? videoPath.substring(0, videoPath.lastIndexOf('/')) : ''
    } catch (e) {
      console.error('Failed to get video path:', e)
    }
  }

  if (!videoPath) {
    subtitleError.value = '无法获取视频路径'
    loadingSubtitles.value = false
    return
  }

  await Promise.all([
    loadWhisperDefaults(),
    fetchSubtitles(videoPath),
  ])
}

async function fetchSubtitles(videoPath: string) {
  loadingSubtitles.value = true
  subtitleError.value = null
  try {
    const resp = await api.get('/subtitles', {
      params: { video_path: videoPath }
    })
    subtitles.value = resp.data.subtitles || []
  } catch (e: any) {
    console.error('Failed to load subtitles:', e)
    subtitleError.value = e?.response?.data?.detail || '加载字幕列表失败'
  } finally {
    loadingSubtitles.value = false
  }
}

async function searchOnlineSubtitles() {
  if (!subtitleVideoPath.value) return

  searchingOnline.value = true
  onlineSubtitles.value = []
  subtitleError.value = null

  try {
    const resp = await api.get('/subtitles/search', {
      params: { video_path: subtitleVideoPath.value }
    })
    onlineSubtitles.value = resp.data.results || []
    videoCodeForSearch.value = resp.data.video_name || ''
    if (onlineSubtitles.value.length === 0) {
      subtitleError.value = '未找到字幕'
    }
  } catch (e: any) {
    console.error('Failed to search subtitles:', e)
    subtitleError.value = e?.response?.data?.detail || '搜索字幕失败'
  } finally {
    searchingOnline.value = false
  }
}

async function downloadOnlineSubtitle(url: string, _filename: string) {
  try {
    const resp = await api.get('/subtitles/download', {
      params: { url, video_path: subtitleVideoPath.value }
    })
    toast.success(`字幕 "${resp.data.filename}" 已下载到: ${resp.data.path}`)
    await refreshLocalSubtitles()
    subtitleTab.value = 'local'
  } catch (e: any) {
    console.error('Failed to download subtitle:', e)
    toast.error(e?.response?.data?.detail || '下载失败')
  }
}

async function previewOnlineSubtitle(url: string, filename: string) {
  loadingSubtitlePreview.value = true
  subtitlePreviewContent.value = ''
  subtitlePreviewFilename.value = filename
  showSubtitlePreview.value = true

  try {
    const resp = await api.get('/subtitles/fetch', {
      params: { url }
    })
    subtitlePreviewContent.value = resp.data.content
  } catch (e: any) {
    console.error('Failed to preview subtitle:', e)
    subtitlePreviewContent.value = '加载字幕失败，请检查网络或尝试下载后查看'
  } finally {
    loadingSubtitlePreview.value = false
  }
}

async function refreshLocalSubtitles() {
  if (!subtitleVideoPath.value) return

  loadingSubtitles.value = true
  try {
    const resp = await api.get('/subtitles', {
      params: { video_path: subtitleVideoPath.value }
    })
    subtitles.value = resp.data.subtitles || []
  } catch (e: any) {
    console.error('Failed to load subtitles:', e)
  } finally {
    loadingSubtitles.value = false
  }
}

function closeSubtitleModal() {
  showSubtitleModal.value = false
  subtitles.value = []
  onlineSubtitles.value = []
  subtitleVideoPath.value = ''
  subtitleVideoDir.value = ''
  videoCodeForSearch.value = ''
}

// Whisper AI functions
function disconnectWhisperEvents() {
  if (whisperEventSource.value) {
    whisperEventSource.value.close()
    whisperEventSource.value = null
  }
}

async function startWhisperTask() {
  if (!subtitleVideoPath.value) {
    toast.warning(t('whisper.selectModel'))
    return
  }

  whisperRunning.value = true
  whisperStatus.value = '正在提交任务...'
  whisperLogs.value = []
  whisperProgress.value = 0

  try {
    const createResp = await api.post('/whisper/tasks', {
      video_path: subtitleVideoPath.value,
      model: whisperModel.value,
      pipeline_mode: whisperPipeline.value,
      merge_strategy: whisperMergeStrategy.value,
      language: whisperLanguage.value,
      sensitivity: whisperSensitivity.value
    })

    whisperTaskId.value = createResp.data.task_id
    whisperStatus.value = '任务已提交，请到JOBS中查看进度'
    whisperProgress.value = 10

    await api.post(`/whisper/tasks/${whisperTaskId.value}/run`)
    jobsStore.fetchJobs()

    disconnectWhisperEvents()
    whisperEventSource.value = new EventSource(`/api/jobs/${whisperTaskId.value}/events`)

    whisperEventSource.value.addEventListener('connected', () => {
      console.log('Whisper SSE connected')
      whisperProgress.value = 20
    })

    whisperEventSource.value.addEventListener('progress', (e) => {
      const data = JSON.parse(e.data)
      const baseProgress = data.progress || 0
      whisperProgress.value = Math.max(20, Math.min(95, 20 + baseProgress * 0.75))
    })

    whisperEventSource.value.addEventListener('done', (e) => {
      const data = JSON.parse(e.data)
      if (data.type === 'completed') {
        whisperStatus.value = '生成完成！'
        whisperProgress.value = 100
        whisperRunning.value = false
        disconnectWhisperEvents()
        refreshLocalSubtitles()
      } else if (data.type === 'failed') {
        whisperStatus.value = '生成失败'
        whisperRunning.value = false
        disconnectWhisperEvents()
      }
    })

    whisperEventSource.value.addEventListener('keepalive', () => {
      // ignore
    })

    whisperEventSource.value.addEventListener('error', (e) => {
      console.error('Whisper SSE error:', e)
      whisperStatus.value = '连接中断'
      whisperRunning.value = false
      disconnectWhisperEvents()
    })

  } catch (e: any) {
    console.error('Whisper task failed:', e)
    whisperStatus.value = '创建任务失败: ' + (e?.response?.data?.detail || e.message)
    whisperRunning.value = false
  }
}

async function openSubtitleFile(path: string, filename: string) {
  loadingSubtitlePreview.value = true
  subtitlePreviewContent.value = ''
  subtitlePreviewFilename.value = filename
  showSubtitlePreview.value = true

  try {
    const resp = await api.get('/subtitles/content', {
      params: { path }
    })
    subtitlePreviewContent.value = resp.data.content
  } catch (e: any) {
    console.error('Failed to load subtitle:', e)
    subtitlePreviewContent.value = '加载字幕失败'
  } finally {
    loadingSubtitlePreview.value = false
  }
}

function closeSubtitlePreview() {
  showSubtitlePreview.value = false
  subtitlePreviewContent.value = ''
  subtitlePreviewFilename.value = ''
}

async function deleteSubtitle(path: string, filename: string) {
  if (!confirm(`确定删除字幕文件 "${filename}" 吗？`)) return

  try {
    await api.delete('/subtitles', {
      params: { path }
    })
    subtitles.value = subtitles.value.filter(s => s.path !== path)
    toast.success('字幕文件已删除')
  } catch (e: any) {
    console.error('Failed to delete subtitle:', e)
    toast.error(e?.response?.data?.detail || '删除失败')
  }
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}
</script>

<template>
  <div class="flex h-[calc(100vh-3.5rem)]">
    <!-- Sidebar - Libraries -->
    <div class="w-64 bg-bg-surface border-r border-border-subtle overflow-y-auto flex-shrink-0">
      <div class="p-4">
        <h2 class="text-xs font-semibold text-text-muted uppercase mb-3 tracking-wider">{{ t('nav.library') }}</h2>
        <div v-if="embyStore.loading && embyStore.libraries.length === 0" class="text-text-muted text-sm">Loading...</div>
        <div v-else-if="embyStore.error" class="text-status-error text-sm">{{ embyStore.error }}</div>
        <div v-else class="space-y-1">
          <button
            v-for="lib in embyStore.libraries"
            :key="lib.id"
            @click="selectLibrary(lib)"
            :class="[
              'w-full text-left px-3 py-2 rounded-lg text-sm transition-all duration-200 flex items-center gap-2',
              embyStore.selectedLibrary?.id === lib.id
                ? 'bg-accent-cyan/10 text-accent-cyan'
                : 'text-text-secondary hover:bg-bg-hover'
            ]"
          >
            <span v-if="lib.poster_path" class="w-8 h-10 bg-bg-elevated rounded overflow-hidden flex-shrink-0">
              <img :src="lib.poster_path" class="w-full h-full object-cover" @error="() => {}" />
            </span>
            <span class="truncate">{{ lib.name }}</span>
          </button>
        </div>
      </div>
    </div>

    <!-- Main Content - Items -->
    <div class="flex-1 overflow-y-auto p-6">
      <div v-if="!embyStore.selectedLibrary" class="h-full flex items-center justify-center text-text-muted">
        {{ t('library.title') }}
      </div>
      <div v-else>
        <!-- Header -->
        <div class="flex flex-wrap justify-between items-center gap-4 mb-6">
          <div>
            <h2 class="font-display font-bold text-2xl text-text-primary">{{ embyStore.selectedLibrary.name }}</h2>
            <p class="text-text-muted text-sm">{{ embyStore.total }} items</p>
          </div>

          <!-- Filter buttons -->
          <div class="flex flex-wrap gap-2">
            <button
              v-for="btn in filterButtons"
              :key="btn.key"
              @click="setFilter(btn.key)"
              :class="[
                'px-3 py-1.5 rounded-lg text-sm transition-all duration-200',
                (btn.key === 'all' ? null : btn.key) === embyStore.filterTag
                  ? 'bg-accent-cyan text-bg-void font-medium'
                  : 'bg-bg-elevated text-text-secondary hover:bg-bg-hover'
              ]"
            >
              {{ t(btn.labelKey) }}
            </button>
          </div>
        </div>

        <!-- Loading -->
        <div v-if="embyStore.loading" class="text-text-muted text-center py-12">Loading...</div>

        <!-- Empty state -->
        <div v-else-if="embyStore.filteredItems.length === 0" class="text-text-muted text-center py-12">
          {{ t('library.noResults') }}
        </div>

        <!-- Items grid -->
        <div v-else class="grid grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-4">
          <MediaCard
            v-for="item in embyStore.items"
            :key="item.id"
            :item="item"
            @click="selectVideo(item)"
            @quickAction="quickSubmit(item)"
            @subtitleAction="showSubtitles(item)"
          />
        </div>

        <!-- Pagination -->
        <div v-if="embyStore.totalPages > 1" class="flex justify-center items-center gap-4 mt-6">
          <BaseButton
            variant="secondary"
            size="sm"
            @click="goPrevPage"
            :disabled="embyStore.currentPage <= 1"
          >
            Previous
          </BaseButton>
          <span class="text-text-secondary text-sm">
            Page {{ embyStore.currentPage }} / {{ embyStore.totalPages }}
          </span>
          <BaseButton
            variant="secondary"
            size="sm"
            @click="goNextPage"
            :disabled="embyStore.currentPage >= embyStore.totalPages"
          >
            Next
          </BaseButton>
        </div>
      </div>
    </div>

    <!-- Detail Panel -->
    <BasePanel :open="showModal" side="right" @close="closeModal">
      <!-- Loading State -->
      <div v-if="loadingDetail" class="flex items-center justify-center h-48">
        <div class="animate-spin w-8 h-8 border-2 border-accent-cyan border-t-transparent rounded-full"></div>
      </div>

      <!-- Error State -->
      <div v-else-if="detailError" class="flex flex-col items-center justify-center h-48 p-8 text-center">
        <div class="text-status-error text-lg mb-2">{{ t('common.error') }}</div>
        <div class="text-text-secondary text-sm max-w-md">{{ detailError }}</div>
        <BaseButton variant="secondary" size="sm" @click="closeModal" class="mt-4">
          {{ t('common.close') }}
        </BaseButton>
      </div>

      <template v-else-if="videoDetail">
        <!-- Header Section with Backdrop -->
        <div class="relative">
          <div v-if="videoDetail.poster_path" class="absolute inset-0 h-48 overflow-hidden">
            <img :src="videoDetail.poster_path" class="w-full h-full object-cover opacity-20 blur-sm" />
            <div class="absolute inset-0 bg-gradient-to-t from-bg-surface via-bg-surface/80 to-transparent"></div>
          </div>
          <div v-else class="absolute inset-0 h-48 bg-gradient-to-t from-bg-elevated to-bg-surface"></div>

          <div class="relative flex gap-6 p-6 pb-8">
            <!-- Poster -->
            <div v-if="videoDetail.poster_path" class="w-36 aspect-[2/3] bg-bg-elevated rounded-xl overflow-hidden shadow-xl flex-shrink-0 ring-1 ring-border-default">
              <img :src="videoDetail.poster_path" class="w-full h-full object-cover" />
            </div>

            <!-- Info -->
            <div class="flex-1 pt-4">
              <h2 class="text-2xl font-bold text-text-primary mb-1">{{ getDisplayTitle(videoDetail) }}</h2>
              <p v-if="videoDetail.nfo?.originaltitle && videoDetail.nfo.originaltitle !== videoDetail.name" class="text-text-secondary text-sm mb-3">
                {{ videoDetail.nfo.originaltitle }}
              </p>

              <!-- Meta Info Row -->
              <div class="flex flex-wrap items-center gap-2 mb-3">
                <span v-if="videoDetail.nfo?.year" class="px-2 py-0.5 bg-bg-elevated rounded text-sm text-text-secondary">{{ videoDetail.nfo.year }}</span>
                <span v-if="videoDetail.nfo?.rating" class="px-2 py-0.5 bg-accent-amber/20 text-accent-amber rounded text-sm flex items-center gap-1">
                  <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20"><path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" /></svg>
                  {{ videoDetail.nfo.rating }}
                </span>
                <span v-if="videoDetail.nfo?.director" class="px-2 py-0.5 bg-bg-elevated rounded text-sm text-text-secondary">
                  {{ t('detail.director') }}: {{ videoDetail.nfo.director }}
                </span>
              </div>

              <!-- Studios -->
              <div v-if="videoDetail.studios?.length" class="flex flex-wrap gap-1 mb-3">
                <BaseBadge v-for="studio in videoDetail.studios.slice(0, 2)" :key="studio" variant="magenta">
                  {{ studio }}
                </BaseBadge>
              </div>

              <!-- Genres -->
              <div v-if="videoDetail.nfo?.genres?.length" class="flex flex-wrap gap-1">
                <BaseBadge v-for="genre in videoDetail.nfo.genres.slice(0, 4)" :key="genre" variant="cyan">
                  {{ genre }}
                </BaseBadge>
              </div>
            </div>
          </div>
        </div>

        <!-- Body Content -->
        <div class="px-6 pb-6">
          <!-- Plot -->
          <div v-if="videoDetail.nfo?.plot" class="mb-6">
            <h3 class="text-xs font-semibold text-text-muted uppercase mb-2 tracking-wider">剧情简介</h3>
            <p class="text-text-secondary text-sm leading-relaxed">{{ videoDetail.nfo.plot }}</p>
          </div>

          <!-- Actors -->
          <div v-if="videoDetail.nfo?.actors?.length" class="mb-6">
            <h3 class="text-xs font-semibold text-text-muted uppercase mb-2 tracking-wider">{{ t('detail.actors') }}</h3>
            <div class="flex flex-wrap gap-2">
              <span v-for="actor in videoDetail.nfo.actors.slice(0, 6)" :key="actor.name"
                class="px-3 py-1 bg-bg-elevated rounded-full text-sm text-text-secondary">
                {{ actor.name }}
                <span v-if="actor.role" class="text-text-muted text-xs ml-1">({{ actor.role }})</span>
              </span>
            </div>
          </div>

          <!-- File Path -->
          <div class="mb-6">
            <h3 class="text-xs font-semibold text-text-muted uppercase mb-2 tracking-wider">File Path</h3>
            <p class="text-sm font-mono bg-bg-elevated p-3 rounded-lg text-text-secondary break-all leading-relaxed">
              {{ videoDetail.file_path || 'N/A' }}
            </p>
          </div>

          <!-- Submit Mode: Settings & Actions -->
          <template v-if="modalMode === 'submit'">
            <div class="bg-bg-elevated rounded-xl p-4 mb-6">
              <h3 class="text-xs font-semibold text-text-muted uppercase mb-4 tracking-wider">Processing Settings</h3>
              <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div>
                  <label class="block text-xs text-text-muted mb-1.5">Detection Model</label>
                  <select v-model="settings.detection_model" class="w-full bg-bg-surface border border-border-subtle rounded-lg px-3 py-2 text-sm text-text-primary focus:ring-2 focus:ring-accent-cyan focus:border-transparent">
                    <option value="v4-fast">v4-fast (快速)</option>
                    <option value="v4">v4 (平衡)</option>
                    <option value="v3.1-accurate">v3.1-accurate (精准)</option>
                  </select>
                </div>
                <div>
                  <label class="block text-xs text-text-muted mb-1.5">Restoration Model</label>
                  <select v-model="settings.restoration_model" class="w-full bg-bg-surface border border-border-subtle rounded-lg px-3 py-2 text-sm text-text-primary focus:ring-2 focus:ring-accent-cyan focus:border-transparent">
                    <option value="basicvsrpp-v1.2">BasicVSR++ v1.2</option>
                    <option value="basicvsrpp-v1">BasicVSR++ v1</option>
                  </select>
                </div>
                <div>
                  <label class="block text-xs text-text-muted mb-1.5">Encoding Preset</label>
                  <select v-model="settings.encoding_preset" class="w-full bg-bg-surface border border-border-subtle rounded-lg px-3 py-2 text-sm text-text-primary focus:ring-2 focus:ring-accent-cyan focus:border-transparent">
                    <option value="hevc-nvidia-gpu-hq">HEVC HQ (高质量)</option>
                    <option value="hevc-nvidia-gpu">HEVC (标准)</option>
                    <option value="hevc-nvidia">HEVC (快速)</option>
                  </select>
                </div>
              </div>
            </div>

            <!-- Actions -->
            <div class="flex gap-3">
              <BaseButton
                variant="primary"
                size="lg"
                class="flex-1"
                :loading="submitting"
                :disabled="!videoDetail?.file_path"
                @click="submitJob"
              >
                Start Processing
              </BaseButton>
              <BaseButton
                variant="secondary"
                size="lg"
                @click="closeModal"
              >
                {{ t('common.cancel') }}
              </BaseButton>
            </div>
          </template>

          <!-- View Mode: Close button only -->
          <div v-else class="flex justify-center">
            <BaseButton variant="secondary" size="lg" @click="closeModal">
              {{ t('common.close') }}
            </BaseButton>
          </div>
        </div>
      </template>
    </BasePanel>

    <!-- Subtitle Panel -->
    <BasePanel :open="showSubtitleModal" side="right" @close="closeSubtitleModal">
      <template #header>
        <h2 class="font-display font-semibold text-lg text-text-primary">{{ t('subtitle.local') }}</h2>
      </template>

      <!-- Video path -->
      <div class="px-6 py-2 bg-bg-elevated text-xs text-text-muted truncate border-b border-border-subtle">
        {{ subtitleVideoPath }}
      </div>

      <!-- Tabs -->
      <div class="flex border-b border-border-subtle px-6">
        <button
          @click="subtitleTab = 'local'"
          :class="[
            'px-4 py-3 text-sm font-medium transition-colors border-b-2 -mb-px',
            subtitleTab === 'local'
              ? 'text-accent-cyan border-accent-cyan'
              : 'text-text-secondary hover:text-text-primary border-transparent'
          ]"
        >
          {{ t('subtitle.local') }} ({{ subtitles.length }})
        </button>
        <button
          @click="subtitleTab = 'search'; searchOnlineSubtitles()"
          :class="[
            'px-4 py-3 text-sm font-medium transition-colors border-b-2 -mb-px',
            subtitleTab === 'search'
              ? 'text-accent-cyan border-accent-cyan'
              : 'text-text-secondary hover:text-text-primary border-transparent'
          ]"
        >
          {{ t('subtitle.online') }}
        </button>
        <button
          @click="subtitleTab = 'whisper'"
          :class="[
            'px-4 py-3 text-sm font-medium transition-colors border-b-2 -mb-px',
            subtitleTab === 'whisper'
              ? 'text-accent-cyan border-accent-cyan'
              : 'text-text-secondary hover:text-text-primary border-transparent'
          ]"
        >
          {{ t('subtitle.whisper') }}
        </button>
      </div>

      <!-- Content -->
      <div class="p-6 overflow-y-auto">
        <!-- Local Tab -->
        <div v-if="subtitleTab === 'local'">
          <div v-if="loadingSubtitles" class="flex items-center justify-center py-8">
            <div class="animate-spin w-8 h-8 border-2 border-accent-cyan border-t-transparent rounded-full"></div>
          </div>
          <div v-else-if="subtitleError" class="text-status-error text-center py-4">
            {{ subtitleError }}
          </div>
          <div v-else-if="subtitles.length === 0" class="text-text-muted text-center py-8">
            {{ t('subtitle.noResults') }}
          </div>
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
                <BaseButton size="sm" variant="secondary" @click="openSubtitleFile(sub.path, sub.filename)">
                  {{ t('subtitle.preview') }}
                </BaseButton>
                <BaseButton size="sm" variant="danger" @click="deleteSubtitle(sub.path, sub.filename)">
                  {{ t('common.delete') }}
                </BaseButton>
              </div>
            </div>
          </div>
        </div>

        <!-- Online Search Tab -->
        <div v-if="subtitleTab === 'search'">
          <div v-if="searchingOnline" class="flex items-center justify-center py-8">
            <div class="animate-spin w-8 h-8 border-2 border-accent-cyan border-t-transparent rounded-full"></div>
            <span class="ml-3 text-text-secondary">{{ t('common.loading') }}</span>
          </div>
          <div v-else-if="subtitleError" class="text-status-error text-center py-4">
            {{ subtitleError }}
          </div>
          <div v-else-if="onlineSubtitles.length === 0" class="text-text-muted text-center py-8">
            <p>{{ t('subtitle.noResults') }}</p>
          </div>
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
                <BaseButton size="sm" variant="secondary" @click="previewOnlineSubtitle(sub.url, sub.name)">
                  {{ t('subtitle.preview') }}
                </BaseButton>
                <BaseButton size="sm" variant="success" @click="downloadOnlineSubtitle(sub.url, sub.name)">
                  {{ t('subtitle.download') }}
                </BaseButton>
              </div>
            </div>
          </div>
        </div>

        <!-- Whisper AI Tab -->
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
              <p class="text-xs text-text-muted mt-1">
                两遍处理: Pass1使用anime-whisper快速覆盖，Pass2使用Faster-Whisper高质量精修
              </p>
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

            <!-- Progress bar -->
            <BaseProgress
              v-if="whisperRunning || whisperProgress > 0"
              :value="whisperProgress"
              variant="cyan"
              :show-label="true"
            />

            <!-- Start button -->
            <BaseButton
              v-if="!whisperRunning"
              variant="primary"
              class="w-full"
              @click="startWhisperTask"
            >
              {{ t('whisper.start') }}
            </BaseButton>
          </div>
        </div>
      </div>
    </BasePanel>

    <!-- Subtitle Preview Modal -->
    <Teleport to="body">
      <div
        v-if="showSubtitlePreview"
        class="fixed inset-0 bg-bg-void/80 backdrop-blur-sm flex items-center justify-center z-[200] p-4"
        @click.self="closeSubtitlePreview"
      >
        <div class="bg-bg-surface rounded-xl max-w-4xl w-full max-h-[90vh] flex flex-col overflow-hidden border border-border-subtle shadow-2xl">
          <div class="flex items-center justify-between px-4 py-3 border-b border-border-subtle">
            <h3 class="text-lg font-medium text-text-primary">{{ subtitlePreviewFilename }}</h3>
            <button
              @click="closeSubtitlePreview"
              class="text-text-muted hover:text-text-primary transition-colors"
            >
              <svg xmlns="http://www.w3.org/2000/svg" class="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
          <div class="flex-1 overflow-auto p-4">
            <div v-if="loadingSubtitlePreview" class="flex items-center justify-center h-32">
              <div class="animate-spin w-8 h-8 border-2 border-accent-cyan border-t-transparent rounded-full"></div>
            </div>
            <pre v-else class="whitespace-pre-wrap text-text-secondary text-sm font-mono leading-relaxed">{{ subtitlePreviewContent }}</pre>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>
