<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import api from '../../api'
import FieldRow from '../../components/ui/FieldRow/FieldRow.vue'
import SettingsSwitch from '../../components/ui/SettingsSwitch.vue'
import VuiBadge from '../../components/ui/Badge/VuiBadge.vue'
import VuiButton from '../../components/ui/Button/VuiButton.vue'
import { useI18n } from '../../composables/useI18n'
import { useToast } from '../../composables/useToast'

type IndexStatus = {
  index_exists: boolean
  indexed_count: number
  index_updated_at: number | null
  configured_paths: string[]
  index_enabled: boolean
}

const { t } = useI18n()
const toast = useToast()

const loading = ref(false)
const saving = ref(false)
const rebuilding = ref(false)
const libraryPaths = ref('')
const indexEnabled = ref(false)
const matchFuzzy = ref(false)
const indexStatus = ref<IndexStatus | null>(null)

const updatedAt = computed(() => {
  const value = indexStatus.value?.index_updated_at
  if (!value) return t('settings.system.never')
  return new Date(value * 1000).toLocaleString()
})

onMounted(load)

async function load() {
  loading.value = true
  try {
    const [configResponse, statusResponse] = await Promise.all([
      api.get('/local-library/config'),
      api.get('/local-library/index/status'),
    ])
    const config = configResponse.data?.config || {}
    libraryPaths.value = String(config.library_paths || '')
    indexEnabled.value = Boolean(config.index_enabled)
    matchFuzzy.value = Boolean(config.match_fuzzy)
    indexStatus.value = statusResponse.data
  } catch (error: any) {
    toast.error(t('settings.saveFailed', { error: error?.response?.data?.detail || error?.message || 'load failed' }))
  } finally {
    loading.value = false
  }
}

async function save() {
  saving.value = true
  try {
    await api.post('/local-library/config', {
      config: {
        library_paths: libraryPaths.value,
        index_enabled: indexEnabled.value,
        match_fuzzy: matchFuzzy.value,
      },
    })
    await refreshStatus()
    toast.success(t('settings.saveSuccess'))
  } catch (error: any) {
    toast.error(t('settings.saveFailed', { error: error?.response?.data?.detail || error?.message || 'save failed' }))
  } finally {
    saving.value = false
  }
}

async function refreshStatus() {
  const response = await api.get('/local-library/index/status')
  indexStatus.value = response.data
}

async function rebuildIndex() {
  rebuilding.value = true
  try {
    const response = await api.post('/local-library/index/rebuild')
    await refreshStatus()
    toast.success(t('settings.system.rebuildDone', {
      count: response.data?.indexed_files || 0,
      seconds: response.data?.elapsed_seconds || 0,
    }))
  } catch (error: any) {
    toast.error(t('settings.saveFailed', { error: error?.response?.data?.detail || error?.message || 'rebuild failed' }))
  } finally {
    rebuilding.value = false
  }
}
</script>

