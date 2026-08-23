<script setup lang="ts">
import { ref, onMounted, watch, nextTick } from 'vue'
import { useEmbyStore } from '../stores/emby'
import { useJobsStore } from '../stores/jobs'
import type { EmbyItem, EmbyItemDetail, JobSettings } from '../api/types'
import api from '../api'

const embyStore = useEmbyStore()
const jobsStore = useJobsStore()

const showModal = ref(false)
const selectedVideo = ref<EmbyItem | null>(null)
const videoDetail = ref<EmbyItemDetail | null>(null)
const loadingDetail = ref(false)
const submitting = ref(false)
const imageLoadErrors = ref<Set<string>>(new Set())
const modalMode = ref<'view' | 'submit'>('view')  // 'view' = 查看详情, 'submit' = 提交任务

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

const settings = ref<JobSettings>({
  detection_model: 'v4-fast',
  restoration_model: 'basicvsrpp-v1.2',
  encoding_preset: 'hevc-nvidia-gpu-hq',
})

onMounted(async () => {
  await embyStore.fetchLibraries()
  jobsStore.fetchJobs()
  // Load Whisper defaults from settings
  await loadWhisperDefaults()
  // Auto-select first library if none selected
  await nextTick()
  if (!embyStore.selectedLibrary && embyStore.libraries.length > 0) {
    embyStore.selectLibrary(embyStore.libraries[0])
  }
})

