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
import { buildWhisperProfileWithTranslation, formatWhisperAudioPreprocessSummary, formatWhisperTranslationSummary, getWhisperSelectableStrategyPresentation, getWhisperStrategyMeta, resolveWhisperEditableDefaults } from '../../composables/useWhisperProfiles'

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
const activeStrategy = ref<'recommended' | 'reazon_nemo'>('recommended')
const audioPreprocessMode = ref('none')
const audioPreprocessModel = ref('vocal_balanced')

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

// 是否有缺失的运行时依赖（控制安装按钮显示）
const hasMissingRuntimeDeps = computed(() => {
  return Object.values(runtimeInstallableDeps.value).some((v: any) => !v.installed)
})
const installStatus = ref<{ status: string; progress: number; message: string; current_package?: string }>({
  status: 'idle',
  progress: 0,
  message: '',
})

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
      activeStrategy.value = defaults.strategy
      audioPreprocessMode.value = defaults.audio_preprocess_mode
      audioPreprocessModel.value = defaults.audio_preprocess_model
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
  return buildWhisperProfileWithTranslation(activeStrategy.value, {
    audio_preprocess_mode: audioPreprocessMode.value,
    audio_preprocess_model: audioPreprocessModel.value,
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
  const torchIsInstalled = !!checkingDepsResult.value.torch?.installed
  const librosaIsInstalled = !!checkingDepsResult.value.librosa?.installed
  const variantChanged = torchIsInstalled && (torchVariant.value === 'gpu') !== !!checkingDepsResult.value.torch?.cuda
  const parts: string[] = []
  if (!librosaIsInstalled) parts.push('librosa')
  if (!torchIsInstalled || variantChanged) parts.push(`torch ${torchVariant.value.toUpperCase()}`)
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

const activeTranslateSummary = computed(() => {
  return formatWhisperTranslationSummary(t, {
    translateEnabled: translateEnabled.value,
    translateTo: translateTo.value,
    translateModel: translateModel.value,
  })
})
const activeAudioPreprocessSummary = computed(() => {
  return formatWhisperAudioPreprocessSummary(t, {
    audioPreprocessMode: audioPreprocessMode.value,
    audioPreprocessModel: audioPreprocessModel.value,
  })
})

const recommendedMeta = computed(() => getWhisperStrategyMeta('recommended'))
const reazonNemoMeta = computed(() => getWhisperStrategyMeta('reazon_nemo'))
const recommendedPresentation = computed(() => getWhisperSelectableStrategyPresentation(t, 'recommended'))
const reazonPresentation = computed(() => getWhisperSelectableStrategyPresentation(t, 'reazon_nemo'))
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

        <div class="settings-form mt-2.5 space-y-1.5">
          <button
            type="button"
            class="whisper-strategy-card whisper-strategy-card--primary whisper-strategy-card--summary"
            :class="{ 'whisper-strategy-card--active': activeStrategy === 'recommended' }"
            @click="activeStrategy = 'recommended'"
          >
            <div class="whisper-strategy-card__head">
              <div>
                <div class="whisper-strategy-card__title">{{ t(recommendedMeta.titleKey) }}</div>
              </div>
              <VuiBadge :color="recommendedPresentation.badgeColor" variant="gradient" size="sm">{{ t(recommendedMeta.badgeKey) }}</VuiBadge>
            </div>
            <p class="whisper-strategy-card__summary">{{ t(recommendedMeta.stackKey) }}</p>
            <div class="whisper-strategy-card__meta">
              <span class="whisper-strategy-card__chip">{{ activeAudioPreprocessSummary }}</span>
              <span class="whisper-strategy-card__chip">{{ activeTranslateSummary }}</span>
            </div>
          </button>

          <button
            type="button"
            class="whisper-strategy-card whisper-strategy-card--muted whisper-strategy-card--summary"
            :class="{ 'whisper-strategy-card--active': activeStrategy === 'reazon_nemo' }"
            @click="activeStrategy = 'reazon_nemo'"
          >
            <div class="whisper-strategy-card__head">
              <div>
                <div class="whisper-strategy-card__title">{{ t(reazonNemoMeta.titleKey) }}</div>
              </div>
              <VuiBadge :color="reazonPresentation.badgeColor" variant="gradient" size="sm">{{ t(reazonNemoMeta.badgeKey) }}</VuiBadge>
            </div>
            <p class="whisper-strategy-card__summary">{{ t(reazonNemoMeta.stackKey) }}</p>
            <div class="whisper-strategy-card__meta">
              <span class="whisper-strategy-card__chip">{{ t(reazonNemoMeta.descKey) }}</span>
            </div>
          </button>
        </div>
      </div>

      <div class="settings-card ui-card settings-card--compact">
        <h2 class="settings-card__title">{{ t('settings.whisper.audioLabTitle') }}</h2>
        <p class="settings-card__desc">{{ t('settings.whisper.audioLabDesc') }}</p>

        <div class="settings-form settings-form--compact mt-2.5">
          <FieldRow customClass="whisper-field-row" :label="t('settings.whisper.audioPreprocessLabel')" :description="t('settings.whisper.audioPreprocessDesc')">
            <select v-model="audioPreprocessMode" class="settings-input">
              <option value="none">{{ t('settings.whisper.audioPreprocessMode.none') }}</option>
              <option value="vocal_isolation">{{ t('settings.whisper.audioPreprocessMode.vocalIsolation') }}</option>
            </select>
          </FieldRow>

          <FieldRow
            customClass="whisper-field-row"
            :label="t('settings.whisper.audioPreprocessModelLabel')"
            :description="t('settings.whisper.audioPreprocessModelDesc')"
          >
            <select v-model="audioPreprocessModel" class="settings-input" :disabled="audioPreprocessMode === 'none'">
              <option value="vocal_clean">{{ t('settings.whisper.audioPreprocessModel.vocalClean') }}</option>
              <option value="vocal_balanced">{{ t('settings.whisper.audioPreprocessModel.vocalBalanced') }}</option>
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
              <SettingsSwitch v-model="translateEnabled" />
              <span class="text-sm text-text-secondary">{{ translateEnabled ? t('common.enabled') : t('common.disabled') }}</span>
            </div>
          </FieldRow>

          <FieldRow customClass="whisper-field-row" :label="t('settings.whisper.translateTargetLabel')" :description="t('settings.whisper.translateTargetDesc')">
            <select v-model="translateTo" class="settings-input" :disabled="!translateEnabled">
              <option v-for="opt in translateLangOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
            </select>
          </FieldRow>

          <FieldRow customClass="whisper-field-row" :label="t('settings.whisper.translateModelLabel')" :description="t('settings.whisper.translateModelDesc')">
            <input v-model="translateModel" type="text" class="settings-input" placeholder="gpt-4o-mini" :disabled="!translateEnabled" />
          </FieldRow>

          <FieldRow customClass="whisper-field-row" :label="t('settings.whisper.translateBaseUrlLabel')" :description="t('settings.whisper.translateBaseUrlDesc')">
            <input v-model="translateBaseUrl" type="text" class="settings-input" placeholder="https://api.openai.com/v1" :disabled="!translateEnabled" />
          </FieldRow>

          <FieldRow customClass="whisper-field-row" :label="t('settings.whisper.translateApiKeyLabel')" :description="t('settings.whisper.translateApiKeyDesc')">
            <input v-model="translateApiKey" type="password" class="settings-input" placeholder="sk-..." :disabled="!translateEnabled" />
          </FieldRow>

          <FieldRow customClass="whisper-field-row" :label="t('settings.whisper.translateStyleLabel')" :description="t('settings.whisper.translateStyleDesc')">
            <select v-model="translateStyle" class="settings-input" :disabled="!translateEnabled">
              <option v-for="opt in translateStyleOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
            </select>
          </FieldRow>

          <FieldRow customClass="whisper-field-row" :label="t('settings.emby.connectionTest')" :description="t('settings.whisper.translateConnectionDesc')">
            <div class="flex flex-wrap items-center gap-2">
              <VuiButton variant="contained" color="secondary" size="small" customClass="settings-secondary-btn settings-secondary-btn--compact" :loading="testingConnection" :disabled="!translateEnabled" @click="testTranslateConnection">
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
              <div v-for="(info, name) in runtimeInstallableDeps" :key="String(name)" class="dep-row">
                <div class="flex items-center justify-between mb-1">
                  <span class="dep-row__name">{{ name === 'torch' ? 'torch (' + torchVariant.toUpperCase() + ')' : name }}</span>
                  <VuiBadge v-if="info.installed" color="success" variant="gradient" size="xs">{{ info.version || t('settings.whisper.installed') }}</VuiBadge>
                  <VuiBadge v-else-if="installStatus.status === 'running' && installStatus.message?.includes(String(name))" color="info" variant="gradient" size="xs">{{ t('settings.whisper.installingShort') }}</VuiBadge>
                  <VuiBadge v-else color="error" variant="gradient" size="xs">{{ t('settings.whisper.notInstalled') }}</VuiBadge>
                </div>
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
/* 强制 VuiBadge 截断 */
.connection-result-badge :deep(.vui-badge) {
  max-width: 240px;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
  display: inline-flex;
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
  line-height: 1.45;
}

.settings-card__desc--compact {
  max-width: 36rem;
}

.settings-card--compact {
  padding-bottom: 1rem;
}

.settings-form__label {
  font-family: var(--font-display);
  font-size: 0.75rem;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.5);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 0.5rem;
  display: block;
}

.settings-form__field {
  margin-bottom: 0;
}

.settings-form__row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.75rem;
}

