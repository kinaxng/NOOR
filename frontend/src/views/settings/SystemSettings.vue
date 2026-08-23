<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
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
const { globalBlurEnabled, syncGlobalBlur } = useBlurCover()
const { t } = useI18n()

const loading = ref(false)
const embySaving = ref(false)
const networkSaving = ref(false)
const uiSaving = ref(false)
const testing = ref(false)
const connectionStatus = ref<{ ok: boolean; message: string } | null>(null)

// Emby / media library settings
const serverUrl = ref('')
const apiKey = ref('')
const userId = ref('')
const tmdbApiKey = ref('')
const tmdbApiToken = ref('')
const mdcNgActorMappingPath = ref('')
const webhookToken = ref('')
const webhookGuideVisible = ref(false)
const enabledLibraryIds = ref<string[]>([])
const availableLibraries = ref<{ id: string; name: string }[]>([])
const librariesLoaded = ref(false)

// Network settings
const httpProxy = ref('')
const githubMirror = ref('https://ghproxy.com')
const githubToken = ref('')
const hfMirror = ref('https://hf-mirror.com')
const pipMirror = ref('https://pypi.tuna.tsinghua.edu.cn/simple')
const hfToken = ref('')
const actorMappingAutoUpdate = ref(true)

const embyWebhookUrl = computed(() => {
  if (!webhookToken.value) return ''
  return `${window.location.origin}/api/media-library/webhook/emby?token=${encodeURIComponent(webhookToken.value)}`
})

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
        tmdbApiKey.value = cfg.tmdb_api_key || ''
        tmdbApiToken.value = cfg.tmdb_api_token || ''
        mdcNgActorMappingPath.value = cfg.mdc_ng_actor_mapping_path || ''
        webhookToken.value = cfg.webhook_token || ''
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

    // Load network settings
    try {
      const resp = await api.get('/settings')
      const data = resp.data
      if (data.network) {
        httpProxy.value = data.network.http_proxy || ''
        githubMirror.value = data.network.github_mirror || 'https://ghproxy.com'
        githubToken.value = data.network.github_token || ''
        hfMirror.value = data.network.hf_mirror || 'https://hf-mirror.com'
        pipMirror.value = data.network.pip_mirror || 'https://pypi.tuna.tsinghua.edu.cn/simple'
        hfToken.value = data.network.hf_token || ''
        actorMappingAutoUpdate.value = data.network.actor_mapping_auto_update !== false
      }
      if (data.ui && typeof data.ui.cover_blur_enabled === 'boolean') {
        syncGlobalBlur(data.ui.cover_blur_enabled)
      }
    } catch (e) {
      console.error('Failed to load network settings:', e)
    }
  } finally {
    loading.value = false
  }
}

