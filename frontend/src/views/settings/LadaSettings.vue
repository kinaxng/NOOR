<script setup lang="ts">
import { ref, onMounted } from 'vue'
import api from '../../api'
import { useToast } from '../../composables/useToast'
import { useConfirm } from '../../composables/useConfirm'
import { useI18n } from '../../composables/useI18n'
import VuiButton from '../../components/ui/Button/VuiButton.vue'
import VuiBadge from '../../components/ui/Badge/VuiBadge.vue'
import FieldRow from '../../components/ui/FieldRow/FieldRow.vue'
import SettingsSwitch from '../../components/ui/SettingsSwitch.vue'

const toast = useToast()
const { confirm } = useConfirm()
const { t } = useI18n()

const loading = ref(false)
const saving = ref(false)
const upgrading = ref(false)

const ladaCliPath = ref('')
const ladaVersion = ref<string | null>(null)
const ladaIsDocker = ref(false)
const ladaInstallMode = ref('external-cli')
const ladaCanSelfUpgrade = ref(false)
const ladaUpgradeStrategy = ref('manual-external')
const ladaUpgradeHint = ref('')
const ladaRepoPath = ref<string | null>(null)

const ladaDevice = ref('cuda:0')
const ladaFp16 = ref(true)
const ladaDetectionModel = ref('v4-fast')
const ladaRestorationModel = ref('basicvsrpp-v1.2')
const ladaEncodingPreset = ref('hevc-nvidia-gpu-hq')
const ladaMaxClipLength = ref(180)
const ladaDetectFaceMosaics = ref(false)

const ladaDevices = ref<any[]>([])
const ladaEncodingPresets = ref<any[]>([])
const ladaDetectionModels = ref<any[]>([])
const ladaRestorationModels = ref<any[]>([])
const ladaModelWeightsDir = ref('')
const loadingLadaInfo = ref(false)

const detectionModelsExpanded = ref(false)
const restorationModelsExpanded = ref(false)

function buildFallbackEncodingPresets() {
  return [
    { id: 'hevc-nvidia-gpu-hq', name: t('settings.lada.encodingPresetName.hevcNvidiaGpuHq') },
    { id: 'hevc-nvidia-gpu-balanced', name: t('settings.lada.encodingPresetName.hevcNvidiaGpuBalanced') },
    { id: 'hevc-nvidia-gpu-uhq', name: t('settings.lada.encodingPresetName.hevcNvidiaGpuUhq') },
    { id: 'h264-nvidia-gpu-fast', name: t('settings.lada.encodingPresetName.h264NvidiaGpuFast') },
    { id: 'h264-cpu-fast', name: t('settings.lada.encodingPresetName.h264CpuFast') },
    { id: 'h264-cpu-uhq', name: t('settings.lada.encodingPresetName.h264CpuUhq') },
    { id: 'av1-cpu-uhq', name: t('settings.lada.encodingPresetName.av1CpuUhq') },
  ]
}

onMounted(async () => {
  await loadSettings()
})

async function loadSettings() {
  loading.value = true
  try {
    const resp = await api.get('/settings')
    const data = resp.data

    ladaCliPath.value = data.lada?.cli_path || ''
    ladaVersion.value = data.lada?.version || null
    ladaIsDocker.value = data.lada?.is_docker || false
    ladaInstallMode.value = data.lada?.install_mode || 'external-cli'
    ladaCanSelfUpgrade.value = data.lada?.can_self_upgrade || false
    ladaUpgradeStrategy.value = data.lada?.upgrade_strategy || 'manual-external'
    ladaUpgradeHint.value = data.lada?.upgrade_hint || ''
    ladaRepoPath.value = data.lada?.repo_path || null

    if (data.lada_defaults) {
      ladaDevice.value = data.lada_defaults.device || 'cuda:0'
      ladaFp16.value = data.lada_defaults.fp16 ?? true
      ladaDetectionModel.value = data.lada_defaults.detection_model || 'v4-fast'
      ladaRestorationModel.value = data.lada_defaults.restoration_model || 'basicvsrpp-v1.2'
      ladaEncodingPreset.value = data.lada_defaults.encoding_preset || 'hevc-nvidia-gpu-hq'
      ladaMaxClipLength.value = data.lada_defaults.max_clip_length || 180
      ladaDetectFaceMosaics.value = data.lada_defaults.detect_face_mosaics ?? false
    }
    // Encoding presets always available immediately
    ladaEncodingPresets.value = buildFallbackEncodingPresets()

    await loadLadaInfo()
  } catch (e: any) {
    toast.error(t('settings.lada.loadFailed'))
  } finally {
    loading.value = false
  }
}

