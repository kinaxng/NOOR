<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useMediaStore } from '../stores/media'
import { useJobsStore } from '../stores/jobs'
import { useToast } from '../composables/useToast'
import { useI18n } from '../composables/useI18n'
import { useBlurCover } from '../composables/useBlurCover'
import { api } from '../api/client'
import type { Job, MediaItem } from '../api/types'
import MediaGrid from '../components/library/MediaGrid.vue'
import DetailPanel from '../components/library/DetailPanel.vue'
import LadaPanel from '../components/library/LadaPanel.vue'
import SubtitlePanel from '../components/library/SubtitlePanel.vue'

const { t } = useI18n()
const media = useMediaStore()
const jobs = useJobsStore()
const toast = useToast()
const route = useRoute()
const router = useRouter()
const { blurEnabled, toggleBlur } = useBlurCover()

type CoverMode = 'cover' | 'fanart'
const COVER_MODE_KEY = 'noor.library.cover_mode'
const coverMode = ref<CoverMode>('cover')
const searchText = ref('')
const subtitleTab = ref<'local' | 'online' | 'whisper'>('local')

// Panel visibility
const showDetailPanel = ref(false)
const showLadaPanel = ref(false)
const showSubtitlePanel = ref(false)
const loadingDetail = ref(false)
const detailError = ref<string | null>(null)
let detailRequestToken = 0

const activeFilter = ref((route.query.filter as string) || '')

const filters = computed(() => [
  { label: t('library.filter.all'), icon: 'i-lucide-grid', to: '/library' },
  { label: t('library.filter.cracked'), icon: 'i-lucide-unlock', to: { query: { filter: 'cracked' } } },
  { label: t('library.filter.chinese'), icon: 'i-lucide-languages', to: { query: { filter: 'chinese' } } },
  { label: t('library.filter.leaked'), icon: 'i-lucide-upload', to: { query: { filter: 'leaked' } } },
  { label: t('library.filter.uncensored'), icon: 'i-lucide-eye', to: { query: { filter: 'uncensored' } } },
])

const coverModeAriaLabel = computed(() =>
  coverMode.value === 'cover' ? t('library.coverMode.toFanart') : t('library.coverMode.toCover'),
)
const blurTitle = computed(() => blurEnabled.value ? t('toolbar.blurOff') : t('toolbar.blurOn'))
const gridMinCardWidth = computed(() => coverMode.value === 'cover' ? 160 : 360)

const libraryOptions = computed(() => [
  { label: '全部媒体库', value: '' },
  ...media.libraries.map(l => ({ label: l.name, value: String(l.id) })),
])

// Detail helpers
const detail = computed(() => media.selectedItem)
const selectedItem = ref<MediaItem | null>(null)

// Variant rows
const variantRows = computed(() => {
  if (!detail.value?.file_path) return []
  const current = {
    id: detail.value.id,
    path: detail.value.file_path,
    name: fileNameOf(detail.value.file_path, detail.value.name),
    dir: detail.value.file_path.substring(0, detail.value.file_path.lastIndexOf('/')),
    tags: detail.value.tags,
  }
  const siblings = (detail.value.siblings || [])
    .filter(s => s.file_path)
    .map((s, i) => ({
      id: s.id || `${detail.value!.id}-sib-${i}`,
      path: s.file_path!,
      name: fileNameOf(s.file_path, s.name || s.label || `文件 ${i + 1}`),
      dir: s.file_path!.substring(0, s.file_path!.lastIndexOf('/')),
      tags: s.tags,
    }))
  return [current, ...siblings]
})

const selectedVariantPath = ref('')

watch(variantRows, (rows) => {
  if (!rows.length) { selectedVariantPath.value = ''; return }
  if (!rows.some(v => v.path === selectedVariantPath.value)) {
    selectedVariantPath.value = rows[0].path
  }
}, { immediate: true })

function selectVariant(path: string) { selectedVariantPath.value = path }

