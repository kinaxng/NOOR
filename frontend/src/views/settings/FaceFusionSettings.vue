<script setup lang="ts">
import { computed, ref, onBeforeUnmount, onMounted, watch } from 'vue'
import api from '../../api'
import { useToast } from '../../composables/useToast'
import { useConfirm } from '../../composables/useConfirm'
import { useI18n } from '../../composables/useI18n'
import VuiButton from '../../components/ui/Button/VuiButton.vue'
import FieldRow from '../../components/ui/FieldRow/FieldRow.vue'

const toast = useToast()
const { confirm } = useConfirm()
const { t } = useI18n()

const loading = ref(false)
const saving = ref(false)
const upgrading = ref(false)
const modelActionLoading = ref(false)
const activeSection = ref<'runtime' | 'models' | 'execution' | 'detection' | 'masking' | 'output'>('runtime')

const sections = [
  { key: 'runtime', label: '源码与路径' },
  { key: 'models', label: '模型管理' },
  { key: 'execution', label: '执行' },
  { key: 'detection', label: '检测选择' },
  { key: 'masking', label: '遮罩' },
  { key: 'output', label: '输出' },
] as const

const executionProviderOptions = ['cpu', 'cuda', 'tensorrt', 'openvino', 'directml', 'rocm', 'coreml']
const downloadProviderOptions = ['github', 'huggingface']
const processorOptions = [
  { id: 'face_swapper', label: '人脸替换', acceleration: 'tensorrt' },
  { id: 'face_enhancer', label: '人脸增强', acceleration: 'tensorrt' },
  { id: 'frame_enhancer', label: '画面增强', acceleration: 'tensorrt' },
  { id: 'face_editor', label: '人脸编辑', acceleration: 'cuda' },
  { id: 'age_modifier', label: '年龄调整', acceleration: 'cuda' },
  { id: 'expression_restorer', label: '表情修复', acceleration: 'cuda' },
  { id: 'lip_syncer', label: '唇形同步', acceleration: 'cuda' },
  { id: 'frame_colorizer', label: '画面上色', acceleration: 'cuda' },
  { id: 'background_remover', label: '背景移除', acceleration: 'cuda' },
  { id: 'deep_swapper', label: 'Deep 换脸', acceleration: 'cuda' },
  { id: 'face_debugger', label: '人脸调试', acceleration: 'none' },
]
const faceSwapperModelOptions = ['blendswap_256', 'ghost_1_256', 'ghost_2_256', 'ghost_3_256', 'hififace_unofficial_256', 'hyperswap_1a_256', 'hyperswap_1b_256', 'hyperswap_1c_256', 'inswapper_128', 'inswapper_128_fp16', 'simswap_256', 'simswap_unofficial_512', 'uniface_256']
const faceSwapperPixelBoostOptionsByModel: Record<string, string[]> = {
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
const faceEnhancerModelOptions = ['gfpgan_1.2', 'gfpgan_1.3', 'gfpgan_1.4', 'gpen_bfr_256', 'gpen_bfr_512', 'restoreformer_plus_plus']
const frameEnhancerModelOptions = ['span_kendata_x4', 'real_esrgan_x2', 'real_esrgan_x2_fp16', 'real_esrgan_x4', 'real_esrgan_x4_fp16', 'real_hatgan_x4', 'ultra_sharp_x4']
const detectorAngleOptions = ['0', '90', '180', '270']
const maskTypeOptions = ['box', 'occlusion', 'area', 'region']
const maskAreaOptions = ['upper-face', 'lower-face', 'mouth']
const maskRegionOptions = ['skin', 'left-eyebrow', 'right-eyebrow', 'left-eye', 'right-eye', 'glasses', 'nose', 'mouth', 'upper-lip', 'lower-lip']
const genderOptions = ['', 'female', 'male']
const raceOptions = ['', 'white', 'black', 'latino', 'asian', 'indian', 'arabic']
const previewModeOptions = [
  { id: 'default', label: '默认' },
  { id: 'frame-by-frame', label: '原图对比' },
  { id: 'face-by-face', label: '人脸对比' },
]
const previewResolutionOptions = ['512x512', '768x768', '1024x1024']
const scaleOptions = Array.from({ length: 32 }, (_, index) => {
  const value = (index + 1) * 0.25
  return Number.isInteger(value) ? value.toFixed(1) : String(value)
})

const facefusionDir = ref('')
const facefusionPythonPath = ref('')
const nativeModelDir = ref('')
const resolvedFacefusionDir = ref('')
const facefusionSourceMode = ref('')
const facefusionVersion = ref('')
const facefusionUpstreamRevision = ref('')
const facefusionUpstreamShortRevision = ref('')
const facefusionUpstreamUpdatedAt = ref('')
const facefusionRuntimeVersions = ref<Record<string, string | null>>({})
const facefusionExecutionProviders = ref<string[]>([])
const facefusionPythonExecutable = ref('')
const facefusionCanSelfUpgrade = ref(false)
const facefusionUpgradeHint = ref('')
const facefusionUpstreamRepo = ref('')
const facefusionModelStatus = ref<any>(null)
const facefusionModelDownloadStatus = ref<any>({ status: 'idle', progress: 0, message: '', output: '' })
const executionProvider = ref('cuda')
const deviceIds = ref('0')
const threadCount = ref(8)
const videoMemoryStrategy = ref('strict')
const systemMemoryLimit = ref(0)
const logLevel = ref('info')
const downloadProviders = ref('github huggingface')
const haltOnError = ref(false)
const badgeAlwaysVisible = ref(false)
const previewMode = ref('default')
const previewResolution = ref('768x768')
const processors = ref('')
const faceSwapperModel = ref('hyperswap_1a_256')
const faceSwapperPixelBoost = ref('256x256')
const faceSwapperWeight = ref(0.5)
const faceEnhancerModel = ref('gfpgan_1.4')
const faceEnhancerBlend = ref(80)
const faceEnhancerWeight = ref(0.5)
const frameEnhancerModel = ref('span_kendata_x4')
const frameEnhancerBlend = ref(80)
const faceDetectorModel = ref('yolo_face')
const faceDetectorSize = ref('640x640')
const faceDetectorScore = ref(0.5)
const faceDetectorAngles = ref('0')
const faceDetectorMargin = ref('0 0 0 0')
const faceLandmarkerModel = ref('2dfan4')
const faceLandmarkerScore = ref(0.5)
const faceSelectorMode = ref('reference')
const faceSelectorOrder = ref('large-small')
const faceSelectorGender = ref('')
const faceSelectorAgeStart = ref('')
const faceSelectorAgeEnd = ref('')
const faceSelectorRace = ref('')
const referenceFrameNumber = ref(0)
const referenceFacePosition = ref(0)
const referenceFaceDistance = ref(0.3)
const faceTrackerScore = ref(0)
const faceMaskTypes = ref('box')
const faceMaskAreas = ref('')
const faceMaskRegions = ref('')
const faceMaskBlur = ref(0.3)
const faceMaskPadding = ref('0 0 0 0')
const faceOccluderModel = ref('xseg_1')
const faceParserModel = ref('bisenet_resnet_34')
const outputVideoEncoder = ref('libx264')
const outputVideoPreset = ref('veryfast')
const outputVideoQuality = ref(80)
const outputVideoScale = ref('1.0')
const outputVideoFps = ref('')
const outputAudioEncoder = ref('aac')
const outputAudioQuality = ref(80)
const outputAudioVolume = ref(100)
const outputImageQuality = ref(80)
const outputImageScale = ref('1.0')
const tempFrameFormat = ref('png')

function splitTokens(value: string) {
  return String(value || '').split(/[\s,]+/).map(item => item.trim()).filter(Boolean)
}

function hasToken(value: string, token: string) {
  return splitTokens(value).includes(token)
}

function toggleToken(value: string, token: string) {
  const items = splitTokens(value)
  const next = items.includes(token) ? items.filter(item => item !== token) : [...items, token]
  return next.join(' ')
}

function quadPart(value: string, index: number) {
  return splitTokens(value)[index] || '0'
}

function updateQuadPart(value: string, index: number, nextValue: string) {
  const items = ['0', '0', '0', '0']
  splitTokens(value).slice(0, 4).forEach((item, itemIndex) => {
    items[itemIndex] = item
  })
  items[index] = nextValue === '' ? '0' : String(nextValue)
  return items.join(' ')
}

function inputValue(event: Event) {
  return (event.target as HTMLInputElement).value
}

function settingsErrorMessage(e: any, fallback = t('settings.saveFailed')) {
  return e?.response?.data?.detail || e?.message || fallback
}

const selectedProcessors = computed(() => splitTokens(processors.value))
const faceSwapperPixelBoostOptions = computed(() => {
  return faceSwapperPixelBoostOptionsByModel[faceSwapperModel.value] || ['256x256']
})

watch(faceSwapperModel, () => {
  if (!faceSwapperPixelBoostOptions.value.includes(faceSwapperPixelBoost.value)) {
    faceSwapperPixelBoost.value = faceSwapperPixelBoostOptions.value[0]
  }
})

function runtimeVersionRows() {
  const versions = facefusionRuntimeVersions.value || {}
  return [
    { key: 'facefusion', label: 'FaceFusion', value: facefusionVersion.value || '未知' },
    { key: 'python', label: 'Python', value: versions.python || '未知' },
    { key: 'onnxruntime', label: 'ONNX Runtime', value: versions.onnxruntime || '未检测到' },
    { key: 'onnx', label: 'ONNX', value: versions.onnx || '未检测到' },
    { key: 'numpy', label: 'NumPy', value: versions.numpy || '未检测到' },
    { key: 'opencv', label: 'OpenCV', value: versions.opencv || '未检测到' },
    { key: 'scipy', label: 'SciPy', value: versions.scipy || '未检测到' },
    { key: 'tqdm', label: 'tqdm', value: versions.tqdm || '未检测到' },
    { key: 'gradio', label: 'Gradio', value: versions.gradio || '未检测到' },
  ]
}

onMounted(async () => {
  await loadSettings()
  await loadFaceFusionModels()
})

onBeforeUnmount(() => {
  if (facefusionModelPollTimer) {
    window.clearInterval(facefusionModelPollTimer)
  }
})

async function loadSettings() {
  loading.value = true
  try {
    const resp = await api.get('/settings')
    const data = resp.data
    facefusionDir.value = data.facefusion?.dir || ''
    facefusionPythonPath.value = data.facefusion?.python_path || ''
    nativeModelDir.value = data.facefusion?.native_model_dir || ''
    resolvedFacefusionDir.value = data.facefusion?.resolved_dir || ''
    facefusionSourceMode.value = data.facefusion?.source_mode || ''
    facefusionVersion.value = data.facefusion?.version || ''
    facefusionUpstreamRevision.value = data.facefusion?.upstream_revision || ''
    facefusionUpstreamShortRevision.value = data.facefusion?.upstream_short_revision || ''
    facefusionUpstreamUpdatedAt.value = data.facefusion?.upstream_updated_at || ''
    facefusionRuntimeVersions.value = data.facefusion?.runtime_versions || {}
    facefusionExecutionProviders.value = data.facefusion?.execution_providers || []
    facefusionPythonExecutable.value = data.facefusion?.python_executable || ''
    facefusionCanSelfUpgrade.value = data.facefusion?.can_self_upgrade || false
    facefusionUpgradeHint.value = data.facefusion?.upgrade_hint || ''
    facefusionUpstreamRepo.value = data.facefusion?.upstream_repo || ''
    if (data.facefusion_defaults) {
      executionProvider.value = data.facefusion_defaults.execution_provider || 'cuda'
      deviceIds.value = data.facefusion_defaults.device_ids || '0'
      threadCount.value = data.facefusion_defaults.thread_count ?? 8
      videoMemoryStrategy.value = data.facefusion_defaults.video_memory_strategy || 'strict'
      systemMemoryLimit.value = data.facefusion_defaults.system_memory_limit ?? 0
      logLevel.value = data.facefusion_defaults.log_level || 'info'
      downloadProviders.value = data.facefusion_defaults.download_providers || 'github huggingface'
      haltOnError.value = data.facefusion_defaults.halt_on_error ?? false
      badgeAlwaysVisible.value = data.facefusion_defaults.badge_always_visible ?? false
      previewMode.value = data.facefusion_defaults.preview_mode || 'default'
      previewResolution.value = data.facefusion_defaults.preview_resolution || '768x768'
      processors.value = data.facefusion_defaults.processors || ''
      faceSwapperModel.value = data.facefusion_defaults.face_swapper_model || 'hyperswap_1a_256'
      faceSwapperPixelBoost.value = data.facefusion_defaults.face_swapper_pixel_boost || '256x256'
      faceSwapperWeight.value = data.facefusion_defaults.face_swapper_weight ?? 0.5
      faceEnhancerModel.value = data.facefusion_defaults.face_enhancer_model || 'gfpgan_1.4'
      faceEnhancerBlend.value = data.facefusion_defaults.face_enhancer_blend ?? 80
      faceEnhancerWeight.value = data.facefusion_defaults.face_enhancer_weight ?? 0.5
      frameEnhancerModel.value = data.facefusion_defaults.frame_enhancer_model || 'span_kendata_x4'
      frameEnhancerBlend.value = data.facefusion_defaults.frame_enhancer_blend ?? 80
      faceDetectorModel.value = data.facefusion_defaults.face_detector_model || 'yolo_face'
      faceDetectorSize.value = data.facefusion_defaults.face_detector_size || '640x640'
      faceDetectorScore.value = data.facefusion_defaults.face_detector_score ?? 0.5
      faceDetectorAngles.value = data.facefusion_defaults.face_detector_angles || '0'
      faceDetectorMargin.value = data.facefusion_defaults.face_detector_margin || '0 0 0 0'
      faceLandmarkerModel.value = data.facefusion_defaults.face_landmarker_model || '2dfan4'
      faceLandmarkerScore.value = data.facefusion_defaults.face_landmarker_score ?? 0.5
      faceSelectorMode.value = data.facefusion_defaults.face_selector_mode || 'reference'
      faceSelectorOrder.value = data.facefusion_defaults.face_selector_order || 'large-small'
      faceSelectorGender.value = data.facefusion_defaults.face_selector_gender || ''
      faceSelectorAgeStart.value = data.facefusion_defaults.face_selector_age_start || ''
      faceSelectorAgeEnd.value = data.facefusion_defaults.face_selector_age_end || ''
      faceSelectorRace.value = data.facefusion_defaults.face_selector_race || ''
      referenceFrameNumber.value = data.facefusion_defaults.reference_frame_number ?? 0
      referenceFacePosition.value = data.facefusion_defaults.reference_face_position ?? 0
      referenceFaceDistance.value = data.facefusion_defaults.reference_face_distance ?? 0.3
      faceTrackerScore.value = data.facefusion_defaults.face_tracker_score ?? 0
      faceMaskTypes.value = data.facefusion_defaults.face_mask_types || 'box'
      faceMaskAreas.value = data.facefusion_defaults.face_mask_areas || ''
      faceMaskRegions.value = data.facefusion_defaults.face_mask_regions || ''
      faceMaskBlur.value = data.facefusion_defaults.face_mask_blur ?? 0.3
      faceMaskPadding.value = data.facefusion_defaults.face_mask_padding || '0 0 0 0'
      faceOccluderModel.value = data.facefusion_defaults.face_occluder_model || 'xseg_1'
      faceParserModel.value = data.facefusion_defaults.face_parser_model || 'bisenet_resnet_34'
      outputVideoEncoder.value = data.facefusion_defaults.output_video_encoder || 'libx264'
      outputVideoPreset.value = data.facefusion_defaults.output_video_preset || 'veryfast'
      outputVideoQuality.value = data.facefusion_defaults.output_video_quality ?? 80
      outputVideoScale.value = data.facefusion_defaults.output_video_scale || '1.0'
      outputVideoFps.value = data.facefusion_defaults.output_video_fps || ''
      outputAudioEncoder.value = data.facefusion_defaults.output_audio_encoder || 'aac'
      outputAudioQuality.value = data.facefusion_defaults.output_audio_quality ?? 80
      outputAudioVolume.value = data.facefusion_defaults.output_audio_volume ?? 100
      outputImageQuality.value = data.facefusion_defaults.output_image_quality ?? 80
      outputImageScale.value = data.facefusion_defaults.output_image_scale || '1.0'
      tempFrameFormat.value = data.facefusion_defaults.temp_frame_format || 'png'
    }
  } catch (e: any) {
    toast.error(settingsErrorMessage(e))
  } finally {
    loading.value = false
  }
}

async function loadFaceFusionModels() {
  try {
    const resp = await api.get('/settings/facefusion/models')
    facefusionModelStatus.value = resp.data?.models || null
    facefusionModelDownloadStatus.value = resp.data?.download_status || { status: 'idle', progress: 0, message: '', output: '' }
  } catch (e: any) {
    toast.error(settingsErrorMessage(e, 'FaceFusion 模型状态读取失败'))
  }
}

async function verifyFaceFusionModels() {
  modelActionLoading.value = true
  try {
    const resp = await api.post('/settings/facefusion/models/verify')
    facefusionModelStatus.value = resp.data?.models || null
    toast.success('FaceFusion 模型校验完成')
  } catch (e: any) {
    toast.error(settingsErrorMessage(e, 'FaceFusion 模型校验失败'))
  } finally {
    modelActionLoading.value = false
  }
}

async function downloadFaceFusionModels(scope: 'lite' | 'full' = 'lite') {
  modelActionLoading.value = true
  try {
    await api.post('/settings/facefusion/models/download', { scope })
    toast.success('FaceFusion 模型预下载已开始')
    await loadFaceFusionModels()
  } catch (e: any) {
    toast.error(settingsErrorMessage(e, 'FaceFusion 模型预下载失败'))
  } finally {
    modelActionLoading.value = false
  }
}

let facefusionModelPollTimer: number | undefined
watch(() => facefusionModelDownloadStatus.value?.status, (status) => {
  if (facefusionModelPollTimer) {
    window.clearInterval(facefusionModelPollTimer)
    facefusionModelPollTimer = undefined
  }
  if (status === 'running') {
    facefusionModelPollTimer = window.setInterval(async () => {
      try {
        const resp = await api.get('/settings/facefusion/models/download-status')
        facefusionModelDownloadStatus.value = resp.data
        if (resp.data?.status && resp.data.status !== 'running') {
          await loadFaceFusionModels()
        }
      } catch {
        // Keep polling best-effort; the settings page will refresh on next manual action.
      }
    }, 2000)
  }
})

async function saveRuntime() {
  saving.value = true
  try {
    await api.put('/settings/facefusion', {
      dir: facefusionDir.value,
      python_path: facefusionPythonPath.value,
    })
    toast.success(t('settings.saveSuccess'))
  } catch (e: any) {
    toast.error(settingsErrorMessage(e))
  } finally {
    saving.value = false
  }
}

async function upgradeFaceFusion() {
  if (!facefusionCanSelfUpgrade.value) {
    toast.error(facefusionUpgradeHint.value || '当前环境不支持 FaceFusion 自升级')
    return
  }
  if (!await confirm({ message: '从上游拉取并升级 NOOR 内置 FaceFusion？升级会先验证，失败会恢复旧源码。' })) return
  upgrading.value = true
  try {
    const resp = await api.post('/settings/facefusion/upgrade')
    facefusionVersion.value = resp.data.version || ''
    facefusionUpstreamRevision.value = resp.data.upstream_revision || ''
    facefusionUpstreamShortRevision.value = (resp.data.upstream_revision || '').slice(0, 12)
    facefusionUpstreamUpdatedAt.value = resp.data.upstream_updated_at || ''
    toast.success(`FaceFusion 已升级到 ${resp.data.version || '未知版本'}`)
    await loadSettings()
  } catch (e: any) {
    toast.error(e.response?.data?.detail || 'FaceFusion 升级失败')
  } finally {
    upgrading.value = false
  }
}

async function saveDefaults() {
  saving.value = true
  try {
    await api.put('/settings/facefusion/defaults', {
      execution_provider: executionProvider.value,
      device_ids: deviceIds.value,
      thread_count: threadCount.value,
      video_memory_strategy: videoMemoryStrategy.value,
      system_memory_limit: systemMemoryLimit.value,
      log_level: logLevel.value,
      download_providers: downloadProviders.value,
      halt_on_error: haltOnError.value,
      badge_always_visible: badgeAlwaysVisible.value,
      preview_mode: previewMode.value,
      preview_resolution: previewResolution.value,
      processors: processors.value,
      face_swapper_model: faceSwapperModel.value,
      face_swapper_pixel_boost: faceSwapperPixelBoost.value,
      face_swapper_weight: faceSwapperWeight.value,
      face_enhancer_model: faceEnhancerModel.value,
      face_enhancer_blend: faceEnhancerBlend.value,
      face_enhancer_weight: faceEnhancerWeight.value,
      frame_enhancer_model: frameEnhancerModel.value,
      frame_enhancer_blend: frameEnhancerBlend.value,
      face_detector_model: faceDetectorModel.value,
      face_detector_size: faceDetectorSize.value,
      face_detector_score: faceDetectorScore.value,
      face_detector_angles: faceDetectorAngles.value,
      face_detector_margin: faceDetectorMargin.value,
      face_landmarker_model: faceLandmarkerModel.value,
      face_landmarker_score: faceLandmarkerScore.value,
      face_selector_mode: faceSelectorMode.value,
      face_selector_order: faceSelectorOrder.value,
      face_selector_gender: faceSelectorGender.value,
      face_selector_age_start: faceSelectorAgeStart.value,
      face_selector_age_end: faceSelectorAgeEnd.value,
      face_selector_race: faceSelectorRace.value,
      reference_frame_number: referenceFrameNumber.value,
      reference_face_position: referenceFacePosition.value,
      reference_face_distance: referenceFaceDistance.value,
      face_tracker_score: faceTrackerScore.value,
      face_mask_types: faceMaskTypes.value,
      face_mask_areas: faceMaskAreas.value,
      face_mask_regions: faceMaskRegions.value,
      face_mask_blur: faceMaskBlur.value,
      face_mask_padding: faceMaskPadding.value,
      face_occluder_model: faceOccluderModel.value,
      face_parser_model: faceParserModel.value,
      output_video_encoder: outputVideoEncoder.value,
      output_video_preset: outputVideoPreset.value,
      output_video_quality: outputVideoQuality.value,
      output_video_scale: outputVideoScale.value,
      output_video_fps: outputVideoFps.value,
      output_audio_encoder: outputAudioEncoder.value,
      output_audio_quality: outputAudioQuality.value,
      output_audio_volume: outputAudioVolume.value,
      output_image_quality: outputImageQuality.value,
      output_image_scale: outputImageScale.value,
      temp_frame_format: tempFrameFormat.value,
    })
    toast.success(t('settings.saveSuccess'))
  } catch (e: any) {
    toast.error(settingsErrorMessage(e))
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="flex flex-col gap-6">
    <div v-if="loading" class="flex items-center justify-center py-16">
      <div class="w-8 h-8 border-2 rounded-full animate-spin border-[#0075FF] border-t-transparent"></div>
    </div>

    <template v-else>
      <div class="facefusion-shell ui-card">
        <div class="facefusion-card-head">
          <div>
            <h2 class="settings-card__title">FaceFusion</h2>
            <p class="settings-card__desc">内置源码路径、升级与默认处理参数。</p>
          </div>
          <div class="facefusion-head-actions">
            <VuiButton
              v-if="activeSection === 'runtime'"
              variant="contained"
              color="secondary"
              size="small"
              customClass="settings-secondary-btn"
              :loading="upgrading"
              :disabled="!facefusionCanSelfUpgrade"
              @click="upgradeFaceFusion"
            >
              {{ upgrading ? '升级中' : '升级 FaceFusion' }}
            </VuiButton>
            <VuiButton
              v-if="!['runtime', 'models'].includes(activeSection)"
              variant="gradient"
              color="info"
              size="small"
              customClass="settings-primary-btn"
              :loading="saving"
              @click="saveDefaults"
            >
              保存默认参数
            </VuiButton>
          </div>
        </div>

        <div class="facefusion-tabbar">
          <div class="facefusion-tabs" role="tablist">
            <button
              v-for="section in sections"
              :key="section.key"
              type="button"
              :class="{ 'is-active': activeSection === section.key }"
              @click="activeSection = section.key"
            >
              {{ section.label }}
            </button>
          </div>
        </div>

      <div v-if="activeSection === 'runtime'" class="facefusion-section">
        <h2 class="settings-card__title">源码与路径</h2>
        <p class="settings-card__desc">默认使用 NOOR 内置 FaceFusion 源码；仅在需要临时覆盖时填写外部目录。</p>

        <div class="settings-form mt-4">
          <FieldRow label="当前版本" description="NOOR 内置 FaceFusion 与运行时依赖版本">
            <div class="facefusion-version-grid">
              <div v-for="item in runtimeVersionRows()" :key="item.key" class="facefusion-version-item">
                <span>{{ item.label }}</span>
                <strong>{{ item.value }}</strong>
              </div>
            </div>
          </FieldRow>

          <FieldRow label="Python 解释器" description="实际运行 FaceFusion CLI 的 Python">
            <input :value="facefusionPythonExecutable" type="text" class="settings-input" readonly />
          </FieldRow>

          <FieldRow label="可用执行后端" description="ONNX Runtime 当前检测到的 providers">
            <div class="choice-chips choice-chips--readonly">
              <button
                v-for="provider in facefusionExecutionProviders"
                :key="provider"
                type="button"
                class="is-active"
                disabled
              >
                {{ provider }}
              </button>
              <span v-if="!facefusionExecutionProviders.length" class="facefusion-empty-state">未检测到</span>
            </div>
          </FieldRow>

          <FieldRow label="上游仓库" description="升级时从该仓库拉取源码并套用 NOOR 适配">
            <input :value="facefusionUpstreamRepo" type="text" class="settings-input" readonly />
          </FieldRow>

          <FieldRow label="上游版本" description="最近一次通过 NOOR 升级记录的上游 commit">
            <div class="facefusion-upstream-grid">
              <div class="facefusion-version-item">
                <span>Commit</span>
                <strong :title="facefusionUpstreamRevision">{{ facefusionUpstreamShortRevision || facefusionUpstreamRevision || '未知' }}</strong>
              </div>
              <div class="facefusion-version-item">
                <span>Updated</span>
                <strong>{{ facefusionUpstreamUpdatedAt || '未知' }}</strong>
              </div>
            </div>
          </FieldRow>

          <FieldRow label="外部 FaceFusion 目录" description="留空使用 NOOR 内置源码；填写时目录下应存在 facefusion.py">
            <input v-model="facefusionDir" type="text" placeholder="留空使用 NOOR 内置 FaceFusion" class="settings-input" />
          </FieldRow>

          <FieldRow label="当前源码目录" description="实际运行 headless-run 的源码入口">
            <input :value="resolvedFacefusionDir" type="text" class="settings-input" readonly />
          </FieldRow>

          <FieldRow label="源码模式" description="embedded 为 NOOR 内置，external 为外部覆盖">
            <input :value="facefusionSourceMode" type="text" class="settings-input" readonly />
          </FieldRow>

          <FieldRow label="Python 路径" description="可留空，NOOR 会优先查找 FaceFusion 目录下的 .venv/venv，再回退到当前 Python">
            <input v-model="facefusionPythonPath" type="text" placeholder="/path/to/python" class="settings-input" />
          </FieldRow>

          <FieldRow label="模型目录" description="FaceFusion 原生模型目录；当前由 .assets/models 提供">
            <input :value="nativeModelDir" type="text" class="settings-input" readonly />
          </FieldRow>

          <div class="settings-actions mt-2">
            <VuiButton variant="gradient" color="info" size="small" customClass="settings-primary-btn" :loading="saving" @click="saveRuntime">
              保存源码设置
            </VuiButton>
          </div>
          <p v-if="facefusionUpgradeHint" class="facefusion-upgrade-hint">{{ facefusionUpgradeHint }}</p>
        </div>
      </div>

      <div v-if="activeSection === 'models'" class="facefusion-section">
        <h2 class="settings-card__title">模型管理</h2>
        <p class="settings-card__desc">预下载 FaceFusion 模型，并校验 NOOR 模型目录中的 hash。</p>

        <div class="settings-form mt-4">
          <FieldRow label="模型目录" description="NOOR 管理的 FaceFusion 模型目录">
            <input :value="facefusionModelStatus?.model_dir || nativeModelDir" type="text" class="settings-input" readonly />
          </FieldRow>

          <FieldRow label="模型状态" description="当前目录中的模型数量与校验结果">
            <div class="facefusion-model-grid">
              <div class="facefusion-version-item">
                <span>ONNX</span>
                <strong>{{ facefusionModelStatus?.onnx_count ?? 0 }}</strong>
              </div>
              <div class="facefusion-version-item">
                <span>已校验</span>
                <strong>{{ facefusionModelStatus?.valid_count ?? 0 }}</strong>
              </div>
              <div class="facefusion-version-item">
                <span>异常</span>
                <strong>{{ facefusionModelStatus?.invalid_count ?? 0 }}</strong>
              </div>
              <div class="facefusion-version-item">
                <span>容量</span>
                <strong>{{ facefusionModelStatus?.total_size_label || '0 B' }}</strong>
              </div>
            </div>
          </FieldRow>

          <FieldRow label="预下载" description="Lite 为常用模型；Full 会下载完整 FaceFusion 模型集，耗时和空间更高">
            <div class="settings-actions">
              <VuiButton variant="gradient" color="info" size="small" :loading="modelActionLoading" @click="downloadFaceFusionModels('lite')">
                预下载 Lite
              </VuiButton>
              <VuiButton variant="contained" color="secondary" size="small" :loading="modelActionLoading" @click="downloadFaceFusionModels('full')">
                预下载 Full
              </VuiButton>
              <VuiButton variant="contained" color="secondary" size="small" :loading="modelActionLoading" @click="verifyFaceFusionModels">
                校验 Hash
              </VuiButton>
              <VuiButton variant="text" color="secondary" size="small" @click="loadFaceFusionModels">
                刷新
              </VuiButton>
            </div>
          </FieldRow>

          <FieldRow label="下载状态" description="后台预下载进度">
            <div class="facefusion-model-status">
              <div class="facefusion-model-status__line">
                <span>{{ facefusionModelDownloadStatus?.status || 'idle' }}</span>
                <strong>{{ facefusionModelDownloadStatus?.progress ?? 0 }}%</strong>
              </div>
              <div class="facefusion-model-progress">
                <i :style="{ width: `${Math.max(0, Math.min(100, Number(facefusionModelDownloadStatus?.progress || 0)))}%` }"></i>
              </div>
              <p>{{ facefusionModelDownloadStatus?.message || '空闲' }}</p>
            </div>
          </FieldRow>

          <FieldRow v-if="facefusionModelStatus?.invalid_count || facefusionModelStatus?.missing_hash_count" label="校验异常" description="最多显示前 50 条">
            <div class="facefusion-model-issues">
              <div v-for="item in facefusionModelStatus?.invalid || []" :key="item.name">
                <strong>{{ item.name }}</strong>
                <span>{{ item.expected }} -> {{ item.actual }}</span>
              </div>
              <div v-for="item in facefusionModelStatus?.missing_hash || []" :key="item">
                <strong>{{ item }}</strong>
                <span>缺少 hash</span>
              </div>
            </div>
          </FieldRow>

          <FieldRow v-if="facefusionModelDownloadStatus?.output" label="最近输出" description="预下载命令输出摘要">
            <pre class="facefusion-model-output">{{ facefusionModelDownloadStatus.output }}</pre>
          </FieldRow>
        </div>
      </div>

      <div v-if="activeSection === 'execution'" class="facefusion-section">
        <h2 class="settings-card__title">执行与处理器</h2>
        <p class="settings-card__desc">这些参数将作为媒体库破解面板中 FaceFusion tab 的默认值。</p>

        <div class="settings-form mt-4">
          <FieldRow label="执行后端" description="FaceFusion headless-run 的 execution provider">
            <div class="choice-chips">
              <button
                v-for="provider in executionProviderOptions"
                :key="provider"
                type="button"
                :class="{ 'is-active': hasToken(executionProvider, provider) }"
                @click="executionProvider = toggleToken(executionProvider, provider)"
              >
                {{ provider }}
              </button>
            </div>
          </FieldRow>

          <FieldRow label="设备 ID" description="多个设备可用空格或逗号分隔">
            <input v-model="deviceIds" type="text" placeholder="0" class="settings-input" />
          </FieldRow>

          <FieldRow label="线程数" description="FaceFusion execution-thread-count">
            <div class="range-control">
              <input v-model.number="threadCount" type="range" min="1" max="32" step="1" />
              <span>{{ threadCount }}</span>
            </div>
          </FieldRow>

          <FieldRow label="视频显存策略" description="strict 更稳，tolerant 更激进">
            <select v-model="videoMemoryStrategy" class="settings-input">
              <option value="strict">strict</option>
              <option value="moderate">moderate</option>
              <option value="tolerant">tolerant</option>
            </select>
          </FieldRow>

          <FieldRow label="系统内存限制" description="单位 GB，0 表示不限制">
            <input v-model.number="systemMemoryLimit" type="number" min="0" max="128" step="4" class="settings-input" />
          </FieldRow>

          <FieldRow label="日志级别" description="控制 FaceFusion CLI 输出日志">
            <select v-model="logLevel" class="settings-input">
              <option value="error">error</option>
              <option value="warn">warn</option>
              <option value="info">info</option>
              <option value="debug">debug</option>
            </select>
          </FieldRow>

          <FieldRow label="下载源" description="多个下载源可用空格或逗号分隔">
            <div class="choice-chips">
              <button
                v-for="provider in downloadProviderOptions"
                :key="provider"
                type="button"
                :class="{ 'is-active': hasToken(downloadProviders, provider) }"
                @click="downloadProviders = toggleToken(downloadProviders, provider)"
              >
                {{ provider }}
              </button>
            </div>
          </FieldRow>

          <FieldRow label="媒体库换脸标签" description="开启后媒体库作品卡片固定显示换脸标签；关闭时仅鼠标指向作品卡片时显示。">
            <label class="facefusion-switch">
              <input v-model="badgeAlwaysVisible" type="checkbox" />
              <span></span>
              <strong>{{ badgeAlwaysVisible ? '固定显示' : '悬停显示' }}</strong>
            </label>
          </FieldRow>

          <FieldRow label="预览模式" description="媒体库 FaceFusion 面板的默认预览展示方式">
            <select v-model="previewMode" class="settings-input">
              <option v-for="mode in previewModeOptions" :key="mode.id" :value="mode.id">{{ mode.label }} ({{ mode.id }})</option>
            </select>
          </FieldRow>

          <FieldRow label="预览分辨率" description="分辨率越高越清晰，但生成更慢、显存占用更高">
            <select v-model="previewResolution" class="settings-input">
              <option v-for="resolution in previewResolutionOptions" :key="resolution" :value="resolution">{{ resolution }}</option>
            </select>
          </FieldRow>

          <FieldRow label="处理器" description="留空则不传 --processors，使用 FaceFusion 自身配置；多个处理器可用空格或逗号分隔">
            <div class="choice-chips">
              <button
                v-for="processor in processorOptions"
                :key="processor.id"
                type="button"
                class="processor-chip"
                :class="{ 'is-active': hasToken(processors, processor.id) }"
                @click="processors = toggleToken(processors, processor.id)"
              >
                <span>{{ processor.label }}</span>
                <small>{{ processor.id }}</small>
                <em :class="{ 'is-cuda': processor.acceleration === 'cuda', 'is-muted': processor.acceleration === 'none' }">
                  {{ processor.acceleration === 'tensorrt' ? 'TRT 推荐' : processor.acceleration === 'cuda' ? 'CUDA 推荐' : '无推理加速' }}
                </em>
              </button>
            </div>
          </FieldRow>

          <div v-if="selectedProcessors.includes('face_swapper')" class="processor-options">
            <div class="processor-options__head">face_swapper</div>
            <FieldRow label="换脸模型" description="FaceFusion face-swapper-model">
              <select v-model="faceSwapperModel" class="settings-input">
                <option v-for="model in faceSwapperModelOptions" :key="model" :value="model">{{ model }}</option>
              </select>
            </FieldRow>
            <FieldRow label="Pixel boost" description="可选范围随换脸模型变化">
              <select v-model="faceSwapperPixelBoost" class="settings-input">
                <option v-for="size in faceSwapperPixelBoostOptions" :key="size" :value="size">{{ size }}</option>
              </select>
            </FieldRow>
            <FieldRow label="换脸权重" description="0-1">
              <div class="range-control">
                <input v-model.number="faceSwapperWeight" type="range" min="0" max="1" step="0.05" />
                <span>{{ Number(faceSwapperWeight).toFixed(2) }}</span>
              </div>
            </FieldRow>
          </div>

          <div v-if="selectedProcessors.includes('face_enhancer')" class="processor-options">
            <div class="processor-options__head">face_enhancer</div>
            <FieldRow label="增强模型" description="FaceFusion face-enhancer-model">
              <select v-model="faceEnhancerModel" class="settings-input">
                <option v-for="model in faceEnhancerModelOptions" :key="model" :value="model">{{ model }}</option>
              </select>
            </FieldRow>
            <FieldRow label="增强混合" description="0-100">
              <div class="range-control">
                <input v-model.number="faceEnhancerBlend" type="range" min="0" max="100" step="1" />
                <span>{{ faceEnhancerBlend }}</span>
              </div>
            </FieldRow>
            <FieldRow label="增强权重" description="0-1">
              <div class="range-control">
                <input v-model.number="faceEnhancerWeight" type="range" min="0" max="1" step="0.05" />
                <span>{{ Number(faceEnhancerWeight).toFixed(2) }}</span>
              </div>
            </FieldRow>
          </div>

          <div v-if="selectedProcessors.includes('frame_enhancer')" class="processor-options">
            <div class="processor-options__head">frame_enhancer</div>
            <FieldRow label="帧增强模型" description="FaceFusion frame-enhancer-model">
              <select v-model="frameEnhancerModel" class="settings-input">
                <option v-for="model in frameEnhancerModelOptions" :key="model" :value="model">{{ model }}</option>
              </select>
            </FieldRow>
            <FieldRow label="帧增强混合" description="0-100">
              <div class="range-control">
                <input v-model.number="frameEnhancerBlend" type="range" min="0" max="100" step="1" />
                <span>{{ frameEnhancerBlend }}</span>
              </div>
            </FieldRow>
          </div>
        </div>
      </div>

      <div v-if="activeSection === 'detection'" class="facefusion-section">
        <h2 class="settings-card__title">检测与选择</h2>

        <div class="settings-form mt-4">
          <FieldRow label="人脸检测模型" description="FaceFusion face-detector-model">
            <select v-model="faceDetectorModel" class="settings-input">
              <option value="many">many</option>
              <option value="retinaface">retinaface</option>
              <option value="scrfd">scrfd</option>
              <option value="yolo_face">yolo_face</option>
              <option value="yunet">yunet</option>
            </select>
          </FieldRow>

          <FieldRow label="检测尺寸" description="当前内置 FaceFusion 支持 640x640">
            <select v-model="faceDetectorSize" class="settings-input">
              <option value="640x640">640x640</option>
            </select>
          </FieldRow>

          <FieldRow label="检测分数" description="0-1">
            <div class="range-control">
              <input v-model.number="faceDetectorScore" type="range" min="0" max="1" step="0.05" />
              <span>{{ Number(faceDetectorScore).toFixed(2) }}</span>
            </div>
          </FieldRow>

          <FieldRow label="检测角度" description="多个角度可用空格或逗号分隔">
            <div class="choice-chips">
              <button
                v-for="angle in detectorAngleOptions"
                :key="angle"
                type="button"
                :class="{ 'is-active': hasToken(faceDetectorAngles, angle) }"
                @click="faceDetectorAngles = toggleToken(faceDetectorAngles, angle)"
              >
                {{ angle }}
              </button>
            </div>
          </FieldRow>

          <FieldRow label="检测边距" description="上 右 下 左">
            <div class="quad-control">
              <label>
                <span>上</span>
                <input :value="quadPart(faceDetectorMargin, 0)" type="number" min="0" max="100" step="1" @input="faceDetectorMargin = updateQuadPart(faceDetectorMargin, 0, inputValue($event))" />
              </label>
              <label>
                <span>右</span>
                <input :value="quadPart(faceDetectorMargin, 1)" type="number" min="0" max="100" step="1" @input="faceDetectorMargin = updateQuadPart(faceDetectorMargin, 1, inputValue($event))" />
              </label>
              <label>
                <span>下</span>
                <input :value="quadPart(faceDetectorMargin, 2)" type="number" min="0" max="100" step="1" @input="faceDetectorMargin = updateQuadPart(faceDetectorMargin, 2, inputValue($event))" />
              </label>
              <label>
                <span>左</span>
                <input :value="quadPart(faceDetectorMargin, 3)" type="number" min="0" max="100" step="1" @input="faceDetectorMargin = updateQuadPart(faceDetectorMargin, 3, inputValue($event))" />
              </label>
            </div>
          </FieldRow>

          <FieldRow label="特征点模型" description="FaceFusion face-landmarker-model">
            <select v-model="faceLandmarkerModel" class="settings-input">
              <option value="many">many</option>
              <option value="2dfan4">2dfan4</option>
              <option value="peppa_wutz">peppa_wutz</option>
            </select>
          </FieldRow>

          <FieldRow label="特征点分数" description="0-1">
            <div class="range-control">
              <input v-model.number="faceLandmarkerScore" type="range" min="0" max="1" step="0.05" />
              <span>{{ Number(faceLandmarkerScore).toFixed(2) }}</span>
            </div>
          </FieldRow>

          <FieldRow label="人脸选择模式" description="默认 reference，适合指定参考帧和参考人脸位置">
            <select v-model="faceSelectorMode" class="settings-input">
              <option value="reference">Reference</option>
              <option value="one">One</option>
              <option value="many">Many</option>
            </select>
          </FieldRow>

          <FieldRow label="人脸排序" description="检测到多张脸时的选择顺序">
            <select v-model="faceSelectorOrder" class="settings-input">
              <option value="large-small">large-small</option>
              <option value="small-large">small-large</option>
              <option value="left-right">left-right</option>
              <option value="right-left">right-left</option>
              <option value="top-bottom">top-bottom</option>
              <option value="bottom-top">bottom-top</option>
              <option value="best-worst">best-worst</option>
              <option value="worst-best">worst-best</option>
            </select>
          </FieldRow>

          <FieldRow label="性别筛选" description="FaceFusion face-selector-gender">
            <div class="choice-chips">
              <button
                v-for="gender in genderOptions"
                :key="gender || 'any'"
                type="button"
                :class="{ 'is-active': faceSelectorGender === gender }"
                @click="faceSelectorGender = gender"
              >
                {{ gender || '不限' }}
              </button>
            </div>
          </FieldRow>

          <FieldRow label="年龄筛选" description="FaceFusion face-selector-age-start / end">
            <div class="paired-control">
              <input v-model="faceSelectorAgeStart" type="number" min="0" max="100" step="1" placeholder="0" class="settings-input" />
              <span>-</span>
              <input v-model="faceSelectorAgeEnd" type="number" min="0" max="100" step="1" placeholder="100" class="settings-input" />
            </div>
          </FieldRow>

          <FieldRow label="种族筛选" description="FaceFusion face-selector-race">
            <div class="choice-chips">
              <button
                v-for="race in raceOptions"
                :key="race || 'any'"
                type="button"
                :class="{ 'is-active': faceSelectorRace === race }"
                @click="faceSelectorRace = race"
              >
                {{ race || '不限' }}
              </button>
            </div>
          </FieldRow>

          <FieldRow label="参考帧" description="目标视频里用于创建参考人脸的帧号">
            <input v-model.number="referenceFrameNumber" type="number" min="0" class="settings-input" />
          </FieldRow>

          <FieldRow label="人脸位置" description="参考帧中使用第几个检测到的人脸">
            <input v-model.number="referenceFacePosition" type="number" min="0" class="settings-input" />
          </FieldRow>

          <FieldRow label="匹配距离" description="reference 模式下的人脸匹配距离">
            <div class="range-control">
              <input v-model.number="referenceFaceDistance" type="range" min="0" max="1" step="0.05" />
              <span>{{ Number(referenceFaceDistance).toFixed(2) }}</span>
            </div>
          </FieldRow>

          <FieldRow v-if="faceSelectorMode === 'reference'" label="追踪匹配阈值" description="0.00 关闭跨帧人脸追踪">
            <div class="range-control">
              <input v-model.number="faceTrackerScore" type="range" min="0" max="0.5" step="0.05" />
              <span>{{ Number(faceTrackerScore).toFixed(2) }}</span>
            </div>
          </FieldRow>
        </div>
      </div>

      <div v-if="activeSection === 'masking'" class="facefusion-section">
        <h2 class="settings-card__title">遮罩</h2>

        <div class="settings-form mt-4">
          <FieldRow label="遮罩类型" description="多个类型可用空格或逗号分隔">
            <div class="choice-chips">
              <button
                v-for="type in maskTypeOptions"
                :key="type"
                type="button"
                :class="{ 'is-active': hasToken(faceMaskTypes, type) }"
                @click="faceMaskTypes = toggleToken(faceMaskTypes, type)"
              >
                {{ type }}
              </button>
            </div>
          </FieldRow>

          <FieldRow label="遮罩模糊" description="0-1">
            <div class="range-control">
              <input v-model.number="faceMaskBlur" type="range" min="0" max="1" step="0.05" />
              <span>{{ Number(faceMaskBlur).toFixed(2) }}</span>
            </div>
          </FieldRow>

          <FieldRow label="遮罩内边距" description="上 右 下 左">
            <div class="quad-control">
              <label>
                <span>上</span>
                <input :value="quadPart(faceMaskPadding, 0)" type="number" min="0" max="100" step="1" @input="faceMaskPadding = updateQuadPart(faceMaskPadding, 0, inputValue($event))" />
              </label>
              <label>
                <span>右</span>
                <input :value="quadPart(faceMaskPadding, 1)" type="number" min="0" max="100" step="1" @input="faceMaskPadding = updateQuadPart(faceMaskPadding, 1, inputValue($event))" />
              </label>
              <label>
                <span>下</span>
                <input :value="quadPart(faceMaskPadding, 2)" type="number" min="0" max="100" step="1" @input="faceMaskPadding = updateQuadPart(faceMaskPadding, 2, inputValue($event))" />
              </label>
              <label>
                <span>左</span>
                <input :value="quadPart(faceMaskPadding, 3)" type="number" min="0" max="100" step="1" @input="faceMaskPadding = updateQuadPart(faceMaskPadding, 3, inputValue($event))" />
              </label>
            </div>
          </FieldRow>

          <FieldRow label="遮罩区域" description="选择 face-mask-areas，仅在 area 类型有效">
            <div class="choice-chips">
              <button
                v-for="area in maskAreaOptions"
                :key="area"
                type="button"
                :class="{ 'is-active': hasToken(faceMaskAreas, area) }"
                @click="faceMaskAreas = toggleToken(faceMaskAreas, area)"
              >
                {{ area }}
              </button>
            </div>
          </FieldRow>

          <FieldRow label="遮罩部位" description="选择 face-mask-regions，仅在 region 类型有效">
            <div class="choice-chips">
              <button
                v-for="region in maskRegionOptions"
                :key="region"
                type="button"
                :class="{ 'is-active': hasToken(faceMaskRegions, region) }"
                @click="faceMaskRegions = toggleToken(faceMaskRegions, region)"
              >
                {{ region }}
              </button>
            </div>
          </FieldRow>

          <FieldRow label="遮挡模型" description="FaceFusion face-occluder-model">
            <select v-model="faceOccluderModel" class="settings-input">
              <option value="many">many</option>
              <option value="xseg_1">xseg_1</option>
              <option value="xseg_2">xseg_2</option>
              <option value="xseg_3">xseg_3</option>
            </select>
          </FieldRow>

          <FieldRow label="区域解析模型" description="FaceFusion face-parser-model">
            <select v-model="faceParserModel" class="settings-input">
              <option value="bisenet_resnet_18">bisenet_resnet_18</option>
              <option value="bisenet_resnet_34">bisenet_resnet_34</option>
            </select>
          </FieldRow>
        </div>
      </div>

      <div v-if="activeSection === 'output'" class="facefusion-section">
        <h2 class="settings-card__title">输出</h2>

        <div class="settings-form mt-4">

          <FieldRow label="视频编码" description="输出视频编码器">
            <select v-model="outputVideoEncoder" class="settings-input">
              <option value="libx264">libx264</option>
              <option value="libx265">libx265</option>
              <option value="h264_nvenc">h264_nvenc</option>
              <option value="hevc_nvenc">hevc_nvenc</option>
            </select>
          </FieldRow>

          <FieldRow label="编码预设" description="输出视频编码速度和压缩预设">
            <select v-model="outputVideoPreset" class="settings-input">
              <option value="ultrafast">ultrafast</option>
              <option value="veryfast">veryfast</option>
              <option value="fast">fast</option>
              <option value="medium">medium</option>
              <option value="slow">slow</option>
            </select>
          </FieldRow>

          <FieldRow label="视频质量" description="0-100">
            <div class="range-control">
              <input v-model.number="outputVideoQuality" type="range" min="0" max="100" step="1" />
              <span>{{ outputVideoQuality }}</span>
            </div>
          </FieldRow>

          <FieldRow label="视频缩放" description="FaceFusion output-video-scale">
            <select v-model="outputVideoScale" class="settings-input">
              <option v-for="scale in scaleOptions" :key="scale" :value="scale">{{ scale }}x</option>
            </select>
          </FieldRow>

          <FieldRow label="视频帧率" description="留空则沿用源视频">
            <input v-model="outputVideoFps" type="number" min="1" max="240" step="1" placeholder="源视频" class="settings-input" />
          </FieldRow>

          <FieldRow label="音频编码" description="输出音频编码器">
            <select v-model="outputAudioEncoder" class="settings-input">
              <option value="aac">aac</option>
              <option value="flac">flac</option>
              <option value="libmp3lame">libmp3lame</option>
              <option value="libopus">libopus</option>
              <option value="libvorbis">libvorbis</option>
              <option value="pcm_s16le">pcm_s16le</option>
              <option value="pcm_s32le">pcm_s32le</option>
            </select>
          </FieldRow>

          <FieldRow label="音频质量" description="0-100">
            <div class="range-control">
              <input v-model.number="outputAudioQuality" type="range" min="0" max="100" step="1" />
              <span>{{ outputAudioQuality }}</span>
            </div>
          </FieldRow>

          <FieldRow label="音频音量" description="0-100">
            <div class="range-control">
              <input v-model.number="outputAudioVolume" type="range" min="0" max="100" step="1" />
              <span>{{ outputAudioVolume }}</span>
            </div>
          </FieldRow>

          <FieldRow label="图片质量" description="0-100">
            <div class="range-control">
              <input v-model.number="outputImageQuality" type="range" min="0" max="100" step="1" />
              <span>{{ outputImageQuality }}</span>
            </div>
          </FieldRow>

          <FieldRow label="图片缩放" description="FaceFusion output-image-scale">
            <select v-model="outputImageScale" class="settings-input">
              <option v-for="scale in scaleOptions" :key="scale" :value="scale">{{ scale }}x</option>
            </select>
          </FieldRow>

          <FieldRow label="临时帧格式" description="FaceFusion temp-frame-format">
            <select v-model="tempFrameFormat" class="settings-input">
              <option value="png">png</option>
              <option value="jpeg">jpeg</option>
              <option value="bmp">bmp</option>
              <option value="tiff">tiff</option>
            </select>
          </FieldRow>
        </div>
      </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.settings-card__title {
  font-family: var(--font-display);
  font-size: 0.875rem;
  font-weight: 700;
  color: rgba(255, 255, 255, 0.7);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 0.5rem;
}

.settings-card__desc {
  font-family: var(--font-display);
  font-size: 0.75rem;
  color: rgba(255, 255, 255, 0.3);
  margin-bottom: 0;
}

.settings-actions {
  display: flex;
  align-items: center;
  justify-content: flex-start;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.settings-primary-btn {
  min-width: 5.5rem;
}

.facefusion-shell {
  padding: 1.25rem;
}

.facefusion-card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  flex-wrap: wrap;
  margin-bottom: 1rem;
}

.facefusion-head-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 0.625rem;
  flex-wrap: wrap;
}

.facefusion-upgrade-hint {
  margin: 0.5rem 0 0;
  color: var(--color-text-tertiary);
  font-size: 0.75rem;
  line-height: 1.5;
}

.facefusion-version-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(9.5rem, 1fr));
  gap: 0.5rem;
  width: 100%;
}

