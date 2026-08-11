<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import api from '../../api'
import { useToast } from '../../composables/useToast'
import { useI18n } from '../../composables/useI18n'
import BaseIcon from '../../components/noor/BaseIcon.vue'
import VuiButton from '../../components/ui/Button/VuiButton.vue'
import FieldRow from '../../components/ui/FieldRow/FieldRow.vue'

const toast = useToast()
const { t } = useI18n()

const loading = ref(false)
const saving = ref(false)

const sourceDir = ref('')
const outputDir = ref('')
const outputDirManuallyEdited = ref(false)
const noorDataDir = ref('')
const modelRootDir = ref('')
const runtimeRootDir = ref('')
const databasePath = ref('')
const whisperModelDir = ref('')
const whisperCacheDir = ref('')
const whisperTempDir = ref('')
const audioSeparatorModelDir = ref('')
const ladaModelDir = ref('')
const ladaCacheDir = ref('')
const ladaTempDir = ref('')
const facefusionModelDir = ref('')
const facefusionCacheDir = ref('')
const facefusionTempDir = ref('')

// Emby path mapping
const embyPathPrefix = ref('')

// Scan groups
interface ScanGroup {
  name: string
  source_dir: string
  hardlink_dir: string
}
const scanGroups = ref<ScanGroup[]>([])

// Directory picker
const showDirPicker = ref(false)
type DirPickerTarget =
  | 'sourceDir'
  | 'outputDir'
  | 'noorDataDir'
  | 'modelRootDir'
  | 'runtimeRootDir'
  | 'whisperModelDir'
  | 'whisperCacheDir'
  | 'whisperTempDir'
  | 'audioSeparatorModelDir'
  | 'ladaModelDir'
  | 'ladaCacheDir'
  | 'ladaTempDir'
  | 'facefusionModelDir'
  | 'facefusionCacheDir'
  | 'facefusionTempDir'
  | 'scanGroupSource'
  | 'scanGroupHardlink'

const dirPickerTarget = ref<DirPickerTarget>('sourceDir')
const dirPickerGroupIndex = ref<number | null>(null)
const dirPickerPath = ref('')
const dirPickerParent = ref<string | null>(null)
const dirPickerEntries = ref<{ name: string; path: string; is_dir: boolean }[]>([])
const dirPickerLoading = ref(false)
const dirPickerError = ref('')

onMounted(async () => {
  await loadSettings()
})

watch(sourceDir, (newVal) => {
  if (!outputDirManuallyEdited.value) {
    outputDir.value = newVal
  }
})

function onSourceDirInput() {
  if (!outputDirManuallyEdited.value) {
    outputDir.value = sourceDir.value
  }
}

async function loadSettings() {
  loading.value = true
  try {
    const resp = await api.get('/settings')
    const data = resp.data

    sourceDir.value = data.storage?.source_dir || ''
    outputDir.value = data.storage?.output_dir || data.storage?.source_dir || ''
    noorDataDir.value = data.storage?.noor_data_dir || ''
    modelRootDir.value = data.storage?.model_root_dir || ''
    runtimeRootDir.value = data.storage?.runtime_root_dir || ''
    databasePath.value = data.storage?.database_path || ''
    whisperModelDir.value = data.storage?.whisper_model_dir || ''
    whisperCacheDir.value = data.storage?.whisper_cache_dir || ''
    whisperTempDir.value = data.storage?.whisper_temp_dir || ''
    audioSeparatorModelDir.value = data.storage?.audio_separator_model_dir || ''
    ladaModelDir.value = data.storage?.lada_model_weights_dir || data.storage?.lada_model_dir || ''
    ladaCacheDir.value = data.storage?.lada_cache_dir || ''
    ladaTempDir.value = data.storage?.lada_temp_dir || ''
    facefusionModelDir.value = data.storage?.facefusion_model_dir || ''
    facefusionCacheDir.value = data.storage?.facefusion_cache_dir || ''
    facefusionTempDir.value = data.storage?.facefusion_temp_dir || ''

    // Also load Emby path prefix config
    try {
      const mlResp = await api.get('/media-library/config')
      const mlCfg = mlResp.data.config || {}
      embyPathPrefix.value = mlCfg.path_prefix || '/data/media'
      scanGroups.value = mlCfg.scan_groups || []
    } catch {
      // ignore
    }
  } catch (e: any) {
    toast.error(t('settings.storage.loadFailed'))
  } finally {
    loading.value = false
  }
}