.settings-field-hint {
  font-family: var(--font-display);
  font-size: 0.6875rem;
  color: rgba(255, 255, 255, 0.25);
  margin-top: 0.375rem;
}

.settings-card__actions {
  display: flex;
  align-items: center;
  justify-content: flex-start;
  gap: 0.75rem;
  flex-wrap: wrap;
  margin-top: 0.75rem;
}

.settings-card__actions--compact {
  margin-top: 0.5rem;
}

.settings-form--compact {
  display: flex;
  flex-direction: column;
  gap: 0.125rem;
}

.settings-card__actions--end {
  justify-content: flex-start;
}

.settings-primary-btn {
  min-width: 5.5rem;
}

.settings-primary-btn--compact {
  min-height: 2rem;
}

.settings-secondary-btn {
  box-shadow: none !important;
  background: rgba(255, 255, 255, 0.05) !important;
  border: 1px solid rgba(255, 255, 255, 0.1) !important;
  color: rgba(255, 255, 255, 0.82) !important;
}

.settings-secondary-btn--compact {
  min-height: 2rem;
}

.settings-secondary-btn:hover:not(:disabled) {
  background: rgba(255, 255, 255, 0.08) !important;
  border-color: rgba(255, 255, 255, 0.16) !important;
  transform: none !important;
}

