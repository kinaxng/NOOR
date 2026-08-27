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
  } else if (dirPickerTarget.value === 'modelRootDir') {
    modelRootDir.value = path
  } else if (dirPickerTarget.value === 'runtimeRootDir') {
    runtimeRootDir.value = path
  } else if (dirPickerTarget.value === 'whisperModelDir') {
    whisperModelDir.value = path
  } else if (dirPickerTarget.value === 'whisperCacheDir') {
    whisperCacheDir.value = path
  } else if (dirPickerTarget.value === 'whisperTempDir') {
    whisperTempDir.value = path
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

      <!-- AI 存储根目录 -->
      <div class="settings-card ui-card">
        <h2 class="settings-card__title">AI 存储</h2>
        <div class="settings-form">
          <FieldRow label="模型路径" description="Whisper、LADA、FaceFusion 等模型都会按模块自动放到这个目录下。">
            <div class="dir-input-row">
              <input v-model="modelRootDir" type="text" placeholder="/path/to/noor/models" class="settings-input" />
              <button @click="openDirPicker('modelRootDir')" class="dir-browse-btn" :title="t('settings.storage.browse')">
                <BaseIcon name="folderOpen" class="w-4 h-4" />
              </button>
            </div>
          </FieldRow>
          <FieldRow label="运行时路径" description="缓存、临时文件、预览帧、任务中间文件都会按模块自动放到这个目录下。">
            <div class="dir-input-row">
              <input v-model="runtimeRootDir" type="text" placeholder="/path/to/noor/runtime" class="settings-input" />
              <button @click="openDirPicker('runtimeRootDir')" class="dir-browse-btn" :title="t('settings.storage.browse')">
                <BaseIcon name="folderOpen" class="w-4 h-4" />
              </button>
            </div>
          </FieldRow>
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

<style scoped>
.settings-card--primary {
  border-color: rgba(0, 117, 255, 0.18);
  box-shadow: inset 0 0 0 1px rgba(0, 117, 255, 0.06);
}

.settings-card--muted {
  background: rgba(255, 255, 255, 0.018);
}

.settings-card__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
}

.settings-card__header--tight {
  margin-bottom: 0.75rem;
}

.settings-card__hint {
  margin-top: 0;
  margin-bottom: 1.25rem;
  font-family: var(--font-display);
  font-size: 0.75rem;
  line-height: 1.6;
}

.settings-card__hint--primary {
  color: rgba(189, 225, 255, 0.72);
}

.settings-card__hint--muted {
  color: rgba(255, 255, 255, 0.32);
}

.settings-card__title {
  font-family: var(--font-display);
  font-size: 0.875rem;
  font-weight: 700;
  color: rgba(255, 255, 255, 0.7);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 1.5rem;
}

.settings-primary-btn {
  min-width: 5.5rem;
}

.dir-input-row {
  display: flex;
  gap: 0.5rem;
}

.dir-browse-btn {
  width: 2.75rem;
  height: 2.75rem;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: var(--radius-md);
  color: rgba(255, 255, 255, 0.4);
  cursor: pointer;
  transition: all var(--transition-fast);
  flex-shrink: 0;
}

.dir-browse-btn:hover {
  background: rgba(255, 255, 255, 0.1);
  color: rgba(255, 255, 255, 0.8);
  border-color: rgba(0, 117, 255, 0.3);
}

.dir-modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.7);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  backdrop-filter: blur(4px);
}

.dir-modal {
  background: linear-gradient(127.09deg, rgba(6, 11, 40, 0.98) 19.41%, rgba(10, 14, 35, 0.95) 76.65%);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: var(--radius-xl);
  width: 100%;
  max-width: 560px;
  margin: 1rem;
  display: flex;
  flex-direction: column;
  max-height: 70vh;
  overflow: hidden;
}

.dir-modal__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1rem 1.25rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

.dir-modal__path-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex: 1;
  min-width: 0;
}

.dir-up-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 2rem;
  height: 2rem;
  border-radius: var(--radius-sm);
  background: transparent;
  border: none;
  color: rgba(255, 255, 255, 0.4);
  cursor: pointer;
  transition: all var(--transition-fast);
  flex-shrink: 0;
}

.dir-up-btn:hover:not(:disabled) {
  background: rgba(255, 255, 255, 0.08);
  color: rgba(255, 255, 255, 0.8);
}

.dir-up-btn:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