async function saveStorage() {
  saving.value = true
  try {
    await api.put('/settings/storage', {
      source_dir: sourceDir.value,
      output_dir: outputDir.value,
      noor_data_dir: noorDataDir.value,
      model_root_dir: modelRootDir.value,
      runtime_root_dir: runtimeRootDir.value,
    })
    // Also save Emby path prefix and scan_groups to media-library config
    await api.post('/media-library/config', {
      path_prefix: embyPathPrefix.value,
      local_path_prefix: sourceDir.value,
      scan_groups: scanGroups.value,
    })
    toast.success(t('settings.saveSuccess'))
  } catch (e: any) {
    toast.error(t('settings.saveFailed'))
  } finally {
    saving.value = false
  }
}

// Scan group management
function addScanGroup() {
  scanGroups.value.push({ name: '', source_dir: '', hardlink_dir: '' })
}

function removeScanGroup(index: number) {
  scanGroups.value.splice(index, 1)
}

// Directory picker
function currentDirPickerPath(target: DirPickerTarget): string {
  const values: Record<DirPickerTarget, string> = {
    sourceDir: sourceDir.value,
    outputDir: outputDir.value,
    noorDataDir: noorDataDir.value,
    modelRootDir: modelRootDir.value,
    runtimeRootDir: runtimeRootDir.value,
    whisperModelDir: whisperModelDir.value,
    whisperCacheDir: whisperCacheDir.value,
    whisperTempDir: whisperTempDir.value,
    audioSeparatorModelDir: audioSeparatorModelDir.value,
    ladaModelDir: ladaModelDir.value,
    ladaCacheDir: ladaCacheDir.value,
    ladaTempDir: ladaTempDir.value,
    facefusionModelDir: facefusionModelDir.value,
    facefusionCacheDir: facefusionCacheDir.value,
    facefusionTempDir: facefusionTempDir.value,
    scanGroupSource: '',
    scanGroupHardlink: '',
  }
  return values[target] || ''
}

async function openDirPicker(target: Exclude<DirPickerTarget, 'scanGroupSource' | 'scanGroupHardlink'>) {
  dirPickerTarget.value = target
  dirPickerGroupIndex.value = null
  dirPickerError.value = ''
  const currentPath = currentDirPickerPath(target)
  await loadDirPicker(currentPath)
  showDirPicker.value = true
}

async function openScanGroupDirPicker(target: 'scanGroupSource' | 'scanGroupHardlink', groupIndex: number) {
  dirPickerTarget.value = target
  dirPickerGroupIndex.value = groupIndex
  dirPickerError.value = ''
  const currentPath = target === 'scanGroupSource'
    ? scanGroups.value[groupIndex].source_dir
    : scanGroups.value[groupIndex].hardlink_dir
  await loadDirPicker(currentPath)
  showDirPicker.value = true
}

async function loadDirPicker(path: string) {
  dirPickerLoading.value = true
  dirPickerError.value = ''
  try {
    const resp = await api.get(`/settings/directories?path=${encodeURIComponent(path)}`)
    dirPickerPath.value = resp.data.path
    dirPickerParent.value = resp.data.parent
    dirPickerEntries.value = resp.data.entries
  } catch (e: any) {
    dirPickerError.value = e?.response?.data?.detail || t('settings.dirPicker.loadDirFailed')
    dirPickerEntries.value = []
  } finally {
    dirPickerLoading.value = false
  }
}