.settings-danger-btn {
  box-shadow: none !important;
  background: rgba(227, 26, 26, 0.08) !important;
  border: 1px solid rgba(227, 26, 26, 0.18) !important;
  color: rgba(255, 255, 255, 0.84) !important;
}

.settings-danger-btn:hover:not(:disabled) {
  background: rgba(227, 26, 26, 0.14) !important;
  border-color: rgba(227, 26, 26, 0.28) !important;
  transform: none !important;
}

.settings-danger-btn--compact {
  min-height: 2rem;
}

.settings-secondary-btn-filter {
  min-width: 3rem;
}

.settings-secondary-btn-filter.filter-btn {
  background: rgba(255, 255, 255, 0.05);
  border-color: rgba(255, 255, 255, 0.1);
  color: rgba(255, 255, 255, 0.78);
}

.settings-secondary-btn-filter.filter-btn:hover {
  background: rgba(255, 255, 255, 0.08);
  border-color: rgba(255, 255, 255, 0.18);
}

.settings-secondary-btn-filter.filter-btn--active {
  background: rgba(0, 117, 255, 0.14);
  border-color: rgba(0, 117, 255, 0.28);
  color: #fff;
}

.pipeline-groups {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.pipeline-group {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.pipeline-group--compat {
  padding-top: 0.125rem;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
}

.pipeline-group__head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 0.75rem;
}

.pipeline-group__title {
  font-size: 0.6875rem;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.72);
}

.pipeline-group__hint {
  font-size: 0.6875rem;
  color: rgba(255, 255, 255, 0.34);
  text-align: right;
}

.settings-input {
  width: 100%;
  padding: 0.625rem 0.875rem;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: var(--radius-md);
  color: rgba(255, 255, 255, 0.8);
  font-family: var(--font-display);
  font-size: 0.8125rem;
  transition: all var(--transition-fast);
}

.settings-input:focus {
  outline: none;
  border-color: rgba(0, 117, 255, 0.5);
  background: rgba(255, 255, 255, 0.06);
}