.facefusion-upstream-grid {
  display: grid;
  grid-template-columns: minmax(8rem, 0.8fr) minmax(12rem, 1.2fr);
  gap: 0.5rem;
  width: 100%;
}

.facefusion-version-item {
  min-width: 0;
  padding: 0.625rem 0.75rem;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: var(--radius-md);
  background: rgba(255, 255, 255, 0.035);
}

.facefusion-version-item span {
  display: block;
  margin-bottom: 0.25rem;
  color: var(--color-text-tertiary);
  font-size: 0.6875rem;
  font-weight: 700;
}

.facefusion-version-item strong {
  display: block;
  overflow: hidden;
  color: var(--color-text-primary);
  font-family: var(--font-mono);
  font-size: 0.8125rem;
  font-weight: 700;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.facefusion-model-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(7.5rem, 1fr));
  gap: 0.5rem;
  width: 100%;
}

.facefusion-model-status {
  display: grid;
  gap: 0.5rem;
  width: 100%;
}

.facefusion-model-status__line {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  color: var(--color-text-secondary);
  font-size: 0.8125rem;
  font-weight: 700;
}

.facefusion-model-status__line strong {
  color: var(--color-text-primary);
  font-family: var(--font-mono);
}

.facefusion-model-status p {
  margin: 0;
  color: var(--color-text-tertiary);
  font-size: 0.75rem;
  line-height: 1.5;
}

