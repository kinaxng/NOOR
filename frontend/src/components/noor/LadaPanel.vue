<script setup lang="ts">
import { computed, ref, watch } from 'vue'
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
const panelTitle = computed(() => t('detail.openLada'))

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

const detectionModels = computed(() => [
  { id: 'v4-fast', name: t('ladaPanel.detectionModelName.v4Fast') },
  { id: 'v4-accurate', name: t('ladaPanel.detectionModelName.v4Accurate') },
])

const restorationModels = computed(() => [
  { id: 'basicvsrpp-v1.2', name: t('ladaPanel.restorationModelName.basicvsrpp') },
  { id: 'deepmosaics', name: t('ladaPanel.restorationModelName.deepmosaics') },
])

const encodingPresets = computed(() => [
  { id: 'hevc-nvidia-gpu-hq', name: t('settings.lada.encodingPresetName.hevcNvidiaGpuHq') },
  { id: 'hevc-nvidia-gpu-balanced', name: t('settings.lada.encodingPresetName.hevcNvidiaGpuBalanced') },
  { id: 'hevc-nvidia-gpu-uhq', name: t('settings.lada.encodingPresetName.hevcNvidiaGpuUhq') },
  { id: 'h264-nvidia-gpu-fast', name: t('settings.lada.encodingPresetName.h264NvidiaGpuFast') },
  { id: 'h264-cpu-fast', name: t('settings.lada.encodingPresetName.h264CpuFast') },
  { id: 'h264-cpu-uhq', name: t('settings.lada.encodingPresetName.h264CpuUhq') },
  { id: 'av1-cpu-uhq', name: t('settings.lada.encodingPresetName.av1CpuUhq') },
])

const settings = ref<JobSettings>({
  detection_model: 'v4-fast',
  restoration_model: 'basicvsrpp-v1.2',
  encoding_preset: 'hevc-nvidia-gpu-hq',
})

watch(() => props.open, async (isOpen) => {
  if (!isOpen) return

  try {
    const resp = await api.get('/settings')
    const defaults = resp.data?.lada_defaults || {}

    settings.value = {
      detection_model: defaults.detection_model || 'v4-fast',
      restoration_model: defaults.restoration_model || 'basicvsrpp-v1.2',
      encoding_preset: defaults.encoding_preset || 'hevc-nvidia-gpu-hq',
    }
  } catch (e) {
    // Use local defaults when settings are unavailable.
  }
}, { immediate: true })

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

const displayTitle = computed(() => {
  if (!props.detail) return ''
  return props.detail.nfo?.title || props.detail.nfo?.originaltitle || props.detail.name
})

const mergedDetectionModels = computed(() => {
  const options = [...detectionModels.value]
  if (settings.value.detection_model && !options.find(m => m.id === settings.value.detection_model)) {
    options.push({ id: settings.value.detection_model, name: settings.value.detection_model })
  }
  return options
})

const mergedRestorationModels = computed(() => {
  const options = [...restorationModels.value]
  if (settings.value.restoration_model && !options.find(m => m.id === settings.value.restoration_model)) {
    options.push({ id: settings.value.restoration_model, name: settings.value.restoration_model })
  }
  return options
})

const mergedEncodingPresets = computed(() => {
  const options = [...encodingPresets.value]
  if (settings.value.encoding_preset && !options.find(p => p.id === settings.value.encoding_preset)) {
    options.push({ id: settings.value.encoding_preset, name: settings.value.encoding_preset })
  }
  return options
})

function handleClose() {
  emit('close')
}

async function handleSubmitJob() {
  if (!selectedSubmitPath.value) return

  submitting.value = true
  submitStatus.value = 'running'
  submitProgress.value = 12
  try {
    const createdJob = await jobsStore.createJob({
      emby_item_id: selectedSubmitId.value,
      emby_item_name: displayTitle.value,
      input_path: selectedSubmitPath.value,
      settings: settings.value,
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
</script>

<template>
  <Teleport to="body">
    <Transition name="panel">
      <div v-if="open" class="fixed inset-0 z-50 flex justify-end">
        <div class="absolute inset-0 bg-bg-void/80 backdrop-blur-sm" @click="handleClose"></div>

        <div class="relative bg-bg-surface border-l border-border-default flex flex-col overflow-hidden shadow-2xl h-full w-full lg:w-[min(50vw,960px)]">
          <template v-if="detail">
            <div class="flex-1 overflow-y-auto p-4 space-y-4 relative">
              <div class="panel-topbar">
                <span class="panel-topbar__title">{{ panelTitle }}</span>
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

              <PanelHeader :detail="detail" :show-play="false" />

              <FilePathSelector
                :file-path="detail?.file_path"
                :sibling-paths="detail?.siblings"
                v-model="selectedSubmitPath"
                @update:model-value="selectedSubmitId = allSubmitPaths.find(p => p.path === $event)?.id || detail?.id || ''"
              />

              <div class="ui-card">
                <span class="text-[10px] text-text-muted uppercase tracking-wider">{{ t('ladaPanel.processingSettings') }}</span>
                <div class="space-y-3 mt-3">
                  <div>
                    <label class="block text-[10px] text-text-muted uppercase tracking-wider mb-1">{{ t('ladaPanel.detectionModel') }}</label>
                    <select v-model="settings.detection_model" class="settings-input w-full">
                      <option v-for="m in mergedDetectionModels" :key="m.id" :value="m.id">{{ m.name }} ({{ m.id }})</option>
                    </select>
                  </div>
                  <div>
                    <label class="block text-[10px] text-text-muted uppercase tracking-wider mb-1">{{ t('ladaPanel.restorationModel') }}</label>
                    <select v-model="settings.restoration_model" class="settings-input w-full">
                      <option v-for="m in mergedRestorationModels" :key="m.id" :value="m.id">{{ m.name }}</option>
                    </select>
                  </div>
                  <div>
                    <label class="block text-[10px] text-text-muted uppercase tracking-wider mb-1">{{ t('ladaPanel.encodingPreset') }}</label>
                    <select v-model="settings.encoding_preset" class="settings-input w-full">
                      <option v-for="p in mergedEncodingPresets" :key="p.id" :value="p.id">{{ p.name }}</option>
                    </select>
                  </div>
                </div>
              </div>

              <div class="flex gap-3 pt-2">
                <VuiSubmitButton
                  class="flex-1"
                  size="lg"
                  :status="submitStatus"
                  :progress="submitProgress"
                  :disabled="!selectedSubmitPath"
                  :idle-label="t('ladaPanel.start')"
                  :success-label="t('ladaPanel.submitQueued')"
                  :error-label="t('ladaPanel.submitFailed')"
                  @click="handleSubmitJob"
                />
                <VuiButton variant="outlined" color="secondary" size="large" @click="handleClose">
                  {{ t('common.cancel') }}
                </VuiButton>
              </div>
            </div>
          </template>
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

.panel-topbar__close {
  width: 2.1rem;
  height: 2.1rem;
  flex: none;
  border-radius: 0.7rem;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(255, 255, 255, 0.04);
  color: var(--color-text-secondary);
  transition: all 0.18s ease;
}

.panel-topbar__close:hover {
  color: var(--color-text-primary);
  border-color: rgba(0, 117, 255, 0.32);
  background: rgba(0, 117, 255, 0.12);
}

.settings-input {
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 0.6rem;
  color: var(--color-text-primary);
  min-height: 2.25rem;
  padding: 0 0.75rem;
}

.settings-input option {
  background: #0a0e23;
  color: #fff;
}
</style>
