<script setup lang="ts">
import { ref, onMounted } from 'vue'
import api from '../../api'
import { useToast } from '../../composables/useToast'
import { useBlurCover } from '../../composables/useBlurCover'
import { useI18n } from '../../composables/useI18n'
import FieldRow from '../../components/ui/FieldRow/FieldRow.vue'
import VuiButton from '../../components/ui/Button/VuiButton.vue'
import VuiBadge from '../../components/ui/Badge/VuiBadge.vue'
import BaseIcon from '../../components/noor/BaseIcon.vue'
import SettingsSwitch from '../../components/ui/SettingsSwitch.vue'

const toast = useToast()
const { blurEnabled, setBlur } = useBlurCover()
const { t, currentLang } = useI18n()

const loading = ref(false)
const embySaving = ref(false)
const localSaving = ref(false)
const networkSaving = ref(false)
const testing = ref(false)
const connectionStatus = ref<{ ok: boolean; message: string } | null>(null)

// Emby / media library settings
const serverUrl = ref('')
const apiKey = ref('')
const userId = ref('')
const enabledLibraryIds = ref<string[]>([])
const availableLibraries = ref<{ id: string; name: string }[]>([])
const librariesLoaded = ref(false)

// Local library settings
const localConfig = ref<Record<string, unknown>>({})
const indexStatus = ref<{
  index_exists: boolean
  indexed_count: number
  index_updated_at: number | null
  configured_paths: string[]
  index_enabled: boolean
} | null>(null)
const rebuilding = ref(false)
const rebuildResult = ref<{ indexed_files: number; elapsed_seconds: number } | null>(null)

// Network settings
const accelerationMode = ref('mirror')
const httpProxy = ref('')
const githubMirror = ref('https://ghproxy.com')
const hfMirror = ref('https://hf-mirror.com')
const pipMirror = ref('https://pypi.tuna.tsinghua.edu.cn/simple')
const hfToken = ref('')

onMounted(async () => {
  await loadSettings()
})

async function loadSettings() {
  loading.value = true
  try {
    // Load media library config
    try {
      const mlRes = await fetch('/api/media-library/config')
      if (mlRes.ok) {
        const mlData = await mlRes.json()
        const cfg = mlData.config || {}
        serverUrl.value = cfg.server_url || ''
        apiKey.value = cfg.api_key || ''
        userId.value = cfg.user_id || ''
        const ids = cfg.enabled_library_ids || ''
        enabledLibraryIds.value = ids ? ids.split(',').map((s: string) => s.trim()).filter(Boolean) : []

        // Auto-fetch libraries if credentials exist
        if (serverUrl.value && apiKey.value) {
          await fetchLibraries()
        }
      }
    } catch (e) {
      console.error('Failed to load media library config:', e)
    }

    // Load local library config
    try {
      const llRes = await fetch('/api/local-library/config')
      if (llRes.ok) {
        const llData = await llRes.json()
        localConfig.value = llData.config || {}
      }
    } catch (e) {
      console.error('Failed to load local library config:', e)
    }

    await fetchIndexStatus()

    // Load network settings
    try {
      const resp = await api.get('/settings')
      const data = resp.data
      if (data.network) {
        accelerationMode.value = data.network.acceleration_mode || 'mirror'
        httpProxy.value = data.network.http_proxy || ''
        githubMirror.value = data.network.github_mirror || 'https://ghproxy.com'
        hfMirror.value = data.network.hf_mirror || 'https://hf-mirror.com'
        pipMirror.value = data.network.pip_mirror || 'https://pypi.tuna.tsinghua.edu.cn/simple'
        hfToken.value = data.network.hf_token || ''
      }
    } catch (e) {
      console.error('Failed to load network settings:', e)
    }
  } finally {
    loading.value = false
  }
}

async function fetchIndexStatus() {
  try {
    const res = await fetch('/api/local-library/index/status')
    if (res.ok) {
      indexStatus.value = await res.json()
    }
  } catch {}
}

async function fetchLibraries() {
  loadingLibraries.value = true
  try {
    const res = await fetch('/api/media-library/libraries')
    if (res.ok) {
      const data = await res.json()
      availableLibraries.value = (data.libraries || []).map((lib: any) => ({
        id: lib.id,
        name: lib.name,
      }))
      librariesLoaded.value = true
    } else {
      console.error('fetchLibraries failed:', res.status, await res.text())
    }
  } catch (e) {
    console.error('fetchLibraries error:', e)
  } finally {
    loadingLibraries.value = false
  }
}