.facefusion-model-progress {
  overflow: hidden;
  width: 100%;
  height: 0.5rem;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.07);
}

.facefusion-model-progress i {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, rgba(0, 117, 255, 0.95), rgba(70, 190, 255, 0.95));
  transition: width 0.2s ease;
}

.facefusion-model-issues {
  display: grid;
  gap: 0.5rem;
  width: 100%;
  max-height: 16rem;
  overflow: auto;
  padding: 0.625rem;
  border: 1px solid rgba(255, 120, 120, 0.18);
  border-radius: var(--radius-lg);
  background: rgba(255, 80, 80, 0.055);
}

.facefusion-model-issues div {
  display: grid;
  grid-template-columns: minmax(8rem, 0.65fr) minmax(0, 1fr);
  gap: 0.75rem;
  min-width: 0;
  color: var(--color-text-secondary);
  font-family: var(--font-mono);
  font-size: 0.75rem;
}

.facefusion-model-issues strong,
.facefusion-model-issues span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.facefusion-model-issues strong {
  color: #ffb4b4;
}

.facefusion-model-output {
  width: 100%;
  max-height: 18rem;
  overflow: auto;
  margin: 0;
  padding: 0.75rem;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: var(--radius-lg);
  background: rgba(0, 0, 0, 0.22);
  color: var(--color-text-secondary);
  font-family: var(--font-mono);
  font-size: 0.75rem;
  line-height: 1.55;
  white-space: pre-wrap;
}

