<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import api from '../../api'
import { useToast } from '../../composables/useToast'
import { useConfirm } from '../../composables/useConfirm'
import { useI18n } from '../../composables/useI18n'
import { dictionaries } from '../../i18n'
import VuiButton from '../../components/ui/Button/VuiButton.vue'
import VuiBadge from '../../components/ui/Badge/VuiBadge.vue'
import VuiProgress from '../../components/ui/Progress/VuiProgress.vue'
import FieldRow from '../../components/ui/FieldRow/FieldRow.vue'
import SettingsSwitch from '../../components/ui/SettingsSwitch.vue'
import { WHISPER_MODEL_BACKENDS, WHISPER_RUNTIME_TIERS, buildWhisperProfileWithTranslation, formatWhisperTranslationSummary, getWhisperModelBackendMeta, getWhisperRuntimeTierMeta, getWhisperSelectableStrategyPresentation, isDirectWhisperTranslationBackend, resolveWhisperEditableDefaults, type WhisperModelBackend, type WhisperRuntimeTier } from '../../composables/useWhisperProfiles'

const toast = useToast()
const { confirm } = useConfirm()
const { t } = useI18n()

const loading = ref(false)
const saving = ref(false)
const checkingDeps = ref(false)
const checkingModels = ref(false)
const downloadingModel = ref<string | null>(null)
const installingDeps = computed(() => installStatus.value.status === 'running')
const modelDownloadStatus = ref<{ status: string; progress: number; message: string }>({ status: 'idle', progress: 0, message: '' })
const activeRuntimeTier = ref<WhisperRuntimeTier>('gpu_standard')
const activeModelBackend = ref<WhisperModelBackend>('chickenrice-zh')
const vadBackend = ref('energy')
const timingRefiner = ref('none')

// ===== Translation settings =====
const translateEnabled = ref(true)
const translateTo = ref('zh')
const translateModel = ref('gpt-4o-mini')
const translateStyle = ref('adult_explicit')
const translateBaseUrl = ref('https://api.openai.com/v1')
const translateApiKey = ref('')
const testingConnection = ref(false)
const connectionResult = ref<{ available: boolean; message: string; models?: string[] } | null>(null)

const checkingDepsResult = ref<Record<string, any>>({})
const whisperCudaAvailable = ref(false)
const torchVariant = ref<'gpu' | 'cpu'>('gpu')
const whisperModels = ref<any[]>([])
const whisperFeatures = ref<any>({})
const depsExpanded = ref(false)
const modelsExpanded = ref(false)

// 只显示不便 Docker build 的运行时依赖（installable: true）
const runtimeInstallableDeps = computed(() =>
  Object.fromEntries(
    Object.entries(checkingDepsResult.value).filter(([, v]) => (v as any).installable)
  )
)
const runtimeDisplayedDeps = computed(() =>
  Object.fromEntries(
    Object.entries(checkingDepsResult.value).filter(([name]) => !String(name).startsWith('_'))
  )
)

// 是否有缺失的运行时依赖（控制安装按钮显示）
const hasMissingRuntimeDeps = computed(() => {
  return Object.entries(runtimeInstallableDeps.value).some(([name, v]: [string, any]) => {
    if (!v.installed) return true
    if (v.in_noor_env === false) return true
    if (name === 'onnxruntime' && torchVariant.value === 'gpu' && checkingDepsResult.value.torch?.cuda && !v.cuda) return true
    return false
  })
})
const installStatus = ref<{ status: string; progress: number; message: string; current_package?: string }>({
  status: 'idle',
  progress: 0,
  message: '',
})

function dependencyDisplayName(name: string) {
  if (name === 'torch') return `torch (${torchVariant.value.toUpperCase()})`
  if (name === 'onnxruntime' && torchVariant.value === 'gpu') return 'onnxruntime-gpu'
  return String(name)
}

function dependencySourceLabel(info: any) {
  if (!info?.installed) return ''
  if (info.in_noor_env === false) {
    if (info.source === 'user_site') return t('settings.whisper.depSourceUser')
    if (info.source === 'system_site') return t('settings.whisper.depSourceSystem')
    return t('settings.whisper.depSourceExternal')
  }
  return t('settings.whisper.depSourceNoor')
}

function dependencyStatusColor(name: string, info: any) {
  if (!info?.installed) return 'error'
  if (info.in_noor_env === false) return 'warning'
  if (name === 'onnxruntime' && torchVariant.value === 'gpu' && checkingDepsResult.value.torch?.cuda && !info.cuda) return 'warning'
  return 'success'
}

