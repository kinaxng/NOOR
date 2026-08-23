<script setup lang="ts">
import { ref, onMounted } from 'vue'
import api from '../../api'
import { useToast } from '../../composables/useToast'
import BaseIcon from '../../components/BaseIcon.vue'
import VuiButton from '../../components/vision/VuiButton/VuiButton.vue'
import VuiBadge from '../../components/vision/VuiBadge/VuiBadge.vue'

const toast = useToast()

const loading = ref(false)
const saving = ref(false)
const testing = ref(false)
const connectionStatus = ref<{ success: boolean; server_name?: string; version?: string; error?: string } | null>(null)

// Emby settings
const embyServer = ref('')
const embyApiKey = ref('')
const embyUserId = ref('')
const enabledLibraryIds = ref<string[]>([])
const availableLibraries = ref<{ id: string; name: string }[]>([])
const loadingLibraries = ref(false)

// Network settings
const accelerationMode = ref('mirror')
const httpProxy = ref('')
const githubMirror = ref('https://ghproxy.com')
const hfMirror = ref('https://hf-mirror.com')
const pipMirror = ref('https://pypi.tuna.tsinghua.edu.cn/simple')

onMounted(async () => {
  await loadSettings()
})

async function loadSettings() {
  loading.value = true
  try {
    const resp = await api.get('/settings')
    const data = resp.data

    embyServer.value = data.emby?.server || ''
    embyApiKey.value = data.emby?.api_key || ''
    embyUserId.value = data.emby?.user_id || ''
    enabledLibraryIds.value = data.emby?.enabled_library_ids || []

    if (data.network) {
      accelerationMode.value = data.network.acceleration_mode || 'mirror'
      httpProxy.value = data.network.http_proxy || ''
      githubMirror.value = data.network.github_mirror || 'https://ghproxy.com'
      hfMirror.value = data.network.hf_mirror || 'https://hf-mirror.com'
      pipMirror.value = data.network.pip_mirror || 'https://pypi.tuna.tsinghua.edu.cn/simple'
    }

    if (embyServer.value && embyApiKey.value) {
      await fetchLibraries()
    }
  } catch (e: any) {
    toast.error('加载设置失败')
  } finally {
    loading.value = false
  }
}

async function fetchLibraries() {
  loadingLibraries.value = true
  try {
    const resp = await api.get('/emby/libraries')
    availableLibraries.value = resp.data.libraries.map((lib: any) => ({
      id: lib.id,
      name: lib.name
    }))
  } catch (e: any) {
    console.error('Failed to fetch libraries:', e)
  } finally {
    loadingLibraries.value = false
  }
}

async function testConnection() {
  testing.value = true
  connectionStatus.value = null
  try {
    await api.put('/settings/emby', {
      server: embyServer.value,
      api_key: embyApiKey.value,
      user_id: embyUserId.value,
      enabled_library_ids: enabledLibraryIds.value,
    })

    const resp = await api.post('/settings/emby/test')
    connectionStatus.value = {
      success: true,
      server_name: resp.data.server_name,
      version: resp.data.version,
    }
    toast.success(`已连接到 ${resp.data.server_name} (${resp.data.version})`)
    await fetchLibraries()
  } catch (e: any) {
    connectionStatus.value = {
      success: false,
      error: e.response?.data?.detail || '连接失败'
    }
    toast.error(connectionStatus.value.error || '连接失败')
  } finally {
    testing.value = false
  }
}

async function saveSystem() {
  saving.value = true
  try {
    await api.put('/settings/emby', {
      server: embyServer.value,
      api_key: embyApiKey.value,
      user_id: embyUserId.value,
      enabled_library_ids: enabledLibraryIds.value,
    })
    toast.success('设置已保存')
  } catch (e: any) {
    toast.error('保存失败')
  } finally {
    saving.value = false
  }
}