const loadingLibraries = ref(false)

async function testConnection() {
  testing.value = true
  connectionStatus.value = null
  availableLibraries.value = []
  librariesLoaded.value = false
  try {
    const res = await fetch('/api/media-library/test', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        server_url: serverUrl.value,
        api_key: apiKey.value,
        user_id: userId.value,
      })
    })
    const data = await res.json()
    connectionStatus.value = { ok: data.ok, message: data.message }

    if (data.ok) {
      toast.success(t('settings.system.connectionSuccess'))
      if (data.libraries && data.libraries.length > 0) {
        availableLibraries.value = data.libraries
      }
      await fetchLibraries()
    } else {
      toast.error(data.message || t('settings.system.connectionFailed'))
    }
  } catch (e) {
    connectionStatus.value = { ok: false, message: t('settings.system.connectionFailed') }
    toast.error(t('settings.system.connectionFailed'))
  } finally {
    testing.value = false
  }
}

async function saveEmby() {
  embySaving.value = true
  try {
    const res = await fetch('/api/media-library/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        server_url: serverUrl.value,
        api_key: apiKey.value,
        user_id: userId.value,
        enabled_library_ids: enabledLibraryIds.value.join(','),
      })
    })
    if (!res.ok) {
      const errText = await res.text()
      throw new Error(errText || `HTTP ${res.status}`)
    }
    toast.success(t('settings.saveSuccess'))
  } catch (e: any) {
    toast.error(t('settings.saveFailed', { error: e.message }))
  } finally {
    embySaving.value = false
  }
}

async function saveLocalLibrary(config: Record<string, unknown>) {
  try {
    await fetch('/api/local-library/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ config }),
    })
  } catch {}
}

async function saveNetwork() {
  networkSaving.value = true
  try {
    await api.put('/settings/network', {
      acceleration_mode: accelerationMode.value,
      http_proxy: httpProxy.value,
      github_mirror: githubMirror.value,
      hf_mirror: hfMirror.value,
      pip_mirror: pipMirror.value,
      hf_token: hfToken.value,
    })
    toast.success(t('settings.saveNetwork'))
  } catch {
    toast.error(t('settings.saveNetworkFailed'))
  } finally {
    networkSaving.value = false
  }
}

function toggleLibrary(libId: string) {
  enabledLibraryIds.value = enabledLibraryIds.value[0] === libId ? [] : [libId]
}

function toggleLocalSwitch(key: string) {
  const newVal = !localConfig.value[key]
  localConfig.value = { ...localConfig.value, [key]: newVal }
  saveLocalLibrary(localConfig.value)
  if (key === 'index_enabled' && newVal) {
    setTimeout(fetchIndexStatus, 500)
  }
}

function handleLocalFormChange(config: Record<string, unknown>) {
  localConfig.value = config
}

async function saveLocalLibraryNow() {
  localSaving.value = true
  try {
    await saveLocalLibrary(localConfig.value)
    toast.success(t('settings.saveSuccess'))
  } catch (e: any) {
    toast.error(t('settings.saveFailed', { error: e.message }))
  } finally {
    localSaving.value = false
  }
}

async function rebuildIndex() {
  rebuilding.value = true
  rebuildResult.value = null
  try {
    const res = await fetch('/api/local-library/index/rebuild', { method: 'POST' })
    if (res.ok) {
      rebuildResult.value = await res.json()
      await fetchIndexStatus()
    }
  } finally {
    rebuilding.value = false
  }
  await saveLocalLibrary({ ...localConfig.value })
}

function formatTime(ts: number | null): string {
  if (!ts) return t('settings.system.never')
  return new Date(ts * 1000).toLocaleString(currentLang.value === 'zh' ? 'zh-CN' : 'en-US')
}
</script>