.settings-input option {
  background: #0a0e23;
  color: #fff;
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

.whisper-strategy-card--summary .whisper-strategy-card__head {
  align-items: flex-start;
}

.whisper-strategy-card--summary .whisper-strategy-card__title {
  font-size: 0.875rem;
}

.whisper-strategy-card--summary .whisper-strategy-card__stack {
  font-size: 0.65625rem;
  line-height: 1.45;
}


.whisper-strategy-card--disabled {
  opacity: 0.82;
}

.whisper-strategy-card--disabled .whisper-strategy-card__actions {
  display: none;
}

.whisper-strategy-card--muted {
  background: rgba(255, 255, 255, 0.02);
}

.whisper-strategy-card--reserved {
  border-style: dashed;
  background: rgba(255, 255, 255, 0.02);
}

.whisper-strategy-mini-grid {
  display: grid;
  gap: 0.75rem;
  grid-template-columns: 1fr;
}

.whisper-strategy-mini-card {
  text-align: left;
  padding: 0.875rem 1rem;
  border-radius: var(--radius-lg);
  border: 1px solid rgba(255, 255, 255, 0.07);
  background: rgba(255, 255, 255, 0.025);
  display: flex;
  flex-direction: column;
  gap: 0.45rem;
  transition: all var(--transition-fast);
}

.whisper-strategy-mini-card:hover {
  border-color: rgba(0, 117, 255, 0.26);
  background: rgba(255, 255, 255, 0.05);
}

.whisper-strategy-mini-card--muted:hover {
  border-color: rgba(255, 193, 7, 0.28);
}

.whisper-strategy-mini-card__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.75rem;
}

.whisper-strategy-mini-card__title {
  font-family: var(--font-display);
  font-size: 0.875rem;
  font-weight: 700;
  color: var(--color-text-primary);
}

.whisper-strategy-mini-card__desc {
  margin: 0;
  font-size: 0.75rem;
  line-height: 1.55;
  color: var(--color-text-secondary);
}

.whisper-strategy-mini-card__stack {
  margin: 0;
  font-size: 0.65625rem;
  color: var(--color-text-muted);
}

.whisper-strategy-card__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
}

.whisper-strategy-card__title {
  font-family: var(--font-display);
  font-size: 0.85rem;
  font-weight: 700;
  color: var(--color-text-primary);
}

.whisper-strategy-card__summary {
  margin: 0;
  font-size: 0.6875rem;
  line-height: 1.45;
  color: var(--color-text-secondary);
}

.whisper-strategy-card__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 0.28rem;
}

.whisper-strategy-card__chip {
  display: inline-flex;
  align-items: center;
  padding: 0.1rem 0.42rem;
  border-radius: 9999px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(255, 255, 255, 0.03);
  font-size: 0.65625rem;
  line-height: 1.35;
  color: var(--color-text-muted);
}

.whisper-strategy-card__stack {
  margin: 0;
  font-size: 0.6875rem;
  color: var(--color-text-muted);
}

.pipeline-card {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  padding: 0.75rem 1rem;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all var(--transition-fast);
  text-align: left;
}

.pipeline-card:hover {
  background: rgba(255, 255, 255, 0.06);
  border-color: rgba(0, 117, 255, 0.3);
}

.pipeline-card--active {
  background: rgba(0, 117, 255, 0.1);
  border-color: rgba(0, 117, 255, 0.5);
}

.pipeline-card__name {
  font-family: var(--font-display);
  font-size: 0.8125rem;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.9);
}

.pipeline-card--active .pipeline-card__name {
  color: #0075FF;
}

.pipeline-card__desc {
  font-family: var(--font-display);
  font-size: 0.6875rem;
  color: rgba(255, 255, 255, 0.3);
  margin-top: 0.25rem;
}

.pipeline-card__check {
  color: #00e676;
  margin-left: 0.25rem;
}

@media (max-width: 767px) {
  .whisper-strategy-grid--duo,
  .whisper-strategy-mini-grid {
    grid-template-columns: 1fr;
  }
}

.dep-row {
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.05);
  border-radius: var(--radius-md);
  padding: 0.625rem 0.8rem;
}

.dep-row__name {
  font-family: 'SF Mono', Monaco, monospace;
  font-size: 0.75rem;
  color: #FFFFFF;
}

.model-row {
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.05);
  border-radius: var(--radius-md);
  padding: 0.72rem 0.8rem;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.875rem;
}

.model-row__info {
  flex: 1;
  min-width: 0;
}

.model-row__name {
  font-family: var(--font-display);
  font-size: 0.8125rem;
  font-weight: 600;
  color: #FFFFFF;
}

.model-row__desc {
  font-family: var(--font-display);
  font-size: 0.65625rem;
  line-height: 1.4;
  color: rgba(255, 255, 255, 0.3);
  margin-top: 0.2rem;
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
  background: #0075FF;
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
  color: rgba(0, 117, 255, 0.7);
  margin-top: 0;
}

