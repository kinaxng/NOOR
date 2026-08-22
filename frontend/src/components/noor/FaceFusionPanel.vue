<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import VuiButton from '../ui/Button/VuiButton.vue'
import VuiSubmitButton from '../ui/SubmitButton.vue'
import { useJobsStore } from '../../stores/jobs'
import { useToast } from '../../composables/useToast'
import api from '../../api'
import type { MediaItem, MediaItemDetail, JobSettings } from '../../api/types'
import PanelHeader from './panels/PanelHeader.vue'
import FilePathSelector from './panels/FilePathSelector.vue'
import { useI18n } from '../../composables/useI18n'
import { useJobNavigation } from '../../composables/useJobNavigation'

const toast = useToast()
const { t } = useI18n()
const jobsStore = useJobsStore()
const { openJobsFocus } = useJobNavigation()
const panelTitle = computed(() => 'FaceFusion')
const isFullWidth = ref(false)

const props = defineProps<{
  open: boolean
  item: MediaItem | null
  detail: MediaItemDetail | null
  initialSelectedPath?: string
  initialSelectedId?: string
}>()

const emit = defineEmits<{
  close: []
}>()

const submitting = ref(false)
const submitStatus = ref<'idle' | 'running' | 'success' | 'error'>('idle')
const submitProgress = ref(0)
const previewLoading = ref(false)
const previewUrl = ref('')
const previewError = ref('')
const previewStale = ref(false)
const previewFrameNumber = ref(0)
const previewFrameTotal = ref(0)
const previewMetadataLoading = ref(false)
const sourceUploadLoading = ref(false)
const uploadedSourceImages = ref<Array<{ id: string; name: string; path: string; preview_url: string }>>([])
const sourceLibraryOpen = ref(false)
const sourceLibraryLoading = ref(false)
const sourceLibraryImages = ref<Array<{ id: string; name: string; path: string; preview_url: string; updated_at?: number }>>([])
const referenceFaces = ref<Array<{ id: string; position: number; preview_url: string; detector_score?: number; gender?: string; age?: number; race?: string }>>([])
const referenceFacesLoading = ref(false)
const referenceFacesError = ref('')
const deepModelDialogOpen = ref(false)
const deepModelLoading = ref(false)
const deepModelUploading = ref(false)
const deepSwapperModels = ref<Array<{
  id: string
  name: string
  filename?: string
  source: string
  size?: number | null
  updated_at?: number | null
  downloaded?: boolean
  downloading?: boolean
  download_status?: string
  progress?: number
  message?: string
}>>([])
let deepModelPollTimer: number | null = null
let referenceFacesTimer: number | null = null

function uniqueSourceImages(images: Array<{ id: string; name: string; path: string; preview_url: string }>) {
  const seen = new Set<string>()
  return images.filter(item => {
    if (!item.path || seen.has(item.path)) return false
    seen.add(item.path)
    return true
  })
}

const facefusionSettings = ref<JobSettings>({
  source_path: '',
  preview_mode: 'default',
  preview_resolution: '768x768',
  execution_provider: 'cuda',
  device_ids: '0',
  thread_count: 8,
  video_memory_strategy: 'strict',
  system_memory_limit: 0,
  log_level: 'info',
  download_providers: 'github huggingface',
  halt_on_error: false,
  processors: 'face_swapper',
  face_swapper_model: 'hyperswap_1a_256',
  face_swapper_pixel_boost: '256x256',
  face_swapper_weight: 0.5,
  face_enhancer_model: 'gfpgan_1.4',
  face_enhancer_blend: 80,
  face_enhancer_weight: 0.5,
  frame_enhancer_model: 'span_kendata_x4',
  frame_enhancer_blend: 80,
  expression_restorer_model: 'live_portrait',
  expression_restorer_factor: 80,
  expression_restorer_areas: 'upper-face lower-face',
  deep_swapper_model: 'iperov/elon_musk_224',
  deep_swapper_morph: 100,
  face_debugger_items: 'face-landmark-5/68 face-mask',
  face_detector_model: 'yolo_face',
  face_detector_size: '640x640',
  face_detector_score: 0.5,
  face_detector_angles: '0',
  face_detector_margin: '0 0 0 0',
  face_landmarker_model: '2dfan4',
  face_landmarker_score: 0.5,
  face_selector_mode: 'reference',
  face_selector_order: 'large-small',
  face_selector_gender: '',
  face_selector_age_start: '',
  face_selector_age_end: '',
  face_selector_race: '',
  reference_frame_number: 0,
  reference_face_position: 0,
  reference_face_distance: 0.3,
  face_tracker_score: 0,
  face_mask_types: 'box',
  face_mask_areas: 'upper-face lower-face mouth',
  face_mask_regions: 'skin left-eyebrow right-eyebrow left-eye right-eye glasses nose mouth upper-lip lower-lip',
  face_mask_blur: 0.3,
  face_mask_padding: '0 0 0 0',
  face_occluder_model: 'xseg_1',
  face_parser_model: 'bisenet_resnet_34',
  output_video_encoder: 'libx264',
  output_video_preset: 'veryfast',
  output_video_quality: 80,
  output_video_scale: '1.0',
  output_video_fps: '',
  output_audio_encoder: 'aac',
  output_audio_quality: 80,
  output_audio_volume: 100,
  output_image_quality: 80,
  output_image_scale: '1.0',
  temp_frame_format: 'png',
})

const facefusionExecutionProviderOptions = ['cpu', 'cuda', 'tensorrt', 'openvino', 'directml', 'rocm', 'coreml']
const facefusionProcessorOptions = [
  { id: 'face_swapper', label: '人脸替换', acceleration: 'tensorrt' },
  { id: 'face_enhancer', label: '人脸增强', acceleration: 'tensorrt' },
  { id: 'frame_enhancer', label: '画面增强', acceleration: 'tensorrt' },
  { id: 'expression_restorer', label: '表情修复', acceleration: 'cuda' },
  { id: 'deep_swapper', label: 'Deep 换脸', acceleration: 'cuda' },
  { id: 'face_debugger', label: '人脸调试', acceleration: 'none' },
]
const facefusionAllowedProcessorIds = new Set(facefusionProcessorOptions.map(item => item.id))
const facefusionDetectorModelOptions = ['many', 'retinaface', 'scrfd', 'yolo_face', 'yunet']
const facefusionDetectorSizeOptionsByModel: Record<string, string[]> = {
  many: ['640x640'],
  retinaface: ['160x160', '320x320', '480x480', '512x512', '640x640'],
  scrfd: ['160x160', '320x320', '480x480', '512x512', '640x640'],
  yolo_face: ['640x640'],
  yunet: ['640x640'],
}
const facefusionDetectorAngleOptions = ['0', '90', '180', '270']
const facefusionMaskTypeOptions = ['box', 'occlusion', 'area', 'region']
const facefusionMaskAreaOptions = ['upper-face', 'lower-face', 'mouth']
const facefusionMaskRegionOptions = ['skin', 'left-eyebrow', 'right-eyebrow', 'left-eye', 'right-eye', 'glasses', 'nose', 'mouth', 'upper-lip', 'lower-lip']
const facefusionOccluderModelOptions = ['many', 'xseg_1', 'xseg_2', 'xseg_3']
const facefusionParserModelOptions = ['bisenet_resnet_18', 'bisenet_resnet_34']
const facefusionLandmarkerModelOptions = ['many', '2dfan4', 'peppa_wutz']
const facefusionSelectorModeOptions = ['reference', 'one', 'many']
const facefusionSelectorOrderOptions = ['large-small', 'small-large', 'left-right', 'right-left', 'top-bottom', 'bottom-top', 'best-worst', 'worst-best']
const facefusionGenderOptions = ['', 'female', 'male']
const facefusionRaceOptions = ['', 'white', 'black', 'latino', 'asian', 'indian', 'arabic']
const facefusionVideoMemoryStrategyOptions = ['strict', 'moderate', 'tolerant']
const facefusionLogLevelOptions = ['error', 'warn', 'info', 'debug']
const facefusionVideoEncoderOptions = ['libx264', 'libx265', 'h264_nvenc', 'hevc_nvenc']
const facefusionVideoPresetOptions = ['ultrafast', 'veryfast', 'fast', 'medium', 'slow']
const facefusionAudioEncoderOptions = ['aac', 'flac', 'libmp3lame', 'libopus', 'libvorbis', 'pcm_s16le', 'pcm_s32le']
const facefusionTempFrameFormatOptions = ['png', 'jpeg', 'bmp', 'tiff']
const facefusionExpressionRestorerModelOptions = ['live_portrait']
const facefusionExpressionRestorerAreaOptions = ['upper-face', 'lower-face']
const facefusionFaceDebuggerItemOptions = ['bounding-box', 'face-landmark-5', 'face-landmark-5/68', 'face-landmark-68', 'face-landmark-68/5', 'face-mask']
const facefusionOptionLabels: Record<string, Record<string, string>> = {
  selectorMode: { reference: '参考人脸', one: '单个人脸', many: '多个人脸' },
  selectorOrder: {
    'large-small': '从大到小',
    'small-large': '从小到大',
    'left-right': '从左到右',
    'right-left': '从右到左',
    'top-bottom': '从上到下',
    'bottom-top': '从下到上',
    'best-worst': '从优到差',
    'worst-best': '从差到优',
  },
  gender: { '': '不限', female: '女性', male: '男性' },
  race: { '': '不限', white: '白人', black: '黑人', latino: '拉丁裔', asian: '亚洲人', indian: '印度人', arabic: '阿拉伯人' },
  maskType: { box: '方框', occlusion: '遮挡', area: '区域', region: '部位' },
  maskArea: { 'upper-face': '上半脸', 'lower-face': '下半脸', mouth: '嘴巴' },
  maskRegion: {
    skin: '皮肤',
    'left-eyebrow': '左眉',
    'right-eyebrow': '右眉',
    'left-eye': '左眼',
    'right-eye': '右眼',
    glasses: '眼镜',
    nose: '鼻子',
    mouth: '嘴巴',
    'upper-lip': '上唇',
    'lower-lip': '下唇',
  },
  memoryStrategy: { strict: '严格', moderate: '均衡', tolerant: '宽松' },
  logLevel: { error: '错误', warn: '警告', info: '信息', debug: '调试' },
  videoPreset: { ultrafast: '最快', veryfast: '很快', fast: '快速', medium: '中等', slow: '慢速' },
  expressionArea: { 'upper-face': '上半脸', 'lower-face': '下半脸' },
  faceDebuggerItem: {
    'bounding-box': '人脸框',
    'face-landmark-5': '5 点特征',
    'face-landmark-5/68': '5/68 点特征',
    'face-landmark-68': '68 点特征',
    'face-landmark-68/5': '68/5 点特征',
    'face-mask': '人脸遮罩',
  },
}
const facefusionScaleOptions = Array.from({ length: 32 }, (_, index) => {
  const value = (index + 1) * 0.25
  return Number.isInteger(value) ? value.toFixed(1) : String(value)
})
const facefusionFaceSwapperModelOptions = ['blendswap_256', 'ghost_1_256', 'ghost_2_256', 'ghost_3_256', 'hififace_unofficial_256', 'hyperswap_1a_256', 'hyperswap_1b_256', 'hyperswap_1c_256', 'inswapper_128', 'inswapper_128_fp16', 'simswap_256', 'simswap_unofficial_512', 'uniface_256']
const facefusionPixelBoostOptionsByModel: Record<string, string[]> = {
  blendswap_256: ['256x256', '384x384', '512x512', '768x768', '1024x1024'],
  ghost_1_256: ['256x256', '512x512', '768x768', '1024x1024'],
  ghost_2_256: ['256x256', '512x512', '768x768', '1024x1024'],
  ghost_3_256: ['256x256', '512x512', '768x768', '1024x1024'],
  hififace_unofficial_256: ['256x256', '512x512', '768x768', '1024x1024'],
  hyperswap_1a_256: ['256x256', '512x512', '768x768', '1024x1024'],
  hyperswap_1b_256: ['256x256', '512x512', '768x768', '1024x1024'],
  hyperswap_1c_256: ['256x256', '512x512', '768x768', '1024x1024'],
  inswapper_128: ['128x128', '256x256', '384x384', '512x512', '768x768', '1024x1024'],
  inswapper_128_fp16: ['128x128', '256x256', '384x384', '512x512', '768x768', '1024x1024'],
  simswap_256: ['256x256', '512x512', '768x768', '1024x1024'],
  simswap_unofficial_512: ['512x512', '768x768', '1024x1024'],
  uniface_256: ['256x256', '512x512', '768x768', '1024x1024'],
}
const facefusionFaceEnhancerModelOptions = ['gfpgan_1.2', 'gfpgan_1.3', 'gfpgan_1.4', 'gpen_bfr_256', 'gpen_bfr_512', 'restoreformer_plus_plus']
const facefusionFrameEnhancerModelOptions = ['span_kendata_x4', 'real_esrgan_x2', 'real_esrgan_x2_fp16', 'real_esrgan_x4', 'real_esrgan_x4_fp16', 'real_hatgan_x4', 'ultra_sharp_x4']

function facefusionOptionLabel(group: keyof typeof facefusionOptionLabels, value: string) {
  const label = facefusionOptionLabels[group]?.[value]
  return label ? `${label} · ${value || 'none'}` : value
}