function dependencyStatusText(name: string, info: any) {
  if (!info?.installed) return t('settings.whisper.notInstalled')
  if (info.in_noor_env === false) return dependencySourceLabel(info)
  if (name === 'onnxruntime' && torchVariant.value === 'gpu' && checkingDepsResult.value.torch?.cuda && !info.cuda) {
    return t('settings.whisper.onnxNoCuda')
  }
  return info.version || t('settings.whisper.installed')
}

function dependencyDetail(info: any) {
  const parts: string[] = []
  if (info?.installed && info?.in_noor_env !== false) parts.push(dependencySourceLabel(info))
  if (Array.isArray(info?.providers) && info.providers.length) parts.push(`Provider: ${info.providers.join(' / ')}`)
  if (info?.path) parts.push(info.path)
  return parts.join(' · ')
}

onMounted(async () => {
  await loadSettings()
  await Promise.all([checkWhisperDeps(), loadWhisperModels()])
})

async function loadSettings() {
  loading.value = true
  try {
    const resp = await api.get('/settings')
    if (resp.data.whisper) {
      const w = resp.data.whisper
      const defaults = resolveWhisperEditableDefaults(w)
      whisperFeatures.value = w.features || {}
      activeRuntimeTier.value = defaults.runtime_tier
      activeModelBackend.value = defaults.model_backend
      vadBackend.value = defaults.vad_backend
      timingRefiner.value = defaults.timing_refiner
      translateEnabled.value = defaults.translate_enabled
      translateTo.value = defaults.translate_to
      translateModel.value = defaults.translate_model
      translateStyle.value = defaults.translate_style
      translateBaseUrl.value = defaults.translate_base_url
      translateApiKey.value = defaults.translate_api_key
    }
  } catch (e) {
    console.error('Failed to load whisper settings:', e)
  } finally {
    loading.value = false
  }
}

async function checkWhisperDeps() {
  checkingDeps.value = true
  try {
    const resp = await api.post('/settings/whisper/check')
    checkingDepsResult.value = resp.data.dependencies
    whisperFeatures.value = resp.data.features || whisperFeatures.value
    whisperCudaAvailable.value = resp.data.cuda_available
    torchVariant.value = resp.data.cuda_available ? 'gpu' : 'cpu'
    const statusResp = await api.get('/settings/whisper/install-status')
    installStatus.value = statusResp.data
  } catch (e: any) {
    toast.error(t('settings.whisper.checkFailed'))
  } finally {
    checkingDeps.value = false
  }
}

async function loadWhisperModels() {
  checkingModels.value = true
  try {
    const resp = await api.get('/settings/whisper/models')
    whisperModels.value = resp.data.models
    // 更新下载状态（如果有正在进行的下载）
    if (resp.data.downloadStatus && resp.data.downloadStatus.status === 'running') {
      modelDownloadStatus.value = resp.data.downloadStatus
      // 恢复 downloadingModel 状态
      if (resp.data.downloadStatus.model) {
        downloadingModel.value = resp.data.downloadStatus.model
      }
    } else if (resp.data.downloadStatus && resp.data.downloadStatus.status === 'idle') {
      // 下载完成或空闲时，清除状态
      downloadingModel.value = null
    }
  } catch (e: any) {
    console.error('Failed to load models:', e)
  } finally {
    checkingModels.value = false
  }
}

function buildWhisperSettingsPayload() {
  return buildWhisperProfileWithTranslation(activeModelBackend.value, {
    runtime_tier: activeRuntimeTier.value,
    vad_backend: vadBackend.value,
    timing_refiner: timingRefiner.value,
    translate_enabled: translateEnabled.value,
    translate_to: translateTo.value,
    translate_model: translateModel.value,
    translate_style: translateStyle.value,
    translate_base_url: translateBaseUrl.value,
    translate_api_key: translateApiKey.value,
  })
}

async function saveWhisper() {
  saving.value = true
  try {
    await api.put('/settings/whisper', buildWhisperSettingsPayload())
    toast.success(t('settings.whisper.whisperSettingsSaved'))
  } catch (e: any) {
    toast.error(t('settings.whisper.saveFailed'))
  } finally {
    saving.value = false
  }
}