async function loadLadaInfo() {
  loadingLadaInfo.value = true
  try {
    const resp = await api.get('/settings/lada/info')
    ladaDevices.value = resp.data.devices || []
    ladaEncodingPresets.value = resp.data.encoding_presets || []
    ladaDetectionModels.value = resp.data.detection_models || []
    ladaRestorationModels.value = resp.data.restoration_models || []
    ladaModelWeightsDir.value = resp.data.model_weights_dir || ''
  } catch (e: any) {
    console.error('Failed to load LADA info:', e)
  } finally {
    loadingLadaInfo.value = false
  }
}

async function saveLada() {
  saving.value = true
  try {
    await api.put('/settings/lada', { cli_path: ladaCliPath.value })
    toast.success(t('settings.saveSuccess'))
  } catch (e: any) {
    toast.error(t('settings.saveFailed'))
  } finally {
    saving.value = false
  }
}

async function upgradeLada() {
  if (!ladaCanSelfUpgrade.value) {
    toast.error(ladaUpgradeHint.value || t('settings.lada.upgradeFailed'))
    return
  }
  if (!await confirm({ message: t('settings.lada.upgradeConfirm') })) return
  upgrading.value = true
  try {
    const resp = await api.post('/settings/lada/upgrade')
    ladaVersion.value = resp.data.version
    toast.success(t('settings.lada.upgradedTo', { version: resp.data.version }))
  } catch (e: any) {
    toast.error(e.response?.data?.detail || t('settings.lada.upgradeFailed'))
  } finally {
    upgrading.value = false
  }
}

async function saveLadaDefaults() {
  saving.value = true
  try {
    await api.put('/settings/lada/defaults', {
      device: ladaDevice.value,
      fp16: ladaFp16.value,
      detection_model: ladaDetectionModel.value,
      restoration_model: ladaRestorationModel.value,
      encoding_preset: ladaEncodingPreset.value,
      max_clip_length: ladaMaxClipLength.value,
      detect_face_mosaics: ladaDetectFaceMosaics.value,
    })
    toast.success(t('settings.saveSuccess'))
  } catch (e: any) {
    toast.error(t('settings.saveFailed'))
  } finally {
    saving.value = false
  }
}

function installModeLabel(mode: string) {
  switch (mode) {
    case 'docker-image':
      return t('settings.lada.installModeDockerImage')
    case 'editable-repo':
      return t('settings.lada.installModeEditableRepo')
    default:
      return t('settings.lada.installModeExternalCli')
  }
}
</script>