<template>
  <div class="subtitle-library-settings">
    <div v-if="loading" class="settings-loading">
      <span class="settings-spinner" />
    </div>

    <div v-else class="settings-cards">
      <section class="settings-card">
        <header class="settings-card__head">
          <h2 class="settings-card__title">{{ t('settings.system.localSubtitleLibraryTitle') }}</h2>
          <p class="settings-card__subtitle">{{ t('settings.system.pathsDesc') }}</p>
        </header>

        <div class="settings-form">
          <FieldRow :label="t('settings.system.paths')" :description="t('settings.system.pathsDesc')">
            <textarea
              v-model="libraryPaths"
              class="settings-textarea"
              rows="6"
              placeholder="/volume1/subtitles"
            />
          </FieldRow>

          <FieldRow :label="t('settings.system.indexToggleLabel')" :description="t('settings.system.indexToggleDesc')">
            <div class="switch-control">
              <SettingsSwitch v-model="indexEnabled" />
              <span>{{ t('settings.system.indexToggleValue') }}</span>
            </div>
          </FieldRow>

          <FieldRow :label="t('settings.system.fuzzyMatchLabel')" :description="t('settings.system.fuzzyMatchDesc')">
            <div class="switch-control">
              <SettingsSwitch v-model="matchFuzzy" />
              <span>{{ t('settings.system.fuzzyMatchValue') }}</span>
            </div>
          </FieldRow>

          <div class="settings-actions">
            <VuiButton variant="gradient" color="info" size="small" :loading="saving" @click="save">
              {{ saving ? t('settings.saving') : t('settings.save') }}
            </VuiButton>
          </div>
        </div>
      </section>

      <section class="settings-card">
        <header class="settings-card__head settings-card__head--row">
          <div>
            <h2 class="settings-card__title">{{ t('settings.system.subtitleIndexTitle') }}</h2>
            <p class="settings-card__subtitle">{{ t('settings.system.configuredPaths') }}：{{ indexStatus?.configured_paths?.length || 0 }}</p>
          </div>
          <VuiBadge :color="indexStatus?.index_exists ? 'success' : 'warning'" variant="gradient" size="sm">
            {{ indexStatus?.index_exists ? t('settings.system.indexReady') : t('settings.system.indexMissing') }}
          </VuiBadge>
        </header>

        <div class="index-facts">
          <div class="index-fact">
            <span>{{ t('settings.system.indexedFiles') }}</span>
            <strong>{{ indexStatus?.indexed_count || 0 }}</strong>
          </div>
          <div class="index-fact">
            <span>{{ t('settings.system.updatedAt') }}</span>
            <strong>{{ updatedAt }}</strong>
          </div>
        </div>

        <div class="settings-actions">
          <VuiButton variant="contained" color="secondary" size="small" :loading="rebuilding" @click="rebuildIndex">
            {{ rebuilding ? t('settings.rebuilding') : t('settings.system.rebuildIndex') }}
          </VuiButton>
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.subtitle-library-settings,
.settings-cards {
  width: 100%;
}

.settings-cards {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.settings-card {
  overflow: hidden;
  border: 1px solid var(--color-border-subtle);
  border-radius: var(--radius-lg);
  background: var(--color-surface-card);
}

.settings-card__head {
  padding: 1rem 1.1rem;
  border-bottom: 1px solid var(--color-border-subtle);
}

.settings-card__head--row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
}

.settings-card__title {
  margin: 0;
  color: var(--color-text-primary);
  font-family: var(--font-display);
  font-size: 0.95rem;
  font-weight: 650;
}

.settings-card__subtitle {
  margin: 0.3rem 0 0;
  color: var(--color-text-tertiary);
  font-size: 0.72rem;
  line-height: 1.5;
}

.settings-form {
  padding: 0 1.1rem 1rem;
}

.settings-textarea {
  width: 100%;
  min-height: 8rem;
  resize: vertical;
  border: 1px solid var(--color-border-subtle);
  border-radius: var(--radius-md);
  padding: 0.75rem;
  color: var(--color-text-primary);
  background: rgba(0, 0, 0, 0.2);
  font: 0.78rem/1.6 var(--font-mono);
}

.settings-textarea:focus {
  outline: none;
  border-color: rgba(0, 117, 255, 0.65);
  box-shadow: 0 0 0 3px rgba(0, 117, 255, 0.12);
}

.switch-control {
  display: flex;
  align-items: center;
  gap: 0.65rem;
  min-height: 2.5rem;
  color: var(--color-text-secondary);
  font-size: 0.78rem;
}

.settings-actions {
  display: flex;
  justify-content: flex-end;
  padding-top: 1rem;
}

.index-facts {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.75rem;
  padding: 1rem 1.1rem 0;
}

.index-fact {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
  min-width: 0;
  padding: 0.75rem;
  border: 1px solid var(--color-border-subtle);
  border-radius: var(--radius-md);
  background: rgba(255, 255, 255, 0.025);
}

.index-fact span {
  color: var(--color-text-tertiary);
  font-size: 0.68rem;
}

.index-fact strong {
  overflow-wrap: anywhere;
  color: var(--color-text-primary);
  font-size: 0.82rem;
  font-weight: 600;
}

.settings-card > .settings-actions {
  padding: 1rem 1.1rem;
}

.settings-loading {
  display: grid;
  min-height: 12rem;
  place-items: center;
}

.settings-spinner {
  width: 2rem;
  height: 2rem;
  border: 2px solid rgba(255, 255, 255, 0.12);
  border-top-color: #0075ff;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

@media (max-width: 640px) {
  .index-facts {
    grid-template-columns: 1fr;
  }
}
</style>