async function testTranslateConnection() {
  testingConnection.value = true
  connectionResult.value = null
  try {
    const resp = await api.post('/whisper/translate/test', null, {
      params: {
        base_url: translateBaseUrl.value,
        api_key: translateApiKey.value || undefined,
        model: translateModel.value,
      },
    })
    connectionResult.value = resp.data
    if (resp.data.available) {
      toast.success(resp.data.message)
    } else {
      toast.error(resp.data.message)
    }
  } catch (e: any) {
    connectionResult.value = { available: false, message: t('settings.emby.connectFailed', { error: t('common.error') }) }
    toast.error(t('settings.whisper.testFailed'))
  } finally {
    testingConnection.value = false
  }
}

async function installDeps() {
  const parts = Object.entries(runtimeInstallableDeps.value)
    .filter(([, info]: [string, any]) => !info?.installed)
    .map(([name]) => name === 'torch' ? `torch ${torchVariant.value.toUpperCase()}` : name)
  const torchIsInstalled = !!checkingDepsResult.value.torch?.installed
  const variantChanged = torchIsInstalled && (torchVariant.value === 'gpu') !== !!checkingDepsResult.value.torch?.cuda


  if (variantChanged && !parts.some(item => item.startsWith('torch'))) {
    parts.push(`torch ${torchVariant.value.toUpperCase()}`)
  }
  const msg = parts.length === 0
    ? t('settings.whisper.installDepsReady')
    : t('settings.whisper.installDepsPlan', { packages: parts.join(' + ') })
  if (!await confirm({ message: msg, danger: false })) return

  installStatus.value = { status: 'running', progress: 0, message: t('settings.whisper.installing') }
  try {
    await api.post('/settings/whisper/install-deps', {
      torch_variant: torchVariant.value,
      torch_current_cuda: !!checkingDepsResult.value.torch?.cuda,
    })
    for (let i = 0; i < 600; i++) {
      await new Promise(r => setTimeout(r, 1000))
      const statusResp = await api.get('/settings/whisper/install-status')
      const status = statusResp.data
      installStatus.value = status
      if (status.status === 'completed') {
        toast.success(t('settings.whisper.installSuccess'))
        await checkWhisperDeps()
        break
      } else if (status.status === 'failed') {
        toast.error(status.message || t('settings.whisper.installFailed'))
        break
      }
    }
  } catch (e: any) {
    toast.error(e.response?.data?.detail || t('settings.whisper.installFailed'))
  }
}

async function downloadModel(modelId: string) {
  if (!await confirm({ message: t('settings.whisper.downloadModelConfirm', { modelId }) })) return

  downloadingModel.value = modelId
  modelDownloadStatus.value = { status: 'running', progress: 0, message: t('settings.whisper.downloading') }
  try {
    await api.post('/settings/whisper/models/download', { model: modelId })
    for (let i = 0; i < 600; i++) {
      await new Promise(r => setTimeout(r, 1000))
      const statusResp = await api.get('/settings/whisper/models/download-status')
      const status = statusResp.data
      modelDownloadStatus.value = status
      if (status.status === 'completed') {
        toast.success(status.message || t('settings.whisper.downloadSuccess'))
        await loadWhisperModels()
        await checkWhisperDeps()
        break
      } else if (status.status === 'failed') {
        toast.error(status.message || t('settings.whisper.downloadFailed'))
        break
      }
    }
  } catch (e: any) {
    toast.error(e.response?.data?.detail || t('settings.whisper.downloadFailed'))
  } finally {
    downloadingModel.value = null
  }
}

async function deleteModel(modelId: string) {
  if (!await confirm({ message: t('settings.whisper.deleteModelConfirm', { modelId }), danger: true })) return
  try {
    await api.delete(`/settings/whisper/models/${modelId}`)
    toast.success(t('settings.whisper.deleted'))
    await loadWhisperModels()
    await checkWhisperDeps()
  } catch (e: any) {
    toast.error(e.response?.data?.detail || t('settings.whisper.deleteFailed'))
  }
}

// ===== Option lists =====


// Translation target language options — derived from available i18n dictionaries
const translateLangOptions = computed(() => {
  return Object.keys(dictionaries).map(lang => ({
    value: lang,
    label: t(`settings.whisper.translateLang.${lang}`) || lang.toUpperCase(),
  }))
})

// Translation style options
const translateStyleOptions = computed(() => [
  { value: 'adult_explicit', label: t('settings.whisper.translateStyle.adultExplicit') },
  { value: 'standard', label: t('settings.whisper.translateStyle.standard') },
])

