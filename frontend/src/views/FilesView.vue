
<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import BaseIcon from '../components/noor/BaseIcon.vue'
import HardlinkView from './HardlinkView.vue'
import ActorManagementView from './ActorManagementView.vue'
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
    { key: 'hardlinks' as FileTab, label: t('files.tab.hardlinks'), icon: 'hardlink' },
    { key: 'actors' as FileTab, label: t('files.tab.actors'), icon: 'user' },
  ]
})

function switchTab(tab: FileTab) {
  if (tab === activeTab.value) return
  router.push(`/files/${tab}`)
}
</script>

<template>
  <div class="files-page animate-fade-in">
    <header class="files-header">
      <h1 class="files-title">{{ t('files.title') }}</h1>
      <div class="files-tabs" role="tablist" aria-label="Files">
        <button
          v-for="tab in tabs"
          :key="tab.key"
          type="button"
          class="files-tab"
          :class="{ 'is-active': activeTab === tab.key }"
          role="tab"
          :aria-selected="activeTab === tab.key"
          @click="switchTab(tab.key)"
        >
          <BaseIcon :name="tab.icon" class="files-tab__icon" />
          <span>{{ tab.label }}</span>
        </button>
      </div>
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
  justify-content: space-between;
  gap: 1rem;
}

.files-title {
  font-family: var(--font-display);
  font-size: 1.35rem;
  font-weight: 700;
  color: var(--color-text-primary);
}

.files-tabs {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.25rem;
  border: 1px solid var(--color-border-subtle);
  border-radius: var(--radius-lg);
  background: rgba(255, 255, 255, 0.04);
}

.files-tab {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  min-height: 2rem;
  padding: 0 0.75rem;
  border: 0;
  border-radius: var(--radius-md);
  color: var(--color-text-secondary);
  background: transparent;
  font-size: 0.82rem;
  cursor: pointer;
}

.files-tab:hover,
.files-tab.is-active {
  color: var(--color-text-primary);
  background: rgba(255, 255, 255, 0.08);
}

.files-tab__icon {
  width: 1rem;
  height: 1rem;
}

.files-empty {
  min-height: 16rem;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  color: var(--color-text-muted);
}

.files-empty__icon {
  width: 1.1rem;
  height: 1.1rem;
}

@media (max-width: 720px) {
  .files-header {
    align-items: stretch;
    flex-direction: column;
  }

  .files-tabs {
    width: 100%;
  }

  .files-tab {
    flex: 1 1 0;
    justify-content: center;
  }
}
</style>