.choice-chips--readonly button {
  cursor: default;
  opacity: 1;
}

.facefusion-empty-state {
  color: var(--color-text-tertiary);
  font-size: 0.8125rem;
}

.facefusion-tabbar {
  display: flex;
  align-items: center;
  margin-bottom: 1.125rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.facefusion-tabs {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  padding: 0.25rem 0.25rem 0 0;
  max-width: 100%;
  overflow-x: auto;
  scrollbar-width: none;
  -ms-overflow-style: none;
}

.facefusion-tabs::-webkit-scrollbar {
  display: none;
}

.facefusion-tabs button {
  position: relative;
  height: 2.25rem;
  padding: 0 0.75rem;
  border: 0;
  border-radius: var(--radius-md) var(--radius-md) 0 0;
  background: transparent;
  color: var(--color-text-tertiary);
  font-size: 0.78125rem;
  font-weight: 700;
  letter-spacing: 0.02em;
  white-space: nowrap;
  cursor: pointer;
  transition: color 0.15s ease;
}

.facefusion-tabs button::after {
  content: '';
  position: absolute;
  left: 0.625rem;
  right: 0.625rem;
  bottom: -1px;
  height: 2px;
  border-radius: 999px;
  background: transparent;
  transition: background 0.15s ease;
}

.facefusion-tabs button:hover {
  background: rgba(255, 255, 255, 0.035);
  color: var(--color-text-secondary);
}

.facefusion-tabs button.is-active {
  background: rgba(255, 255, 255, 0.055);
  color: #fff;
  box-shadow: none;
}

.facefusion-tabs button.is-active::after {
  background: var(--color-brand);
}

.facefusion-section {
  padding: 0;
}

.choice-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  width: 100%;
}