async function onDirEntryClick(entry: { name: string; path: string; is_dir: boolean }) {
  if (entry.is_dir) {
    await loadDirPicker(entry.path)
  }
}

async function onDirPickerGoUp() {
  if (dirPickerParent.value) {
    await loadDirPicker(dirPickerParent.value)
  }
}

function confirmDirPicker() {
  const path = dirPickerPath.value
  if (dirPickerTarget.value === 'sourceDir') {
    sourceDir.value = path
    if (!outputDirManuallyEdited.value) outputDir.value = path
  } else if (dirPickerTarget.value === 'outputDir') {
    outputDir.value = path
    outputDirManuallyEdited.value = true
  } else if (dirPickerTarget.value === 'noorDataDir') {
    noorDataDir.value = path
  } else if (dirPickerTarget.value === 'whisperModelDir') {
    whisperModelDir.value = path
  } else if (dirPickerTarget.value === 'whisperCacheDir') {
    whisperCacheDir.value = path
  } else if (dirPickerTarget.value === 'whisperTempDir') {
    whisperTempDir.value = path
  } else if (dirPickerTarget.value === 'audioSeparatorModelDir') {
    audioSeparatorModelDir.value = path
  } else if (dirPickerTarget.value === 'ladaModelDir') {
    ladaModelDir.value = path
  } else if (dirPickerTarget.value === 'ladaCacheDir') {
    ladaCacheDir.value = path
  } else if (dirPickerTarget.value === 'ladaTempDir') {
    ladaTempDir.value = path
  } else if (dirPickerTarget.value === 'facefusionModelDir') {
    facefusionModelDir.value = path
  } else if (dirPickerTarget.value === 'facefusionCacheDir') {
    facefusionCacheDir.value = path
  } else if (dirPickerTarget.value === 'facefusionTempDir') {
    facefusionTempDir.value = path
  } else if (dirPickerTarget.value === 'scanGroupSource' && dirPickerGroupIndex.value !== null) {
    scanGroups.value[dirPickerGroupIndex.value].source_dir = path
  } else if (dirPickerTarget.value === 'scanGroupHardlink' && dirPickerGroupIndex.value !== null) {
    scanGroups.value[dirPickerGroupIndex.value].hardlink_dir = path
  }
  showDirPicker.value = false
}

function closeDirPicker() {
  showDirPicker.value = false
}
</script>