.custom-pipeline-panel {
  background: rgba(0, 117, 255, 0.04);
  border: 1px solid rgba(0, 117, 255, 0.12);
  border-left: 3px solid rgba(0, 117, 255, 0.5);
  border-radius: var(--radius-md);
  overflow: hidden;
}

.custom-pipeline-panel__header {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.625rem 1rem;
  background: rgba(0, 117, 255, 0.06);
  border-bottom: 1px solid rgba(0, 117, 255, 0.1);
  font-family: var(--font-display);
  font-size: 0.6875rem;
  font-weight: 600;
  color: rgba(0, 117, 255, 0.8);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.custom-pipeline-panel__body {
  padding: 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.625rem;
}

.custom-pipeline-panel__body > * {
  margin: 0;
}

.pipeline-specs-panel {
  margin-top: 0.5rem;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.625rem;
}

.pipeline-specs-panel:not(.pipeline-specs-panel--dual) {
  grid-template-columns: 1fr;
  max-width: 50%;
}

.pipeline-specs-card {
  background: rgba(255, 255, 255, 0.025);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: var(--radius-md);
  overflow: hidden;
  transition: all var(--transition-fast);
}

.pipeline-specs-card--primary {
  border-color: rgba(0, 117, 255, 0.3);
  background: rgba(0, 117, 255, 0.04);
}

.pipeline-specs-card__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.5rem 0.75rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
  background: rgba(255, 255, 255, 0.015);
}

.pipeline-specs-card__name {
  font-family: var(--font-display);
  font-size: 0.8125rem;
  font-weight: 700;
  color: rgba(255, 255, 255, 0.85);
}

.pipeline-specs-card--primary .pipeline-specs-card__name {
  color: #0075FF;
}

.pipeline-specs-card__best-for {
  font-family: var(--font-display);
  font-size: 0.625rem;
  color: rgba(255, 255, 255, 0.28);
}

.pipeline-specs-card__body {
  padding: 0.625rem 0.75rem;
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
}

.pipeline-specs-bar-row {
  display: grid;
  grid-template-columns: 2.5rem 1fr auto;
  align-items: center;
  gap: 0.5rem;
}

.pipeline-specs-bar-row__label {
  font-family: var(--font-display);
  font-size: 0.625rem;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.3);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.pipeline-specs-bar-row__track {
  height: 0.25rem;
  background: rgba(255, 255, 255, 0.06);
  border-radius: 9999px;
  overflow: hidden;
}

.pipeline-specs-bar-row__fill {
  height: 100%;
  border-radius: 9999px;
  transition: width 0.4s ease;
}

.pipeline-specs-bar-row__fill--speed {
  background: #01B574;
}

.pipeline-specs-bar-row__fill--accuracy {
  background: #0075FF;
}

.pipeline-specs-bar-row__val {
  font-family: var(--font-display);
  font-size: 0.625rem;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.5);
  min-width: 2.5rem;
  text-align: right;
}

.pipeline-specs-info-row {
  display: grid;
  grid-template-columns: 2.5rem 1fr;
  gap: 0.5rem;
  align-items: center;
  margin-top: 0.1rem;
}

.pipeline-specs-info-row__label {
  font-family: var(--font-display);
  font-size: 0.625rem;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.3);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.pipeline-specs-info-row__val {
  font-family: 'SF Mono', Monaco, monospace;
  font-size: 0.625rem;
  color: rgba(255, 255, 255, 0.5);
}

.pipeline-specs-tips {
  display: flex;
  flex-wrap: wrap;
  gap: 0.25rem;
  margin-top: 0.25rem;
  padding-top: 0.375rem;
  border-top: 1px solid rgba(255, 255, 255, 0.04);
}

.pipeline-specs-tip-tag {
  font-family: var(--font-display);
  font-size: 0.5625rem;
  font-weight: 500;
  color: rgba(255, 255, 255, 0.55);
  border-radius: 4px;
  padding: 0.125rem 0.35rem;
  line-height: 1.5;
}

.enhancer-toggles {
  display: flex;
  flex-direction: column;
  gap: 0.375rem;
}

.enhancer-toggles--row {
  flex-direction: row;
  gap: 0.5rem;
}

.enhancer-toggle {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.375rem 0.75rem;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.07);
  border-radius: 9999px;
  cursor: pointer;
  transition: all var(--transition-fast);
  font-size: inherit;
  flex: 1;
}