.choice-chips button {
  height: 2rem;
  padding: 0 0.875rem;
  border: 1px solid var(--color-border-default);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.045);
  color: var(--color-text-secondary);
  font-size: 0.8125rem;
  font-weight: 650;
  line-height: 1;
  cursor: pointer;
  transition: border-color 0.15s ease, background 0.15s ease, color 0.15s ease;
}

.choice-chips button:hover {
  border-color: rgba(255, 255, 255, 0.22);
  color: var(--color-text-primary);
}

.choice-chips button.is-active {
  border-color: rgba(0, 117, 255, 0.72);
  background: rgba(0, 117, 255, 0.18);
  color: #fff;
}

.choice-chips .processor-chip {
  align-items: flex-start;
  display: inline-flex;
  flex-direction: column;
  gap: 0.2rem;
  height: auto;
  min-height: 3.25rem;
  min-width: 7.75rem;
  padding: 0.45rem 0.75rem;
  text-align: left;
}

.choice-chips .processor-chip span {
  color: inherit;
  font-size: 0.8rem;
  font-weight: 760;
  line-height: 1.15;
}

.choice-chips .processor-chip small {
  color: var(--color-text-tertiary);
  font-family: var(--font-mono);
  font-size: 0.64rem;
  line-height: 1;
}

