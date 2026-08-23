<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import VisionTabs from '../../components/vision/VisionTabs/VisionTabs.vue'
import { defineAsyncComponent } from 'vue'

const SystemSettings = defineAsyncComponent(() => import('./SystemSettings.vue'))
const StorageSettings = defineAsyncComponent(() => import('./StorageSettings.vue'))
const LadaSettings = defineAsyncComponent(() => import('./LadaSettings.vue'))
const WhisperSettings = defineAsyncComponent(() => import('./WhisperSettings.vue'))

const activeTab = ref<'system' | 'storage' | 'lada' | 'whisper'>('system')

// Preload non-active tab chunks after initial paint
onMounted(() => {
  setTimeout(() => {
    import('./StorageSettings.vue')
    import('./LadaSettings.vue')
    import('./WhisperSettings.vue')
  }, 500)
})

const tabs = [
  { key: 'system' as const, label: '系统', component: SystemSettings },
  { key: 'storage' as const, label: '存储', component: StorageSettings },
  { key: 'lada' as const, label: 'LADA', component: LadaSettings },
  { key: 'whisper' as const, label: 'Whisper', component: WhisperSettings },
]

const currentComponent = computed(() => {
  return tabs.find(t => t.key === activeTab.value)?.component || SystemSettings
})
</script>

<template>
  <div class="w-full space-y-6 animate-fade-in">
    <!-- Tab Bar -->
    <VisionTabs v-model="activeTab" :tabs="tabs.map(t => ({ key: t.key, label: t.label }))" />

    <!-- Tab Content -->
    <component :is="currentComponent" :key="activeTab" />
  </div>
</template>