<template>
  <div class="flex flex-col gap-6">
    <div v-if="loading" class="flex items-center justify-center py-16">
      <div class="w-8 h-8 border-2 rounded-full animate-spin border-[#0075FF] border-t-transparent"></div>
    </div>

    <div v-else class="flex flex-col gap-6">

      <!-- 本地处理路径 -->
      <div class="settings-card ui-card">
        <h2 class="settings-card__title">{{ t('settings.storage.section.mediaPaths') }}</h2>
        <div class="settings-form">
          <FieldRow :label="t('settings.storage.output')" :description="t('settings.storage.outputHint')">
            <div class="dir-input-row">
              <input v-model="outputDir" @focus="outputDirManuallyEdited = true" type="text" placeholder="/path/to/output" class="settings-input" />
              <button @click="openDirPicker('outputDir')" class="dir-browse-btn" :title="t('settings.storage.browse')">
                <BaseIcon name="folderOpen" class="w-4 h-4" />
              </button>
            </div>
          </FieldRow>
        </div>
      </div>

      <!-- 模型路径 -->
      <div class="settings-card ui-card">
        <h2 class="settings-card__title">{{ t('settings.storage.section.modelPaths') }}</h2>
        <div class="settings-form">
          <FieldRow :label="t('settings.storage.noorDataDir')" :description="t('settings.storage.noorDataDirHint')">
            <div class="dir-input-row">
              <input v-model="noorDataDir" type="text" :placeholder="t('settings.storage.noorDataPlaceholder')" class="settings-input" />
              <button @click="openDirPicker('noorDataDir')" class="dir-browse-btn" :title="t('settings.storage.browse')">
                <BaseIcon name="folderOpen" class="w-4 h-4" />
              </button>
            </div>
          </FieldRow>
          <FieldRow :label="t('settings.storage.databasePath')" :description="t('settings.storage.databasePathHint')">
            <input :value="databasePath" type="text" class="settings-input settings-input--readonly" readonly />
          </FieldRow>
          <FieldRow :label="t('settings.storage.whisperModelDir')" :description="t('settings.storage.whisperModelDirHint')">
            <div class="dir-input-row">
              <input v-model="whisperModelDir" type="text" :placeholder="t('settings.storage.whisperPlaceholder')" class="settings-input" />
              <button @click="openDirPicker('whisperModelDir')" class="dir-browse-btn" :title="t('settings.storage.browse')">
                <BaseIcon name="folderOpen" class="w-4 h-4" />
              </button>
            </div>
          </FieldRow>
          <FieldRow :label="t('settings.storage.audioSeparatorModelDir')" :description="t('settings.storage.audioSeparatorModelDirHint')">
            <div class="dir-input-row">
              <input v-model="audioSeparatorModelDir" type="text" :placeholder="t('settings.storage.audioSeparatorModelPlaceholder')" class="settings-input" />
              <button @click="openDirPicker('audioSeparatorModelDir')" class="dir-browse-btn" :title="t('settings.storage.browse')">
                <BaseIcon name="folderOpen" class="w-4 h-4" />
              </button>
            </div>
          </FieldRow>
          <FieldRow :label="t('settings.storage.ladaModelDir')" :description="t('settings.storage.ladaModelDirHint')">
            <div class="dir-input-row">
              <input v-model="ladaModelDir" type="text" :placeholder="t('settings.storage.ladaModelPlaceholder')" class="settings-input" />
              <button @click="openDirPicker('ladaModelDir')" class="dir-browse-btn" :title="t('settings.storage.browse')">
                <BaseIcon name="folderOpen" class="w-4 h-4" />
              </button>
            </div>
          </FieldRow>
          <FieldRow :label="t('settings.storage.facefusionModelDir')" :description="t('settings.storage.facefusionModelDirHint')">
            <div class="dir-input-row">
              <input v-model="facefusionModelDir" type="text" :placeholder="t('settings.storage.facefusionModelPlaceholder')" class="settings-input" />
              <button @click="openDirPicker('facefusionModelDir')" class="dir-browse-btn" :title="t('settings.storage.browse')">
                <BaseIcon name="folderOpen" class="w-4 h-4" />
              </button>
            </div>
          </FieldRow>
        </div>
      </div>

      <!-- 运行时路径 -->
      <div class="settings-card ui-card">
        <h2 class="settings-card__title">{{ t('settings.storage.section.runtimePaths') }}</h2>
        <div class="runtime-path-grid">
          <FieldRow :label="t('settings.storage.whisperCacheDir')" :description="t('settings.storage.cacheDirHint')">
            <div class="dir-input-row">
              <input v-model="whisperCacheDir" type="text" class="settings-input" />
              <button @click="openDirPicker('whisperCacheDir')" class="dir-browse-btn" :title="t('settings.storage.browse')">
                <BaseIcon name="folderOpen" class="w-4 h-4" />
              </button>
            </div>
          </FieldRow>
          <FieldRow :label="t('settings.storage.whisperTempDir')" :description="t('settings.storage.tempDirHint')">
            <div class="dir-input-row">
              <input v-model="whisperTempDir" type="text" class="settings-input" />
              <button @click="openDirPicker('whisperTempDir')" class="dir-browse-btn" :title="t('settings.storage.browse')">
                <BaseIcon name="folderOpen" class="w-4 h-4" />
              </button>
            </div>
          </FieldRow>
          <FieldRow :label="t('settings.storage.ladaCacheDir')" :description="t('settings.storage.cacheDirHint')">
            <div class="dir-input-row">
              <input v-model="ladaCacheDir" type="text" class="settings-input" />
              <button @click="openDirPicker('ladaCacheDir')" class="dir-browse-btn" :title="t('settings.storage.browse')">
                <BaseIcon name="folderOpen" class="w-4 h-4" />
              </button>
            </div>
          </FieldRow>
          <FieldRow :label="t('settings.storage.ladaTempDir')" :description="t('settings.storage.tempDirHint')">
            <div class="dir-input-row">
              <input v-model="ladaTempDir" type="text" class="settings-input" />
              <button @click="openDirPicker('ladaTempDir')" class="dir-browse-btn" :title="t('settings.storage.browse')">
                <BaseIcon name="folderOpen" class="w-4 h-4" />
              </button>
            </div>
          </FieldRow>
          <FieldRow :label="t('settings.storage.facefusionCacheDir')" :description="t('settings.storage.facefusionCacheDirHint')">
            <div class="dir-input-row">
              <input v-model="facefusionCacheDir" type="text" class="settings-input" />
              <button @click="openDirPicker('facefusionCacheDir')" class="dir-browse-btn" :title="t('settings.storage.browse')">
                <BaseIcon name="folderOpen" class="w-4 h-4" />
              </button>
            </div>
          </FieldRow>
          <FieldRow :label="t('settings.storage.facefusionTempDir')" :description="t('settings.storage.tempDirHint')">
            <div class="dir-input-row">
              <input v-model="facefusionTempDir" type="text" class="settings-input" />
              <button @click="openDirPicker('facefusionTempDir')" class="dir-browse-btn" :title="t('settings.storage.browse')">
                <BaseIcon name="folderOpen" class="w-4 h-4" />
              </button>
            </div>
          </FieldRow>
        </div>
      </div>

      <!-- Emby 路径映射 -->
      <div class="settings-card ui-card settings-card--primary">
        <div class="settings-card__header settings-card__header--tight">
          <h2 class="settings-card__title">{{ t('settings.storage.section.embyPathMapping') }}</h2>
        </div>
        <p class="settings-card__hint settings-card__hint--primary">{{ t('settings.storage.embyMappingPairHint') }}</p>
        <div class="settings-form settings-form--pair">
          <FieldRow :label="t('settings.storage.embyPrefix')" :description="t('settings.storage.embyPrefixHint')">
            <input v-model="embyPathPrefix" type="text" placeholder="/data/media" class="settings-input" />
          </FieldRow>
          <FieldRow :label="t('settings.storage.mediaRoot')" :description="t('settings.storage.mediaRootHint')">
            <div class="dir-input-row">
              <input v-model="sourceDir" type="text" :placeholder="t('settings.storage.mediaRootPlaceholder')" class="settings-input" @input="onSourceDirInput" />
              <button @click="openDirPicker('sourceDir')" class="dir-browse-btn" :title="t('settings.storage.browse')">
                <BaseIcon name="folderOpen" class="w-4 h-4" />
              </button>
            </div>
          </FieldRow>
        </div>
      </div>

      <!-- 扫描分组 -->
      <div class="settings-card ui-card settings-card--muted">
        <div class="scan-groups-header">
          <h2 class="settings-card__title" style="margin-bottom:0">{{ t('settings.storage.section.scanGroups') }}</h2>
          <button @click="addScanGroup" class="add-scan-group-btn">
            <BaseIcon name="plus" class="w-3 h-3" />
            {{ t('settings.storage.addScanGroup') }}
          </button>
        </div>
        <p class="settings-card__hint settings-card__hint--muted">{{ t('settings.storage.scanGroupsHint') }}</p>
        <div class="scan-groups-list">
          <div v-for="(group, index) in scanGroups" :key="index" class="scan-group-row">
            <div class="scan-group-fields">
              <FieldRow :label="t('settings.storage.groupName')">
                <input v-model="group.name" type="text" :placeholder="t('settings.storage.groupNamePlaceholder')" class="settings-input" />
              </FieldRow>
              <FieldRow :label="t('settings.storage.sourceDir')">
                <div class="dir-input-row">
                  <input v-model="group.source_dir" type="text" :placeholder="t('settings.storage.sourceDirPlaceholder')" class="settings-input" />
                  <button @click="openScanGroupDirPicker('scanGroupSource', index)" class="dir-browse-btn" :title="t('settings.storage.browse')">
                    <BaseIcon name="folderOpen" class="w-4 h-4" />
                  </button>
                </div>
              </FieldRow>
              <FieldRow :label="t('settings.storage.hardlinkDir')">
                <div class="dir-input-row">
                  <input v-model="group.hardlink_dir" type="text" :placeholder="t('settings.storage.hardlinkDirPlaceholder')" class="settings-input" />
                  <button @click="openScanGroupDirPicker('scanGroupHardlink', index)" class="dir-browse-btn" :title="t('settings.storage.browse')">
                    <BaseIcon name="folderOpen" class="w-4 h-4" />
                  </button>
                </div>
              </FieldRow>
            </div>
            <button @click="removeScanGroup(index)" class="remove-scan-group-btn" :title="t('settings.storage.removeGroup')">
              <BaseIcon name="trash" class="w-4 h-4" />
            </button>
          </div>
          <div v-if="scanGroups.length === 0" class="scan-groups-empty">
            {{ t('settings.storage.noScanGroups') }}
          </div>
        </div>
      </div>

      <!-- 统一保存按钮 -->
      <div class="flex justify-start">
        <VuiButton variant="gradient" color="info" size="small" customClass="settings-primary-btn" :loading="saving" @click="saveStorage">
          {{ saving ? t('settings.storage.loading') : t('settings.storage.save') }}
        </VuiButton>
      </div>

    </div>
  </div>

  <!-- Directory Picker Modal -->
  <div v-if="showDirPicker" class="dir-modal-overlay" @click.self="closeDirPicker">
    <div class="dir-modal">
      <!-- Header -->
      <div class="dir-modal__header">
        <div class="dir-modal__path-row">
          <button @click="onDirPickerGoUp" :disabled="!dirPickerParent" class="dir-up-btn" :title="t('settings.dirPicker.parentDir')">
            <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M5 10l7-7m0 0l7 7m-7-7v18" />
            </svg>
          </button>
          <span class="dir-modal__path">{{ dirPickerPath || '/' }}</span>
        </div>
        <button @click="closeDirPicker" class="dir-close-btn">
          <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      <!-- Content -->
      <div class="dir-modal__content">
        <div v-if="dirPickerLoading" class="flex items-center justify-center py-8 text-white/30">
          {{ t('settings.dirPicker.loading') }}
        </div>
        <div v-else-if="dirPickerError" class="dir-error">
          {{ dirPickerError }}
        </div>
        <div v-else>
          <div
            v-for="entry in dirPickerEntries"
            :key="entry.path"
            @click="onDirEntryClick(entry)"
            class="dir-entry"
          >
            <BaseIcon :name="entry.is_dir ? 'folderOpen' : 'file'" :class="`w-4 h-4 dir-entry__icon${entry.is_dir ? ' dir-entry__icon--folder' : ''}`" />
            <span class="dir-entry__name">{{ entry.name }}</span>
          </div>
          <div v-if="dirPickerEntries.length === 0 && !dirPickerLoading" class="dir-empty">
            {{ t('settings.dirPicker.emptyDir') }}
          </div>
        </div>
      </div>

      <!-- Footer -->
      <div class="dir-modal__footer">
        <span class="dir-modal__hint">{{ t('settings.dirPicker.hint') }}</span>
        <div class="flex gap-2">
          <VuiButton variant="outlined" color="secondary" size="small" @click="closeDirPicker">{{ t('common.cancel') }}</VuiButton>
          <VuiButton variant="gradient" color="info" size="small" @click="confirmDirPicker">{{ t('settings.dirPicker.selectFolder') }}</VuiButton>
        </div>
      </div>
    </div>
  </div>
</template>