.choice-chips .processor-chip em {
  align-self: flex-start;
  padding: 0.08rem 0.3rem;
  border: 1px solid rgba(0, 117, 255, 0.4);
  border-radius: 999px;
  background: rgba(0, 117, 255, 0.14);
  color: #8fc2ff;
  font-size: 0.57rem;
  font-style: normal;
  font-weight: 850;
  letter-spacing: 0.04em;
  line-height: 1.15;
}

.choice-chips .processor-chip em.is-muted {
  border-color: rgba(255, 255, 255, 0.1);
  background: rgba(255, 255, 255, 0.045);
  color: var(--color-text-tertiary);
}

.choice-chips .processor-chip em.is-cuda {
  border-color: rgba(80, 220, 140, 0.28);
  background: rgba(80, 220, 140, 0.1);
  color: #8be0a9;
}

.facefusion-switch {
  display: inline-flex;
  align-items: center;
  gap: 0.65rem;
  min-height: 2.25rem;
  cursor: pointer;
}

.facefusion-switch input {
  position: absolute;
  opacity: 0;
  pointer-events: none;
}

.facefusion-switch span {
  position: relative;
  width: 2.6rem;
  height: 1.4rem;
  border-radius: 999px;
  border: 1px solid rgba(255, 255, 255, 0.14);
  background: rgba(255, 255, 255, 0.06);
  transition: border-color 0.16s ease, background 0.16s ease;
}