<template>
  <div class="system-settings">
    <!-- Loading -->
    <div v-if="loading" class="flex items-center justify-center py-16">
      <div class="w-8 h-8 border-2 rounded-full animate-spin border-[#0075FF] border-t-transparent"></div>
    </div>

    <div v-else class="settings-cards">
      <!-- Emby / Jellyfin 媒体库 -->
      <div class="settings-card">
        <div class="settings-card__head"><h2 class="settings-card__title">{{ t('settings.system.mediaServerTitle') }}</h2><p class="settings-card__subtitle">连接媒体服务器并选择当前使用的媒体库</p></div>

        <div class="settings-form">
          <FieldRow :label="t('settings.emby.server')" :description="t('settings.emby.serverDesc')">
            <input v-model="serverUrl" type="text" placeholder="http://localhost:8096" class="settings-input" />
          </FieldRow>

          <FieldRow :label="t('settings.emby.apiKey')" :description="t('settings.emby.apiKeyDesc')">
            <input v-model="apiKey" type="password" :placeholder="t('settings.emby.apiKeyPlaceholder')" class="settings-input" />
          </FieldRow>

          <FieldRow :label="t('settings.emby.userId')" :description="t('settings.emby.userIdDesc')">
            <input v-model="userId" type="text" :placeholder="t('settings.emby.userIdPlaceholder')" class="settings-input" />
          </FieldRow>

          <!-- Test Connection -->
          <FieldRow :label="t('settings.emby.connectionTest')" :description="t('settings.emby.connectionTestDesc')">
            <div class="flex items-center gap-3">
              <VuiButton variant="contained" color="secondary" size="small" customClass="settings-inline-action" :loading="testing" :disabled="!serverUrl || !apiKey" @click="testConnection">
                {{ testing ? t('settings.testing') : t('settings.emby.testConnection') }}
              </VuiButton>
              <VuiBadge
                v-if="connectionStatus"
                :color="connectionStatus.ok ? 'success' : 'error'"
                variant="gradient"
                size="sm"
              >
                {{ connectionStatus.message }}
              </VuiBadge>
            </div>
          </FieldRow>

          <!-- Library Selection -->
          <div class="field-row-full">
            <div class="field-row__label-col">
              <span class="field-row__label-text">{{ t('settings.emby.selectLibrary') }}</span>
              <span class="field-row__label-desc">{{ t('settings.emby.singleLibraryOnly') }}</span>
            </div>
            <div class="field-row__input-col">
              <!-- Loading libraries -->
              <div v-if="loadingLibraries" class="text-sm text-text-secondary">
                {{ t('settings.emby.loadingLibraries') }}
              </div>
              <!-- Libraries loaded -->
              <div v-else-if="availableLibraries.length > 0" class="flex flex-wrap gap-2">
                <button
                  v-for="lib in availableLibraries"
                  :key="lib.id"
                  @click="toggleLibrary(lib.id)"
                  class="library-chip settings-subtle-chip"
                  :class="{ 'library-chip--active': enabledLibraryIds.includes(lib.id) }"
                >
                  <BaseIcon name="library" class="w-3.5 h-3.5" />
                  {{ lib.name }}
                </button>
              </div>
              <!-- No libraries yet -->
              <div v-else class="text-sm text-text-secondary">
                {{ connectionStatus ? t('settings.emby.noLibraries') : t('settings.emby.fetchLibrariesHint') }}
              </div>
              <!-- Selected summary -->
              <p v-if="availableLibraries.length > 0" class="field-row__hint">
                {{ t('settings.emby.selectedSummary', { libs: enabledLibraryIds.length > 0 ? availableLibraries.filter(l => enabledLibraryIds.includes(l.id)).map(l => l.name).join(', ') : t('settings.emby.noneSelected') }) }}
              </p>
            </div>
          </div>

          <!-- Blur Toggle -->
          <FieldRow :label="t('settings.ui.blur')" :description="t('settings.ui.blurDesc')">
            <div class="flex items-center gap-3">
              <SettingsSwitch :model-value="blurEnabled" @update:model-value="setBlur" />
              <span class="text-sm text-text-secondary">
                {{ blurEnabled ? t('settings.ui.blurEnabled') : t('settings.ui.blurDisabled') }}
              </span>
            </div>
          </FieldRow>

          <div class="settings-card__actions settings-card__actions--end">
            <VuiButton variant="contained" color="info" size="small" customClass="settings-save-btn" :loading="embySaving" @click="saveEmby">
              {{ embySaving ? t('settings.loading') : t('common.save') }}
            </VuiButton>
          </div>
        </div>
      </div>

      <!-- 本地字幕库 -->
      <div class="settings-card">
        <div class="settings-card__head"><h2 class="settings-card__title">{{ t('settings.system.localSubtitleLibraryTitle') }}</h2><p class="settings-card__subtitle">管理本地字幕库路径与索引策略</p></div>

        <div class="settings-form">
          <!-- Index section (when enabled) -->
          <template v-if="localConfig['index_enabled']">
            <div class="index-section">
              <div class="index-section__header">
                <span class="index-section__title">{{ t('settings.system.subtitleIndexTitle') }}</span>
                <button class="btn-rebuild settings-subtle-btn" :disabled="rebuilding" @click="rebuildIndex">
                  {{ rebuilding ? t('settings.rebuilding') : t('settings.system.rebuildIndex') }}
                </button>
              </div>
              <div v-if="indexStatus" class="index-stats">
                <div class="index-stat">
                  <span class="index-stat__label">{{ t('settings.system.indexStatus') }}</span>
                  <span class="index-stat__value">
                    <span class="status-dot" :class="indexStatus.index_exists ? 'status-dot--ok' : 'status-dot--empty'" />
                    {{ indexStatus.index_exists ? t('settings.system.indexReady') : t('settings.system.indexMissing') }}
                  </span>
                </div>
                <div class="index-stat">
                  <span class="index-stat__label">{{ t('settings.system.indexedFiles') }}</span>
                  <span class="index-stat__value">{{ indexStatus.indexed_count.toLocaleString() }}</span>
                </div>
                <div class="index-stat">
                  <span class="index-stat__label">{{ t('settings.system.updatedAt') }}</span>
                  <span class="index-stat__value">{{ formatTime(indexStatus.index_updated_at) }}</span>
                </div>
                <div class="index-stat">
                  <span class="index-stat__label">{{ t('settings.system.configuredPaths') }}</span>
                  <span class="index-stat__value">{{ indexStatus.configured_paths.length }}</span>
                </div>
              </div>
              <div v-if="rebuildResult" class="rebuild-result">
                {{ t('settings.system.rebuildDone', { count: rebuildResult.indexed_files.toLocaleString(), seconds: rebuildResult.elapsed_seconds }) }}
              </div>
            </div>
          </template>

          <!-- 字幕库路径 -->
          <FieldRow :label="t('settings.system.paths')" :description="t('settings.system.pathsDesc')">
            <textarea
              class="settings-textarea"
              :value="(localConfig['library_paths'] as string) ?? ''"
              :placeholder="t('settings.system.pathsDesc')"
              rows="3"
              @input="e => { const updated = { ...localConfig, library_paths: (e.target as HTMLTextAreaElement).value }; handleLocalFormChange(updated) }"
            />
          </FieldRow>

          <!-- 搜索选项 -->
          <FieldRow :label="t('settings.system.indexToggleLabel')" :description="t('settings.system.indexToggleDesc')">
            <div class="flex items-center gap-3">
              <SettingsSwitch :model-value="!!localConfig['index_enabled']" @update:model-value="toggleLocalSwitch('index_enabled')" />
              <span class="text-sm text-text-secondary">{{ t('settings.system.indexToggleValue') }}</span>
            </div>
          </FieldRow>

          <FieldRow :label="t('settings.system.fuzzyMatchLabel')" :description="t('settings.system.fuzzyMatchDesc')">
            <div class="flex items-center gap-3">
              <SettingsSwitch :model-value="!!localConfig['match_fuzzy']" @update:model-value="toggleLocalSwitch('match_fuzzy')" />
              <span class="text-sm text-text-secondary">{{ t('settings.system.fuzzyMatchValue') }}</span>
            </div>
          </FieldRow>

          <div class="settings-card__actions settings-card__actions--end">
            <VuiButton variant="contained" color="info" size="small" customClass="settings-save-btn" :loading="localSaving" @click="saveLocalLibraryNow">
              {{ t('common.save') }}
            </VuiButton>
          </div>
        </div>
      </div>

      <!-- 网络加速 -->
      <div class="settings-card">
        <div class="settings-card__head"><h2 class="settings-card__title">{{ t('settings.network.title') }}</h2><p class="settings-card__subtitle">配置下载与模型访问所使用的网络加速方式</p></div>

        <div class="settings-form">
          <FieldRow :label="t('settings.network.mode')" :description="accelerationMode === 'none' ? t('settings.network.noneHint') : accelerationMode === 'proxy' ? t('settings.network.proxyHint2') : t('settings.network.mirrorHint')">
            <select v-model="accelerationMode" class="settings-input">
              <option value="none">{{ t('settings.network.mode.none') }}</option>
              <option value="proxy">{{ t('settings.network.mode.proxy') }}</option>
              <option value="mirror">{{ t('settings.network.mode.mirror') }}</option>
            </select>
          </FieldRow>

          <template v-if="accelerationMode === 'proxy'">
            <FieldRow :label="t('settings.network.proxy')" :description="t('settings.network.proxyDesc')">
              <input v-model="httpProxy" type="text" placeholder="http://127.0.0.1:7890" class="settings-input" />
            </FieldRow>
            <FieldRow :label="t('settings.network.hfToken')" :description="t('settings.network.hfTokenDesc')">
              <input v-model="hfToken" type="password" placeholder="hf_xxxxxxxxxxxx" class="settings-input" />
            </FieldRow>
          </template>

          <template v-if="accelerationMode === 'mirror'">
            <FieldRow :label="t('settings.network.githubMirror')" :description="t('settings.network.githubMirrorDesc')">
              <input v-model="githubMirror" type="text" placeholder="https://ghproxy.com" class="settings-input" />
            </FieldRow>
            <FieldRow :label="t('settings.network.hfMirror')" :description="t('settings.network.hfMirrorDesc')">
              <input v-model="hfMirror" type="text" placeholder="https://hf-mirror.com" class="settings-input" />
            </FieldRow>
            <FieldRow :label="t('settings.network.pipMirror')" :description="t('settings.network.pipMirrorDesc')">
              <input v-model="pipMirror" type="text" placeholder="https://pypi.tuna.tsinghua.edu.cn/simple" class="settings-input" />
            </FieldRow>
          </template>

          <div class="settings-card__actions settings-card__actions--end">
            <VuiButton variant="contained" color="info" size="small" customClass="settings-save-btn" :loading="networkSaving" @click="saveNetwork">
              {{ networkSaving ? t('settings.saving') : t('settings.saveNetwork') }}
            </VuiButton>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.system-settings {
  width: 100%;
}

