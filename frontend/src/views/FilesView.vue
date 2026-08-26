<script setup lang="ts">
import { computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import VisionTabs from '../components/ui/Tabs.vue'
import ActorManagementView from './ActorManagementView.vue'
import HardlinkView from './HardlinkView.vue'
import { useI18n } from '../composables/useI18n'

type FileTab = 'hardlinks' | 'actors'

const route = useRoute()
const router = useRouter()
const { t, i18nVersion } = useI18n()

const activeTab = computed<FileTab>(() => {
  const tab = String(route.params.fileTab || 'hardlinks')
  return tab === 'actors' ? 'actors' : 'hardlinks'
})

const tabs = computed(() => {
  void i18nVersion.value
  return [
    { key: 'hardlinks' as FileTab, label: t('files.tab.hardlinks') },
    { key: 'actors' as FileTab, label: t('files.tab.actors') },
  ]
})

watch(activeTab, (tab) => {
  if (!route.params.fileTab) {
    router.replace(`/files/${tab}`)
  }
}, { immediate: true })

function switchTab(tab: FileTab) {
  if (tab === activeTab.value) return
  router.push(`/files/${tab}`)
}
</script>

<template>
  <div class="files-page animate-fade-in">
    <header class="files-header" :aria-label="t('files.title')">
      <h1 class="files-title">{{ t('files.title') }}</h1>
      <VisionTabs
        :model-value="activeTab"
        :tabs="tabs"
        @update:model-value="switchTab($event as FileTab)"
      />
    </header>

    <HardlinkView v-if="activeTab === 'hardlinks'" />

    <ActorManagementView v-else />
  </div>
</template>

<style scoped>
.files-page {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.files-header {
  display: flex;
  align-items: center;
  justify-content: flex-start;
  gap: 1rem;
}

.files-title {
  font-family: var(--font-display);
  font-size: 1.35rem;
  font-weight: 700;
  color: var(--color-text-primary);
}

@media (max-width: 720px) {
  .files-header {
    align-items: stretch;
    flex-direction: column;
  }

}
</style>