.dir-modal__path {
  font-family: var(--font-display);
  font-size: 0.8125rem;
  color: rgba(255, 255, 255, 0.72);
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.dir-close-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 2rem;
  height: 2rem;
  border-radius: var(--radius-sm);
  background: transparent;
  border: none;
  color: rgba(255, 255, 255, 0.4);
  cursor: pointer;
  transition: all var(--transition-fast);
  flex-shrink: 0;
}

.dir-close-btn:hover {
  background: rgba(255, 255, 255, 0.08);
  color: rgba(255, 255, 255, 0.8);
}

.dir-modal__content {
  flex: 1;
  overflow-y: auto;
  padding: 0.5rem;
}

.dir-entry {
  display: flex;
  align-items: center;
  gap: 0.625rem;
  padding: 0.625rem 0.875rem;
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: background var(--transition-fast);
}

.dir-entry:hover {
  background: rgba(255, 255, 255, 0.06);
}

.dir-entry__icon {
  color: rgba(255, 255, 255, 0.2);
  flex-shrink: 0;
}

.dir-entry__icon--folder {
  color: rgba(255, 181, 71, 0.6);
}

.dir-entry__name {
  font-family: var(--font-display);
  font-size: 0.8125rem;
  color: rgba(255, 255, 255, 0.6);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.dir-empty {
  text-align: center;
  padding: 2rem;
  font-family: var(--font-display);
  font-size: 0.875rem;
  color: rgba(255, 255, 255, 0.2);
}

.dir-error {
  padding: 1rem;
  font-family: var(--font-display);
  font-size: 0.875rem;
  color: #E31A1A;
}

.dir-modal__footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1rem 1.25rem;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
}

.dir-modal__hint {
  font-family: var(--font-display);
  font-size: 0.6875rem;
  color: rgba(255, 255, 255, 0.2);
}

.scan-groups-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 0.5rem;
}

.add-scan-group-btn {
  display: flex;
  align-items: center;
  gap: 0.375rem;
  padding: 0.375rem 0.75rem;
  background: rgba(255, 255, 255, 0.045);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: var(--radius-md);
  color: rgba(255, 255, 255, 0.72);
  font-family: var(--font-display);
  font-size: 0.75rem;
  font-weight: 600;
  cursor: pointer;
  transition: all var(--transition-fast);
}

.add-scan-group-btn:hover {
  background: rgba(255, 255, 255, 0.08);
  border-color: rgba(255, 255, 255, 0.14);
}

.scan-groups-hint {
  font-family: var(--font-display);
  font-size: 0.75rem;
  color: rgba(255, 255, 255, 0.3);
  margin-bottom: 1.25rem;
  margin-top: 0;
}

.scan-groups-list {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.scan-group-row {
  display: flex;
  align-items: flex-start;
  gap: 1rem;
  padding: 1rem;
  background: rgba(255, 255, 255, 0.015);
  border: 1px solid rgba(255, 255, 255, 0.045);
  border-radius: var(--radius-lg);
}

.scan-group-fields {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  min-width: 0;
}

.remove-scan-group-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 2.25rem;
  height: 2.25rem;
  background: transparent;
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: var(--radius-md);
  color: rgba(255, 255, 255, 0.3);
  cursor: pointer;
  transition: all var(--transition-fast);
  flex-shrink: 0;
  margin-top: 0.25rem;
}

.remove-scan-group-btn:hover {
  background: rgba(227, 26, 26, 0.1);
  border-color: rgba(227, 26, 26, 0.3);
  color: #E31A1A;
}

.scan-groups-empty {
  text-align: center;
  padding: 2rem;
  font-family: var(--font-display);
  font-size: 0.8125rem;
  color: rgba(255, 255, 255, 0.2);
}

@media (max-width: 640px) {
  .scan-groups-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 0.75rem;
  }

  .scan-group-row {
    flex-direction: column;
  }

  .remove-scan-group-btn {
    margin-top: 0;
    width: 100%;
    height: 2.5rem;
  }

  .dir-modal__footer {
    flex-direction: column;
    align-items: flex-start;
    gap: 0.75rem;
  }

  .dir-modal__footer > .flex.gap-2 {
    width: 100%;
  }

  .dir-modal__footer > .flex.gap-2 :deep(button),
  .dir-modal__footer > .flex.gap-2 button {
    flex: 1;
  }
}
</style>
