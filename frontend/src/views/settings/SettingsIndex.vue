<script setup lang="ts">
import { computed, defineAsyncComponent, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import VisionTabs from '../../components/ui/Tabs.vue'
import { useI18n } from '../../composables/useI18n'
import { useRouteTabs } from '../../composables/useRouteTabs'

const { t, i18nVersion } = useI18n()
const route = useRoute()
const router = useRouter()

const SystemSettings = defineAsyncComponent(() => import('./SystemSettings.vue'))
const StorageSettings = defineAsyncComponent(() => import('./StorageSettings.vue'))
const LadaSettings = defineAsyncComponent(() => import('./LadaSettings.vue'))
const FaceFusionSettings = defineAsyncComponent(() => import('./FaceFusionSettings.vue'))
const WhisperSettings = defineAsyncComponent(() => import('./WhisperSettings.vue'))
const LocalSubtitleLibrarySettings = defineAsyncComponent(() => import('./LocalSubtitleLibrarySettings.vue'))
const PluginManager = defineAsyncComponent(() => import('../PluginManager.vue'))

type SettingsTab = 'system' | 'storage' | 'lada' | 'facefusion' | 'whisper' | 'local-library' | 'plugins'
const activeTab = useRouteTabs<SettingsTab>({
  route,
  router,
  basePath: '/settings',
  paramName: 'settingsTab',
  tabs: ['system', 'storage', 'lada', 'facefusion', 'whisper', 'local-library', 'plugins'],
  defaultTab: 'system',
})

onMounted(() => {
  setTimeout(() => {
    import('./StorageSettings.vue')
    import('./LadaSettings.vue')
    import('./FaceFusionSettings.vue')
    import('./WhisperSettings.vue')
    import('./LocalSubtitleLibrarySettings.vue')
    import('../PluginManager.vue')
  }, 500)
})

const tabs = computed(() => {
  void i18nVersion.value
  return [
    { key: 'system' as const, label: t('settings.tab.system'), component: SystemSettings },
    { key: 'storage' as const, label: t('settings.tab.storage'), component: StorageSettings },
    { key: 'lada' as const, label: t('settings.tab.lada'), component: LadaSettings },
    { key: 'facefusion' as const, label: t('settings.tab.facefusion'), component: FaceFusionSettings },
    { key: 'whisper' as const, label: t('settings.tab.whisper'), component: WhisperSettings },
    { key: 'local-library' as const, label: t('settings.tab.local-library'), component: LocalSubtitleLibrarySettings },
    { key: 'plugins' as const, label: '插件', component: PluginManager },
  ]
})

const currentComponent = computed(() => {
  return tabs.value.find(tab => tab.key === activeTab.value)?.component || SystemSettings
})
</script>

<template>
  <div class="settings-page">
    <div class="settings-page__header">
      <VisionTabs v-model="activeTab" :tabs="tabs.map(tab => ({ key: tab.key, label: tab.label }))" />
    </div>

    <div class="settings-page__content">
      <component :is="currentComponent" :key="activeTab" />
    </div>
  </div>
</template>

<style scoped>
.settings-page {
  max-width: 896px;
  margin: 0 auto;
  width: 100%;
  overflow-x: hidden;
}

.settings-page__header {
  display: flex;
  flex-direction: column;
  gap: 0.65rem;
  margin-bottom: 1rem;
}

@media (max-width: 768px) {
}
</style>