async function saveNetwork() {
  saving.value = true
  try {
    await api.put('/settings/network', {
      acceleration_mode: accelerationMode.value,
      http_proxy: httpProxy.value,
      github_mirror: githubMirror.value,
      hf_mirror: hfMirror.value,
      pip_mirror: pipMirror.value,
    })
    toast.success('网络设置已保存')
  } catch (e: any) {
    toast.error('保存网络设置失败')
  } finally {
    saving.value = false
  }
}

function toggleLibrary(libId: string) {
  const idx = enabledLibraryIds.value.indexOf(libId)
  if (idx === -1) {
    enabledLibraryIds.value.push(libId)
  } else {
    enabledLibraryIds.value.splice(idx, 1)
  }
}
</script>

<template>
  <div class="space-y-6">
    <!-- Loading -->
    <div v-if="loading" class="flex items-center justify-center py-16">
      <div class="w-8 h-8 border-2 rounded-full animate-spin" style="border-color: #0075FF; border-top-color: transparent;"></div>
    </div>

    <div v-else>
      <!-- Emby Connection -->
      <div class="settings-card">
        <h2 class="settings-card__title">Emby 连接</h2>

        <div class="settings-form">
          <div class="settings-form__row">
            <div class="settings-form__field">
              <label class="settings-form__label">Emby 服务器</label>
              <input
                v-model="embyServer"
                type="text"
                placeholder="http://localhost:8096"
                class="settings-input"
              />
            </div>
            <div class="settings-form__field">
              <label class="settings-form__label">Emby API Key</label>
              <input
                v-model="embyApiKey"
                type="password"
                placeholder="Your Emby API key"
                class="settings-input"
              />
            </div>
          </div>

          <div class="settings-form__field">
            <label class="settings-form__label">Emby User ID</label>
            <input
              v-model="embyUserId"
              type="text"
              placeholder="Emby User ID (可在 Emby Web URL 或 用户设置中找到)"
              class="settings-input"
            />
            <p class="settings-form__hint">用于获取媒体详情</p>
          </div>

          <!-- Test Connection -->
          <div class="flex items-center gap-3">
            <VuiButton variant="outlined" color="secondary" size="small" :loading="testing" :disabled="!embyServer || !embyApiKey" @click="testConnection">
              测试连接
            </VuiButton>
            <VuiBadge
              v-if="connectionStatus"
              :color="connectionStatus.success ? 'success' : 'error'"
              variant="gradient"
              size="sm"
            >
              {{ connectionStatus.success ? `已连接 ${connectionStatus.server_name}` : connectionStatus.error }}
            </VuiBadge>
          </div>

          <!-- Library Selection -->
          <div v-if="availableLibraries.length > 0" class="mt-4">
            <label class="settings-form__label">显示媒体库</label>
            <p class="settings-form__hint mb-3">选择要显示的媒体库（留空显示全部）</p>
            <div class="flex flex-wrap gap-2">
              <button
                v-for="lib in availableLibraries"
                :key="lib.id"
                @click="toggleLibrary(lib.id)"
                class="library-chip"
                :class="{ 'library-chip--active': enabledLibraryIds.includes(lib.id) }"
              >
                <BaseIcon name="library" class="w-3.5 h-3.5" />
                {{ lib.name }}
              </button>
            </div>
            <p class="settings-form__hint mt-2">
              已选择: {{ enabledLibraryIds.length > 0 ? availableLibraries.filter(l => enabledLibraryIds.includes(l.id)).map(l => l.name).join(', ') : '全部' }}
            </p>
          </div>

          <div class="mt-4">
            <VuiButton variant="gradient" color="info" size="small" :loading="saving" @click="saveSystem">
              {{ saving ? '保存中...' : '保存' }}
            </VuiButton>
          </div>
        </div>
      </div>

      <!-- Network Settings -->
      <div class="settings-card">
        <h2 class="settings-card__title">网络加速</h2>

        <div class="settings-form">
          <div class="settings-form__field">
            <label class="settings-form__label">加速方式</label>
            <select v-model="accelerationMode" class="settings-input">
              <option value="none">无（直连）</option>
              <option value="proxy">HTTP 代理 (如 http://127.0.0.1:7890)</option>
              <option value="mirror">国内镜像 (GitHub + HF + pip)</option>
            </select>
            <p class="settings-form__hint">
              <span v-if="accelerationMode === 'none'">无加速，直连访问</span>
              <span v-else-if="accelerationMode === 'proxy'">使用 HTTP 代理进行所有下载</span>
              <span v-else>使用 ghproxy.com (GitHub)、hf-mirror.com (HuggingFace)、清华 pip 镜像</span>
            </p>
          </div>

          <div v-if="accelerationMode === 'proxy'" class="settings-form__field">
            <label class="settings-form__label">代理地址</label>
            <input v-model="httpProxy" type="text" placeholder="http://127.0.0.1:7890" class="settings-input" />
            <p class="settings-form__hint">用于 Git 克隆和所有下载</p>
          </div>

          <div v-if="accelerationMode === 'mirror'" class="space-y-4">
            <div class="settings-form__field">
              <label class="settings-form__label">GitHub 镜像</label>
              <input v-model="githubMirror" type="text" placeholder="https://ghproxy.com" class="settings-input" />
            </div>
            <div class="settings-form__field">
              <label class="settings-form__label">HuggingFace 镜像</label>
              <input v-model="hfMirror" type="text" placeholder="https://hf-mirror.com" class="settings-input" />
            </div>
            <div class="settings-form__field">
              <label class="settings-form__label">pip 镜像</label>
              <input v-model="pipMirror" type="text" placeholder="https://pypi.tuna.tsinghua.edu.cn/simple" class="settings-input" />
            </div>
          </div>

          <div class="mt-4">
            <VuiButton variant="gradient" color="info" size="small" :loading="saving" @click="saveNetwork">
              {{ saving ? '保存中...' : '保存并应用' }}
            </VuiButton>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.settings-card {
  background: linear-gradient(127.09deg, rgba(6, 11, 40, 0.94) 19.41%, rgba(10, 14, 35, 0.49) 76.65%);
  border-radius: var(--radius-xl);
  border: 1px solid rgba(255, 255, 255, 0.06);
  padding: 1.5rem;
}

.settings-card__title {
  font-family: var(--font-display);
  font-size: 0.875rem;
  font-weight: 700;
  color: rgba(255, 255, 255, 0.7);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 1.5rem;
}

.settings-form {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.settings-form__row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
}

@media (max-width: 768px) {
  .settings-form__row {
    grid-template-columns: 1fr;
  }
}

.settings-form__field {
  display: flex;
  flex-direction: column;
  gap: 0.375rem;
}

.settings-form__label {
  font-family: var(--font-display);
  font-size: 0.75rem;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.5);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.settings-form__hint {
  font-family: var(--font-display);
  font-size: 0.6875rem;
  color: rgba(255, 255, 255, 0.3);
  margin-top: 0.125rem;
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
}

.settings-input:focus {
  background: rgba(255, 255, 255, 0.07);
  border-color: rgba(0, 117, 255, 0.4);
  box-shadow: 0 0 0 3px rgba(0, 117, 255, 0.1);
}

.settings-input::placeholder {
  color: rgba(255, 255, 255, 0.2);
}

select.settings-input {
  cursor: pointer;
  appearance: none;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' fill='rgba(255,255,255,0.3)' viewBox='0 0 16 16'%3E%3Cpath d='M7.247 11.14L2.451 5.658C1.885 5.013 2.345 4 3.204 4h9.592a1 1 0 0 1 .753 1.659l-4.796 5.48a1 1 0 0 1-1.506 0z'/%3E%3C/svg%3E");
  background-repeat: no-repeat;
  background-position: calc(100% - 0.875rem) center;
  padding-right: 2.5rem;
}

select.settings-input option {
  background: #0f123b;
  color: #FFFFFF;
}

.library-chip {
  display: inline-flex;
  align-items: center;
  gap: 0.375rem;
  padding: 0.375rem 0.875rem;
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
</style>