const vadBackendOptions = computed(() => [
  { value: 'energy', label: t('settings.whisper.vadBackend.energy') },
  { value: 'whisper_vad_onnx', label: t('settings.whisper.vadBackend.whisperVadOnnx') },
])

const timingRefinerOptions = computed(() => [
  { value: 'none', label: t('settings.whisper.timingRefiner.none') },
  { value: 'subtimer_vad', label: t('settings.whisper.timingRefiner.subtimerVad') },
])

const activeTranslateSummary = computed(() => {
  return formatWhisperTranslationSummary(t, {
    translateEnabled: translateEnabled.value,
    translateTo: translateTo.value,
    translateModel: translateModel.value,
    directTranslate: isDirectWhisperTranslationBackend(activeModelBackend.value),
  })
})
const modelBackendOptions = computed(() => WHISPER_MODEL_BACKENDS.map((backend) => ({
  backend,
  meta: getWhisperModelBackendMeta(backend),
  presentation: getWhisperSelectableStrategyPresentation(t, backend),
})))
const runtimeTierOptions = computed(() => WHISPER_RUNTIME_TIERS.map((tier) => ({
  tier,
  meta: getWhisperRuntimeTierMeta(tier),
})))
const activeModelDirectTranslate = computed(() => isDirectWhisperTranslationBackend(activeModelBackend.value))
</script>
<template>
  <div class="flex flex-col gap-6">
    <div v-if="loading" class="flex items-center justify-center py-16">
      <div class="w-8 h-8 border-2 rounded-full animate-spin border-[#0075FF] border-t-transparent"></div>
    </div>

    <template v-if="!loading">
      <!-- 1. Default Settings -->
      <div class="settings-card ui-card settings-card--compact">
        <h2 class="settings-card__title">{{ t('settings.whisper.currentProfileTitle') }}</h2>
        <p class="settings-card__desc settings-card__desc--compact">{{ t('settings.whisper.currentProfileDesc') }}</p>

        <div class="whisper-section-label">{{ t('settings.whisper.runtimeTierTitle') }}</div>
        <div class="settings-form mt-2.5 space-y-1.5">
          <button
            v-for="option in runtimeTierOptions"
            :key="option.tier"
            type="button"
            class="whisper-strategy-card whisper-strategy-card--summary"
            :class="{ 'whisper-strategy-card--active': activeRuntimeTier === option.tier }"
            @click="activeRuntimeTier = option.tier"
          >
            <div class="whisper-strategy-card__head">
              <div class="whisper-strategy-card__title">{{ t(option.meta.titleKey) }}</div>
              <VuiBadge color="info" variant="gradient" size="sm">{{ t(option.meta.badgeKey) }}</VuiBadge>
            </div>
            <p class="whisper-strategy-card__summary">{{ t(option.meta.descKey) }}</p>
          </button>
        </div>

        <div class="whisper-section-label whisper-section-label--spaced">{{ t('settings.whisper.modelBackendTitle') }}</div>
        <div class="settings-form mt-2.5 space-y-1.5">
          <button
            v-for="option in modelBackendOptions"
            :key="option.backend"
            type="button"
            class="whisper-strategy-card whisper-strategy-card--primary whisper-strategy-card--summary"
            :class="{ 'whisper-strategy-card--active': activeModelBackend === option.backend }"
            @click="activeModelBackend = option.backend"
          >
            <div class="whisper-strategy-card__head">
              <div>
                <div class="whisper-strategy-card__title">{{ t(option.meta.titleKey) }}</div>
              </div>
              <VuiBadge :color="option.presentation.badgeColor" variant="gradient" size="sm">{{ t(option.meta.badgeKey) }}</VuiBadge>
            </div>
            <p class="whisper-strategy-card__summary">{{ t(option.meta.stackKey) }}</p>
            <div class="whisper-strategy-card__meta">
              <span v-if="activeModelBackend === option.backend" class="whisper-strategy-card__chip">{{ activeTranslateSummary }}</span>
              <span v-else class="whisper-strategy-card__chip">{{ t(option.meta.descKey) }}</span>
            </div>
          </button>
        </div>
      </div>

      <div class="settings-card ui-card settings-card--compact">
        <h2 class="settings-card__title">{{ t('settings.whisper.vadSettingsTitle') }}</h2>
        <p class="settings-card__desc">{{ t('settings.whisper.vadSettingsDesc') }}</p>

        <div class="settings-form settings-form--compact mt-2.5">
          <FieldRow customClass="whisper-field-row" :label="t('settings.whisper.vadBackendLabel')" :description="t('settings.whisper.vadBackendDesc')">
            <select v-model="vadBackend" class="settings-input">
              <option v-for="opt in vadBackendOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
            </select>
          </FieldRow>

          <FieldRow customClass="whisper-field-row" :label="t('settings.whisper.timingRefinerLabel')" :description="t('settings.whisper.timingRefinerDesc')">
            <select v-model="timingRefiner" class="settings-input">
              <option v-for="opt in timingRefinerOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
            </select>
          </FieldRow>

          <div class="settings-card__actions settings-card__actions--compact mt-1">
            <VuiButton variant="gradient" color="info" size="small" customClass="settings-primary-btn" :loading="saving" @click="saveWhisper">
              {{ saving ? t('settings.whisper.saving') : t('common.save') }}
            </VuiButton>
          </div>
        </div>
      </div>

      <!-- 2. OpenAI Translation Card -->
      <div class="settings-card ui-card settings-card--compact">
        <h2 class="settings-card__title">{{ t('settings.whisper.translationTitle') }}</h2>
        <p class="settings-card__desc">{{ t('settings.whisper.translationDesc') }}</p>

        <div class="settings-form settings-form--compact mt-2.5">
          <FieldRow customClass="whisper-field-row" :label="t('settings.whisper.translateEnable')" :description="t('settings.whisper.translateEnableDesc')">
            <div class="flex items-center gap-3">
              <SettingsSwitch v-model="translateEnabled" :disabled="activeModelDirectTranslate" />
              <span class="text-sm text-text-secondary">{{ activeModelDirectTranslate ? t('settings.whisper.directTranslateOn') : (translateEnabled ? t('common.enabled') : t('common.disabled')) }}</span>
            </div>
          </FieldRow>

          <FieldRow customClass="whisper-field-row" :label="t('settings.whisper.translateTargetLabel')" :description="t('settings.whisper.translateTargetDesc')">
            <select v-model="translateTo" class="settings-input" :disabled="activeModelDirectTranslate || !translateEnabled">
              <option v-for="opt in translateLangOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
            </select>
          </FieldRow>

          <FieldRow customClass="whisper-field-row" :label="t('settings.whisper.translateModelLabel')" :description="t('settings.whisper.translateModelDesc')">
            <input v-model="translateModel" type="text" class="settings-input" placeholder="gpt-4o-mini" :disabled="activeModelDirectTranslate || !translateEnabled" />
          </FieldRow>

          <FieldRow customClass="whisper-field-row" :label="t('settings.whisper.translateBaseUrlLabel')" :description="t('settings.whisper.translateBaseUrlDesc')">
            <input v-model="translateBaseUrl" type="text" class="settings-input" placeholder="https://api.openai.com/v1" :disabled="activeModelDirectTranslate || !translateEnabled" />
          </FieldRow>

          <FieldRow customClass="whisper-field-row" :label="t('settings.whisper.translateApiKeyLabel')" :description="t('settings.whisper.translateApiKeyDesc')">
            <input v-model="translateApiKey" type="password" class="settings-input" placeholder="sk-..." :disabled="activeModelDirectTranslate || !translateEnabled" />
          </FieldRow>

          <FieldRow customClass="whisper-field-row" :label="t('settings.whisper.translateStyleLabel')" :description="t('settings.whisper.translateStyleDesc')">
            <select v-model="translateStyle" class="settings-input" :disabled="activeModelDirectTranslate || !translateEnabled">
              <option v-for="opt in translateStyleOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
            </select>
          </FieldRow>

          <FieldRow customClass="whisper-field-row" :label="t('settings.emby.connectionTest')" :description="t('settings.whisper.translateConnectionDesc')">
            <div class="flex flex-wrap items-center gap-2">
              <VuiButton variant="contained" color="secondary" size="small" customClass="settings-secondary-btn settings-secondary-btn--compact" :loading="testingConnection" :disabled="activeModelDirectTranslate || !translateEnabled" @click="testTranslateConnection">
                {{ testingConnection ? t('settings.whisper.testing') : t('settings.whisper.testConnection') }}
              </VuiButton>
              <span class="connection-result-badge">
                <VuiBadge
                  v-if="connectionResult"
                  :color="connectionResult.available ? 'success' : 'error'"
                  variant="gradient"
                  size="sm"
                >
                  {{ connectionResult.message }}
                </VuiBadge>
              </span>
            </div>
          </FieldRow>

          <div class="settings-card__actions settings-card__actions--end settings-card__actions--compact mt-1">
            <VuiButton variant="gradient" color="info" size="small" customClass="settings-primary-btn" :loading="saving" @click="saveWhisper">
              {{ saving ? t('settings.whisper.saving') : t('common.save') }}
            </VuiButton>
          </div>
        </div>
      </div>

      <!-- 3. Dependencies Card (collapsible) -->
      <div class="settings-card ui-card settings-card--compact">
        <div class="collapsible-card__header collapsible-card__header--compact" @click="depsExpanded = !depsExpanded">
          <div class="flex items-center gap-2">
            <svg class="collapsible-card__chevron" :class="{ 'collapsible-card__chevron--open': depsExpanded }" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 18l6-6-6-6"/></svg>
            <h2 class="settings-card__title !mb-0">{{ t('settings.whisper.dependencies') }}</h2>
          </div>
          <VuiButton variant="contained" color="secondary" size="small" customClass="settings-secondary-btn settings-secondary-btn--compact" :loading="checkingDeps" @click.stop="checkWhisperDeps">
            {{ checkingDeps ? t('settings.whisper.checking') : t('settings.whisper.refresh') }}
          </VuiButton>
        </div>

        <div class="collapsible-card__body" :class="{ 'collapsible-card__body--open': depsExpanded }">
          <div class="collapsible-card__inner">
            <div class="space-y-1.5 mt-3">
              <div v-for="(info, name) in runtimeDisplayedDeps" :key="String(name)" class="dep-row">
                <div class="flex items-center justify-between mb-1">
                  <span class="dep-row__name">{{ dependencyDisplayName(String(name)) }}</span>
                  <VuiBadge v-if="info.installed" :color="dependencyStatusColor(String(name), info)" variant="gradient" size="xs">{{ dependencyStatusText(String(name), info) }}</VuiBadge>
                  <VuiBadge v-else-if="installStatus.status === 'running' && installStatus.message?.includes(String(name))" color="info" variant="gradient" size="xs">{{ t('settings.whisper.installingShort') }}</VuiBadge>
                  <VuiBadge v-else color="error" variant="gradient" size="xs">{{ t('settings.whisper.notInstalled') }}</VuiBadge>
                </div>
                <p v-if="dependencyDetail(info)" class="dep-row__detail">{{ dependencyDetail(info) }}</p>
                <div v-if="installStatus.status === 'running' && installStatus.message?.includes(String(name))">
                  <VuiProgress :value="installStatus.progress" color="info" variant="gradient" />
                </div>
              </div>

              <div class="dep-row">
                <div class="flex items-center justify-between">
                  <span class="dep-row__name">{{ t('settings.whisper.cuda') }}</span>
                  <VuiBadge v-if="checkingDepsResult.torch?.cuda" color="success" variant="gradient" size="xs">
                    {{ checkingDepsResult.torch.cuda_info?.device_name || t('settings.whisper.gpuAvailable') }}
                  </VuiBadge>
                  <VuiBadge v-else color="warning" variant="gradient" size="xs">{{ t('settings.whisper.cpuOnly') }}</VuiBadge>
                </div>
              </div>

              <!-- torch GPU/CPU variant selector -->
              <div class="dep-row">
                <div class="flex items-center justify-between">
                  <span class="dep-row__name">{{ t('settings.whisper.torchVariant') }}</span>
                  <div class="flex gap-1">
                    <button
                      class="filter-btn settings-secondary-btn-filter"
                      :class="{ 'filter-btn--active': torchVariant === 'gpu' }"
                      @click="torchVariant = 'gpu'"
                    >{{ t('settings.whisper.torchVariant.gpu') }}</button>
                    <button
                      class="filter-btn settings-secondary-btn-filter"
                      :class="{ 'filter-btn--active': torchVariant === 'cpu' }"
                      @click="torchVariant = 'cpu'"
                    >{{ t('settings.whisper.torchVariant.cpu') }}</button>
                  </div>
                </div>
              </div>

            </div>

            <p v-if="installStatus.status === 'running'" class="settings-note mt-3">
              {{ installStatus.message }}
            </p>

            <div v-if="hasMissingRuntimeDeps" class="mt-4">
              <VuiButton variant="gradient" color="info" size="small" customClass="settings-primary-btn settings-primary-btn--compact" :loading="installingDeps" @click="installDeps">
                {{ installingDeps ? t('settings.whisper.installing') : t('settings.whisper.installDeps') }}
              </VuiButton>
            </div>
            <p v-else class="mt-4 settings-note">{{ t('settings.whisper.runtimeReady') }}</p>
          </div>
        </div>
      </div>

      <!-- 4. Models Card (collapsible) -->
      <div class="settings-card ui-card settings-card--compact">
        <div class="collapsible-card__header collapsible-card__header--compact" @click="modelsExpanded = !modelsExpanded">
          <div class="flex items-center gap-2">
            <svg class="collapsible-card__chevron" :class="{ 'collapsible-card__chevron--open': modelsExpanded }" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 18l6-6-6-6"/></svg>
            <h2 class="settings-card__title !mb-0">{{ t('settings.whisper.models') }}</h2>
          </div>
          <VuiButton variant="contained" color="secondary" size="small" customClass="settings-secondary-btn settings-secondary-btn--compact" :loading="checkingModels" @click.stop="loadWhisperModels">
            {{ checkingModels ? t('settings.whisper.refreshing') : t('settings.whisper.refresh') }}
          </VuiButton>
        </div>

        <div class="collapsible-card__body" :class="{ 'collapsible-card__body--open': modelsExpanded }">
          <div class="collapsible-card__inner">
            <div class="space-y-1.5 mt-3">
              <div v-for="model in whisperModels" :key="model.id" class="model-row">
                <div class="model-row__info">
                  <div class="flex items-center gap-2 flex-wrap">
                    <span class="model-row__name">{{ model.name }}</span>
                    <VuiBadge :color="model.type === 'transformers' ? 'info' : 'secondary'" variant="gradient" size="xs">
                      {{ model.type }}
                    </VuiBadge>
                  </div>
                  <p class="model-row__desc">{{ model.size }}{{ model.description ? ' · ' + model.description : (model.downloaded ? ' · ' + t('settings.whisper.downloaded') : ' · ' + t('settings.whisper.notInstalled')) }}</p>
                </div>

                <div class="flex items-center gap-2 flex-shrink-0">
                  <VuiBadge v-if="model.downloaded" color="success" variant="gradient" size="xs">{{ t('settings.whisper.downloaded') }}</VuiBadge>

                  <div v-else-if="downloadingModel === model.id" class="flex items-center gap-2">
                    <div class="model-progress">
                      <div class="model-progress__bar" :style="{ width: modelDownloadStatus.progress + '%' }"></div>
                    </div>
                    <span class="model-progress__text">{{ modelDownloadStatus.progress }}%</span>
                  </div>

                  <VuiButton
                    v-else
                    variant="contained"
                    color="secondary"
                    size="small"
                    customClass="settings-secondary-btn settings-secondary-btn--compact"
                    :disabled="downloadingModel !== null"
                    @click="downloadModel(model.id)"
                  >
                    {{ t('settings.whisper.download') }}
                  </VuiButton>

                  <VuiButton
                    v-if="model.downloaded"
                    variant="contained"
                    color="secondary"
                    size="small"
                    customClass="settings-danger-btn settings-danger-btn--compact"
                    @click="deleteModel(model.id)"
                  >
                    {{ t('settings.whisper.deleteModel') }}
                  </VuiButton>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>