// Load settings from backend when panel opens
watch(() => props.open, async (isOpen) => {
  if (!isOpen) return

  try {
    const resp = await api.get('/settings')
    const ffDefaults = resp.data?.facefusion_defaults || {}
    facefusionSettings.value = {
      ...facefusionSettings.value,
      preview_mode: ffDefaults.preview_mode || 'default',
      preview_resolution: ffDefaults.preview_resolution || '768x768',
      execution_provider: ffDefaults.execution_provider || 'cuda',
      device_ids: ffDefaults.device_ids || '0',
      thread_count: ffDefaults.thread_count ?? 8,
      video_memory_strategy: ffDefaults.video_memory_strategy || 'strict',
      system_memory_limit: ffDefaults.system_memory_limit ?? 0,
      log_level: ffDefaults.log_level || 'info',
      download_providers: ffDefaults.download_providers || 'github huggingface',
      halt_on_error: ffDefaults.halt_on_error ?? false,
      processors: sanitizeFacefusionProcessors(ffDefaults.processors || 'face_swapper'),
      face_swapper_model: ffDefaults.face_swapper_model || 'hyperswap_1a_256',
      face_swapper_pixel_boost: ffDefaults.face_swapper_pixel_boost || '256x256',
      face_swapper_weight: ffDefaults.face_swapper_weight ?? 0.5,
      face_enhancer_model: ffDefaults.face_enhancer_model || 'gfpgan_1.4',
      face_enhancer_blend: ffDefaults.face_enhancer_blend ?? 80,
      face_enhancer_weight: ffDefaults.face_enhancer_weight ?? 0.5,
      frame_enhancer_model: ffDefaults.frame_enhancer_model || 'span_kendata_x4',
      frame_enhancer_blend: ffDefaults.frame_enhancer_blend ?? 80,
      expression_restorer_model: ffDefaults.expression_restorer_model || 'live_portrait',
      expression_restorer_factor: ffDefaults.expression_restorer_factor ?? 80,
      expression_restorer_areas: ffDefaults.expression_restorer_areas || 'upper-face lower-face',
      deep_swapper_model: ffDefaults.deep_swapper_model || 'iperov/elon_musk_224',
      deep_swapper_morph: ffDefaults.deep_swapper_morph ?? 100,
      face_debugger_items: ffDefaults.face_debugger_items || 'face-landmark-5/68 face-mask',
      face_detector_model: ffDefaults.face_detector_model || 'yolo_face',
      face_detector_size: ffDefaults.face_detector_size || '640x640',
      face_detector_score: ffDefaults.face_detector_score ?? 0.5,
      face_detector_angles: ffDefaults.face_detector_angles || '0',
      face_detector_margin: ffDefaults.face_detector_margin || '0 0 0 0',
      face_landmarker_model: ffDefaults.face_landmarker_model || '2dfan4',
      face_landmarker_score: ffDefaults.face_landmarker_score ?? 0.5,
      face_selector_mode: ffDefaults.face_selector_mode || 'reference',
      face_selector_order: ffDefaults.face_selector_order || 'large-small',
      face_selector_gender: ffDefaults.face_selector_gender || '',
      face_selector_age_start: ffDefaults.face_selector_age_start || '',
      face_selector_age_end: ffDefaults.face_selector_age_end || '',
      face_selector_race: ffDefaults.face_selector_race || '',
      reference_frame_number: ffDefaults.reference_frame_number ?? 0,
      reference_face_position: ffDefaults.reference_face_position ?? 0,
      reference_face_distance: ffDefaults.reference_face_distance ?? 0.3,
      face_tracker_score: ffDefaults.face_tracker_score ?? 0,
      face_mask_types: ffDefaults.face_mask_types || 'box',
      face_mask_areas: ffDefaults.face_mask_areas || facefusionMaskAreaOptions.join(' '),
      face_mask_regions: ffDefaults.face_mask_regions || facefusionMaskRegionOptions.join(' '),
      face_mask_blur: ffDefaults.face_mask_blur ?? 0.3,
      face_mask_padding: ffDefaults.face_mask_padding || '0 0 0 0',
      face_occluder_model: ffDefaults.face_occluder_model || 'xseg_1',
      face_parser_model: ffDefaults.face_parser_model || 'bisenet_resnet_34',
      output_video_encoder: ffDefaults.output_video_encoder || 'libx264',
      output_video_preset: ffDefaults.output_video_preset || 'veryfast',
      output_video_quality: ffDefaults.output_video_quality ?? 80,
      output_video_scale: ffDefaults.output_video_scale || '1.0',
      output_video_fps: ffDefaults.output_video_fps || '',
      output_audio_encoder: ffDefaults.output_audio_encoder || 'aac',
      output_audio_quality: ffDefaults.output_audio_quality ?? 80,
      output_audio_volume: ffDefaults.output_audio_volume ?? 100,
      output_image_quality: ffDefaults.output_image_quality ?? 80,
      output_image_scale: ffDefaults.output_image_scale || '1.0',
      temp_frame_format: ffDefaults.temp_frame_format || 'png',
    }
  } catch (e) {
    // Use hardcoded defaults on error
  }
}, { immediate: true })

// Init selected path when detail changes
const selectedSubmitPath = ref('')
const selectedSubmitId = ref('')

const allSubmitPaths = computed(() => {
  if (!props.detail?.file_path) return []
  const paths = [{ path: props.detail.file_path, id: props.detail.id }]
  for (const s of (props.detail.siblings || [])) {
    if (s.file_path && !paths.some(p => p.path === s.file_path)) {
      paths.push({ path: s.file_path, id: s.id || props.detail.id })
    }
  }
  return paths
})

watch([() => props.detail, () => props.initialSelectedPath, () => props.initialSelectedId], ([detail, initialPath, initialId]) => {
  if (!detail?.file_path) return
  selectedSubmitPath.value = initialPath || detail.file_path
  selectedSubmitId.value = initialId || detail.id
}, { immediate: true })

watch(selectedSubmitPath, async () => {
  if (!selectedSubmitPath.value) return
  await loadFaceFusionPreviewMetadata()
}, { immediate: true })

watch(
  [selectedSubmitPath, () => facefusionSettings.value.source_path, uploadedSourceImages],
  () => {
    if (previewUrl.value) {
      previewStale.value = true
    }
  }
)

watch(facefusionSettings, () => {
  if (previewUrl.value) {
    previewStale.value = true
  }
}, { deep: true })

watch(deepModelDialogOpen, (isOpen) => {
  if (!isOpen) stopDeepModelPolling()
})

watch(
  [
    selectedSubmitPath,
    () => facefusionSettings.value.face_selector_mode,
    () => facefusionSettings.value.reference_frame_number,
    () => facefusionSettings.value.face_detector_model,
    () => facefusionSettings.value.face_detector_size,
    () => facefusionSettings.value.face_detector_score,
    () => facefusionSettings.value.face_detector_angles,
    () => facefusionSettings.value.face_detector_margin,
    () => facefusionSettings.value.face_landmarker_model,
    () => facefusionSettings.value.face_landmarker_score,
    () => facefusionSettings.value.face_selector_order,
    () => facefusionSettings.value.face_selector_gender,
    () => facefusionSettings.value.face_selector_race,
    () => facefusionSettings.value.face_selector_age_start,
    () => facefusionSettings.value.face_selector_age_end,
  ],
  () => scheduleReferenceFacesLoad(),
)

const displayTitle = computed(() => {
  if (!props.detail) return ''
  return props.detail.nfo?.title || props.detail.nfo?.originaltitle || props.detail.name
})

const previewFrameMax = computed(() => Math.max(0, previewFrameTotal.value > 0 ? previewFrameTotal.value - 1 : 0))
const previewTimeLabel = computed(() => {
  if (!previewFrameTotal.value) return `帧 ${previewFrameNumber.value}`
  return `帧 ${previewFrameNumber.value} / ${previewFrameMax.value}`
})
const facefusionSourcePaths = computed(() => {
  const uploadedPaths = uploadedSourceImages.value.map(item => item.path).filter(Boolean)
  return Array.from(new Set(uploadedPaths))
})
const selectedFacefusionProcessors = computed(() => splitTokens(String(facefusionSettings.value.processors || '')).filter(item => facefusionAllowedProcessorIds.has(item)))
const selectedFacefusionMaskTypes = computed(() => splitTokens(String(facefusionSettings.value.face_mask_types || '')))
const facefusionReferenceMode = computed(() => String(facefusionSettings.value.face_selector_mode || 'reference') === 'reference')
const facefusionPixelBoostOptions = computed(() => {
  const model = String(facefusionSettings.value.face_swapper_model || 'hyperswap_1a_256')
  return facefusionPixelBoostOptionsByModel[model] || ['256x256']
})
const facefusionDetectorSizeOptions = computed(() => {
  const model = String(facefusionSettings.value.face_detector_model || 'yolo_face')
  return facefusionDetectorSizeOptionsByModel[model] || ['640x640']
})

watch(() => facefusionSettings.value.face_swapper_model, () => {
  const options = facefusionPixelBoostOptions.value
  if (!options.includes(String(facefusionSettings.value.face_swapper_pixel_boost || ''))) {
    facefusionSettings.value.face_swapper_pixel_boost = options[0]
  }
})

watch(() => facefusionSettings.value.face_detector_model, () => {
  const options = facefusionDetectorSizeOptions.value
  if (!options.includes(String(facefusionSettings.value.face_detector_size || ''))) {
    facefusionSettings.value.face_detector_size = options[options.length - 1] || '640x640'
  }
})

function splitTokens(value: string) {
  return String(value || '').split(/[\s,]+/).map(item => item.trim()).filter(Boolean)
}

function sanitizeFacefusionProcessors(value: string) {
  const processors = splitTokens(value).filter(item => facefusionAllowedProcessorIds.has(item))
  return (processors.length ? processors : ['face_swapper']).join(' ')
}

function hasFacefusionToken(key: string, token: string) {
  const settingsValue = facefusionSettings.value as Record<string, unknown>
  return splitTokens(String(settingsValue[key] || '')).includes(token)
}

function toggleFacefusionToken(key: string, token: string) {
  const settingsValue = facefusionSettings.value as Record<string, unknown>
  const values = splitTokens(String(settingsValue[key] || ''))
  const next = values.includes(token)
    ? values.filter(item => item !== token)
    : [...values, token]
  settingsValue[key] = next.join(' ')
}

function getFacefusionQuadValue(key: string, index: number) {
  const settingsValue = facefusionSettings.value as Record<string, unknown>
  const values = splitTokens(String(settingsValue[key] || '0 0 0 0')).map(item => Number(item))
  return Number.isFinite(values[index]) ? values[index] : 0
}

function updateFacefusionQuadValue(key: string, index: number, value: unknown) {
  const settingsValue = facefusionSettings.value as Record<string, unknown>
  const values = [0, 0, 0, 0].map((fallback, itemIndex) => getFacefusionQuadValue(key, itemIndex) || fallback)
  const next = Math.max(0, Math.min(100, Number(value) || 0))
  values[index] = next
  settingsValue[key] = values.map(item => String(Math.round(item))).join(' ')
}

function scheduleReferenceFacesLoad(delay = 450) {
  if (referenceFacesTimer !== null) {
    window.clearTimeout(referenceFacesTimer)
    referenceFacesTimer = null
  }
  if (!selectedSubmitPath.value || !facefusionReferenceMode.value) {
    referenceFaces.value = []
    referenceFacesError.value = ''
    return
  }
  referenceFacesTimer = window.setTimeout(() => {
    void loadReferenceFaces()
  }, delay)
}

async function loadReferenceFaces() {
  if (!selectedSubmitPath.value || !facefusionReferenceMode.value) return
  referenceFacesLoading.value = true
  referenceFacesError.value = ''
  try {
    const frameNumber = Math.max(0, Number(facefusionSettings.value.reference_frame_number || 0))
    const resp = await api.post('/facefusion/reference-faces', {
      input_path: selectedSubmitPath.value,
      settings: facefusionSettings.value,
      frame_number: frameNumber,
    })
    referenceFaces.value = Array.isArray(resp.data?.faces) ? resp.data.faces : []
    if (!referenceFaces.value.some(face => face.position === Number(facefusionSettings.value.reference_face_position || 0))) {
      facefusionSettings.value.reference_face_position = referenceFaces.value[0]?.position ?? 0
    }
  } catch (e: any) {
    referenceFaces.value = []
    referenceFacesError.value = e.response?.data?.detail || '参考人脸读取失败'
  } finally {
    referenceFacesLoading.value = false
  }
}

function selectReferenceFace(position: number) {
  facefusionSettings.value.reference_face_position = position
}

async function loadDeepSwapperModels() {
  deepModelLoading.value = true
  try {
    const resp = await api.get('/facefusion/deep-swapper-models')
    deepSwapperModels.value = Array.isArray(resp.data?.models) ? resp.data.models : []
    scheduleDeepModelPolling()
  } catch (e: any) {
    toast.error(e.response?.data?.detail || '读取 Deep 模型失败')
  } finally {
    deepModelLoading.value = false
  }
}

async function openDeepModelDialog() {
  deepModelDialogOpen.value = true
  await loadDeepSwapperModels()
}

function stopDeepModelPolling() {
  if (deepModelPollTimer !== null) {
    window.clearTimeout(deepModelPollTimer)
    deepModelPollTimer = null
  }
}

function scheduleDeepModelPolling() {
  stopDeepModelPolling()
  if (!deepModelDialogOpen.value || !deepSwapperModels.value.some(model => model.downloading)) return
  deepModelPollTimer = window.setTimeout(() => {
    void loadDeepSwapperModels()
  }, 1200)
}