.facefusion-switch span::after {
  content: '';
  position: absolute;
  top: 0.18rem;
  left: 0.18rem;
  width: 0.94rem;
  height: 0.94rem;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.72);
  transition: transform 0.16s ease, background 0.16s ease;
}

.facefusion-switch input:checked + span {
  border-color: rgba(0, 117, 255, 0.58);
  background: rgba(0, 117, 255, 0.24);
}

.facefusion-switch input:checked + span::after {
  transform: translateX(1.18rem);
  background: #fff;
}

.facefusion-switch strong {
  color: var(--color-text-secondary);
  font-size: 0.82rem;
  font-weight: 750;
}

.processor-options {
  display: grid;
  gap: 0.75rem;
  padding: 0.875rem;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: var(--radius-lg);
  background: rgba(255, 255, 255, 0.025);
}

.processor-options__head {
  color: var(--color-text-tertiary);
  font-family: var(--font-mono);
  font-size: 0.75rem;
  font-weight: 800;
  letter-spacing: 0.04em;
}

.range-control {
  display: grid;
  grid-template-columns: minmax(10rem, 1fr) 3.25rem;
  align-items: center;
  gap: 0.75rem;
  width: 100%;
}

.range-control input[type='range'] {
  width: 100%;
  accent-color: var(--color-brand);
}