<style scoped>
.settings-card {
  background: linear-gradient(127.09deg, rgba(6, 11, 40, 0.94) 19.41%, rgba(10, 14, 35, 0.49) 76.65%);
  border-radius: var(--radius-xl);
  border: 1px solid rgba(255, 255, 255, 0.06);
  padding: 1.5rem;
}

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

.settings-form {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.settings-form__row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
}

@media (max-width: 768px) {
  .settings-form__row {
    grid-template-columns: 1fr;
  }
}

.settings-form__field {
  display: flex;
  flex-direction: column;
  gap: 0.375rem;
}

.settings-form__label {
  font-family: var(--font-display);
  font-size: 0.75rem;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.5);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.settings-input {
  padding: 0.625rem 0.875rem;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: var(--radius-md);
  font-family: var(--font-display);
  font-size: 0.875rem;
  color: #FFFFFF;
  outline: none;
  transition: all var(--transition-fast);
  width: 100%;
}

.settings-input:focus {
  background: rgba(255, 255, 255, 0.07);
  border-color: rgba(67, 56, 255, 0.4);
  box-shadow: 0 0 0 3px rgba(67, 56, 255, 0.1);
}

select.settings-input {
  cursor: pointer;
  appearance: none;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' fill='rgba(255,255,255,0.3)' viewBox='0 0 16 16'%3E%3Cpath d='M7.247 11.14L2.451 5.658C1.885 5.013 2.345 4 3.204 4h9.592a1 1 0 0 1 .753 1.659l-4.796 5.48a1 1 0 0 1-1.506 0z'/%3E%3C/svg%3E");
  background-repeat: no-repeat;
  background-position: calc(100% - 0.875rem) center;
  padding-right: 2.5rem;
}