async function selectDeepSwapperModel(modelId: string) {
  const model = deepSwapperModels.value.find(item => item.id === modelId)
  if (model && model.source !== 'custom' && !model.downloaded) {
    await downloadDeepSwapperModel(model.id)
    return
  }
  facefusionSettings.value.deep_swapper_model = modelId
  deepModelDialogOpen.value = false
  stopDeepModelPolling()
}

async function downloadDeepSwapperModel(modelId: string) {
  try {
    const resp = await api.post('/facefusion/deep-swapper-models/download', { model_id: modelId })
    const nextModel = resp.data?.model
    if (nextModel?.id) {
      deepSwapperModels.value = deepSwapperModels.value.map(model => model.id === nextModel.id ? { ...model, ...nextModel } : model)
    }
    scheduleDeepModelPolling()
  } catch (e: any) {
    toast.error(e.response?.data?.detail || '下载 Deep 模型失败')
  }
}

async function handleDeepModelUpload(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  deepModelUploading.value = true
  try {
    const formData = new FormData()
    formData.append('file', file)
    const resp = await api.post('/facefusion/deep-swapper-models', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    const model = resp.data?.model
    if (model?.id) {
      facefusionSettings.value.deep_swapper_model = model.id
    }
    await loadDeepSwapperModels()
    toast.success('Deep 模型已上传')
  } catch (e: any) {
    toast.error(e.response?.data?.detail || '上传 Deep 模型失败')
  } finally {
    deepModelUploading.value = false
    input.value = ''
  }
}

function handleClose() {
  emit('close')
}

async function loadSourceImageLibrary() {
  sourceLibraryLoading.value = true
  try {
    const resp = await api.get('/facefusion/source-images')
    sourceLibraryImages.value = Array.isArray(resp.data?.files)
      ? resp.data.files.map((item: any) => ({
        id: item.id || '',
        name: item.name || '源脸图片',
        path: item.path || '',
        preview_url: item.preview_url || '',
        updated_at: item.updated_at,
      })).filter((item: any) => item.id && item.path)
      : []
  } catch (e: any) {
    toast.error(e.response?.data?.detail || '图片库读取失败')
  } finally {
    sourceLibraryLoading.value = false
  }
}

async function toggleSourceLibrary() {
  sourceLibraryOpen.value = !sourceLibraryOpen.value
  if (sourceLibraryOpen.value) {
    await loadSourceImageLibrary()
  }
}

function isSourceSelected(path: string) {
  return uploadedSourceImages.value.some(item => item.path === path)
}

function toggleLibraryImage(image: { id: string; name: string; path: string; preview_url: string }) {
  if (isSourceSelected(image.path)) {
    uploadedSourceImages.value = uploadedSourceImages.value.filter(item => item.path !== image.path)
  } else {
    uploadedSourceImages.value = uniqueSourceImages([
      ...uploadedSourceImages.value,
      {
        id: image.id,
        name: image.name,
        path: image.path,
        preview_url: image.preview_url,
      },
    ])
  }
  if (previewUrl.value) previewStale.value = true
}

async function deleteLibraryImage(image: { id: string; path: string }) {
  try {
    await api.delete(`/facefusion/source-images/${encodeURIComponent(image.id)}`)
    sourceLibraryImages.value = sourceLibraryImages.value.filter(item => item.id !== image.id)
    uploadedSourceImages.value = uploadedSourceImages.value.filter(item => item.path !== image.path)
    if (previewUrl.value) previewStale.value = true
    toast.success('图片已删除')
  } catch (e: any) {
    toast.error(e.response?.data?.detail || '图片删除失败')
  }
}

async function loadFaceFusionPreviewMetadata() {
  previewMetadataLoading.value = true
  try {
    const resp = await api.post('/facefusion/preview/metadata', {
      input_path: selectedSubmitPath.value,
    })
    previewFrameTotal.value = Number(resp.data?.frame_total || 0)
    if (previewFrameTotal.value > 0 && previewFrameNumber.value > previewFrameMax.value) {
      previewFrameNumber.value = previewFrameMax.value
    }
  } catch (e) {
    previewFrameTotal.value = 0
  } finally {
    previewMetadataLoading.value = false
  }
}

function markPreviewFrameChanged() {
  if (previewUrl.value) {
    previewStale.value = true
  }
}

async function handlePreviewSliderCommit() {
  markPreviewFrameChanged()
  if (facefusionSourcePaths.value.length && !previewLoading.value) {
    await handleGenerateFaceFusionPreview()
  }
}

async function handleSubmitFaceFusionJob() {
  if (!selectedSubmitPath.value || !facefusionSourcePaths.value.length) return

  submitting.value = true
  submitStatus.value = 'running'
  submitProgress.value = 12
  try {
    const createdJob = await jobsStore.createJob({
      job_type: 'facefusion_restore',
      emby_item_id: selectedSubmitId.value,
      emby_item_name: displayTitle.value,
      input_path: selectedSubmitPath.value,
      settings: {
        ...facefusionSettings.value,
        source_paths: facefusionSourcePaths.value,
      },
    })
    submitProgress.value = 72
    await jobsStore.fetchJobs()
    submitProgress.value = 100
    submitStatus.value = 'success'
    handleClose()
    toast.success(t('ladaPanel.submitQueued'))
    await openJobsFocus({ jobId: createdJob.id, chainId: createdJob.chain_id })
  } catch (e) {
    console.error(e)
    submitProgress.value = 100
    submitStatus.value = 'error'
    toast.error(t('ladaPanel.submitFailed'))
  } finally {
    submitting.value = false
  }
}

async function handleGenerateFaceFusionPreview() {
  if (previewLoading.value) return
  if (!selectedSubmitPath.value || !facefusionSourcePaths.value.length) {
    toast.error('请先填写源脸图片')
    return
  }

  previewLoading.value = true
  previewError.value = ''
  try {
    const frameNumber = Math.max(0, Math.min(Number(previewFrameNumber.value || 0), previewFrameMax.value || Number(previewFrameNumber.value || 0)))
    const resp = await api.post('/facefusion/preview', {
      input_path: selectedSubmitPath.value,
      frame_number: frameNumber,
      preview_mode: String(facefusionSettings.value.preview_mode || 'default'),
      preview_resolution: String(facefusionSettings.value.preview_resolution || '768x768'),
      settings: {
        ...facefusionSettings.value,
        source_paths: facefusionSourcePaths.value,
      },
    }, {
      timeout: 300000,
    })
    previewFrameNumber.value = frameNumber
    previewUrl.value = `${resp.data.preview_url}?t=${Date.now()}`
    previewStale.value = false
  } catch (e: any) {
    console.error(e)
    previewError.value = e.response?.data?.detail || 'FaceFusion 预览失败'
    toast.error(previewError.value)
  } finally {
    previewLoading.value = false
  }
}

async function handleSourceImageUpload(event: Event) {
  const input = event.target as HTMLInputElement
  const files = Array.from(input.files || [])
  if (!files.length) return

  sourceUploadLoading.value = true
  try {
    const form = new FormData()
    files.forEach(file => form.append('files', file))
    const resp = await api.post('/facefusion/source-images', form)
    const nextFiles = Array.isArray(resp.data?.files) ? resp.data.files : []
    uploadedSourceImages.value = uniqueSourceImages([
      ...uploadedSourceImages.value,
      ...nextFiles
        .filter((item: any) => item?.path)
        .map((item: any) => ({
          id: item.id || '',
          name: item.name || '源脸图片',
          path: item.path,
          preview_url: item.preview_url || '',
        })),
    ])
    await loadSourceImageLibrary()
    if (previewUrl.value) previewStale.value = true
  } catch (e: any) {
    toast.error(e.response?.data?.detail || '源脸图片上传失败')
  } finally {
    sourceUploadLoading.value = false
    input.value = ''
  }
}

async function removeUploadedSourceImage(source: { id: string; path: string }) {
  uploadedSourceImages.value = uploadedSourceImages.value.filter(item => item.path !== source.path)
  if (previewUrl.value) previewStale.value = true
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
        <div
          class="relative bg-bg-surface border-l border-border-default flex flex-col overflow-hidden shadow-2xl h-full w-full"
          :class="isFullWidth ? 'lg:w-[min(96vw,1680px)]' : 'lg:w-[min(50vw,960px)]'"
        >
          <!-- Content -->
          <template v-if="detail">
            <!-- Scrollable wrapper -->
            <div class="flex-1 overflow-y-auto p-4 space-y-4 relative">

              <div class="panel-topbar">
                <span class="panel-topbar__title">{{ panelTitle }}</span>
                <div class="panel-topbar__actions">
                  <button
                    @click="isFullWidth = !isFullWidth"
                    :title="isFullWidth ? '收回默认面板' : '扩展至全屏面板'"
                    :aria-label="isFullWidth ? '收回默认面板' : '扩展至全屏面板'"
                    class="panel-topbar__close"
                  >
                    <svg v-if="!isFullWidth" xmlns="http://www.w3.org/2000/svg" class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5" />
                    </svg>
                    <svg v-else xmlns="http://www.w3.org/2000/svg" class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 4v5H4M15 4v5h5M9 20v-5H4M15 20v-5h5" />
                    </svg>
                  </button>
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
              </div>

              <!-- Shared Header: backdrop + title + tagline + actors -->
              <PanelHeader v-if="!isFullWidth" :detail="detail" :show-play="false">
                <template #media>
                  <div class="facefusion-preview">
                    <img
                      v-if="previewUrl"
                      :src="previewUrl"
                      class="facefusion-preview__image"
                      alt="FaceFusion 预览"
                    />
                    <div v-else class="facefusion-preview__empty">
                      <span>FaceFusion 预览</span>
                    </div>
                    <div class="facefusion-preview__overlay">
                      <div class="facefusion-preview__controls">
                        <input
                          v-model.number="previewFrameNumber"
                          class="preview-frame-slider"
                          type="range"
                          min="0"
                          :max="previewFrameMax"
                          step="1"
                          :disabled="previewLoading || previewMetadataLoading || previewFrameMax <= 0"
                          @input="markPreviewFrameChanged"
                          @change="handlePreviewSliderCommit"
                        />
                        <span class="facefusion-preview__frame">{{ previewLoading ? '生成中' : previewMetadataLoading ? '读取中' : previewTimeLabel }}</span>
                      </div>
                    </div>
                    <div v-if="previewLoading" class="facefusion-preview__busy">
                      <span></span>
                      <strong>正在生成预览</strong>
                    </div>
                  </div>
                </template>
              </PanelHeader>

              <!-- File Selector -->
              <FilePathSelector
                v-if="!isFullWidth"
                :file-path="detail?.file_path"
                :sibling-paths="detail?.siblings"
                v-model="selectedSubmitPath"
                @update:model-value="selectedSubmitId = allSubmitPaths.find(p => p.path === $event)?.id || detail?.id || ''"
              />

              <div v-if="isFullWidth" class="facefusion-native-shell">
                <div class="facefusion-native-grid">
                  <section class="facefusion-native-column facefusion-native-column--processors">
                    <div class="facefusion-native-group facefusion-native-group--left">
                      <h3>处理器</h3>
                      <div class="facefusion-choice-chips">
                        <button
                          v-for="processor in facefusionProcessorOptions"
                          :key="processor.id"
                          type="button"
                          class="processor-chip"
                          :class="{ 'is-active': hasFacefusionToken('processors', processor.id) }"
                          @click="toggleFacefusionToken('processors', processor.id)"
                        >
                          <span>{{ processor.label }}</span>
                          <small>{{ processor.id }}</small>
                          <em :class="{ 'is-cuda': processor.acceleration === 'cuda', 'is-muted': processor.acceleration === 'none' }">
                            {{ processor.acceleration === 'tensorrt' ? 'TRT 推荐' : processor.acceleration === 'cuda' ? 'CUDA 推荐' : '无推理加速' }}
                          </em>
                        </button>
                      </div>
                    </div>

                    <div v-if="selectedFacefusionProcessors.includes('face_swapper')" class="facefusion-native-group facefusion-native-group--left">
                      <h3>换脸参数</h3>
                      <div class="facefusion-native-fields">
                        <label>
                          <span>换脸模型</span>
                          <select v-model="facefusionSettings.face_swapper_model" class="settings-input w-full">
                            <option v-for="model in facefusionFaceSwapperModelOptions" :key="model" :value="model">{{ model }}</option>
                          </select>
                        </label>
                        <label>
                          <span>像素增强尺寸</span>
                          <select v-model="facefusionSettings.face_swapper_pixel_boost" class="settings-input w-full">
                            <option v-for="size in facefusionPixelBoostOptions" :key="size" :value="size">{{ size }}</option>
                          </select>
                        </label>
                        <label>
                          <span>换脸权重 {{ Number(facefusionSettings.face_swapper_weight || 0).toFixed(2) }}</span>
                          <input v-model.number="facefusionSettings.face_swapper_weight" type="range" min="0" max="1" step="0.05" class="facefusion-range" />
                        </label>
                      </div>
                    </div>

                    <div v-if="selectedFacefusionProcessors.includes('face_enhancer')" class="facefusion-native-group facefusion-native-group--left">
                      <h3>脸部增强参数</h3>
                      <div class="facefusion-native-fields">
                        <label>
                          <span>脸部增强模型</span>
                          <select v-model="facefusionSettings.face_enhancer_model" class="settings-input w-full">
                            <option v-for="model in facefusionFaceEnhancerModelOptions" :key="model" :value="model">{{ model }}</option>
                          </select>
                        </label>
                        <label>
                          <span>脸部增强混合 {{ facefusionSettings.face_enhancer_blend }}</span>
                          <input v-model.number="facefusionSettings.face_enhancer_blend" type="range" min="0" max="100" step="1" class="facefusion-range" />
                        </label>
                        <label>
                          <span>脸部增强权重 {{ Number(facefusionSettings.face_enhancer_weight || 0).toFixed(2) }}</span>
                          <input v-model.number="facefusionSettings.face_enhancer_weight" type="range" min="0" max="1" step="0.05" class="facefusion-range" />
                        </label>
                      </div>
                    </div>

                    <div v-if="selectedFacefusionProcessors.includes('expression_restorer')" class="facefusion-native-group facefusion-native-group--left">
                      <h3>表情修复参数</h3>
                      <div class="facefusion-native-fields">
                        <label>
                          <span>表情修复模型</span>
                          <select v-model="facefusionSettings.expression_restorer_model" class="settings-input w-full">
                            <option v-for="model in facefusionExpressionRestorerModelOptions" :key="model" :value="model">{{ model }}</option>
                          </select>
                        </label>
                        <label>
                          <span>修复强度 {{ facefusionSettings.expression_restorer_factor }}</span>
                          <input v-model.number="facefusionSettings.expression_restorer_factor" type="range" min="0" max="100" step="1" class="facefusion-range" />
                        </label>
                        <label>
                          <span>修复区域</span>
                          <div class="facefusion-choice-chips">
                            <button
                              v-for="area in facefusionExpressionRestorerAreaOptions"
                              :key="area"
                              type="button"
                              :class="{ 'is-active': hasFacefusionToken('expression_restorer_areas', area) }"
                              @click="toggleFacefusionToken('expression_restorer_areas', area)"
                            >
                              {{ facefusionOptionLabel('expressionArea', area) }}
                            </button>
                          </div>
                        </label>
                      </div>
                    </div>

                    <div v-if="selectedFacefusionProcessors.includes('deep_swapper')" class="facefusion-native-group facefusion-native-group--left">
                      <h3>Deep 换脸参数</h3>
                      <div class="facefusion-native-fields">
                        <label>
                          <span>Deep 模型</span>
                          <button type="button" class="facefusion-model-select" @click="openDeepModelDialog">
                            <strong>{{ facefusionSettings.deep_swapper_model || '选择 Deep 模型' }}</strong>
                            <span>选择 / 上传</span>
                          </button>
                        </label>
                        <label>
                          <span>融合强度 {{ facefusionSettings.deep_swapper_morph }}</span>
                          <input v-model.number="facefusionSettings.deep_swapper_morph" type="range" min="0" max="100" step="1" class="facefusion-range" />
                        </label>
                      </div>
                    </div>

                    <div v-if="selectedFacefusionProcessors.includes('face_debugger')" class="facefusion-native-group facefusion-native-group--left">
                      <h3>人脸调试参数</h3>
                      <div class="facefusion-native-fields">
                        <label>
                          <span>调试叠加项</span>
                          <div class="facefusion-choice-chips">
                            <button
                              v-for="item in facefusionFaceDebuggerItemOptions"
                              :key="item"
                              type="button"
                              :class="{ 'is-active': hasFacefusionToken('face_debugger_items', item) }"
                              @click="toggleFacefusionToken('face_debugger_items', item)"
                            >
                              {{ facefusionOptionLabel('faceDebuggerItem', item) }}
                            </button>
                          </div>
                        </label>
                      </div>
                    </div>

                    <div class="facefusion-native-group facefusion-native-group--left">
                      <h3>人脸选择</h3>
                      <div class="facefusion-native-fields">
                        <label>
                          <span>选择模式</span>
                          <select v-model="facefusionSettings.face_selector_mode" class="settings-input w-full">
                            <option v-for="mode in facefusionSelectorModeOptions" :key="mode" :value="mode">{{ facefusionOptionLabel('selectorMode', mode) }}</option>
                          </select>
                        </label>
                        <label>
                          <span>人脸排序</span>
                          <select v-model="facefusionSettings.face_selector_order" class="settings-input w-full">
                            <option v-for="order in facefusionSelectorOrderOptions" :key="order" :value="order">{{ facefusionOptionLabel('selectorOrder', order) }}</option>
                          </select>
                        </label>
                        <label>
                          <span>性别筛选</span>
                          <select v-model="facefusionSettings.face_selector_gender" class="settings-input w-full">
                            <option v-for="gender in facefusionGenderOptions" :key="gender || 'none'" :value="gender">{{ facefusionOptionLabel('gender', gender) }}</option>
                          </select>
                        </label>
                        <label>
                          <span>种族筛选</span>
                          <select v-model="facefusionSettings.face_selector_race" class="settings-input w-full">
                            <option v-for="race in facefusionRaceOptions" :key="race || 'none'" :value="race">{{ facefusionOptionLabel('race', race) }}</option>
                          </select>
                        </label>
                        <label>
                          <span>年龄下限</span>
                          <input v-model="facefusionSettings.face_selector_age_start" type="number" min="0" max="100" class="settings-input w-full" />
                        </label>
                        <label>
                          <span>年龄上限</span>
                          <input v-model="facefusionSettings.face_selector_age_end" type="number" min="0" max="100" class="settings-input w-full" />
                        </label>
                      </div>
                      <div v-if="facefusionReferenceMode" class="facefusion-reference-box facefusion-reference-box--native">
                        <div class="facefusion-reference-box__gallery">
                          <button
                            v-for="face in referenceFaces"
                            :key="face.id"
                            type="button"
                            :class="{ 'is-active': Number(facefusionSettings.reference_face_position || 0) === face.position }"
                            @click="selectReferenceFace(face.position)"
                          >
                            <img :src="face.preview_url" :alt="`参考人脸 ${face.position}`" />
                            <i>{{ face.position }}</i>
                          </button>
                          <span v-if="referenceFacesLoading">读取中</span>
                          <span v-else-if="referenceFacesError">{{ referenceFacesError }}</span>
                          <span v-else-if="!referenceFaces.length">未检测到人脸</span>
                        </div>
                        <div class="facefusion-reference-box__controls">
                          <label>
                            <span>参考帧编号</span>
                            <input v-model.number="facefusionSettings.reference_frame_number" type="number" min="0" class="settings-input" @change="loadReferenceFaces" />
                          </label>
                          <label>
                            <span>参考人脸距离 {{ Number(facefusionSettings.reference_face_distance || 0).toFixed(2) }}</span>
                            <input v-model.number="facefusionSettings.reference_face_distance" type="range" min="0" max="1" step="0.05" class="facefusion-range" />
                          </label>
                          <label>
                            <span>追踪阈值 {{ Number(facefusionSettings.face_tracker_score || 0).toFixed(2) }}</span>
                            <input v-model.number="facefusionSettings.face_tracker_score" type="range" min="0" max="0.5" step="0.05" class="facefusion-range" />
                          </label>
                          <button type="button" class="facefusion-reference-box__refresh" :disabled="referenceFacesLoading" @click="loadReferenceFaces">
                            {{ referenceFacesLoading ? '读取中' : '刷新人脸库' }}
                          </button>
                        </div>
                      </div>
                    </div>

                    <div class="facefusion-native-group facefusion-native-group--left">
                      <h3>遮罩 / 检测 / 定位</h3>
                      <div class="facefusion-native-fields">
                        <label>
                          <span>遮罩类型</span>
                          <div class="facefusion-choice-chips">
                            <button v-for="type in facefusionMaskTypeOptions" :key="type" type="button" :class="{ 'is-active': hasFacefusionToken('face_mask_types', type) }" @click="toggleFacefusionToken('face_mask_types', type)">
                              {{ facefusionOptionLabel('maskType', type) }}
                            </button>
                          </div>
                        </label>
                        <label>
                          <span>遮罩模糊 {{ Number(facefusionSettings.face_mask_blur || 0).toFixed(2) }}</span>
                          <input v-model.number="facefusionSettings.face_mask_blur" type="range" min="0" max="1" step="0.05" class="facefusion-range" />
                        </label>
                        <label v-if="selectedFacefusionMaskTypes.includes('region')">
                          <span>遮罩部位</span>
                          <div class="facefusion-choice-chips">
                            <button v-for="region in facefusionMaskRegionOptions" :key="region" type="button" :class="{ 'is-active': hasFacefusionToken('face_mask_regions', region) }" @click="toggleFacefusionToken('face_mask_regions', region)">
                              {{ facefusionOptionLabel('maskRegion', region) }}
                            </button>
                          </div>
                        </label>
                        <label v-if="selectedFacefusionMaskTypes.includes('area')">
                          <span>遮罩区域</span>
                          <div class="facefusion-choice-chips">
                            <button v-for="area in facefusionMaskAreaOptions" :key="area" type="button" :class="{ 'is-active': hasFacefusionToken('face_mask_areas', area) }" @click="toggleFacefusionToken('face_mask_areas', area)">
                              {{ facefusionOptionLabel('maskArea', area) }}
                            </button>
                          </div>
                        </label>
                        <div v-if="selectedFacefusionMaskTypes.includes('box')" class="facefusion-native-subgrid">
                          <label>
                            <span>上边距 {{ getFacefusionQuadValue('face_mask_padding', 0) }}</span>
                            <input :value="getFacefusionQuadValue('face_mask_padding', 0)" type="range" min="0" max="100" step="1" class="facefusion-range" @input="updateFacefusionQuadValue('face_mask_padding', 0, ($event.target as HTMLInputElement).value)" />
                          </label>
                          <label>
                            <span>右边距 {{ getFacefusionQuadValue('face_mask_padding', 1) }}</span>
                            <input :value="getFacefusionQuadValue('face_mask_padding', 1)" type="range" min="0" max="100" step="1" class="facefusion-range" @input="updateFacefusionQuadValue('face_mask_padding', 1, ($event.target as HTMLInputElement).value)" />
                          </label>
                          <label>
                            <span>下边距 {{ getFacefusionQuadValue('face_mask_padding', 2) }}</span>
                            <input :value="getFacefusionQuadValue('face_mask_padding', 2)" type="range" min="0" max="100" step="1" class="facefusion-range" @input="updateFacefusionQuadValue('face_mask_padding', 2, ($event.target as HTMLInputElement).value)" />
                          </label>
                          <label>
                            <span>左边距 {{ getFacefusionQuadValue('face_mask_padding', 3) }}</span>
                            <input :value="getFacefusionQuadValue('face_mask_padding', 3)" type="range" min="0" max="100" step="1" class="facefusion-range" @input="updateFacefusionQuadValue('face_mask_padding', 3, ($event.target as HTMLInputElement).value)" />
                          </label>
                        </div>
                        <label>
                          <span>遮挡模型</span>
                          <select v-model="facefusionSettings.face_occluder_model" class="settings-input w-full">
                            <option v-for="model in facefusionOccluderModelOptions" :key="model" :value="model">{{ model }}</option>
                          </select>
                        </label>
                        <label>
                          <span>解析模型</span>
                          <select v-model="facefusionSettings.face_parser_model" class="settings-input w-full">
                            <option v-for="model in facefusionParserModelOptions" :key="model" :value="model">{{ model }}</option>
                          </select>
                        </label>
                        <label>
                          <span>检测模型</span>
                          <select v-model="facefusionSettings.face_detector_model" class="settings-input w-full">
                            <option v-for="model in facefusionDetectorModelOptions" :key="model" :value="model">{{ model }}</option>
                          </select>
                        </label>
                        <label>
                          <span>检测尺寸</span>
                          <select v-model="facefusionSettings.face_detector_size" class="settings-input w-full">
                            <option v-for="size in facefusionDetectorSizeOptions" :key="size" :value="size">{{ size }}</option>
                          </select>
                        </label>
                        <label>
                          <span>检测分数 {{ Number(facefusionSettings.face_detector_score || 0).toFixed(2) }}</span>
                          <input v-model.number="facefusionSettings.face_detector_score" type="range" min="0" max="1" step="0.05" class="facefusion-range" />
                        </label>
                        <div class="facefusion-native-subgrid">
                          <label>
                            <span>检测上边距 {{ getFacefusionQuadValue('face_detector_margin', 0) }}</span>
                            <input :value="getFacefusionQuadValue('face_detector_margin', 0)" type="range" min="0" max="100" step="1" class="facefusion-range" @input="updateFacefusionQuadValue('face_detector_margin', 0, ($event.target as HTMLInputElement).value)" />
                          </label>
                          <label>
                            <span>检测右边距 {{ getFacefusionQuadValue('face_detector_margin', 1) }}</span>
                            <input :value="getFacefusionQuadValue('face_detector_margin', 1)" type="range" min="0" max="100" step="1" class="facefusion-range" @input="updateFacefusionQuadValue('face_detector_margin', 1, ($event.target as HTMLInputElement).value)" />
                          </label>
                          <label>
                            <span>检测下边距 {{ getFacefusionQuadValue('face_detector_margin', 2) }}</span>
                            <input :value="getFacefusionQuadValue('face_detector_margin', 2)" type="range" min="0" max="100" step="1" class="facefusion-range" @input="updateFacefusionQuadValue('face_detector_margin', 2, ($event.target as HTMLInputElement).value)" />
                          </label>
                          <label>
                            <span>检测左边距 {{ getFacefusionQuadValue('face_detector_margin', 3) }}</span>
                            <input :value="getFacefusionQuadValue('face_detector_margin', 3)" type="range" min="0" max="100" step="1" class="facefusion-range" @input="updateFacefusionQuadValue('face_detector_margin', 3, ($event.target as HTMLInputElement).value)" />
                          </label>
                        </div>
                        <label>
                          <span>检测角度</span>
                          <div class="facefusion-choice-chips">
                            <button v-for="angle in facefusionDetectorAngleOptions" :key="angle" type="button" :class="{ 'is-active': hasFacefusionToken('face_detector_angles', angle) }" @click="toggleFacefusionToken('face_detector_angles', angle)">
                              {{ angle }}
                            </button>
                          </div>
                        </label>
                        <label>
                          <span>定位模型</span>
                          <select v-model="facefusionSettings.face_landmarker_model" class="settings-input w-full">
                            <option v-for="model in facefusionLandmarkerModelOptions" :key="model" :value="model">{{ model }}</option>
                          </select>
                        </label>
                        <label>
                          <span>定位分数 {{ Number(facefusionSettings.face_landmarker_score || 0).toFixed(2) }}</span>
                          <input v-model.number="facefusionSettings.face_landmarker_score" type="range" min="0" max="1" step="0.05" class="facefusion-range" />
                        </label>
                      </div>
                    </div>

                  </section>


                  <section class="facefusion-native-workspace">
                    <div class="facefusion-native-group facefusion-native-group--preview">
                      <h3>预览</h3>
                      <div class="facefusion-preview">
                        <img
                          v-if="previewUrl"
                          :src="previewUrl"
                          class="facefusion-preview__image"
                          alt="FaceFusion 预览"
                        />
                        <div v-else class="facefusion-preview__empty">
                          <span>FaceFusion 预览</span>
                        </div>
                        <div class="facefusion-preview__overlay">
                          <div class="facefusion-preview__controls">
                            <input
                              v-model.number="previewFrameNumber"
                              class="preview-frame-slider"
                              type="range"
                              min="0"
                              :max="previewFrameMax"
                              step="1"
                              :disabled="previewLoading || previewMetadataLoading || previewFrameMax <= 0"
                              @input="markPreviewFrameChanged"
                              @change="handlePreviewSliderCommit"
                            />
                            <span class="facefusion-preview__frame">{{ previewLoading ? '生成中' : previewMetadataLoading ? '读取中' : previewTimeLabel }}</span>
                          </div>
                        </div>
                        <div v-if="previewLoading" class="facefusion-preview__busy">
                          <span></span>
                          <strong>正在生成预览</strong>
                        </div>
                      </div>
                    </div>

                    <div class="facefusion-native-workspace__lower">
                      <section class="facefusion-native-column facefusion-native-column--source">
                        <FilePathSelector
                          :file-path="detail?.file_path"
                          :sibling-paths="detail?.siblings"
                          v-model="selectedSubmitPath"
                          @update:model-value="selectedSubmitId = allSubmitPaths.find(p => p.path === $event)?.id || detail?.id || ''"
                        />

                        <div class="facefusion-native-group facefusion-native-group--noor">
                          <div class="facefusion-native-group__head">
                            <h3>源脸图片</h3>
                            <span>{{ facefusionSourcePaths.length }} 张</span>
                          </div>
                          <div class="facefusion-source-actions">
                            <label class="facefusion-source-action">
                              <input type="file" accept="image/*" multiple :disabled="sourceUploadLoading" @change="handleSourceImageUpload" />
                              <span>{{ sourceUploadLoading ? '上传中' : '上传图片' }}</span>
                            </label>
                            <button type="button" class="facefusion-source-action" @click="toggleSourceLibrary">
                              {{ sourceLibraryOpen ? '收起图片库' : '图片库' }}
                            </button>
                            <button v-if="sourceLibraryOpen" type="button" class="facefusion-source-action" :disabled="sourceLibraryLoading" @click="loadSourceImageLibrary">
                              {{ sourceLibraryLoading ? '刷新中' : '刷新' }}
                            </button>
                          </div>
                          <div v-if="uploadedSourceImages.length" class="facefusion-source-manager">
                            <div v-for="source in uploadedSourceImages" :key="source.path" class="facefusion-source-card">
                              <img v-if="source.preview_url" :src="source.preview_url" :alt="source.name" loading="lazy" />
                              <div v-else class="facefusion-source-card__placeholder">IMG</div>
                              <div class="facefusion-source-card__meta">
                                <span>{{ source.name }}</span>
                                <button type="button" @click="removeUploadedSourceImage(source)">移除</button>
                              </div>
                            </div>
                          </div>
                          <div v-else class="facefusion-source-empty">未选择源脸图片</div>
                          <div v-if="sourceLibraryOpen" class="facefusion-source-library">
                            <div class="facefusion-source-library__head">
                              <span>{{ sourceLibraryLoading ? '读取中' : `图片库 · ${sourceLibraryImages.length}` }}</span>
                              <small>点击图片即可加入或移除</small>
                            </div>
                            <div v-if="!sourceLibraryLoading && !sourceLibraryImages.length" class="facefusion-source-library__empty">暂无缓存图片</div>
                            <div v-else class="facefusion-source-library__grid">
                              <div
                                v-for="image in sourceLibraryImages"
                                :key="image.id"
                                class="facefusion-source-library__item"
                                :class="{ 'is-used': isSourceSelected(image.path) }"
                              >
                                <button type="button" class="facefusion-source-library__use" @click="toggleLibraryImage(image)">
                                  <img v-if="image.preview_url" :src="image.preview_url" :alt="image.name" loading="lazy" />
                                  <span>{{ isSourceSelected(image.path) ? '移除' : '使用' }}</span>
                                </button>
                                <button type="button" class="facefusion-source-library__delete" title="删除图片" @click.stop="deleteLibraryImage(image)">×</button>
                              </div>
                            </div>
                          </div>
                        </div>

                      </section>

                  <section class="facefusion-native-column facefusion-native-column--right">
                    <div v-if="selectedFacefusionProcessors.includes('frame_enhancer')" class="facefusion-native-group">
                      <h3>画面增强参数</h3>
                      <div class="facefusion-native-fields">
                        <label>
                          <span>画面增强模型</span>
                          <select v-model="facefusionSettings.frame_enhancer_model" class="settings-input w-full">
                            <option v-for="model in facefusionFrameEnhancerModelOptions" :key="model" :value="model">{{ model }}</option>
                          </select>
                        </label>
                        <label>
                          <span>画面增强混合 {{ facefusionSettings.frame_enhancer_blend }}</span>
                          <input v-model.number="facefusionSettings.frame_enhancer_blend" type="range" min="0" max="100" step="1" class="facefusion-range" />
                        </label>
                      </div>
                    </div>

                    <div class="facefusion-native-group">
                      <h3>执行参数</h3>
                      <div class="facefusion-native-fields">
                        <label>
                          <span>执行后端</span>
                          <select v-model="facefusionSettings.execution_provider" class="settings-input w-full">
                            <option v-for="provider in facefusionExecutionProviderOptions" :key="provider" :value="provider">{{ provider }}</option>
                          </select>
                        </label>
                        <label>
                          <span>设备编号</span>
                          <input v-model="facefusionSettings.device_ids" class="settings-input w-full" />
                        </label>
                        <label>
                          <span>线程数</span>
                          <input v-model.number="facefusionSettings.thread_count" type="number" min="1" max="64" class="settings-input w-full" />
                        </label>
                        <label>
                          <span>显存策略</span>
                          <select v-model="facefusionSettings.video_memory_strategy" class="settings-input w-full">
                            <option v-for="item in facefusionVideoMemoryStrategyOptions" :key="item" :value="item">{{ facefusionOptionLabel('memoryStrategy', item) }}</option>
                          </select>
                        </label>
                        <label>
                          <span>系统内存限制</span>
                          <input v-model.number="facefusionSettings.system_memory_limit" type="number" min="0" class="settings-input w-full" />
                        </label>
                        <label>
                          <span>日志等级</span>
                          <select v-model="facefusionSettings.log_level" class="settings-input w-full">
                            <option v-for="item in facefusionLogLevelOptions" :key="item" :value="item">{{ facefusionOptionLabel('logLevel', item) }}</option>
                          </select>
                        </label>
                      </div>
                    </div>

                    <div class="facefusion-native-group facefusion-native-group--right">
                      <h3>输出参数</h3>
                      <div class="facefusion-native-fields">
                        <label>
                          <span>视频编码器</span>
                          <select v-model="facefusionSettings.output_video_encoder" class="settings-input w-full">
                            <option v-for="item in facefusionVideoEncoderOptions" :key="item" :value="item">{{ item }}</option>
                          </select>
                        </label>
                        <label>
                          <span>视频预设</span>
                          <select v-model="facefusionSettings.output_video_preset" class="settings-input w-full">
                            <option v-for="item in facefusionVideoPresetOptions" :key="item" :value="item">{{ facefusionOptionLabel('videoPreset', item) }}</option>
                          </select>
                        </label>
                        <label>
                          <span>视频质量 {{ facefusionSettings.output_video_quality }}</span>
                          <input v-model.number="facefusionSettings.output_video_quality" type="range" min="0" max="100" step="1" class="facefusion-range" />
                        </label>
                        <label>
                          <span>视频缩放</span>
                          <select v-model="facefusionSettings.output_video_scale" class="settings-input w-full">
                            <option v-for="scale in facefusionScaleOptions" :key="scale" :value="scale">{{ scale }}x</option>
                          </select>
                        </label>
                        <label>
                          <span>视频帧率</span>
                          <input v-model="facefusionSettings.output_video_fps" type="number" min="1" max="240" placeholder="跟随源视频" class="settings-input w-full" />
                        </label>
                        <label>
                          <span>音频编码器</span>
                          <select v-model="facefusionSettings.output_audio_encoder" class="settings-input w-full">
                            <option v-for="item in facefusionAudioEncoderOptions" :key="item" :value="item">{{ item }}</option>
                          </select>
                        </label>
                        <label>
                          <span>音频质量 {{ facefusionSettings.output_audio_quality }}</span>
                          <input v-model.number="facefusionSettings.output_audio_quality" type="range" min="0" max="100" step="1" class="facefusion-range" />
                        </label>
                        <label>
                          <span>临时帧格式</span>
                          <select v-model="facefusionSettings.temp_frame_format" class="settings-input w-full">
                            <option v-for="item in facefusionTempFrameFormatOptions" :key="item" :value="item">{{ item }}</option>
                          </select>
                        </label>
                      </div>
                    </div>
                  </section>
                    </div>
                  </section>
                </div>
              </div>

              <div v-else class="ui-card">
                <span class="text-[10px] text-text-muted uppercase tracking-wider">FACEFUSION</span>
                <div class="facefusion-panel-layout mt-3" :class="{ 'facefusion-panel-layout--wide': isFullWidth }">
                  <div class="facefusion-panel-column">
                  <div class="facefusion-source-section">
                    <div class="facefusion-native-group__head">
                      <label class="block text-[10px] text-text-muted uppercase tracking-wider">源脸图片</label>
                      <span>{{ facefusionSourcePaths.length }} 张</span>
                    </div>
                    <div class="facefusion-source-actions">
                      <label class="facefusion-source-action">
                        <input
                          type="file"
                          accept="image/*"
                          multiple
                          :disabled="sourceUploadLoading"
                          @change="handleSourceImageUpload"
                        />
                        <span>{{ sourceUploadLoading ? '上传中' : '上传图片' }}</span>
                      </label>
                      <button type="button" class="facefusion-source-action" @click="toggleSourceLibrary">
                        {{ sourceLibraryOpen ? '收起图片库' : '图片库' }}
                      </button>
                      <button v-if="sourceLibraryOpen" type="button" class="facefusion-source-action" :disabled="sourceLibraryLoading" @click="loadSourceImageLibrary">
                        {{ sourceLibraryLoading ? '刷新中' : '刷新' }}
                      </button>
                    </div>
                    <div v-if="uploadedSourceImages.length" class="facefusion-source-manager">
                      <div v-for="source in uploadedSourceImages" :key="source.path" class="facefusion-source-card">
                        <img
                          v-if="source.preview_url"
                          :src="source.preview_url"
                          :alt="source.name"
                          loading="lazy"
                        />
                        <div v-else class="facefusion-source-card__placeholder">IMG</div>
                        <div class="facefusion-source-card__meta">
                          <span>{{ source.name }}</span>
                          <button type="button" @click="removeUploadedSourceImage(source)">移除</button>
                        </div>
                      </div>
                    </div>
                    <div v-else class="facefusion-source-empty">未选择源脸图片</div>
                    <div v-if="sourceLibraryOpen" class="facefusion-source-library">
                      <div class="facefusion-source-library__head">
                        <span>{{ sourceLibraryLoading ? '读取中' : `图片库 · ${sourceLibraryImages.length}` }}</span>
                        <small>点击图片即可加入或移除</small>
                      </div>
                      <div v-if="!sourceLibraryLoading && !sourceLibraryImages.length" class="facefusion-source-library__empty">暂无缓存图片</div>
                      <div v-else class="facefusion-source-library__grid">
                        <div
                          v-for="image in sourceLibraryImages"
                          :key="image.id"
                          class="facefusion-source-library__item"
                          :class="{ 'is-used': isSourceSelected(image.path) }"
                        >
                          <button type="button" class="facefusion-source-library__use" @click="toggleLibraryImage(image)">
                            <img v-if="image.preview_url" :src="image.preview_url" :alt="image.name" loading="lazy" />
                            <span>{{ isSourceSelected(image.path) ? '移除' : '使用' }}</span>
                          </button>
                          <button type="button" class="facefusion-source-library__delete" title="删除图片" @click.stop="deleteLibraryImage(image)">×</button>
                        </div>
                      </div>
                    </div>
                  </div>
                  <div>
                    <div>
                      <label class="block text-[10px] text-text-muted uppercase tracking-wider mb-1">预览帧</label>
                      <input
                        v-model.number="previewFrameNumber"
                        class="settings-input w-full"
                        type="number"
                        min="0"
                        :max="previewFrameMax"
                        step="1"
                        :disabled="previewLoading"
                        @input="markPreviewFrameChanged"
                        @change="handlePreviewSliderCommit"
                      />
                    </div>
                  </div>
                  <div class="facefusion-subpanel">
                    <span>人脸选择</span>
                    <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
                      <div>
                        <label class="block text-[10px] text-text-muted uppercase tracking-wider mb-1">人脸选择模式</label>
                        <select v-model="facefusionSettings.face_selector_mode" class="settings-input w-full">
                          <option v-for="mode in facefusionSelectorModeOptions" :key="mode" :value="mode">{{ mode }}</option>
                        </select>
                      </div>
                      <div>
                        <label class="block text-[10px] text-text-muted uppercase tracking-wider mb-1">人脸排序</label>
                        <select v-model="facefusionSettings.face_selector_order" class="settings-input w-full">
                          <option v-for="order in facefusionSelectorOrderOptions" :key="order" :value="order">{{ order }}</option>
                        </select>
                      </div>
                    </div>
                    <div v-if="facefusionReferenceMode" class="facefusion-reference-box">
                      <div class="facefusion-reference-box__gallery">
                        <button
                          v-for="face in referenceFaces"
                          :key="face.id"
                          type="button"
                          :class="{ 'is-active': Number(facefusionSettings.reference_face_position || 0) === face.position }"
                          @click="selectReferenceFace(face.position)"
                        >
                          <img :src="face.preview_url" :alt="`参考人脸 ${face.position}`" />
                          <i>{{ face.position }}</i>
                        </button>
                        <span v-if="referenceFacesLoading">读取中</span>
                        <span v-else-if="referenceFacesError">{{ referenceFacesError }}</span>
                        <span v-else-if="!referenceFaces.length">未检测到人脸</span>
                      </div>
                      <div class="facefusion-reference-box__controls">
                        <label>
                          <span>参考帧</span>
                          <input v-model.number="facefusionSettings.reference_frame_number" type="number" min="0" class="settings-input" @change="loadReferenceFaces" />
                        </label>
                        <label>
                          <span>匹配距离 {{ Number(facefusionSettings.reference_face_distance || 0).toFixed(2) }}</span>
                          <input v-model.number="facefusionSettings.reference_face_distance" type="range" min="0" max="1" step="0.05" class="facefusion-range" />
                        </label>
                        <label>
                          <span>追踪阈值 {{ Number(facefusionSettings.face_tracker_score || 0).toFixed(2) }}</span>
                          <input v-model.number="facefusionSettings.face_tracker_score" type="range" min="0" max="0.5" step="0.05" class="facefusion-range" />
                        </label>
                        <button type="button" class="facefusion-reference-box__refresh" :disabled="referenceFacesLoading" @click="loadReferenceFaces">
                          {{ referenceFacesLoading ? '读取中' : '刷新人脸库' }}
                        </button>
                      </div>
                    </div>
                  </div>
                  <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
                    <div>
                      <label class="block text-[10px] text-text-muted uppercase tracking-wider mb-1">执行后端</label>
                      <select v-model="facefusionSettings.execution_provider" class="settings-input w-full">
                        <option v-for="provider in facefusionExecutionProviderOptions" :key="provider" :value="provider">{{ provider }}</option>
                      </select>
                    </div>
                    <div>
                      <label class="block text-[10px] text-text-muted uppercase tracking-wider mb-1">人脸检测模型</label>
                      <select v-model="facefusionSettings.face_detector_model" class="settings-input w-full">
                        <option v-for="model in facefusionDetectorModelOptions" :key="model" :value="model">{{ model }}</option>
                      </select>
                    </div>
                  </div>

                  <div>
                    <label class="block text-[10px] text-text-muted uppercase tracking-wider mb-1">处理器</label>
                    <div class="facefusion-choice-chips">
                      <button
                        v-for="processor in facefusionProcessorOptions"
                        :key="processor.id"
                        type="button"
                        class="processor-chip"
                        :class="{ 'is-active': hasFacefusionToken('processors', processor.id) }"
                        @click="toggleFacefusionToken('processors', processor.id)"
                      >
                        <span>{{ processor.label }}</span>
                        <small>{{ processor.id }}</small>
                        <em :class="{ 'is-cuda': processor.acceleration === 'cuda', 'is-muted': processor.acceleration === 'none' }">
                          {{ processor.acceleration === 'tensorrt' ? 'TRT 推荐' : processor.acceleration === 'cuda' ? 'CUDA 推荐' : '无推理加速' }}
                        </em>
                      </button>
                    </div>
                  </div>
                  </div>

                  <div class="facefusion-panel-column">

                  <div v-if="selectedFacefusionProcessors.includes('face_swapper')" class="facefusion-subpanel">
                    <span>face_swapper</span>
                    <div class="grid grid-cols-1 md:grid-cols-3 gap-3">
                      <div>
                        <label class="block text-[10px] text-text-muted uppercase tracking-wider mb-1">模型</label>
                        <select v-model="facefusionSettings.face_swapper_model" class="settings-input w-full">
                          <option v-for="model in facefusionFaceSwapperModelOptions" :key="model" :value="model">{{ model }}</option>
                        </select>
                      </div>
                      <div>
                        <label class="block text-[10px] text-text-muted uppercase tracking-wider mb-1">Pixel boost</label>
                        <select v-model="facefusionSettings.face_swapper_pixel_boost" class="settings-input w-full">
                          <option v-for="size in facefusionPixelBoostOptions" :key="size" :value="size">{{ size }}</option>
                        </select>
                      </div>
                      <div>
                        <label class="block text-[10px] text-text-muted uppercase tracking-wider mb-1">权重 {{ Number(facefusionSettings.face_swapper_weight || 0).toFixed(2) }}</label>
                        <input v-model.number="facefusionSettings.face_swapper_weight" type="range" min="0" max="1" step="0.05" class="facefusion-range" />
                      </div>
                    </div>
                  </div>

                  <div v-if="selectedFacefusionProcessors.includes('face_enhancer')" class="facefusion-subpanel">
                    <span>face_enhancer</span>
                    <div class="grid grid-cols-1 md:grid-cols-3 gap-3">
                      <div>
                        <label class="block text-[10px] text-text-muted uppercase tracking-wider mb-1">模型</label>
                        <select v-model="facefusionSettings.face_enhancer_model" class="settings-input w-full">
                          <option v-for="model in facefusionFaceEnhancerModelOptions" :key="model" :value="model">{{ model }}</option>
                        </select>
                      </div>
                      <div>
                        <label class="block text-[10px] text-text-muted uppercase tracking-wider mb-1">混合 {{ facefusionSettings.face_enhancer_blend }}</label>
                        <input v-model.number="facefusionSettings.face_enhancer_blend" type="range" min="0" max="100" step="1" class="facefusion-range" />
                      </div>
                      <div>
                        <label class="block text-[10px] text-text-muted uppercase tracking-wider mb-1">权重 {{ Number(facefusionSettings.face_enhancer_weight || 0).toFixed(2) }}</label>
                        <input v-model.number="facefusionSettings.face_enhancer_weight" type="range" min="0" max="1" step="0.05" class="facefusion-range" />
                      </div>
                    </div>
                  </div>

                  <div v-if="selectedFacefusionProcessors.includes('frame_enhancer')" class="facefusion-subpanel">
                    <span>frame_enhancer</span>
                    <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
                      <div>
                        <label class="block text-[10px] text-text-muted uppercase tracking-wider mb-1">模型</label>
                        <select v-model="facefusionSettings.frame_enhancer_model" class="settings-input w-full">
                          <option v-for="model in facefusionFrameEnhancerModelOptions" :key="model" :value="model">{{ model }}</option>
                        </select>
                      </div>
                      <div>
                        <label class="block text-[10px] text-text-muted uppercase tracking-wider mb-1">混合 {{ facefusionSettings.frame_enhancer_blend }}</label>
                        <input v-model.number="facefusionSettings.frame_enhancer_blend" type="range" min="0" max="100" step="1" class="facefusion-range" />
                      </div>
                    </div>
                  </div>

                  <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
                    <div>
                      <label class="block text-[10px] text-text-muted uppercase tracking-wider mb-1">检测尺寸</label>
                      <select v-model="facefusionSettings.face_detector_size" class="settings-input w-full">
                        <option v-for="size in facefusionDetectorSizeOptions" :key="size" :value="size">{{ size }}</option>
                      </select>
                    </div>
                    <div>
                      <label class="block text-[10px] text-text-muted uppercase tracking-wider mb-1">检测分数 {{ Number(facefusionSettings.face_detector_score || 0).toFixed(2) }}</label>
                      <input v-model.number="facefusionSettings.face_detector_score" type="range" min="0" max="1" step="0.05" class="facefusion-range" />
                    </div>
                    <div>
                      <label class="block text-[10px] text-text-muted uppercase tracking-wider mb-1">遮罩模糊 {{ Number(facefusionSettings.face_mask_blur || 0).toFixed(2) }}</label>
                      <input v-model.number="facefusionSettings.face_mask_blur" type="range" min="0" max="1" step="0.05" class="facefusion-range" />
                    </div>
                  </div>

                  <div class="grid grid-cols-1 md:grid-cols-4 gap-3">
                    <div>
                      <label class="block text-[10px] text-text-muted uppercase tracking-wider mb-1">检测上边距 {{ getFacefusionQuadValue('face_detector_margin', 0) }}</label>
                      <input :value="getFacefusionQuadValue('face_detector_margin', 0)" type="range" min="0" max="100" step="1" class="facefusion-range" @input="updateFacefusionQuadValue('face_detector_margin', 0, ($event.target as HTMLInputElement).value)" />
                    </div>
                    <div>
                      <label class="block text-[10px] text-text-muted uppercase tracking-wider mb-1">检测右边距 {{ getFacefusionQuadValue('face_detector_margin', 1) }}</label>
                      <input :value="getFacefusionQuadValue('face_detector_margin', 1)" type="range" min="0" max="100" step="1" class="facefusion-range" @input="updateFacefusionQuadValue('face_detector_margin', 1, ($event.target as HTMLInputElement).value)" />
                    </div>
                    <div>
                      <label class="block text-[10px] text-text-muted uppercase tracking-wider mb-1">检测下边距 {{ getFacefusionQuadValue('face_detector_margin', 2) }}</label>
                      <input :value="getFacefusionQuadValue('face_detector_margin', 2)" type="range" min="0" max="100" step="1" class="facefusion-range" @input="updateFacefusionQuadValue('face_detector_margin', 2, ($event.target as HTMLInputElement).value)" />
                    </div>
                    <div>
                      <label class="block text-[10px] text-text-muted uppercase tracking-wider mb-1">检测左边距 {{ getFacefusionQuadValue('face_detector_margin', 3) }}</label>
                      <input :value="getFacefusionQuadValue('face_detector_margin', 3)" type="range" min="0" max="100" step="1" class="facefusion-range" @input="updateFacefusionQuadValue('face_detector_margin', 3, ($event.target as HTMLInputElement).value)" />
                    </div>
                  </div>

                  <div>
                    <label class="block text-[10px] text-text-muted uppercase tracking-wider mb-1">检测角度</label>
                    <div class="facefusion-choice-chips">
                      <button
                        v-for="angle in facefusionDetectorAngleOptions"
                        :key="angle"
                        type="button"
                        :class="{ 'is-active': hasFacefusionToken('face_detector_angles', angle) }"
                        @click="toggleFacefusionToken('face_detector_angles', angle)"
                      >
                        {{ angle }}
                      </button>
                    </div>
                  </div>

                  <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
                    <div>
                      <label class="block text-[10px] text-text-muted uppercase tracking-wider mb-1">遮罩类型</label>
                      <div class="facefusion-choice-chips">
                        <button
                          v-for="type in facefusionMaskTypeOptions"
                          :key="type"
                          type="button"
                          :class="{ 'is-active': hasFacefusionToken('face_mask_types', type) }"
                          @click="toggleFacefusionToken('face_mask_types', type)"
                        >
                          {{ type }}
                        </button>
                      </div>
                    </div>
                    <div>
                      <label class="block text-[10px] text-text-muted uppercase tracking-wider mb-1">遮挡模型</label>
                      <select v-model="facefusionSettings.face_occluder_model" class="settings-input w-full">
                        <option v-for="model in facefusionOccluderModelOptions" :key="model" :value="model">{{ model }}</option>
                      </select>
                    </div>
                  </div>

                  <div v-if="selectedFacefusionMaskTypes.includes('area')">
                    <label class="block text-[10px] text-text-muted uppercase tracking-wider mb-1">遮罩区域</label>
                    <div class="facefusion-choice-chips">
                      <button
                        v-for="area in facefusionMaskAreaOptions"
                        :key="area"
                        type="button"
                        :class="{ 'is-active': hasFacefusionToken('face_mask_areas', area) }"
                        @click="toggleFacefusionToken('face_mask_areas', area)"
                      >
                        {{ facefusionOptionLabel('maskArea', area) }}
                      </button>
                    </div>
                  </div>

                  <div v-if="selectedFacefusionMaskTypes.includes('region')">
                    <label class="block text-[10px] text-text-muted uppercase tracking-wider mb-1">遮罩部位</label>
                    <div class="facefusion-choice-chips">
                      <button
                        v-for="region in facefusionMaskRegionOptions"
                        :key="region"
                        type="button"
                        :class="{ 'is-active': hasFacefusionToken('face_mask_regions', region) }"
                        @click="toggleFacefusionToken('face_mask_regions', region)"
                      >
                        {{ region }}
                      </button>
                    </div>
                  </div>

                  <div v-if="selectedFacefusionMaskTypes.includes('box')" class="grid grid-cols-1 md:grid-cols-4 gap-3">
                    <div>
                      <label class="block text-[10px] text-text-muted uppercase tracking-wider mb-1">遮罩上边距 {{ getFacefusionQuadValue('face_mask_padding', 0) }}</label>
                      <input :value="getFacefusionQuadValue('face_mask_padding', 0)" type="range" min="0" max="100" step="1" class="facefusion-range" @input="updateFacefusionQuadValue('face_mask_padding', 0, ($event.target as HTMLInputElement).value)" />
                    </div>
                    <div>
                      <label class="block text-[10px] text-text-muted uppercase tracking-wider mb-1">遮罩右边距 {{ getFacefusionQuadValue('face_mask_padding', 1) }}</label>
                      <input :value="getFacefusionQuadValue('face_mask_padding', 1)" type="range" min="0" max="100" step="1" class="facefusion-range" @input="updateFacefusionQuadValue('face_mask_padding', 1, ($event.target as HTMLInputElement).value)" />
                    </div>
                    <div>
                      <label class="block text-[10px] text-text-muted uppercase tracking-wider mb-1">遮罩下边距 {{ getFacefusionQuadValue('face_mask_padding', 2) }}</label>
                      <input :value="getFacefusionQuadValue('face_mask_padding', 2)" type="range" min="0" max="100" step="1" class="facefusion-range" @input="updateFacefusionQuadValue('face_mask_padding', 2, ($event.target as HTMLInputElement).value)" />
                    </div>
                    <div>
                      <label class="block text-[10px] text-text-muted uppercase tracking-wider mb-1">遮罩左边距 {{ getFacefusionQuadValue('face_mask_padding', 3) }}</label>
                      <input :value="getFacefusionQuadValue('face_mask_padding', 3)" type="range" min="0" max="100" step="1" class="facefusion-range" @input="updateFacefusionQuadValue('face_mask_padding', 3, ($event.target as HTMLInputElement).value)" />
                    </div>
                  </div>
                  </div>

                </div>
              </div>

              <!-- Bottom Buttons -->
              <div class="flex gap-3 pt-2">
                <VuiSubmitButton
                  class="flex-1"
                  size="lg"
                  :status="submitStatus"
                  :progress="submitProgress"
                  :disabled="!selectedSubmitPath || !facefusionSourcePaths.length"
                  :idle-label="t('ladaPanel.start')"
                  :success-label="t('ladaPanel.submitQueued')"
                  :error-label="t('ladaPanel.submitFailed')"
                  @click="handleSubmitFaceFusionJob"
                />
                <VuiButton
                  variant="outlined"
                  color="secondary"
                  size="large"
                  @click="handleClose"
                >
                  {{ t('common.cancel') }}
                </VuiButton>
              </div>

            </div>
          </template>
        </div>
      </div>
    </Transition>

    <Transition name="panel">
      <div v-if="deepModelDialogOpen" class="facefusion-model-dialog">
        <div class="facefusion-model-dialog__backdrop" @click="deepModelDialogOpen = false"></div>
        <div class="facefusion-model-dialog__panel">
          <div class="facefusion-model-dialog__head">
            <strong>选择 Deep 模型</strong>
            <button type="button" @click="deepModelDialogOpen = false">关闭</button>
          </div>

          <div class="facefusion-model-toolbar">
            <label class="facefusion-model-upload">
              <input
                type="file"
                accept=".dfm,.onnx,.pth,.pt"
                :disabled="deepModelUploading"
                @change="handleDeepModelUpload"
              />
              <span>{{ deepModelUploading ? '上传中' : '上传' }}</span>
            </label>
            <button type="button" @click="loadDeepSwapperModels">刷新</button>
          </div>

          <div v-if="!deepModelLoading && !deepSwapperModels.length" class="facefusion-model-dialog__empty">暂无可选模型</div>
          <div v-else class="facefusion-model-list">
            <button
              v-for="model in deepSwapperModels"
              :key="model.id"
              type="button"
              class="facefusion-model-item"
              :class="{
                'is-active': facefusionSettings.deep_swapper_model === model.id,
                'is-missing': model.source !== 'custom' && !model.downloaded,
                'is-downloading': model.downloading,
              }"
              @click="selectDeepSwapperModel(model.id)"
            >
              <strong>{{ model.name }}</strong>
              <b>
                {{
                  facefusionSettings.deep_swapper_model === model.id
                    ? '已选'
                    : model.downloading
                      ? `下载中 ${Math.max(0, Math.min(100, Number(model.progress || 0)))}%`
                      : model.downloaded || model.source === 'custom'
                        ? '已下载'
                        : '下载'
                }}
              </b>
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
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

.panel-topbar__actions {
  display: flex;
  align-items: center;
  gap: 0.45rem;
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

.facefusion-native-shell {
  display: grid;
  gap: 1rem;
  padding: 0.35rem 0 0;
}

.facefusion-native-head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 1rem;
  padding-bottom: 0.85rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.facefusion-native-head div {
  display: grid;
  gap: 0.2rem;
}

.facefusion-native-head span {
  color: var(--color-text-muted);
  font-size: 0.68rem;
  font-weight: 850;
  letter-spacing: 0.12em;
}

.facefusion-native-head strong {
  color: var(--color-text-primary);
  font-size: 1rem;
  font-weight: 850;
}

.facefusion-native-head em {
  max-width: 34rem;
  color: var(--color-text-muted);
  font-size: 0.74rem;
  font-style: normal;
  line-height: 1.45;
  text-align: right;
}

.facefusion-native-grid {
  display: grid;
  grid-template-columns: minmax(26rem, 0.9fr) minmax(44rem, 1.35fr);
  gap: 1rem;
  align-items: start;
}

.facefusion-native-column {
  display: grid;
  min-width: 0;
  gap: 0.85rem;
  overflow: hidden;
}

.facefusion-native-column > * {
  min-width: 0;
  width: 100%;
  max-width: 100%;
  box-sizing: border-box;
}

.facefusion-native-column--source {
  grid-column: auto;
  grid-row: auto;
}

.facefusion-native-column--processors {
  grid-column: 1;
  grid-row: 1;
}

.facefusion-native-column--right {
  grid-column: auto;
  grid-row: auto;
}

.facefusion-native-workspace {
  display: grid;
  min-width: 0;
  gap: 1rem;
  align-content: start;
}

.facefusion-native-workspace__lower {
  display: grid;
  width: 100%;
  min-width: 0;
  grid-template-columns: minmax(0, 0.88fr) minmax(0, 1fr);
  gap: 1rem;
  align-items: start;
}

.facefusion-native-workspace__lower > * {
  min-width: 0;
}

.facefusion-native-group {
  display: grid;
  gap: 0.75rem;
  padding: 0.85rem;
  border-radius: 0.8rem;
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(255, 255, 255, 0.026);
}

.facefusion-native-group--noor {
  border-color: rgba(0, 117, 255, 0.18);
  background: rgba(0, 117, 255, 0.055);
}

.facefusion-native-group--preview {
  width: 100%;
  padding: 0.75rem;
}

.facefusion-native-group--preview .facefusion-preview {
  width: 100%;
  min-height: 0;
}

.facefusion-native-group__head {
  display: flex;
  min-width: 0;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
}

.facefusion-native-group__head > span {
  flex: none;
  color: var(--color-text-muted);
  font-size: 0.72rem;
}

.facefusion-native-group h3 {
  margin: 0;
  color: rgba(255, 255, 255, 0.86);
  font-size: 0.74rem;
  font-weight: 850;
  letter-spacing: 0.1em;
  text-transform: uppercase;
}

.facefusion-native-fields label > span {
  color: var(--color-text-muted);
  font-size: 0.66rem;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.facefusion-native-fields {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.7rem;
}

.facefusion-native-fields label {
  display: grid;
  min-width: 0;
  gap: 0.35rem;
}

.facefusion-native-fields label:has(.facefusion-choice-chips) {
  grid-column: 1 / -1;
}

.facefusion-native-subgrid {
  display: grid;
  grid-column: 1 / -1;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.7rem;
}

.facefusion-reference-box--native {
  grid-template-columns: minmax(12rem, 0.8fr) minmax(0, 1fr);
}

.facefusion-panel-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 0.9rem;
}

.facefusion-panel-layout--wide {
  grid-template-columns: minmax(20rem, 0.9fr) minmax(24rem, 1.1fr) minmax(28rem, 1.2fr);
  align-items: start;
}

.facefusion-panel-column {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 0.9rem;
}

.facefusion-reference-box {
  display: grid;
  grid-template-columns: minmax(8rem, 11rem) minmax(0, 1fr);
  gap: 0.75rem;
  align-items: stretch;
}

.facefusion-reference-box__gallery {
  position: relative;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(4.2rem, 1fr));
  align-content: start;
  gap: 0.4rem;
  overflow: hidden;
  min-height: 8rem;
  max-height: 12rem;
  overflow-y: auto;
  padding: 0.45rem;
  border-radius: 0.75rem;
  border: 1px solid rgba(0, 117, 255, 0.3);
  background: rgba(0, 117, 255, 0.08);
}

.facefusion-reference-box__gallery button {
  position: relative;
  overflow: hidden;
  aspect-ratio: 1 / 1;
  border-radius: 0.52rem;
  border: 2px solid transparent;
  background: rgba(255, 255, 255, 0.055);
}

.facefusion-reference-box__gallery button.is-active {
  border-color: rgba(0, 117, 255, 0.92);
  box-shadow: 0 0 0 2px rgba(0, 117, 255, 0.18);
}

.facefusion-reference-box__gallery img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.facefusion-reference-box__gallery > span {
  grid-column: 1 / -1;
  display: grid;
  min-height: 7rem;
  place-items: center;
  color: var(--color-text-muted);
  font-size: 0.78rem;
  text-align: center;
}

.facefusion-reference-box__gallery i {
  position: absolute;
  right: 0.3rem;
  bottom: 0.3rem;
  display: inline-flex;
  min-width: 1.35rem;
  height: 1.35rem;
  align-items: center;
  justify-content: center;
  border-radius: 999px;
  border: 1px solid rgba(255, 255, 255, 0.82);
  background: rgba(0, 117, 255, 0.74);
  color: #fff;
  font-size: 0.66rem;
  font-style: normal;
  font-weight: 900;
  box-shadow: 0 0.3rem 0.8rem rgba(0, 0, 0, 0.28);
}

.facefusion-reference-box__controls {
  display: grid;
  gap: 0.55rem;
}

.facefusion-reference-box__controls label {
  display: grid;
  gap: 0.3rem;
}

.facefusion-reference-box__controls span {
  color: var(--color-text-muted);
  font-size: 0.68rem;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.facefusion-reference-box__refresh {
  min-height: 2rem;
  border-radius: 999px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  background: rgba(255, 255, 255, 0.045);
  color: var(--color-text-secondary);
  font-size: 0.72rem;
  font-weight: 800;
}

.panel-topbar__close:hover {
  color: var(--color-text-primary);
  background: var(--color-bg-hover);
  border-color: var(--color-border-strong);
  transform: translateY(-1px);
}

.facefusion-preview {
  position: relative;
  min-height: 0;
  aspect-ratio: 16 / 9;
  display: flex;
  align-items: center;
  justify-content: center;
  background:
    radial-gradient(circle at 20% 20%, rgba(0, 117, 255, 0.16), transparent 32%),
    linear-gradient(135deg, rgba(10, 18, 28, 0.98), rgba(17, 24, 39, 0.94));
}

.facefusion-preview__image {
  width: 100%;
  height: 100%;
  object-fit: contain;
  background: rgba(0, 0, 0, 0.3);
}

.facefusion-preview__empty {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  height: 100%;
  color: var(--color-text-muted);
  font-size: 0.78rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.facefusion-preview__overlay {
  position: absolute;
  left: 0.75rem;
  right: 0.75rem;
  bottom: 0.75rem;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.55rem;
  padding: 0.55rem 0.65rem;
  border-radius: 0.65rem;
  border: 1px solid rgba(255, 255, 255, 0.12);
  background: rgba(5, 10, 18, 0.76);
  color: var(--color-text-secondary);
  font-size: 0.75rem;
  backdrop-filter: blur(14px);
}

.facefusion-preview__busy {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  gap: 0.6rem;
  background: rgba(4, 8, 14, 0.52);
  color: var(--color-text-primary);
  pointer-events: none;
}

.facefusion-preview__busy span {
  width: 2rem;
  height: 2rem;
  border-radius: 999px;
  border: 2px solid rgba(255, 255, 255, 0.22);
  border-top-color: var(--color-accent-blue, #0075ff);
  animation: facefusion-preview-spin 0.8s linear infinite;
}

.facefusion-preview__busy strong {
  font-size: 0.78rem;
  font-weight: 760;
  letter-spacing: 0.04em;
}

@keyframes facefusion-preview-spin {
  to {
    transform: rotate(360deg);
  }
}

.facefusion-preview__controls {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
}

.facefusion-preview__frame {
  color: var(--color-text-secondary);
  font-size: 0.72rem;
  white-space: nowrap;
}

.preview-frame-slider {
  width: 100%;
  min-width: 0;
  height: 0.35rem;
  border-radius: 999px;
  appearance: none;
  background: linear-gradient(90deg, rgba(0, 117, 255, 0.68), rgba(59, 130, 246, 0.28));
  outline: none;
}

.preview-frame-slider::-webkit-slider-thumb {
  width: 1rem;
  height: 1rem;
  border-radius: 999px;
  appearance: none;
  border: 2px solid rgba(255, 255, 255, 0.9);
  background: var(--color-accent-blue, #0075ff);
  box-shadow: 0 0 0 0.35rem rgba(0, 117, 255, 0.16);
}

.preview-frame-slider::-moz-range-thumb {
  width: 1rem;
  height: 1rem;
  border-radius: 999px;
  border: 2px solid rgba(255, 255, 255, 0.9);
  background: var(--color-accent-blue, #0075ff);
  box-shadow: 0 0 0 0.35rem rgba(0, 117, 255, 0.16);
}

.preview-frame-slider:disabled {
  opacity: 0.45;
}

.facefusion-source-manager {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(6.75rem, 1fr));
  gap: 0.65rem;
}

.facefusion-source-section {
  display: grid;
  gap: 0.65rem;
}

.facefusion-source-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.45rem;
}

.facefusion-source-action {
  position: relative;
  display: inline-flex;
  min-height: 2rem;
  align-items: center;
  justify-content: center;
  gap: 0.35rem;
  padding: 0 0.78rem;
  border-radius: 999px;
  border: 1px solid rgba(0, 117, 255, 0.34);
  background: rgba(0, 117, 255, 0.1);
  color: var(--color-text-primary);
  font-size: 0.74rem;
  font-weight: 760;
  cursor: pointer;
  overflow: hidden;
}

.facefusion-source-action input {
  position: absolute;
  inset: 0;
  opacity: 0;
  cursor: pointer;
}

.facefusion-source-action:disabled,
.facefusion-source-action:has(input:disabled) {
  opacity: 0.55;
  cursor: not-allowed;
}

.facefusion-source-action:hover:not(:disabled) {
  border-color: rgba(0, 117, 255, 0.55);
  background: rgba(0, 117, 255, 0.16);
}

.facefusion-source-card {
  min-width: 0;
  display: flex;
  min-height: 7.6rem;
  flex-direction: column;
  overflow: hidden;
  border-radius: 0.6rem;
  border: 1px solid var(--color-border-default);
  background: rgba(255, 255, 255, 0.035);
}

.facefusion-source-card img,
.facefusion-source-card__placeholder {
  width: 100%;
  aspect-ratio: 1 / 1;
  object-fit: cover;
  background: rgba(255, 255, 255, 0.055);
}

.facefusion-source-card__placeholder {
  display: grid;
  place-items: center;
  color: var(--color-text-muted);
  font-size: 0.75rem;
}

.facefusion-source-card__meta {
  display: flex;
  min-width: 0;
  align-items: center;
  justify-content: space-between;
  gap: 0.45rem;
  padding: 0.45rem 0.5rem;
}

.facefusion-source-card__meta span {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--color-text-secondary);
  font-size: 0.75rem;
}

.facefusion-source-card__meta button {
  flex: none;
  color: var(--color-text-muted);
  font-size: 0.72rem;
}

.facefusion-source-card__meta button:hover {
  color: var(--color-text-primary);
}

.facefusion-source-empty {
  display: grid;
  min-height: 4.5rem;
  place-items: center;
  border-radius: 0.65rem;
  border: 1px dashed rgba(255, 255, 255, 0.12);
  color: var(--color-text-muted);
  font-size: 0.72rem;
}

.facefusion-source-library {
  display: grid;
  gap: 0.75rem;
  padding: 0.75rem;
  border-radius: 0.75rem;
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(255, 255, 255, 0.025);
}

.facefusion-source-library__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.facefusion-source-library__head > span {
  color: var(--color-text-secondary);
  font-size: 0.76rem;
  font-weight: 750;
}

.facefusion-source-library__head small {
  color: var(--color-text-muted);
  font-size: 0.68rem;
}

.facefusion-source-library__empty {
  color: var(--color-text-muted);
  font-size: 0.75rem;
}

.facefusion-source-library__grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(5.75rem, 1fr));
  grid-auto-rows: 5.75rem;
  gap: 0.55rem;
  max-height: 18rem;
  overflow: auto;
  padding-right: 0.15rem;
}

.facefusion-source-library__item {
  position: relative;
  display: grid;
  width: 100%;
  height: 5.75rem;
  min-width: 0;
  overflow: hidden;
  border-radius: 0.6rem;
  border: 1px solid rgba(255, 255, 255, 0.1);
  background: rgba(255, 255, 255, 0.04);
  isolation: isolate;
}

.facefusion-source-library__use {
  position: relative;
  display: block;
  width: 100%;
  height: 100%;
  min-width: 0;
  overflow: hidden;
  padding: 0;
  border: 0;
  border-radius: inherit;
  background: transparent;
  text-align: left;
  cursor: pointer;
}

.facefusion-source-library__use img {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.facefusion-source-library__use span {
  position: absolute;
  left: 0.35rem;
  right: 0.35rem;
  bottom: 0.35rem;
  display: inline-flex;
  justify-content: center;
  min-height: 1.35rem;
  align-items: center;
  border-radius: 999px;
  background: rgba(5, 10, 18, 0.74);
  color: var(--color-text-primary);
  font-size: 0.68rem;
  font-weight: 760;
  backdrop-filter: blur(10px);
}

.facefusion-source-library__delete {
  position: absolute;
  top: 0.35rem;
  right: 0.35rem;
  z-index: 2;
  display: inline-grid;
  width: 1.45rem;
  height: 1.45rem;
  place-items: center;
  border-radius: 999px;
  border: 1px solid rgba(255, 255, 255, 0.22);
  background: rgba(7, 12, 22, 0.76);
  color: var(--color-text-primary);
  font-size: 1rem;
  line-height: 1;
  cursor: pointer;
  backdrop-filter: blur(10px);
}

.facefusion-source-library__delete:hover {
  border-color: rgba(255, 99, 99, 0.65);
  background: rgba(180, 35, 35, 0.82);
}

.facefusion-source-library__item.is-used {
  border-color: rgba(0, 117, 255, 0.72);
  box-shadow: 0 0 0 2px rgba(0, 117, 255, 0.22);
}

.facefusion-source-library__item.is-used .facefusion-source-library__use span {
  background: rgba(0, 117, 255, 0.82);
}

.facefusion-choice-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 0.45rem;
}

.facefusion-choice-chips button {
  min-height: 1.9rem;
  padding: 0 0.65rem;
  border-radius: 999px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  background: rgba(255, 255, 255, 0.035);
  color: var(--color-text-secondary);
  font-size: 0.72rem;
  cursor: pointer;
  transition: border-color 0.18s ease, background 0.18s ease, color 0.18s ease;
}

.facefusion-choice-chips button:hover {
  border-color: rgba(0, 117, 255, 0.34);
  color: var(--color-text-primary);
}

.facefusion-choice-chips button.is-active {
  border-color: rgba(0, 117, 255, 0.55);
  background: rgba(0, 117, 255, 0.16);
  color: var(--color-text-primary);
}

.facefusion-choice-chips .processor-chip {
  align-items: flex-start;
  display: inline-flex;
  flex-direction: column;
  gap: 0.18rem;
  min-height: 3.15rem;
  min-width: 7.25rem;
  padding: 0.42rem 0.68rem;
  border-radius: 0.55rem;
  text-align: left;
}

.facefusion-choice-chips .processor-chip span {
  color: inherit;
  font-size: 0.76rem;
  font-weight: 760;
  line-height: 1.15;
}

.facefusion-choice-chips .processor-chip small {
  color: var(--color-text-muted);
  font-family: var(--font-mono);
  font-size: 0.62rem;
  line-height: 1;
}

.facefusion-choice-chips .processor-chip em {
  align-self: flex-start;
  padding: 0.08rem 0.28rem;
  border: 1px solid rgba(0, 117, 255, 0.36);
  border-radius: 0.38rem;
  background: rgba(0, 117, 255, 0.12);
  color: #8fc2ff;
  font-size: 0.56rem;
  font-style: normal;
  font-weight: 850;
  letter-spacing: 0.04em;
  line-height: 1.15;
}

.facefusion-choice-chips .processor-chip em.is-muted {
  border-color: rgba(255, 255, 255, 0.1);
  background: rgba(255, 255, 255, 0.045);
  color: var(--color-text-muted);
}

.facefusion-choice-chips .processor-chip em.is-cuda {
  border-color: rgba(80, 220, 140, 0.28);
  background: rgba(80, 220, 140, 0.1);
  color: #8be0a9;
}

.facefusion-subpanel {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  padding: 0.75rem;
  border-radius: 0.65rem;
  border: 1px solid rgba(255, 255, 255, 0.07);
  background: rgba(255, 255, 255, 0.025);
}

.facefusion-subpanel > span {
  color: var(--color-text-muted);
  font-size: 0.68rem;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.facefusion-range {
  width: 100%;
  accent-color: var(--color-accent-blue, #0075ff);
}

.facefusion-model-select {
  display: flex;
  min-width: 0;
  min-height: 2.45rem;
  width: 100%;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  padding: 0.45rem 0.7rem;
  border-radius: 0.65rem;
  border: 1px solid rgba(255, 255, 255, 0.1);
  background: rgba(255, 255, 255, 0.045);
  color: var(--color-text-secondary);
  text-align: left;
}

.facefusion-model-select strong {
  min-width: 0;
  overflow: hidden;
  color: var(--color-text-primary);
  font-size: 0.74rem;
  font-weight: 760;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.facefusion-model-select span {
  flex: none;
  color: #8fc2ff;
  font-size: 0.68rem;
  font-weight: 800;
}

.facefusion-model-dialog {
  position: fixed;
  inset: 0;
  z-index: 70;
  display: grid;
  place-items: center;
  padding: 1rem;
}

.facefusion-model-dialog__backdrop {
  position: absolute;
  inset: 0;
  background: rgba(2, 6, 12, 0.78);
  backdrop-filter: blur(10px);
}

.facefusion-model-dialog__panel {
  position: relative;
  display: grid;
  grid-template-rows: auto auto minmax(0, 1fr);
  width: min(42rem, 100%);
  height: min(42rem, calc(100vh - 2rem));
  max-height: min(42rem, calc(100vh - 2rem));
  gap: 0.85rem;
  overflow: hidden;
  padding: 1rem;
  border-radius: 0.9rem;
  border: 1px solid rgba(255, 255, 255, 0.12);
  background: var(--color-bg-surface);
  box-shadow: 0 28px 80px rgba(0, 0, 0, 0.45);
}

.facefusion-model-dialog__head,
.facefusion-model-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
}

.facefusion-model-dialog__head strong {
  overflow: hidden;
  color: var(--color-text-primary);
  font-size: 0.94rem;
  font-weight: 850;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.facefusion-model-dialog__head button,
.facefusion-model-toolbar button,
.facefusion-model-upload {
  min-height: 2rem;
  padding: 0 0.75rem;
  border-radius: 999px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  background: rgba(255, 255, 255, 0.045);
  color: var(--color-text-secondary);
  font-size: 0.72rem;
}

.facefusion-model-upload {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}

.facefusion-model-upload input {
  display: none;
}

.facefusion-model-upload span {
  font-weight: 780;
}

.facefusion-model-dialog__empty {
  color: var(--color-text-muted);
  font-size: 0.78rem;
}

.facefusion-model-list {
  display: grid;
  align-content: start;
  gap: 0.32rem;
  min-height: 0;
  overflow: auto;
  padding-right: 0.2rem;
  overscroll-behavior: contain;
}

.facefusion-model-item {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
  gap: 0.75rem;
  min-height: 2.35rem;
  padding: 0.58rem 0.75rem;
  border-radius: 0.7rem;
  border: 1px solid rgba(255, 255, 255, 0.09);
  background: rgba(255, 255, 255, 0.035);
  color: var(--color-text-secondary);
  text-align: left;
}

.facefusion-model-item strong {
  min-width: 0;
  overflow: hidden;
  color: var(--color-text-primary);
  font-size: 0.8rem;
  font-weight: 820;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.facefusion-model-item b {
  flex: none;
  color: #7ec2ff;
  font-size: 0.68rem;
  font-weight: 850;
}

.facefusion-model-item.is-active {
  border-color: rgba(0, 117, 255, 0.72);
  background: rgba(0, 117, 255, 0.14);
}

.facefusion-model-item.is-missing {
  border-color: rgba(255, 255, 255, 0.08);
}

.facefusion-model-item.is-missing b {
  color: #f6c86f;
}

.facefusion-model-item.is-downloading {
  border-color: rgba(0, 117, 255, 0.56);
  background: rgba(0, 117, 255, 0.1);
}

@media (max-width: 1460px) {
  .facefusion-native-workspace__lower {
    grid-template-columns: minmax(0, 1fr);
  }
}

@media (max-width: 1180px) {
  .facefusion-native-grid {
    grid-template-columns: minmax(0, 1fr);
  }

  .facefusion-native-workspace__lower {
    grid-template-columns: minmax(0, 1fr);
  }

  .facefusion-native-column--source,
  .facefusion-native-column--processors,
  .facefusion-native-column--right,
  .facefusion-native-group--preview,
  .facefusion-native-group--left,
  .facefusion-native-group--right {
    grid-column: auto;
    grid-row: auto;
  }
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
</style>