.settings-cards {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.settings-card {
  border-radius: var(--radius-xl);
  padding: 1.35rem;
  overflow-x: hidden;
}

.settings-card__head {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  margin-bottom: 1.2rem;
}

.settings-card__title {
  font-family: var(--font-display);
  font-size: 0.875rem;
  font-weight: 700;
  color: rgba(255, 255, 255, 0.78);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.settings-card__subtitle {
  margin: 0;
  font-size: 0.7rem;
  color: rgba(255,255,255,0.34);
}

.settings-input {
  padding: 0.625rem 0.875rem;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: var(--radius-md);
  font-family: var(--font-display);
  font-size: 0.875rem;
  color: #FFFFFF;
  outline: none;
  transition: all var(--transition-fast);
  width: 100%;
  box-sizing: border-box;
}

.settings-input:focus {
  background: rgba(255, 255, 255, 0.07);
  border-color: rgba(0, 117, 255, 0.4);
  box-shadow: 0 0 0 3px rgba(0, 117, 255, 0.1);
}

.settings-textarea {
  padding: 0.625rem 0.875rem;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: var(--radius-md);
  font-family: var(--font-mono);
  font-size: 0.75rem;
  color: rgba(255, 255, 255, 0.8);
  outline: none;
  transition: all var(--transition-fast);
  width: 100%;
  resize: vertical;
  box-sizing: border-box;
}

.settings-textarea:focus {
  border-color: rgba(0, 117, 255, 0.4);
  box-shadow: 0 0 0 3px rgba(0, 117, 255, 0.1);
}

.field-row-full {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1.25rem;
  align-items: start;
  padding: 0.7rem 0;
  border-bottom: 1px solid rgba(255, 255, 255, 0.04);
}

.field-row__label-col {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
  padding-top: 0.55rem;
}

.field-row__label-text {
  font-family: var(--font-display);
  font-size: 0.8rem;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.75);
}

.field-row__label-desc {
  font-family: var(--font-display);
  font-size: 0.675rem;
  color: rgba(255, 255, 255, 0.28);
  line-height: 1.55;
}

.field-row__input-col {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.field-row__hint {
  font-family: var(--font-display);
  font-size: 0.625rem;
  color: rgba(255, 255, 255, 0.22);
  margin: 0;
  line-height: 1.5;
}

.library-chip {
  display: inline-flex;
  align-items: center;
  gap: 0.375rem;
  padding: 0.34rem 0.78rem;
  border-radius: var(--radius-md);
  font-family: var(--font-display);
  font-size: 0.75rem;
  font-weight: 500;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.08);
  color: rgba(255, 255, 255, 0.5);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.library-chip:hover {
  background: rgba(255, 255, 255, 0.08);
  border-color: rgba(0, 117, 255, 0.3);
  color: rgba(255, 255, 255, 0.7);
}

.library-chip--active {
  background: rgba(0, 117, 255, 0.15);
  border-color: rgba(0, 117, 255, 0.4);
  color: #0075FF;
}


.index-section {
  background: rgba(99, 102, 241, 0.06);
  border: 1px solid rgba(99, 102, 241, 0.2);
  border-radius: var(--radius-lg);
  padding: 0.95rem;
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
  margin-bottom: 0.5rem;
}

.index-section__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.index-section__title {
  font-size: 0.75rem;
  font-weight: 600;
  color: #818cf8;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.btn-rebuild {
  font-size: 0.675rem;
  font-family: var(--font-display);
  font-weight: 600;
  background: rgba(99, 102, 241, 0.15);
  border: 1px solid rgba(99, 102, 241, 0.3);
  color: #818cf8;
  padding: 0.28rem 0.65rem;
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.15s;
}
.btn-rebuild:hover:not(:disabled) {
  background: rgba(99, 102, 241, 0.25);
}
.btn-rebuild:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.index-stats {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 0.45rem;
}

.index-stat {
  display: flex;
  flex-direction: column;
  gap: 0.125rem;
}

.index-stat__label {
  font-size: 0.5625rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: rgba(255, 255, 255, 0.25);
}

.index-stat__value {
  font-size: 0.78rem;
  color: rgba(255, 255, 255, 0.7);
  display: flex;
  align-items: center;
  gap: 0.375rem;
}

.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  display: inline-block;
}
.status-dot--ok {
  background: #10b981;
  box-shadow: 0 0 4px #10b981;
}
.status-dot--empty {
  background: rgba(255, 255, 255, 0.2);
}

.rebuild-result {
  font-size: 0.6875rem;
  color: #10b981;
  background: rgba(16, 185, 129, 0.08);
  padding: 0.46rem 0.68rem;
  border-radius: 6px;
}

.settings-card__actions {
  display: flex;
  align-items: center;
  justify-content: flex-start;
  margin-top: 1rem;
}

.settings-card__actions--end {
  justify-content: flex-start;
}

.settings-inline-action,
.settings-save-btn {
  box-shadow: none;
}

.settings-save-btn {
  min-width: 5.25rem;
}

.settings-card__actions .settings-save-btn {
  justify-content: center;
}

@media (max-width: 780px) {
  .settings-card {
    padding: 1rem;
  }

  .field-row-full {
    grid-template-columns: 1fr;
    gap: 0.7rem;
  }

  .field-row__label-col {
    padding-top: 0;
  }

  .index-stats {
    grid-template-columns: 1fr;
  }

  .settings-card__actions,
  .settings-card__actions--end {
    justify-content: flex-start;
  }
}


.settings-inline-action {
  background: rgba(255,255,255,0.04) !important;
  border: 1px solid var(--color-border-default) !important;
  color: var(--color-text-primary) !important;
  box-shadow: none !important;
}

.settings-inline-action:hover:not(:disabled) {
  background: rgba(255,255,255,0.07) !important;
  transform: none !important;
}

.settings-save-btn {
  background: #0075FF !important;
  border: 1px solid rgba(0, 117, 255, 0.9) !important;
  color: #FFFFFF !important;
  box-shadow: 0 6px 18px rgba(0, 117, 255, 0.24) !important;
}

.settings-save-btn:hover:not(:disabled) {
  background: #2184ff !important;
  border-color: #2184ff !important;
  transform: none !important;
  box-shadow: 0 8px 22px rgba(0, 117, 255, 0.28) !important;
}

.settings-subtle-chip {
  min-height: 2rem;
}

.index-section {
  background: rgba(0, 117, 255, 0.05);
  border: 1px solid rgba(0, 117, 255, 0.16);
}

.index-section__header {
  gap: 0.75rem;
}

.index-stat {
  gap: 0.18rem;
}

.btn-rebuild.settings-subtle-btn {
  background: rgba(0,117,255,0.08);
  border-color: rgba(0,117,255,0.18);
  color: rgba(255,255,255,0.8);
}

.btn-rebuild.settings-subtle-btn:hover:not(:disabled) {
  background: rgba(0,117,255,0.14);
}

</style>