select.settings-input option {
  background: #0a0e23;
  color: #fff;
}

.whisper-section-label {
  margin-top: 0.7rem;
  color: rgba(255, 255, 255, 0.74);
  font-size: 0.78rem;
  font-weight: 700;
}

.whisper-section-label--spaced {
  margin-top: 1rem;
}
.whisper-strategy-card {
  appearance: none;
  width: 100%;
  text-align: left;
  padding: 0.72rem 0.84rem;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: var(--radius-lg);
  background: rgba(255, 255, 255, 0.03);
  display: flex;
  flex-direction: column;
  gap: 0.38rem;
}

.whisper-strategy-card__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
}

.whisper-strategy-card__title {
  font-family: var(--font-display);
  font-size: 0.875rem;
  font-weight: 700;
  color: rgba(255, 255, 255, 0.96);
}

.whisper-strategy-card__summary {
  font-family: var(--font-display);
  font-size: 0.75rem;
  line-height: 1.45;
  color: rgba(255, 255, 255, 0.55);
}

.whisper-strategy-card__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
  margin-top: 0.15rem;
}

.whisper-strategy-card__chip {
  display: inline-flex;
  align-items: center;
  padding: 0.18rem 0.5rem;
  border-radius: 9999px;
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.08);
  font-family: var(--font-display);
  font-size: 0.6875rem;
  color: rgba(255, 255, 255, 0.72);
}