async function loadWhisperDefaults() {
  try {
    const resp = await api.get('/settings')
    if (resp.data.whisper) {
      whisperModel.value = resp.data.whisper.model || 'anime-whisper'
      whisperPipeline.value = resp.data.whisper.pipeline_mode || 'ensemble'
      whisperMergeStrategy.value = resp.data.whisper.merge_strategy || 'smart_merge'
      whisperLanguage.value = resp.data.whisper.language || 'ja'
      whisperSensitivity.value = resp.data.whisper.sensitivity || 'balanced'
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
  modalMode.value = 'view'  // 查看模式

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

function onImageError(itemId: string) {
  imageLoadErrors.value.add(itemId)
}

function getDisplayName(item: EmbyItem): string {
  return item.nfo?.title || item.nfo?.originaltitle || item.name
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
    alert(`Job submitted! Job ID: ${job.id}`)
  } catch (e) {
    console.error(e)
    alert('Failed to submit job')
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
  modalMode.value = 'submit'  // 提交模式

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
  // 绿色状态（已破解/已完成）不执行任何操作
  if (item.tags?.is_cracked || hasCompletedJob(item.id)) {
    return
  }

  // 灰色状态弹出提交对话框
  openSubmitModal(item)
}

function goNextPage() {
  embyStore.nextPage()
}

function goPrevPage() {
  embyStore.prevPage()
}

const filterButtons = [
  { key: 'all', label: '全部' },
  { key: 'cracked', label: '破解' },
  { key: 'chinese', label: '中文' },
  { key: 'leaked', label: '流出' },
  { key: 'uncensored', label: '无码' },
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
  // First get the video path
  let videoPath = item.path
  if (!videoPath) {
    try {
      await embyStore.fetchItemDetail(item.id)
      videoPath = embyStore.selectedItem?.file_path || ''
    } catch (e) {
      console.error('Failed to get video path:', e)
      alert('无法获取视频路径')
      return
    }
  }

  if (!videoPath) {
    alert('无法获取视频路径')
    return
  }

  subtitleVideoPath.value = videoPath
  subtitleVideoDir.value = videoPath.substring(0, videoPath.lastIndexOf('/'))
  subtitleTab.value = 'local'
  // Reload Whisper defaults from settings
  await loadWhisperDefaults()
  showSubtitleModal.value = true
  loadingSubtitles.value = true
  subtitleError.value = null
  subtitles.value = []
  onlineSubtitles.value = []
  videoCodeForSearch.value = ''

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
    alert(`字幕 "${resp.data.filename}" 已下载到: ${resp.data.path}`)
    // Refresh local subtitles
    await refreshLocalSubtitles()
    // Switch to local tab
    subtitleTab.value = 'local'
  } catch (e: any) {
    console.error('Failed to download subtitle:', e)
    alert(e?.response?.data?.detail || '下载失败')
  }
}

async function previewOnlineSubtitle(url: string, filename: string) {
  loadingSubtitlePreview.value = true
  subtitlePreviewContent.value = ''
  subtitlePreviewFilename.value = filename
  showSubtitlePreview.value = true

  try {
    // Use backend proxy to avoid CORS issues
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
    alert('请先选择一个视频')
    return
  }

  whisperRunning.value = true
  whisperStatus.value = '正在提交任务...'
  whisperLogs.value = []
  whisperProgress.value = 0

  try {
    // 创建任务
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

    // 启动任务
    await api.post(`/whisper/tasks/${whisperTaskId.value}/run`)

    // 刷新 jobs 列表
    jobsStore.fetchJobs()

    // 连接 SSE (使用 jobs 的事件端点)
    disconnectWhisperEvents()
    whisperEventSource.value = new EventSource(`/api/jobs/${whisperTaskId.value}/events`)

    whisperEventSource.value.addEventListener('connected', () => {
      console.log('Whisper SSE connected')
      whisperProgress.value = 20
    })

    whisperEventSource.value.addEventListener('progress', (e) => {
      const data = JSON.parse(e.data)
      // 将 0-100 的进度映射到 20-95
      const baseProgress = data.progress || 0
      whisperProgress.value = Math.max(20, Math.min(95, 20 + baseProgress * 0.75))
    })

    // 后端发送 'done' 事件，包含 type: 'completed' 或 'failed'
    whisperEventSource.value.addEventListener('done', (e) => {
      const data = JSON.parse(e.data)
      if (data.type === 'completed') {
        whisperStatus.value = '生成完成！'
        whisperProgress.value = 100
        whisperRunning.value = false
        disconnectWhisperEvents()
        // 刷新本地字幕
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

function stopWhisperTask() {
  disconnectWhisperEvents()
  whisperRunning.value = false
  whisperStatus.value = '已停止'
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
    // Remove from list
    subtitles.value = subtitles.value.filter(s => s.path !== path)
    alert('字幕文件已删除')
  } catch (e: any) {
    console.error('Failed to delete subtitle:', e)
    alert(e?.response?.data?.detail || '删除失败')
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
    <div class="w-64 bg-gray-800 border-r border-gray-700 overflow-y-auto">
      <div class="p-4">
        <h2 class="text-sm font-semibold text-gray-400 uppercase mb-3">Media Libraries</h2>
        <div v-if="embyStore.loading && embyStore.libraries.length === 0" class="text-gray-400">Loading...</div>
        <div v-else-if="embyStore.error" class="text-red-400 text-sm">{{ embyStore.error }}</div>
        <div v-else class="space-y-1">
          <button
            v-for="lib in embyStore.libraries"
            :key="lib.id"
            @click="selectLibrary(lib)"
            :class="[
              'w-full text-left px-3 py-2 rounded-md text-sm transition-colors flex items-center gap-2',
              embyStore.selectedLibrary?.id === lib.id
                ? 'bg-blue-600 text-white'
                : 'text-gray-300 hover:bg-gray-700'
            ]"
          >
            <span v-if="lib.poster_path" class="w-8 h-10 bg-gray-600 rounded overflow-hidden flex-shrink-0">
              <img :src="lib.poster_path" class="w-full h-full object-cover" @error="() => {}" />
            </span>
            <span class="truncate">{{ lib.name }}</span>
          </button>
        </div>
      </div>
    </div>

    <!-- Main Content - Items -->
    <div class="flex-1 overflow-y-auto p-6">
      <div v-if="!embyStore.selectedLibrary" class="h-full flex items-center justify-center text-gray-400">
        Select a library to browse videos
      </div>
      <div v-else>
        <!-- Header with filters and pagination -->
        <div class="flex flex-wrap justify-between items-center gap-4 mb-6">
          <div>
            <h2 class="text-2xl font-bold">{{ embyStore.selectedLibrary.name }}</h2>
            <p class="text-gray-400 text-sm">{{ embyStore.total }} items</p>
          </div>

          <!-- Filter buttons -->
          <div class="flex flex-wrap gap-2">
            <button
              v-for="btn in filterButtons"
              :key="btn.key"
              @click="setFilter(btn.key)"
              :class="[
                'px-3 py-1 rounded text-sm transition-colors',
                (btn.key === 'all' ? null : btn.key) === embyStore.filterTag
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
              ]"
            >
              {{ btn.label }}
            </button>
          </div>
        </div>

        <!-- Loading -->
        <div v-if="embyStore.loading" class="text-gray-400">Loading...</div>

        <!-- Items grid -->
        <div v-else-if="embyStore.filteredItems.length === 0" class="text-gray-400">
          No items found with current filter
        </div>
        <div v-else class="grid grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-3">
          <div
            v-for="item in embyStore.items"
            :key="item.id"
            @click="selectVideo(item)"
            class="bg-gray-800 rounded-lg overflow-hidden cursor-pointer hover:ring-2 hover:ring-blue-500 transition-all group"
          >
            <div class="aspect-[2/3] bg-gray-700 relative">
              <img
                v-if="item.poster_path && !imageLoadErrors.has(item.id)"
                :src="item.poster_path"
                :alt="item.name"
                class="w-full h-full object-cover"
                loading="lazy"
                @error="() => onImageError(item.id)"
              />
              <div v-else class="w-full h-full flex items-center justify-center text-gray-500 text-xs">
                No Cover
              </div>
              <!-- NFO badge -->
              <div v-if="item.nfo" class="absolute top-1 right-1 bg-yellow-500 text-black text-xs px-1 rounded">
                NFO
              </div>
            </div>
            <div class="p-2">
              <p class="text-xs line-clamp-2 h-8" :title="getDisplayName(item)">{{ getDisplayName(item) }}</p>
              <!-- Tags row -->
              <div class="flex flex-wrap gap-1 mt-1">
                <!-- Chinese tag - always show, bright if has Chinese, dim if not -->
                <button
                  class="text-xs px-1.5 py-0.5 rounded transition-colors cursor-pointer"
                  :class="(item.tags?.has_chinese || (item.subtitle_count ?? 0) > 0) ? 'bg-red-600 text-white hover:bg-red-500' : 'bg-gray-600 text-gray-400 hover:bg-gray-500'"
                  @click.stop="showSubtitles(item)"
                  title="查看字幕文件"
                >
                  中文
                </button>

                <!-- Cracked button - only show for regular videos (no release_type) -->
                <button
                  v-if="!item.tags?.release_type"
                  class="text-xs px-1.5 py-0.5 rounded transition-colors"
                  :class="item.tags?.is_cracked || hasCompletedJob(item.id)
                    ? 'bg-green-600 text-white hover:bg-green-500'
                    : 'bg-gray-600 text-gray-400 hover:bg-green-600 hover:text-white'"
                  @click.stop="quickSubmit(item)"
                  :title="item.tags?.is_cracked || hasCompletedJob(item.id) ? '已完成' : '点击提交任务'"
                >
                  破解
                </button>

                <!-- Release type badge - only show when detected (流出 or 无码) -->
                <span
                  v-if="item.tags?.release_type"
                  class="text-xs px-1.5 py-0.5 rounded"
                  :class="item.tags?.release_type === '流出' ? 'bg-orange-600 text-white' : 'bg-purple-600 text-white'"
                >
                  {{ item.tags.release_type }}
                </span>
              </div>
            </div>
          </div>
        </div>

        <!-- Pagination -->
        <div v-if="embyStore.totalPages > 1" class="flex justify-center items-center gap-4 mt-6">
          <button
            @click="goPrevPage"
            :disabled="embyStore.currentPage <= 1"
            class="px-4 py-2 rounded bg-gray-700 hover:bg-gray-600 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Previous
          </button>
          <span class="text-gray-400">
            Page {{ embyStore.currentPage }} / {{ embyStore.totalPages }}
          </span>
          <button
            @click="goNextPage"
            :disabled="embyStore.currentPage >= embyStore.totalPages"
            class="px-4 py-2 rounded bg-gray-700 hover:bg-gray-600 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Next
          </button>
        </div>
      </div>
    </div>

    <!-- Modal -->
    <Teleport to="body">
      <div
        v-if="showModal"
        class="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50 p-4"
        @click.self="closeModal"
      >
        <div class="bg-gray-800 rounded-xl w-full max-w-3xl max-h-[90vh] overflow-hidden shadow-2xl border border-gray-700">
          <!-- Loading State -->
          <div v-if="loadingDetail" class="flex items-center justify-center h-96">
            <div class="animate-spin w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full"></div>
          </div>

          <!-- Error State -->
          <div v-else-if="detailError" class="flex flex-col items-center justify-center h-96 p-8">
            <div class="text-red-400 text-lg mb-2">加载详情失败</div>
            <div class="text-gray-400 text-sm text-center max-w-md">{{ detailError }}</div>
            <button
              @click="closeModal"
              class="mt-4 px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded-lg text-white"
            >
              关闭
            </button>
          </div>

          <template v-else-if="videoDetail">
            <!-- Header Section with Backdrop -->
            <div class="relative">
              <!-- Backdrop Image -->
              <div v-if="videoDetail.poster_path" class="absolute inset-0 h-48 overflow-hidden">
                <img :src="videoDetail.poster_path" class="w-full h-full object-cover opacity-20 blur-sm" />
                <div class="absolute inset-0 bg-gradient-to-t from-gray-800 via-gray-800/80 to-transparent"></div>
              </div>
              <div v-else class="absolute inset-0 h-48 bg-gradient-to-t from-gray-700 to-gray-800"></div>

              <!-- Close Button -->
              <button
                @click="closeModal"
                class="absolute top-4 right-4 w-8 h-8 rounded-full bg-black/50 hover:bg-black/70 flex items-center justify-center text-white transition-colors z-10"
              >
                <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>

              <!-- Header Content -->
              <div class="relative flex gap-6 p-6 pb-8">
                <!-- Poster -->
                <div v-if="videoDetail.poster_path" class="w-36 aspect-[2/3] bg-gray-700 rounded-lg overflow-hidden shadow-xl flex-shrink-0 ring-2 ring-gray-600">
                  <img :src="videoDetail.poster_path" class="w-full h-full object-cover" />
                </div>

                <!-- Info -->
                <div class="flex-1 pt-4">
                  <h2 class="text-2xl font-bold text-white mb-1">{{ getDisplayTitle(videoDetail) }}</h2>
                  <p v-if="videoDetail.nfo?.originaltitle && videoDetail.nfo.originaltitle !== videoDetail.name" class="text-gray-400 text-sm mb-3">
                    {{ videoDetail.nfo.originaltitle }}
                  </p>

                  <!-- Meta Info Row -->
                  <div class="flex flex-wrap items-center gap-2 mb-3">
                    <span v-if="videoDetail.nfo?.year" class="px-2 py-0.5 bg-white/10 rounded text-sm text-gray-200">{{ videoDetail.nfo.year }}</span>
                    <span v-if="videoDetail.nfo?.rating" class="px-2 py-0.5 bg-yellow-500/20 text-yellow-400 rounded text-sm flex items-center gap-1">
                      <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20"><path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" /></svg>
                      {{ videoDetail.nfo.rating }}
                    </span>
                    <span v-if="videoDetail.nfo?.director" class="px-2 py-0.5 bg-white/10 rounded text-sm text-gray-300">
                      导演: {{ videoDetail.nfo.director }}
                    </span>
                  </div>

                  <!-- Studios -->
                  <div v-if="videoDetail.studios?.length" class="flex flex-wrap gap-1 mb-3">
                    <span v-for="studio in videoDetail.studios.slice(0, 2)" :key="studio"
                      class="px-2 py-0.5 bg-purple-500/20 text-purple-300 rounded text-xs">
                      {{ studio }}
                    </span>
                  </div>

                  <!-- Genres -->
                  <div v-if="videoDetail.nfo?.genres?.length" class="flex flex-wrap gap-1">
                    <span v-for="genre in videoDetail.nfo.genres.slice(0, 4)" :key="genre"
                      class="px-2 py-0.5 bg-blue-500/20 text-blue-300 rounded text-xs">
                      {{ genre }}
                    </span>
                  </div>
                </div>
              </div>
            </div>

            <!-- Body Content -->
            <div class="px-6 pb-6 max-h-[calc(90vh-320px)] overflow-y-auto">
              <!-- Plot -->
              <div v-if="videoDetail.nfo?.plot" class="mb-6">
                <h3 class="text-sm font-semibold text-gray-400 uppercase mb-2">剧情简介</h3>
                <p class="text-gray-300 text-sm leading-relaxed">{{ videoDetail.nfo.plot }}</p>
              </div>

              <!-- Actors -->
              <div v-if="videoDetail.nfo?.actors?.length" class="mb-6">
                <h3 class="text-sm font-semibold text-gray-400 uppercase mb-2">演员</h3>
                <div class="flex flex-wrap gap-2">
                  <span v-for="actor in videoDetail.nfo.actors.slice(0, 6)" :key="actor.name"
                    class="px-3 py-1 bg-gray-700 rounded-full text-sm text-gray-200">
                    {{ actor.name }}
                    <span v-if="actor.role" class="text-gray-400 text-xs ml-1">({{ actor.role }})</span>
                  </span>
                </div>
              </div>

              <!-- File Path -->
              <div class="mb-6">
                <h3 class="text-sm font-semibold text-gray-400 uppercase mb-2">文件路径</h3>
                <p class="text-sm font-mono bg-gray-900/50 p-3 rounded-lg text-gray-300 break-all leading-relaxed">
                  {{ videoDetail.file_path || 'N/A' }}
                </p>
              </div>

              <!-- Submit Mode: Settings & Actions -->
              <template v-if="modalMode === 'submit'">
                <div class="bg-gray-900/50 rounded-xl p-4 mb-6">
                  <h3 class="text-sm font-semibold text-gray-400 uppercase mb-4">处理设置</h3>
                  <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div>
                      <label class="block text-xs text-gray-500 mb-1.5">检测模型</label>
                      <select v-model="settings.detection_model" class="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-sm text-white focus:ring-2 focus:ring-blue-500 focus:border-transparent">
                        <option value="v4-fast">v4-fast (快速)</option>
                        <option value="v4">v4 (平衡)</option>
                        <option value="v3.1-accurate">v3.1-accurate (精准)</option>
                      </select>
                    </div>
                    <div>
                      <label class="block text-xs text-gray-500 mb-1.5">修复模型</label>
                      <select v-model="settings.restoration_model" class="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-sm text-white focus:ring-2 focus:ring-blue-500 focus:border-transparent">
                        <option value="basicvsrpp-v1.2">BasicVSR++ v1.2</option>
                        <option value="basicvsrpp-v1">BasicVSR++ v1</option>
                      </select>
                    </div>
                    <div>
                      <label class="block text-xs text-gray-500 mb-1.5">编码预设</label>
                      <select v-model="settings.encoding_preset" class="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-sm text-white focus:ring-2 focus:ring-blue-500 focus:border-transparent">
                        <option value="hevc-nvidia-gpu-hq">HEVC HQ (高质量)</option>
                        <option value="hevc-nvidia-gpu">HEVC (标准)</option>
                        <option value="hevc-nvidia">HEVC (快速)</option>
                      </select>
                    </div>
                  </div>
                </div>

                <!-- Actions -->
                <div class="flex gap-3">
                  <button
                    @click="submitJob"
                    :disabled="submitting || !videoDetail?.file_path"
                    class="flex-1 bg-gradient-to-r from-blue-600 to-blue-700 hover:from-blue-700 hover:to-blue-800 disabled:from-gray-600 disabled:to-gray-600 text-white py-3 rounded-xl font-medium transition-all duration-200 shadow-lg hover:shadow-xl disabled:shadow-none flex items-center justify-center gap-2"
                  >
                    <svg v-if="!submitting" class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
                    </svg>
                    <svg v-else class="w-5 h-5 animate-spin" fill="none" viewBox="0 0 24 24">
                      <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                      <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                    {{ submitting ? '提交中...' : '开始修复' }}
                  </button>
                  <button
                    @click="closeModal"
                    class="px-6 py-3 bg-gray-700 hover:bg-gray-600 rounded-xl text-gray-200 font-medium transition-colors"
                  >
                    取消
                  </button>
                </div>
              </template>

              <!-- View Mode: Close button only -->
              <div v-else class="flex justify-center">
                <button
                  @click="closeModal"
                  class="px-8 py-2 bg-gray-700 hover:bg-gray-600 rounded-xl text-gray-200 font-medium transition-colors"
                >
                  关闭
                </button>
              </div>
            </div>
          </template>
        </div>
      </div>
    </Teleport>

    <!-- Subtitle Modal -->
    <Teleport to="body">
        <div
          v-if="showSubtitleModal"
          class="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50 p-4"
          @click.self="closeSubtitleModal"
        >
          <div class="bg-gray-800 rounded-xl w-full max-w-2xl max-h-[80vh] overflow-hidden shadow-2xl border border-gray-700">
            <!-- Header -->
            <div class="flex justify-between items-center p-4 border-b border-gray-700">
              <h2 class="text-lg font-bold text-white">字幕管理</h2>
              <button
                @click="closeSubtitleModal"
                class="w-8 h-8 rounded-full bg-gray-700 hover:bg-gray-600 flex items-center justify-center text-white transition-colors"
              >
                <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            <!-- Video path -->
            <div class="px-4 py-2 bg-gray-900/50 text-xs text-gray-400 truncate">
              {{ subtitleVideoPath }}
            </div>

            <!-- Tabs -->
            <div class="flex border-b border-gray-700">
              <button
                @click="subtitleTab = 'local'"
                :class="[
                  'flex-1 px-4 py-3 text-sm font-medium transition-colors',
                  subtitleTab === 'local'
                    ? 'text-blue-400 border-b-2 border-blue-400'
                    : 'text-gray-400 hover:text-gray-300'
                ]"
              >
                本地字幕 ({{ subtitles.length }})
              </button>
              <button
                @click="subtitleTab = 'search'; searchOnlineSubtitles()"
                :class="[
                  'flex-1 px-4 py-3 text-sm font-medium transition-colors',
                  subtitleTab === 'search'
                    ? 'text-blue-400 border-b-2 border-blue-400'
                    : 'text-gray-400 hover:text-gray-300'
                ]"
              >
                在线搜索
              </button>
              <button
                @click="subtitleTab = 'whisper'"
                :class="[
                  'flex-1 px-4 py-3 text-sm font-medium transition-colors',
                  subtitleTab === 'whisper'
                    ? 'text-blue-400 border-b-2 border-blue-400'
                    : 'text-gray-400 hover:text-gray-300'
                ]"
              >
                AI生成
              </button>
            </div>

            <!-- Content -->
            <div class="p-4 overflow-y-auto max-h-[calc(80vh-180px)]">
              <!-- Local Tab -->
              <div v-if="subtitleTab === 'local'">
                <div v-if="loadingSubtitles" class="flex items-center justify-center py-8">
                  <div class="animate-spin w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full"></div>
                </div>
                <div v-else-if="subtitleError" class="text-red-400 text-center py-4">
                  {{ subtitleError }}
                </div>
                <div v-else-if="subtitles.length === 0" class="text-gray-400 text-center py-8">
                  未找到字幕文件
                </div>
                <div v-else class="space-y-2">
                  <div
                    v-for="sub in subtitles"
                    :key="sub.path"
                    class="flex items-center justify-between bg-gray-700 rounded-lg p-3 hover:bg-gray-600 transition-colors"
                  >
                    <div class="flex-1 min-w-0">
                      <p class="text-white text-sm font-medium truncate">{{ sub.filename }}</p>
                      <p class="text-gray-400 text-xs truncate">{{ sub.path }}</p>
                      <p class="text-gray-500 text-xs">{{ formatFileSize(sub.size) }}</p>
                    </div>
                    <div class="flex gap-2 ml-4">
                      <button
                        @click="openSubtitleFile(sub.path, sub.filename)"
                        class="px-3 py-1 bg-blue-600 hover:bg-blue-500 text-white text-sm rounded transition-colors"
                      >
                        查看
                      </button>
                      <button
                        @click="deleteSubtitle(sub.path, sub.filename)"
                        class="px-3 py-1 bg-red-600 hover:bg-red-500 text-white text-sm rounded transition-colors"
                      >
                        删除
                      </button>
                    </div>
                  </div>
                </div>
              </div>

              <!-- Online Search Tab -->
              <div v-if="subtitleTab === 'search'">
                <div v-if="searchingOnline" class="flex items-center justify-center py-8">
                  <div class="animate-spin w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full"></div>
                  <span class="ml-3 text-gray-400">搜索中...</span>
                </div>
                <div v-else-if="subtitleError" class="text-red-400 text-center py-4">
                  {{ subtitleError }}
                </div>
                <div v-else-if="onlineSubtitles.length === 0" class="text-gray-400 text-center py-8">
                  <p>点击上方"在线搜索"按钮搜索字幕</p>
                </div>
                <div v-else class="space-y-2">
                  <div
                    v-for="(sub, index) in onlineSubtitles"
                    :key="index"
                    class="flex items-center justify-between bg-gray-700 rounded-lg p-3 hover:bg-gray-600 transition-colors"
                  >
                    <div class="flex-1 min-w-0">
                      <p class="text-white text-sm font-medium truncate">{{ sub.name }}</p>
                      <p class="text-gray-400 text-xs">语言: {{ sub.language }} | 来源: {{ sub.source }}</p>
                    </div>
                    <div class="flex gap-2 ml-4">
                      <button
                        @click="previewOnlineSubtitle(sub.url, sub.name)"
                        class="px-3 py-1 bg-blue-600 hover:bg-blue-500 text-white text-sm rounded transition-colors"
                      >
                        预览
                      </button>
                      <button
                        @click="downloadOnlineSubtitle(sub.url, sub.name)"
                        class="px-3 py-1 bg-green-600 hover:bg-green-500 text-white text-sm rounded transition-colors"
                      >
                        下载
                      </button>
                    </div>
                  </div>
                </div>
              </div>

              <!-- Whisper AI Tab -->
              <div v-if="subtitleTab === 'whisper'">
                <div class="space-y-4">
                  <!-- 模型选择 -->
                  <div>
                    <label class="block text-sm font-medium text-gray-300 mb-2">模型</label>
                    <select
                      v-model="whisperModel"
                      :disabled="whisperRunning"
                      class="w-full bg-gray-700 text-white rounded px-3 py-2"
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

                  <!-- 处理管线 -->
                  <div>
                    <label class="block text-sm font-medium text-gray-300 mb-2">处理管线</label>
                    <select
                      v-model="whisperPipeline"
                      :disabled="whisperRunning"
                      class="w-full bg-gray-700 text-white rounded px-3 py-2"
                    >
                      <option value="ensemble">两遍处理 + 智能合并 (推荐)</option>
                      <option value="single">单遍处理</option>
                    </select>
                    <p class="text-xs text-gray-500 mt-1">
                      两遍处理: Pass1使用anime-whisper快速覆盖，Pass2使用Faster-Whisper高质量精修
                    </p>
                  </div>

                  <!-- 合并策略 -->
                  <div v-if="whisperPipeline === 'ensemble'">
                    <label class="block text-sm font-medium text-gray-300 mb-2">合并策略</label>
                    <select
                      v-model="whisperMergeStrategy"
                      :disabled="whisperRunning"
                      class="w-full bg-gray-700 text-white rounded px-3 py-2"
                    >
                      <option value="smart_merge">智能合并 (推荐)</option>
                      <option value="full_merge">合并所有</option>
                      <option value="pass1_primary">Pass1 为主</option>
                      <option value="pass2_primary">Pass2 为主</option>
                      <option value="longest">选择最长文本</option>
                    </select>
                  </div>

                  <!-- 语言 -->
                  <div>
                    <label class="block text-sm font-medium text-gray-300 mb-2">语言</label>
                    <select
                      v-model="whisperLanguage"
                      :disabled="whisperRunning"
                      class="w-full bg-gray-700 text-white rounded px-3 py-2"
                    >
                      <option value="ja">日语</option>
                      <option value="auto">自动检测</option>
                      <option value="en">英语</option>
                      <option value="zh">中文</option>
                    </select>
                  </div>

                  <!-- 敏感度 -->
                  <div>
                    <label class="block text-sm font-medium text-gray-300 mb-2">识别敏感度</label>
                    <select
                      v-model="whisperSensitivity"
                      :disabled="whisperRunning"
                      class="w-full bg-gray-700 text-white rounded px-3 py-2"
                    >
                      <option value="conservative">保守 (减少误识别)</option>
                      <option value="balanced">平衡 (推荐)</option>
                      <option value="aggressive">激进 (更多检测)</option>
                    </select>
                  </div>

                  <!-- 状态 -->
                  <div v-if="whisperStatus" class="text-center py-2 rounded" :class="{
                    'text-blue-400': whisperStatus.includes('创建') || whisperStatus.includes('启动'),
                    'text-green-400': whisperStatus.includes('完成'),
                    'text-red-400': whisperStatus.includes('失败') || whisperStatus.includes('错误')
                  }">
                    {{ whisperStatus }}
                  </div>

                  <!-- 进度条 -->
                  <div v-if="whisperRunning" class="w-full bg-gray-600 rounded-full h-2">
                    <div
                      class="bg-blue-500 h-2 rounded-full transition-all"
                      :style="{ width: whisperProgress + '%' }"
                    ></div>
                  </div>

                  <!-- 开始/停止按钮 -->
                  <div class="flex gap-3">
                    <button
                      v-if="!whisperRunning"
                      @click="startWhisperTask"
                      class="flex-1 px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded transition-colors"
                    >
                      开始生成字幕
                    </button>
                    <button
                      v-else
                      @click="stopWhisperTask"
                      class="flex-1 px-4 py-2 bg-red-600 hover:bg-red-500 text-white rounded transition-colors"
                    >
                      停止
                    </button>
                  </div>

                  <!-- 日志 -->
                  <div
                    v-if="whisperLogs.length > 0"
                    id="whisper-logs"
                    class="bg-gray-900 rounded p-3 h-48 overflow-y-auto font-mono text-sm"
                  >
                    <div v-for="(log, i) in whisperLogs" :key="i" class="text-gray-300 whitespace-pre-wrap">
                      {{ log }}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Subtitle Preview Modal -->
        <Teleport to="body">
          <div
            v-if="showSubtitlePreview"
            class="fixed inset-0 bg-black/80 flex items-center justify-center z-[200] p-4"
            @click.self="closeSubtitlePreview"
          >
            <div class="bg-gray-800 rounded-xl max-w-4xl w-full max-h-[90vh] flex flex-col overflow-hidden">
              <div class="flex items-center justify-between px-4 py-3 border-b border-gray-700">
                <h3 class="text-lg font-medium text-white">{{ subtitlePreviewFilename }}</h3>
                <button
                  @click="closeSubtitlePreview"
                  class="text-gray-400 hover:text-white transition-colors"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" class="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
              <div class="flex-1 overflow-auto p-4">
                <div v-if="loadingSubtitlePreview" class="flex items-center justify-center h-32">
                  <div class="animate-spin w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full"></div>
                </div>
                <pre v-else class="whitespace-pre-wrap text-gray-300 text-sm font-mono leading-relaxed">{{ subtitlePreviewContent }}</pre>
              </div>
            </div>
          </div>
        </Teleport>
      </Teleport>
  </div>
</template>