const ladaSelectedPath = ref('')
const subtitleSelectedPath = ref('')

watch(detail, (d) => {
  if (d?.file_path) {
    ladaSelectedPath.value = d.file_path
    subtitleSelectedPath.value = d.file_path
  }
})

// Panel state management
function resetPanelState(options: { keepSelectedItem?: boolean } = {}) {
  showDetailPanel.value = false
  showLadaPanel.value = false
  showSubtitlePanel.value = false
  loadingDetail.value = false
  detailError.value = null
  subtitleSelectedPath.value = ''
  if (!options.keepSelectedItem) {
    selectedItem.value = null
    media.closeDetail()
  }
}

async function loadItemDetail(item: MediaItem) {
  const token = ++detailRequestToken
  loadingDetail.value = true
  detailError.value = null
  try {
    await media.fetchItemDetail(item.id)
    if (token !== detailRequestToken || selectedItem.value?.id !== item.id) return null
    return media.selectedItem
  } catch (e: any) {
    if (token === detailRequestToken && selectedItem.value?.id === item.id) {
      detailError.value = e?.message || t('common.loadFailed')
    }
    return null
  } finally {
    if (token === detailRequestToken && selectedItem.value?.id === item.id) {
      loadingDetail.value = false
    }
  }
}

// Panel open handlers
function openDetail(item: MediaItem) {
  resetPanelState({ keepSelectedItem: true })
  selectedItem.value = item
  showDetailPanel.value = true
  void loadItemDetail(item)
}

function openLada(item: MediaItem) {
  resetPanelState({ keepSelectedItem: true })
  selectedItem.value = item
  showLadaPanel.value = true
  void loadItemDetail(item)
  loadLadaDefaults()
}