.range-control span {
  min-width: 3.25rem;
  height: 2rem;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid var(--color-border-default);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.045);
  color: var(--color-text-primary);
  font-size: 0.8125rem;
  font-weight: 700;
}

.quad-control {
  display: grid;
  grid-template-columns: repeat(4, minmax(4.75rem, 1fr));
  gap: 0.5rem;
  width: 100%;
}

.quad-control label {
  display: flex;
  align-items: center;
  gap: 0.375rem;
  height: 2.25rem;
  padding: 0 0.5rem;
  border: 1px solid var(--color-border-default);
  border-radius: var(--radius-lg);
  background: rgba(255, 255, 255, 0.045);
}

.quad-control span {
  color: var(--color-text-tertiary);
  font-size: 0.75rem;
  font-weight: 700;
  white-space: nowrap;
}

.quad-control input {
  width: 100%;
  min-width: 0;
  border: 0;
  outline: 0;
  background: transparent;
  color: var(--color-text-primary);
  font-size: 0.8125rem;
}

.paired-control {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr);
  align-items: center;
  gap: 0.5rem;
  width: 100%;
}

.paired-control span {
  color: var(--color-text-tertiary);
  font-weight: 700;
}

@media (max-width: 768px) {
  .facefusion-shell {
    padding: 1rem;
  }

  .facefusion-card-head {
    align-items: stretch;
  }

  .facefusion-tabbar {
    align-items: center;
    margin-bottom: 1rem;
  }

  .facefusion-tabs {
    width: 100%;
  }

  .range-control {
    grid-template-columns: minmax(0, 1fr) 3rem;
  }

  .quad-control {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
