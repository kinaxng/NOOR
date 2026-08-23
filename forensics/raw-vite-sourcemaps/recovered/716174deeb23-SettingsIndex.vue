<script setup lang="ts">
import { ref, computed } from 'vue'
import { defineAsyncComponent } from 'vue'

const SystemSettings = defineAsyncComponent(() => import('./SystemSettings.vue'))
const StorageSettings = defineAsyncComponent(() => import('./StorageSettings.vue'))
const LadaSettings = defineAsyncComponent(() => import('./LadaSettings.vue'))
const WhisperSettings = defineAsyncComponent(() => import('./WhisperSettings.vue'))

const activeTab = ref<'system' | 'storage' | 'lada' | 'whisper'>('system')

const tabs = [
  { key: 'system' as const, label: '系统', component: SystemSettings },
  { key: 'storage' as const, label: '存储', component: StorageSettings },
  { key: 'lada' as const, label: 'LADA', component: LadaSettings },
  { key: 'whisper' as const, label: 'Whisper', component: WhisperSettings },
]

const currentComponent = computed(() => {
  return tabs.find(t => t.key === activeTab.value)?.component || SystemSettings
})

function switchTab(tab: 'system' | 'storage' | 'lada' | 'whisper') {
  activeTab.value = tab
}
</script>

<template>
  <div class="max-w-[1400px] mx-auto space-y-6 animate-fade-in">
    <!-- Tab Bar -->
    <div class="settings-tabs">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        @click="switchTab(tab.key)"
        class="settings-tab"
        :class="{ 'settings-tab--active': activeTab === tab.key }"
      >
        {{ tab.label }}
      </button>
    </div>

    <!-- Tab Content -->
    <Suspense>
      <component :is="currentComponent" :key="activeTab" />
      <template #fallback>
        <div class="flex items-center justify-center py-24">
          <div class="w-8 h-8 border-2 rounded-full animate-spin" style="border-color: #0075FF; border-top-color: transparent;"></div>
        </div>
      </template>
    </Suspense>
  </div>
</template>

<style scoped>
.settings-tabs {
  display: flex;
  gap: 0.25rem;
  padding: 0.375rem;
  border-radius: var(--radius-xl);
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.06);
  width: fit-content;
}

.settings-tab {
  padding: 0.5rem 1.5rem;
  border-radius: var(--radius-lg);
  font-family: var(--font-display);
  font-size: 0.875rem;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.4);
  background: transparent;
  border: none;
  cursor: pointer;
  transition: all var(--transition-fast);
}

.settings-tab:hover {
  color: rgba(255, 255, 255, 0.7);
  background: rgba(255, 255, 255, 0.04);
}

.settings-tab--active {
  background: #0075FF;
  color: #FFFFFF;
  box-shadow: 0 4px 12px rgba(0, 117, 255, 0.3);
}
</style>