async function saveGlobalBlur(value: boolean) {
  const previous = globalBlurEnabled.value
  syncGlobalBlur(value)
  uiSaving.value = true
  try {
    await api.put('/settings/ui', { cover_blur_enabled: value })
    toast.success(t('settings.saveSuccess'))
  } catch {
    syncGlobalBlur(previous)
    toast.error(t('settings.saveFailed'))
  } finally {
    uiSaving.value = false
  }
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
        tmdb_api_key: tmdbApiKey.value,
        tmdb_api_token: tmdbApiToken.value,
        mdc_ng_actor_mapping_path: mdcNgActorMappingPath.value,
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

async function copyWebhookUrl() {
  if (!embyWebhookUrl.value) return
  try {
    if (navigator.clipboard?.writeText && window.isSecureContext) {
      await navigator.clipboard.writeText(embyWebhookUrl.value)
    } else {
      const textarea = document.createElement('textarea')
      textarea.value = embyWebhookUrl.value
      textarea.setAttribute('readonly', 'true')
      textarea.style.position = 'fixed'
      textarea.style.left = '-9999px'
      textarea.style.top = '0'
      document.body.appendChild(textarea)
      textarea.focus()
      textarea.select()
      const copied = document.execCommand('copy')
      document.body.removeChild(textarea)
      if (!copied) throw new Error('copy failed')
    }
    webhookGuideVisible.value = true
    toast.success('Webhook 地址已复制')
  } catch {
    toast.error('复制失败，请手动复制')
  }
}

async function saveNetwork() {
  networkSaving.value = true
  try {
    const effectiveMode = githubMirror.value || hfMirror.value || pipMirror.value
      ? 'mirror'
      : httpProxy.value
        ? 'proxy'
        : 'none'
    await api.put('/settings/network', {
      acceleration_mode: effectiveMode,
      http_proxy: httpProxy.value,
      github_mirror: githubMirror.value,
      github_token: githubToken.value,
      hf_mirror: hfMirror.value,
      pip_mirror: pipMirror.value,
      hf_token: hfToken.value,
      actor_mapping_auto_update: actorMappingAutoUpdate.value,
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

          <FieldRow :label="t('settings.emby.tmdbApiKey')" :description="t('settings.emby.tmdbApiKeyDesc')">
            <input v-model="tmdbApiKey" type="password" placeholder="TMDB v3 API Key" class="settings-input" />
          </FieldRow>

          <FieldRow :label="t('settings.emby.tmdbApiToken')" :description="t('settings.emby.tmdbApiTokenDesc')">
            <input v-model="tmdbApiToken" type="password" placeholder="TMDB v4 Read Access Token" class="settings-input" />
          </FieldRow>

          <FieldRow :label="t('settings.emby.mdcNgActorMappingPath')" :description="t('settings.emby.mdcNgActorMappingPathDesc')">
            <input v-model="mdcNgActorMappingPath" type="text" placeholder="/home/kinax/dsm/docker/mdc-ng" class="settings-input" />
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

          <div class="field-row-full">
            <div class="field-row__label-col">
              <span class="field-row__label-text">Emby Webhook</span>
              <span class="field-row__label-desc">Emby 媒体库变化后通知 NOOR 清空缓存</span>
            </div>
            <div class="field-row__input-col">
              <div class="webhook-box">
                <div class="webhook-url-row">
                  <code class="webhook-url">{{ embyWebhookUrl || '保存或重新加载设置后生成 Webhook 地址' }}</code>
                  <VuiButton
                    variant="contained"
                    color="secondary"
                    size="small"
                    customClass="settings-inline-action"
                    :disabled="!embyWebhookUrl"
                    @click="copyWebhookUrl"
                  >
                    <BaseIcon name="copy" class="w-3.5 h-3.5" />
                    复制
                  </VuiButton>
                </div>
                <div v-if="webhookGuideVisible" class="webhook-guide">
                  <div>1. 在 Emby 安装并打开 Webhooks 插件。</div>
                  <div>2. 新增 Webhook，URL 填入上面的地址，Method 选择 POST。</div>
                  <div>3. 请求内容类型选择 application/json，Body 模板可保持插件默认 JSON。</div>
                  <div>4. 事件选择媒体新增、删除、更新、库扫描完成等媒体库相关事件。</div>
                  <div>5. 保存后可在 Emby 里发送测试请求；NOOR 收到后会清空媒体库缓存，并在系统日志显示接收记录。</div>
                </div>
              </div>
            </div>
          </div>

          <!-- Blur Toggle -->
          <FieldRow :label="t('settings.ui.blur')" :description="t('settings.ui.blurDesc')">
            <div class="flex items-center gap-3">
              <SettingsSwitch :model-value="globalBlurEnabled" :disabled="uiSaving" @update:model-value="saveGlobalBlur" />
              <span class="text-sm text-text-secondary">
                {{ globalBlurEnabled ? t('settings.ui.blurEnabled') : t('settings.ui.blurDisabled') }}
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

      <!-- 网络加速 -->
      <div class="settings-card">
        <div class="settings-card__head"><h2 class="settings-card__title">{{ t('settings.network.title') }}</h2><p class="settings-card__subtitle">镜像和 HTTP 代理可同时配置；执行时按镜像 → HTTP 代理 → 直连回退</p></div>

        <div class="settings-form">
          <FieldRow :label="t('settings.network.githubMirror')" :description="t('settings.network.githubMirrorDesc')">
            <input v-model="githubMirror" type="text" placeholder="https://ghproxy.com" class="settings-input" />
          </FieldRow>
          <FieldRow :label="t('settings.network.githubToken')" :description="t('settings.network.githubTokenDesc')">
            <input v-model="githubToken" type="password" placeholder="github_pat_xxxxxxxxxxxx" class="settings-input" />
          </FieldRow>
          <FieldRow :label="t('settings.network.hfMirror')" :description="t('settings.network.hfMirrorDesc')">
            <input v-model="hfMirror" type="text" placeholder="https://hf-mirror.com" class="settings-input" />
          </FieldRow>
          <FieldRow :label="t('settings.network.hfToken')" :description="t('settings.network.hfTokenDesc')">
            <input v-model="hfToken" type="password" placeholder="hf_xxxxxxxxxxxx" class="settings-input" />
          </FieldRow>
          <FieldRow :label="t('settings.network.pipMirror')" :description="t('settings.network.pipMirrorDesc')">
            <input v-model="pipMirror" type="text" placeholder="https://pypi.tuna.tsinghua.edu.cn/simple" class="settings-input" />
          </FieldRow>
          <FieldRow :label="t('settings.network.proxy')" :description="t('settings.network.proxyDesc')">
            <input v-model="httpProxy" type="text" placeholder="http://127.0.0.1:7890" class="settings-input" />
          </FieldRow>
          <FieldRow :label="t('settings.network.actorMappingAutoUpdate')" :description="t('settings.network.actorMappingAutoUpdateDesc')">
            <label class="settings-toggle-row">
              <input v-model="actorMappingAutoUpdate" type="checkbox" />
              <span>{{ actorMappingAutoUpdate ? t('common.enabled') : t('common.disabled') }}</span>
            </label>
          </FieldRow>

          <div class="settings-card__actions settings-card__actions--end">
            <VuiButton variant="contained" color="info" size="small" customClass="settings-save-btn" :loading="networkSaving" @click="saveNetwork">
              {{ networkSaving ? t('settings.saving') : t('common.save') }}
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
</style>