.enhancer-toggle:hover {
  background: rgba(255, 255, 255, 0.07);
  border-color: rgba(255, 255, 255, 0.12);
}

.enhancer-toggle--active {
  border-color: transparent;
}

.enhancer-toggle__dot {
  width: 1.125rem;
  height: 0.625rem;
  border-radius: 9999px;
  background: rgba(255, 255, 255, 0.15);
  flex-shrink: 0;
  transition: all 0.2s ease;
  position: relative;
}

.enhancer-toggle__dot::after {
  content: '';
  position: absolute;
  top: 50%;
  left: 2px;
  transform: translateY(-50%);
  width: 0.5rem;
  height: 0.5rem;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.4);
  transition: all 0.2s ease;
}

.enhancer-toggle--active .enhancer-toggle__dot {
  background: rgba(255, 255, 255, 0.25);
}

.enhancer-toggle--active .enhancer-toggle__dot::after {
  left: auto;
  right: 2px;
  background: #fff;
}

.enhancer-toggle__label {
  font-family: var(--font-display);
  font-size: 0.6875rem;
  font-weight: 500;
  color: rgba(255, 255, 255, 0.45);
  transition: color var(--transition-fast);
  white-space: nowrap;
}

.enhancer-toggle--active .enhancer-toggle__label {
  color: rgba(255, 255, 255, 0.9);
}

/* Action row (测试连接) */
.settings-action-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1.5rem;
  align-items: center;
  padding: 0.75rem 0 0;
}

.settings-action-row__label-col {}

.settings-action-row__input-col {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

/* Collapsible card */
.collapsible-card__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  cursor: pointer;
  user-select: none;
}

.collapsible-card__header--compact {
  gap: 0.75rem;
}

.collapsible-card__chevron {
  color: rgba(255, 255, 255, 0.35);
  transition: transform 0.25s ease;
  flex-shrink: 0;
}

.collapsible-card__chevron--open {
  transform: rotate(90deg);
}

.collapsible-card__body {
  display: grid;
  grid-template-rows: 0fr;
  transition: grid-template-rows 0.3s ease;
  overflow: hidden;
}

.collapsible-card__body--open {
  grid-template-rows: 1fr;
}

.collapsible-card__inner {
  min-height: 0;
  overflow: hidden;
  padding-top: 0.125rem;
}

.settings-card__hint {
  font-size: 0.78rem;
  line-height: 1.45;
  color: rgba(255, 208, 122, 0.88);
}
</style>


@media (max-width: 640px) {
  .whisper-strategy-grid--duo {
    grid-template-columns: 1fr;
  }

  .collapsible-card__header {
    align-items: flex-start;
    gap: 0.75rem;
  }

  .model-row {
    gap: 0.75rem;
  }

  .model-row > .flex.items-center.gap-2.flex-shrink-0 {
    width: 100%;
    justify-content: flex-start;
    flex-wrap: wrap;
  }

  .connection-result-badge {
    width: 100%;
  }
}


.whisper-current-profile {
  display: flex;
  flex-direction: column;
  gap: 0.625rem;
  margin-bottom: 0.875rem;
  padding: 0.875rem 1rem;
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: var(--radius-lg);
  background: rgba(255,255,255,0.035);
}

.whisper-current-profile__label {
  margin: 0 0 0.25rem;
  font-size: 0.6875rem;
  color: rgba(255,255,255,0.42);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.whisper-current-profile__headline {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
  font-size: 0.9375rem;
  font-weight: 700;
  color: rgba(255,255,255,0.92);
}

.whisper-current-profile__desc {
  margin: 0.25rem 0 0;
  font-size: 0.75rem;
  color: rgba(255,255,255,0.42);
}

.whisper-current-profile__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 0.45rem;
}

.whisper-current-profile__chip {
  display: inline-flex;
  align-items: center;
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 9999px;
  padding: 0.2rem 0.55rem;
  font-size: 0.6875rem;
  color: rgba(255,255,255,0.58);
}

.whisper-field-row {
  padding-top: 0.125rem;
}

.whisper-field-row + .whisper-field-row {
  margin-top: -0.25rem;
}

.whisper-field-row :deep(.field-row) {
  gap: 0.625rem;
}

.whisper-field-row :deep(.field-row__content) {
  gap: 0.375rem;
}

.whisper-field-row :deep(.field-row__label) {
  font-size: 0.75rem;
}

.whisper-field-row :deep(.field-row__description) {
  font-size: 0.6875rem;
  line-height: 1.45;
}
