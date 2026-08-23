<script setup lang="ts">
import type { MediaItemDetail } from '../../api/types'

interface ModelOption { id: string; name: string }

interface VariantRow {
  id: string
  path: string
  name: string
  dir: string
}

interface LadaSettings {
  detection_model: string
  restoration_model: string
  encoding_preset: string
}

const props = defineProps<{
  open: boolean
  detail: MediaItemDetail | null
  loading: boolean
  error: string | null
  variantRows: VariantRow[]
  selectedPath: string
  settings: LadaSettings
  detectionModels: ModelOption[]
  restorationModels: ModelOption[]
  encodingPresets: ModelOption[]
  submitStatus: 'idle' | 'submitting' | 'success' | 'error'
  submitProgress: number
}>()

const emit = defineEmits<{
  close: []
  'update:selectedPath': [path: string]
  'update:settings': [settings: LadaSettings]
  submit: []
}>()
</script>

<template>
  <Teleport to="body">
    <Transition enter-active-class="transition-opacity duration-200" enter-from-class="opacity-0" leave-active-class="transition-opacity duration-200" leave-to-class="opacity-0">
      <div v-if="open" class="fixed inset-0 z-50 flex justify-end">
        <div class="absolute inset-0 bg-black/80 backdrop-blur-sm" @click="emit('close')" />
        <div class="relative bg-(--ui-bg) border-l border-(--ui-border) flex flex-col overflow-hidden shadow-2xl h-full w-full max-w-md">
          <!-- Loading -->
          <div v-if="loading" class="flex items-center justify-center flex-1">
            <UIcon name="i-heroicons-arrow-path-20-solid" class="w-8 h-8 animate-spin text-(--ui-text-muted)" />
          </div>
          <!-- Error -->
          <div v-else-if="error" class="flex flex-col items-center justify-center flex-1 p-8 text-center">
            <p class="text-(--ui-error) text-lg mb-2">错误</p>
            <p class="text-(--ui-text-muted) text-sm max-w-md">{{ error }}</p>
            <UButton color="neutral" variant="ghost" size="sm" class="mt-4" @click="emit('close')">关闭</UButton>
          </div>
          <!-- Content -->
          <template v-else-if="detail">
            <div class="flex-1 overflow-y-auto p-4 space-y-4 relative">
              <!-- Hero -->
              <div class="detail-hero shrink-0 -mx-4 -mt-4">
                <img v-if="detail.backdrop_path || detail.poster_path" :src="detail.backdrop_path || detail.poster_path" :alt="detail.name" />
                <div class="detail-hero__actions">
                  <UButton color="white" variant="ghost" icon="i-heroicons-x-mark-20-solid" class="detail-close" @click="emit('close')" />
                </div>
                <div class="absolute bottom-4 left-4 right-4 z-10">
                  <h2 class="text-xl font-bold text-white truncate">{{ detail.name }}</h2>
                  <p class="text-xs text-white/70 mt-1">LADA 修复</p>
                </div>
              </div>
              <!-- File selector -->
              <div v-if="variantRows.length > 1">
                <label class="text-xs text-(--ui-text-muted) uppercase tracking-wider mb-1.5 block">选择文件</label>
                <select
                  :value="selectedPath"
                  class="w-full h-9 px-3 rounded-lg border border-(--ui-border) bg-(--ui-bg) text-sm text-(--ui-text) outline-none focus:border-(--ui-border-accented)"
                  @change="emit('update:selectedPath', ($event.target as HTMLSelectElement).value)"
                >
                  <option v-for="v in variantRows" :key="v.path" :value="v.path">{{ v.name }}</option>
                </select>
              </div>
              <!-- Settings -->
              <div>
                <label class="text-xs text-(--ui-text-muted) uppercase tracking-wider mb-1.5 block">检测模型</label>
                <select
                  :value="settings.detection_model"
                  class="w-full h-9 px-3 rounded-lg border border-(--ui-border) bg-(--ui-bg) text-sm text-(--ui-text) outline-none focus:border-(--ui-border-accented)"
                  @change="emit('update:settings', { ...settings, detection_model: ($event.target as HTMLSelectElement).value })"
                >
                  <option v-for="m in detectionModels" :key="m.id" :value="m.id">{{ m.name }} ({{ m.id }})</option>
                </select>
              </div>
              <div>
                <label class="text-xs text-(--ui-text-muted) uppercase tracking-wider mb-1.5 block">修复模型</label>
                <select
                  :value="settings.restoration_model"
                  class="w-full h-9 px-3 rounded-lg border border-(--ui-border) bg-(--ui-bg) text-sm text-(--ui-text) outline-none focus:border-(--ui-border-accented)"
                  @change="emit('update:settings', { ...settings, restoration_model: ($event.target as HTMLSelectElement).value })"
                >
                  <option v-for="m in restorationModels" :key="m.id" :value="m.id">{{ m.name }}</option>
                </select>
              </div>
              <div>
                <label class="text-xs text-(--ui-text-muted) uppercase tracking-wider mb-1.5 block">编码预设</label>
                <select
                  :value="settings.encoding_preset"
                  class="w-full h-9 px-3 rounded-lg border border-(--ui-border) bg-(--ui-bg) text-sm text-(--ui-text) outline-none focus:border-(--ui-border-accented)"
                  @change="emit('update:settings', { ...settings, encoding_preset: ($event.target as HTMLSelectElement).value })"
                >
                  <option v-for="p in encodingPresets" :key="p.id" :value="p.id">{{ p.name }}</option>
                </select>
              </div>
              <!-- Submit -->
              <div class="flex gap-3 pt-2">
                <UButton color="primary" class="flex-1" :loading="submitStatus === 'submitting'" :disabled="!selectedPath || submitStatus === 'submitting'" @click="emit('submit')">
                  {{ submitStatus === 'success' ? '已提交' : submitStatus === 'error' ? '重试' : '提交修复任务' }}
                </UButton>
                <UButton color="neutral" variant="ghost" @click="emit('close')">取消</UButton>
              </div>
              <!-- Progress -->
              <div v-if="submitStatus === 'submitting'" class="mt-2">
                <UProgress :value="submitProgress" color="primary" size="sm" />
              </div>
            </div>
          </template>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>