async function openSubtitle(item: MediaItem) {
  resetPanelState({ keepSelectedItem: true })
  selectedItem.value = item
  subtitleSelectedPath.value = item.file_path || item.path || ''
  const d = await loadItemDetail(item)
  if (!d) return
  subtitleSelectedPath.value = d.file_path || item.path || ''
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

// LADA settings
const ladaSettings = ref({
  detection_model: 'v4-fast',
  restoration_model: 'basicvsrpp-v1.2',
  encoding_preset: 'hevc-nvidia-gpu-hq',
})
const ladaSubmitStatus = ref<'idle' | 'submitting' | 'success' | 'error'>('idle')
const ladaSubmitProgress = ref(0)
let ladaProgressTimer: ReturnType<typeof setInterval> | undefined

const detectionModels = [
  { id: 'v4-fast', name: 'V4 Fast' },
  { id: 'v4-accurate', name: 'V4 Accurate' },
]
const restorationModels = [
  { id: 'basicvsrpp-v1.2', name: 'BasicVSR++' },
  { id: 'deepmosaics', name: 'DeepMosaics' },
]
const encodingPresets = [
  { id: 'hevc-nvidia-gpu-hq', name: 'HEVC NVidia GPU HQ' },
  { id: 'hevc-nvidia-gpu-balanced', name: 'HEVC NVidia GPU Balanced' },
  { id: 'hevc-nvidia-gpu-uhq', name: 'HEVC NVidia GPU UHQ' },
  { id: 'h264-nvidia-gpu-fast', name: 'H264 NVidia GPU Fast' },
  { id: 'h264-cpu-fast', name: 'H264 CPU Fast' },
  { id: 'h264-cpu-uhq', name: 'H264 CPU UHQ' },
  { id: 'av1-cpu-uhq', name: 'AV1 CPU UHQ' },
]

// Helpers
function fileNameOf(path?: string | null, fallback = '-') {
  if (!path) return fallback
  return path.split('/').pop() || fallback
}

// Subtitle path watch
watch(subtitleSelectedPath, async (newPath) => {
  if (newPath && showSubtitlePanel.value) {
    selectVariant(newPath)
  }
})

// Cover mode
function toggleCoverMode() {
  coverMode.value = coverMode.value === 'cover' ? 'fanart' : 'cover'
  if (typeof window !== 'undefined') localStorage.setItem(COVER_MODE_KEY, coverMode.value)
}

// Filter
watch(activeFilter, (key) => {
  media.filterTag = key || null
  media.fetchItems(1)
  router.replace({ query: key ? { filter: key } : {} })
})

watch(() => route.query.filter, (f) => {
  const key = (f as string) || ''
  if (key !== activeFilter.value) activeFilter.value = key
})

watch(() => media.selectedLibraryId, () => media.fetchItems(1))

// Debounced search
let searchDebounce: ReturnType<typeof setTimeout> | null = null
watch(searchText, (val) => {
  if (searchDebounce) clearTimeout(searchDebounce)
  searchDebounce = setTimeout(() => {
    media.query = val
    media.fetchItems(1)
  }, 220)
})

// Video preview
const previewVideoPath = ref('')

function openVideoPreview(path?: string) {
  const target = path || selectedVariantPath.value
  if (target) previewVideoPath.value = target
}

// LADA actions
async function loadLadaDefaults() {
  try {
    const data = await api.get<any>('/settings')
    const defaults = data?.lada_defaults || {}
    ladaSettings.value = {
      detection_model: defaults.detection_model || 'v4-fast',
      restoration_model: defaults.restoration_model || 'basicvsrpp-v1.2',
      encoding_preset: defaults.encoding_preset || 'hevc-nvidia-gpu-hq',
    }
  } catch { /* use hardcoded defaults */ }
}

async function submitLadaJob() {
  if (!ladaSelectedPath.value || !detail.value) return
  ladaSubmitStatus.value = 'submitting'
  ladaSubmitProgress.value = 20
  ladaProgressTimer = setInterval(() => {
    ladaSubmitProgress.value = Math.min(92, ladaSubmitProgress.value + 12)
  }, 180)
  try {
    const result = await api.post<Job>('/jobs', {
      emby_item_id: detail.value.id,
      emby_item_name: `[LADA] ${detail.value.name}`,
      input_path: ladaSelectedPath.value,
      settings: { ...ladaSettings.value },
    })
    ladaSubmitProgress.value = 100
    ladaSubmitStatus.value = 'success'
    toast.success(t('ladaPanel.submitQueued') || 'LADA 任务已提交')
    await jobs.fetchJobs()
    handleCloseDetail()
  } catch (e: any) {
    ladaSubmitStatus.value = 'error'
    toast.error(e?.message || '提交失败')
  } finally {
    if (ladaProgressTimer) { clearInterval(ladaProgressTimer); ladaProgressTimer = undefined }
  }
}

// Whisper task submit
const whisperSubmitting = ref(false)
async function submitWhisperTask() {
  const path = subtitleSelectedPath.value || selectedVariantPath.value
  if (!path) return
  whisperSubmitting.value = true
  try {
    await media.submitWhisperTask()
    handleCloseDetail()
  } finally {
    whisperSubmitting.value = false
  }
}

// Subtitle tab change
watch(subtitleTab, (val) => {
  if (val === 'online') media.searchOnlineSubtitles()
})

// Lifecycle
onMounted(async () => {
  if (typeof window !== 'undefined') {
    const saved = localStorage.getItem(COVER_MODE_KEY)
    if (saved === 'cover' || saved === 'fanart') coverMode.value = saved
  }
  const initialFilter = (route.query.filter as string) || ''
  activeFilter.value = initialFilter
  media.filterTag = initialFilter || null
  await media.initialize()
})

onBeforeUnmount(() => {
  if (searchDebounce) clearTimeout(searchDebounce)
  if (ladaProgressTimer) clearInterval(ladaProgressTimer)
})
</script>

<template>
  <UDashboardPanel id="library" grow>
    <template #header>
      <UDashboardNavbar :title="t('library.title')">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #right>
          <div class="flex items-center gap-2">
            <UButton
              color="neutral"
              variant="ghost"
              size="sm"
              class="h-9 w-9"
              :class="coverMode === 'fanart' ? 'ring-1 ring-(--color-noor-500) bg-(--color-noor-600)/15' : ''"
              :aria-label="coverModeAriaLabel"
              :title="coverModeAriaLabel"
              icon="i-heroicons-squares-2x2-20-solid"
              @click="toggleCoverMode"
            />
            <UButton
              color="neutral"
              variant="ghost"
              size="sm"
              class="h-9 w-9"
              :class="blurEnabled ? 'ring-1 ring-(--color-noor-500) bg-(--color-noor-600)/15' : ''"
              :title="blurTitle"
              :icon="blurEnabled ? 'i-heroicons-eye-slash-20-solid' : 'i-heroicons-eye-20-solid'"
              @click="toggleBlur"
            />
            <select v-model="media.selectedLibraryId" class="h-8 px-3 rounded-lg border border-(--ui-border) bg-(--ui-bg) text-sm text-(--ui-text) outline-none focus:border-(--ui-border-accented)">
              <option v-for="lib in libraryOptions" :key="String(lib.value)" :value="String(lib.value)">{{ lib.label }}</option>
            </select>
            <UInput v-model="searchText" icon="i-heroicons-magnifying-glass-20-solid" :placeholder="t('library.search.placeholder')" clearable />
          </div>
        </template>
      </UDashboardNavbar>

      <UDashboardToolbar>
        <UNavigationMenu :items="filters" highlight class="-mx-1 flex-1" />
      </UDashboardToolbar>
    </template>

    <template #body>
      <MediaGrid
        :cover-mode="coverMode"
        :blur-enabled="blurEnabled"
        :grid-min-card-width="gridMinCardWidth"
        :selected-item-id="selectedItem?.id ?? null"
        @open-detail="openDetail"
        @open-lada="openLada"
        @open-subtitle="openSubtitle"
        @page-change="(p: number) => media.fetchItems(p)"
      />
    </template>
  </UDashboardPanel>

  <DetailPanel
    :open="showDetailPanel"
    :detail="detail"
    :loading="loadingDetail"
    :error="detailError"
    :variant-rows="variantRows"
    :selected-variant-path="selectedVariantPath"
    :preview-video-path="previewVideoPath"
    @close="handleCloseDetail"
    @select-variant="selectVariant"
    @open-preview="openVideoPreview()"
    @update:preview-video-path="previewVideoPath = $event"
  />

  <LadaPanel
    :open="showLadaPanel"
    :detail="detail"
    :loading="loadingDetail"
    :error="detailError"
    :variant-rows="variantRows"
    :selected-path="ladaSelectedPath"
    :settings="ladaSettings"
    :detection-models="detectionModels"
    :restoration-models="restorationModels"
    :encoding-presets="encodingPresets"
    :submit-status="ladaSubmitStatus"
    :submit-progress="ladaSubmitProgress"
    @close="handleCloseDetail"
    @update:selected-path="ladaSelectedPath = $event"
    @update:settings="ladaSettings = $event"
    @submit="submitLadaJob"
  />

  <SubtitlePanel
    :open="showSubtitlePanel"
    :detail="detail"
    :loading="loadingDetail"
    :error="detailError"
    :variant-rows="variantRows"
    :selected-path="subtitleSelectedPath"
    :tab="subtitleTab"
    :whisper-preprocess="media.whisperPreprocess"
    :whisper-translate="media.whisperTranslate"
    :whisper-submitting="whisperSubmitting"
    @close="handleCloseSubtitle"
    @update:selected-path="subtitleSelectedPath = $event"
    @update:tab="subtitleTab = $event"
    @submit-whisper="submitWhisperTask"
  />
</template>