<template>
  <div class="flex flex-col gap-6">
    <div v-if="loading" class="flex items-center justify-center py-16">
      <div class="w-8 h-8 border-2 rounded-full animate-spin border-[#0075FF] border-t-transparent"></div>
    </div>

    <template v-else>
      <!-- CLI & Version Info -->
      <div class="settings-card ui-card">
        <h2 class="settings-card__title">{{ t('settings.lada.cli') }}</h2>

        <div class="settings-form">
          <div class="settings-info-row">
            <div>
              <p class="info-label">{{ t('settings.lada.version') }}</p>
              <p class="info-value">{{ ladaVersion || t('settings.lada.versionNotFound') }}</p>
            </div>
            <div class="text-right">
              <p class="info-label">{{ t('settings.lada.runningMode') }}</p>
              <VuiBadge :color="ladaIsDocker ? 'success' : 'warning'" variant="gradient" size="sm">
                {{ ladaIsDocker ? t('settings.lada.docker') : t('settings.lada.native') }}
              </VuiBadge>
            </div>
          </div>

          <div class="settings-info-row">
            <div>
              <p class="info-label">{{ t('settings.lada.installMode') }}</p>
              <p class="info-value">{{ installModeLabel(ladaInstallMode) }}</p>
            </div>
            <div v-if="ladaRepoPath" class="text-right">
              <p class="info-label">{{ t('settings.lada.repoPath') }}</p>
              <p class="info-value info-value--mono">{{ ladaRepoPath }}</p>
            </div>
          </div>

          <FieldRow :label="t('settings.lada.cliPath')" :description="t('settings.lada.cliPathDesc')">
            <input v-model="ladaCliPath" type="text" placeholder="python3 -m lada.cli.main" class="settings-input" />
          </FieldRow>

          <div class="settings-info-row">
            <span class="info-label">{{ t('settings.lada.modelWeightsDir') }}</span>
            <span class="info-value info-value--mono">{{ ladaModelWeightsDir || t('settings.lada.modelWeightsDirNotConfigured') }}</span>
          </div>

          <div class="settings-actions settings-actions--stack mt-2">
            <VuiButton variant="gradient" color="info" size="small" customClass="settings-primary-btn" :loading="saving" @click="saveLada">
              {{ saving ? t('settings.lada.saving') : t('settings.lada.savePaths') }}
            </VuiButton>
            <VuiButton
              variant="contained"
              color="secondary"
              size="small"
              customClass="settings-secondary-btn"
              :loading="upgrading"
              :disabled="!ladaCanSelfUpgrade"
              @click="upgradeLada"
            >
              {{ upgrading ? t('settings.lada.upgrading') : t('settings.lada.upgrade') }}
            </VuiButton>
          </div>
          <p v-if="ladaUpgradeHint" class="mt-3 text-xs text-text-secondary">{{ ladaUpgradeHint }}</p>
        </div>
      </div>

      <!-- Default Settings -->
      <div class="settings-card ui-card">
        <h2 class="settings-card__title">{{ t('settings.lada.defaultSettings') }}</h2>
        <p class="settings-card__desc">{{ t('settings.lada.defaultSettingsHint') }}</p>

        <div class="settings-form mt-4">
          <FieldRow :label="t('settings.lada.device')" :description="t('settings.lada.deviceDesc')">
            <select v-model="ladaDevice" class="settings-input">
              <option v-for="dev in ladaDevices" :key="dev.id" :value="dev.id">
                {{ dev.name }} ({{ dev.id }})
              </option>
            </select>
          </FieldRow>

          <FieldRow :label="t('settings.lada.fp16')" :description="t('settings.lada.fp16Desc')">
            <select v-model="ladaFp16" class="settings-input">
              <option :value="true">{{ t('settings.lada.fp16Enabled') }}</option>
              <option :value="false">{{ t('settings.lada.fp16Disabled') }}</option>
            </select>
          </FieldRow>

          <FieldRow :label="t('settings.lada.detectionModel')" :description="t('settings.lada.detectionModelDesc')">
            <select v-model="ladaDetectionModel" class="settings-input">
              <option v-for="m in ladaDetectionModels" :key="m.id" :value="m.id">
                {{ m.id }} - {{ m.name }} {{ m.downloaded ? '✓' : '' }}
              </option>
            </select>
          </FieldRow>

          <FieldRow :label="t('settings.lada.restorationModel')" :description="t('settings.lada.restorationModelDesc')">
            <select v-model="ladaRestorationModel" class="settings-input">
              <option v-for="m in ladaRestorationModels" :key="m.id" :value="m.id">
                {{ m.id }} - {{ m.name }} {{ m.downloaded ? '✓' : '' }}
              </option>
            </select>
          </FieldRow>

          <FieldRow :label="t('settings.lada.encodingPreset')" :description="t('settings.lada.encodingPresetDesc')">
            <select v-model="ladaEncodingPreset" class="settings-input">
              <option v-for="p in ladaEncodingPresets" :key="p.id" :value="p.id">
                {{ p.name }}
              </option>
            </select>
          </FieldRow>

          <FieldRow :label="t('settings.lada.maxClipLength')" :description="t('settings.lada.maxClipLengthDesc')">
            <input v-model.number="ladaMaxClipLength" type="number" min="30" max="600" class="settings-input" />
          </FieldRow>

          <FieldRow :label="t('settings.lada.detectFaceMosaics')" :description="t('settings.lada.detectFaceMosaicsHint')">
            <div class="flex items-center gap-3">
              <SettingsSwitch v-model="ladaDetectFaceMosaics" />
              <span class="text-sm text-text-secondary">{{ ladaDetectFaceMosaics ? t('common.enabled') : t('common.disabled') }}</span>
            </div>
          </FieldRow>

          <div class="settings-actions mt-2">
            <VuiButton variant="gradient" color="info" size="small" customClass="settings-primary-btn" :loading="saving" @click="saveLadaDefaults">
              {{ saving ? t('settings.lada.saving') : t('settings.lada.saveDefaults') }}
            </VuiButton>
          </div>
        </div>
      </div>

      <!-- Detection Models -->
      <div class="settings-card ui-card">
        <div class="collapsible-card__header" @click="detectionModelsExpanded = !detectionModelsExpanded">
          <div class="flex items-center gap-2">
            <svg class="collapsible-card__chevron" :class="{ 'collapsible-card__chevron--open': detectionModelsExpanded }" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 18l6-6-6-6"/></svg>
            <h2 class="settings-card__title !mb-0">{{ t('settings.lada.detectionModels') }}</h2>
          </div>
          <VuiButton variant="outlined" color="secondary" size="small" :loading="loadingLadaInfo" @click.stop="loadLadaInfo">
            {{ loadingLadaInfo ? t('settings.lada.refreshing') : t('settings.lada.refresh') }}
          </VuiButton>
        </div>

        <div class="collapsible-card__body" :class="{ 'collapsible-card__body--open': detectionModelsExpanded }">
          <div class="collapsible-card__inner">
            <div class="space-y-2 mt-4">
              <div v-for="model in ladaDetectionModels" :key="model.id" class="model-row">
                <div class="model-row__info">
                  <div class="flex items-center gap-2 flex-wrap">
                    <span class="model-row__name">{{ model.name }}</span>
                    <VuiBadge v-if="model.downloaded" color="success" variant="gradient" size="xs">{{ model.size }}</VuiBadge>
                    <VuiBadge v-else color="error" variant="gradient" size="xs">{{ t('settings.lada.notDownloaded') }}</VuiBadge>
                  </div>
                  <p class="model-row__desc">{{ model.description_zh }}</p>
                </div>
              </div>
            </div>
            <p class="settings-note mt-4">{{ t('settings.lada.detectionModelsNote') }}</p>
          </div>
        </div>
      </div>

      <!-- Restoration Models -->
      <div class="settings-card ui-card">
        <div class="collapsible-card__header" @click="restorationModelsExpanded = !restorationModelsExpanded">
          <div class="flex items-center gap-2">
            <svg class="collapsible-card__chevron" :class="{ 'collapsible-card__chevron--open': restorationModelsExpanded }" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 18l6-6-6-6"/></svg>
            <h2 class="settings-card__title !mb-0">{{ t('settings.lada.restorationModels') }}</h2>
          </div>
        </div>

        <div class="collapsible-card__body" :class="{ 'collapsible-card__body--open': restorationModelsExpanded }">
          <div class="collapsible-card__inner">
            <div class="space-y-2 mt-4">
              <div v-for="model in ladaRestorationModels" :key="model.id" class="model-row">
                <div class="model-row__info">
                  <div class="flex items-center gap-2 flex-wrap">
                    <span class="model-row__name">{{ model.name }}</span>
                    <VuiBadge v-if="model.downloaded" color="success" variant="gradient" size="xs">{{ model.size }}</VuiBadge>
                    <VuiBadge v-else color="error" variant="gradient" size="xs">{{ t('settings.lada.notDownloaded') }}</VuiBadge>
                  </div>
                  <p class="model-row__desc">{{ model.description_zh }}</p>
                </div>
              </div>
            </div>
            <p class="settings-note mt-4">{{ t('settings.lada.restorationModelsNote') }}</p>
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