.whisper-strategy-card__actions {
  min-height: 2rem;
  display: flex;
  align-items: flex-end;
}

.whisper-strategy-card__actions :deep(.vui-button) {
  opacity: 0;
  transform: translateY(4px);
  pointer-events: none;
  transition: opacity var(--transition-fast), transform var(--transition-fast);
}

.whisper-strategy-card:hover .whisper-strategy-card__actions :deep(.vui-button),
.whisper-strategy-card:focus-within .whisper-strategy-card__actions :deep(.vui-button) {
  opacity: 1;
  transform: translateY(0);
  pointer-events: auto;
}

.whisper-strategy-card--active {
  border-color: rgba(0, 117, 255, 0.4);
  background: rgba(0, 117, 255, 0.08);
  box-shadow: 0 0 0 1px rgba(0, 117, 255, 0.08) inset;
}

.whisper-strategy-grid {
  display: grid;
  gap: 0.5rem;
}

.whisper-strategy-grid--duo {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.whisper-strategy-card--primary {
  min-height: 100%;
}

.whisper-strategy-card--summary {
  padding: 0.66rem 0.82rem;
  gap: 0.34rem;
}



.dep-row {
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.05);
  border-radius: var(--radius-md);
  padding: 0.75rem 1rem;
}

.dep-row__name {
  font-family: 'SF Mono', Monaco, monospace;
  font-size: 0.8125rem;
  color: #FFFFFF;
}

.model-row {
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.05);
  border-radius: var(--radius-md);
  padding: 0.875rem 1rem;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
}

.model-row__info {
  flex: 1;
  min-width: 0;
}

.model-row__name {
  font-family: var(--font-display);
  font-size: 0.875rem;
  font-weight: 600;
  color: #FFFFFF;
}

.model-row__desc {
  font-family: var(--font-display);
  font-size: 0.6875rem;
  color: rgba(255, 255, 255, 0.3);
  margin-top: 0.25rem;
}

.model-progress {
  width: 6rem;
  height: 0.375rem;
  background: rgba(255, 255, 255, 0.08);
  border-radius: 9999px;
  overflow: hidden;
}

.model-progress__bar {
  height: 100%;
  background: linear-gradient(97.89deg, #0075FF 0%, #21D4FD 100%);
  border-radius: 9999px;
  transition: width 0.3s ease;
}

.model-progress__text {
  font-family: var(--font-display);
  font-size: 0.6875rem;
  color: rgba(255, 255, 255, 0.4);
  min-width: 2.5rem;
  text-align: right;
}

.settings-note {
  font-family: var(--font-display);
  font-size: 0.6875rem;
  color: rgba(67, 56, 255, 0.7);
  margin-top: 0;
}
</style>
