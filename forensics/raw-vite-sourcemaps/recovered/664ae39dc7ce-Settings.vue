<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import api from '../api'

const activeTab = ref<'system' | 'storage' | 'lada' | 'whisper'>('system')
const loading = ref(false)
const saving = ref(false)
const testing = ref(false)
const message = ref<{ type: 'success' | 'error'; text: string } | null>(null)
const connectionStatus = ref<{ success: boolean; server_name?: string; version?: string; error?: string } | null>(null)

// System settings
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

// Storage settings
const sourceDir = ref('')
const outputDir = ref('')
const whisperModelDir = ref('')
const ladaModelDir = ref('')

// LADA settings
const ladaCliPath = ref('')
const ladaVersion = ref<string | null>(null)
const ladaIsDocker = ref(false)
const upgrading = ref(false)

// LADA defaults
const ladaDevice = ref('cuda:0')
const ladaFp16 = ref(true)
const ladaDetectionModel = ref('v4-fast')
const ladaRestorationModel = ref('basicvsrpp-v1.2')
const ladaEncodingPreset = ref('hevc-nvidia-gpu-hq')
const ladaMaxClipLength = ref(180)
const ladaDetectFaceMosaics = ref(false)

// LADA system info
const ladaDevices = ref<any[]>([])
const ladaEncodingPresets = ref<any[]>([])
const ladaDetectionModels = ref<any[]>([])
const ladaRestorationModels = ref<any[]>([])
const ladaModelWeightsDir = ref('')
const loadingLadaInfo = ref(false)

// Whisper settings
const whisperModel = ref('anime-whisper')
const whisperPipelineMode = ref('ensemble')
const whisperMergeStrategy = ref('smart_merge')
const whisperLanguage = ref('ja')
const whisperSensitivity = ref('balanced')
const checkingDeps = ref(false)
const checkingModels = ref(false)
const downloadingModel = ref<string | null>(null)
const installingDeps = computed(() => installStatus.value.status === 'running')
const modelDownloadStatus = ref<{ status: string; progress: number; message: string }>({ status: 'idle', progress: 0, message: '' })
const whisperDeps = ref<Record<string, any>>({})
const whisperModels = ref<any[]>([])
const whisperCudaAvailable = ref(false)

// Install progress
const installStatus = ref<{ status: string; progress: number; message: string; current_package?: string }>({
  status: 'idle',
  progress: 0,
  message: '',
  current_package: ''
})

onMounted(async () => {
  await loadSettings()
})

async function loadSettings() {
  loading.value = true
  try {
    const resp = await api.get('/settings')
    const data = resp.data

    embyServer.value = data.emby.server
    embyApiKey.value = data.emby.api_key
    embyUserId.value = data.emby.user_id || ''
    enabledLibraryIds.value = data.emby.enabled_library_ids || []
    sourceDir.value = data.storage.source_dir
    outputDir.value = data.storage.output_dir
    whisperModelDir.value = data.storage.whisper_model_dir || ''
    ladaModelDir.value = data.storage.lada_model_dir || ''
    ladaCliPath.value = data.lada.cli_path
    ladaVersion.value = data.lada.version
    ladaIsDocker.value = data.lada.is_docker

    // LADA defaults
    if (data.lada_defaults) {
      ladaDevice.value = data.lada_defaults.device || 'cuda:0'
      ladaFp16.value = data.lada_defaults.fp16 ?? true
      ladaDetectionModel.value = data.lada_defaults.detection_model || 'v4-fast'
      ladaRestorationModel.value = data.lada_defaults.restoration_model || 'basicvsrpp-v1.2'
      ladaEncodingPreset.value = data.lada_defaults.encoding_preset || 'hevc-nvidia-gpu-hq'
      ladaMaxClipLength.value = data.lada_defaults.max_clip_length || 180
      ladaDetectFaceMosaics.value = data.lada_defaults.detect_face_mosaics ?? false
    }

    // Network settings
    if (data.network) {
      accelerationMode.value = data.network.acceleration_mode || 'mirror'
      httpProxy.value = data.network.http_proxy || ''
      githubMirror.value = data.network.github_mirror || 'https://ghproxy.com'
      hfMirror.value = data.network.hf_mirror || 'https://hf-mirror.com'
      pipMirror.value = data.network.pip_mirror || 'https://pypi.tuna.tsinghua.edu.cn/simple'
    }

    // Whisper defaults
    if (data.whisper) {
      whisperModel.value = data.whisper.model || 'anime-whisper'
      whisperPipelineMode.value = data.whisper.pipeline_mode || 'ensemble'
      whisperMergeStrategy.value = data.whisper.merge_strategy || 'smart_merge'
      whisperLanguage.value = data.whisper.language || 'ja'
      whisperSensitivity.value = data.whisper.sensitivity || 'balanced'
    }

    // Fetch available libraries if Emby is configured
    if (embyServer.value && embyApiKey.value) {
      await fetchLibraries()
    }
  } catch (e: any) {
    showMessage('error', 'Failed to load settings')
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
    // Temporarily save current settings to test
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
    showMessage('success', `Connected to ${resp.data.server_name} (${resp.data.version})`)

    // Refresh libraries after successful connection
    await fetchLibraries()
  } catch (e: any) {
    connectionStatus.value = {
      success: false,
      error: e.response?.data?.detail || 'Connection failed'
    }
    showMessage('error', connectionStatus.value.error || 'Connection failed')
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
    showMessage('success', 'Settings saved to .env')
  } catch (e: any) {
    showMessage('error', 'Failed to save settings')
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
    showMessage('success', 'Network settings saved and applied')
  } catch (e: any) {
    showMessage('error', 'Failed to save network settings')
  } finally {
    saving.value = false
  }
}

async function saveStorage() {
  saving.value = true
  try {
    await api.put('/settings/storage', {
      source_dir: sourceDir.value,
      output_dir: outputDir.value,
      whisper_model_dir: whisperModelDir.value,
      lada_model_dir: ladaModelDir.value,
    })
    showMessage('success', 'Settings saved to .env')
  } catch (e: any) {
    showMessage('error', 'Failed to save settings')
  } finally {
    saving.value = false
  }
}

async function saveLada() {
  saving.value = true
  try {
    await api.put('/settings/lada', {
      cli_path: ladaCliPath.value,
    })
    showMessage('success', 'Settings saved to .env')
  } catch (e: any) {
    showMessage('error', 'Failed to save settings')
  } finally {
    saving.value = false
  }
}

async function upgradeLada() {
  if (!confirm('Upgrade Lada to latest version?')) return

  upgrading.value = true
  try {
    const resp = await api.post('/settings/lada/upgrade')
    ladaVersion.value = resp.data.version
    showMessage('success', `Lada upgraded to ${resp.data.version}`)
  } catch (e: any) {
    showMessage('error', e.response?.data?.detail || 'Upgrade failed')
  } finally {
    upgrading.value = false
  }
}

async function loadLadaInfo() {
  loadingLadaInfo.value = true
  try {
    const resp = await api.get('/settings/lada/info')
    ladaDevices.value = resp.data.devices || []
    ladaEncodingPresets.value = resp.data.encoding_presets || []
    ladaDetectionModels.value = resp.data.detection_models || []
    ladaRestorationModels.value = resp.data.restoration_models || []
    ladaModelWeightsDir.value = resp.data.model_weights_dir || ''
  } catch (e: any) {
    console.error('Failed to load LADA info:', e)
  } finally {
    loadingLadaInfo.value = false
  }
}

async function saveLadaDefaults() {
  saving.value = true
  try {
    await api.put('/settings/lada/defaults', {
      device: ladaDevice.value,
      fp16: ladaFp16.value,
      detection_model: ladaDetectionModel.value,
      restoration_model: ladaRestorationModel.value,
      encoding_preset: ladaEncodingPreset.value,
      max_clip_length: ladaMaxClipLength.value,
      detect_face_mosaics: ladaDetectFaceMosaics.value,
    })
    showMessage('success', 'Lada defaults saved to .env')
  } catch (e: any) {
    showMessage('error', 'Failed to save Lada defaults')
  } finally {
    saving.value = false
  }
}

async function saveWhisper() {
  saving.value = true
  try {
    await api.put('/settings/whisper', {
      model: whisperModel.value,
      pipeline_mode: whisperPipelineMode.value,
      merge_strategy: whisperMergeStrategy.value,
      language: whisperLanguage.value,
      sensitivity: whisperSensitivity.value,
    })
    showMessage('success', 'Whisper settings saved')
  } catch (e: any) {
    showMessage('error', 'Failed to save Whisper settings')
  } finally {
    saving.value = false
  }
}

async function checkWhisperDeps() {
  checkingDeps.value = true
  try {
    const resp = await api.post('/settings/whisper/check')
    whisperDeps.value = resp.data.dependencies
    whisperCudaAvailable.value = resp.data.cuda_available
    // Also check install status
    const statusResp = await api.get('/settings/whisper/install-status')
    installStatus.value = statusResp.data
    showMessage('success', 'Dependency check completed')
  } catch (e: any) {
    showMessage('error', 'Failed to check dependencies')
  } finally {
    checkingDeps.value = false
  }
}

async function loadWhisperModels() {
  checkingModels.value = true
  try {
    const resp = await api.get('/settings/whisper/models')
    whisperModels.value = resp.data.models
  } catch (e: any) {
    console.error('Failed to load models:', e)
  } finally {
    checkingModels.value = false
  }
}

async function downloadModel(modelId: string) {
  if (!confirm(`Download model ${modelId}?`)) return

  downloadingModel.value = modelId
  modelDownloadStatus.value = { status: 'running', progress: 0, message: 'Starting download...' }
  try {
    await api.post('/settings/whisper/models/download', { model: modelId })
    // Poll for status
    for (let i = 0; i < 600; i++) { // Max 10 minutes
      await new Promise(r => setTimeout(r, 1000))
      const statusResp = await api.get('/settings/whisper/models/download-status')
      const status = statusResp.data
      modelDownloadStatus.value = status
      if (status.status === 'completed') {
        showMessage('success', status.message || 'Model downloaded successfully')
        await loadWhisperModels()
        await checkWhisperDeps()
        break
      } else if (status.status === 'failed') {
        showMessage('error', status.message || 'Download failed')
        break
      }
    }
  } catch (e: any) {
    showMessage('error', e.response?.data?.detail || 'Download failed')
  } finally {
    downloadingModel.value = null
  }
}

async function deleteModel(modelId: string) {
  if (!confirm(`Delete model ${modelId}?`)) return

  try {
    await api.delete(`/settings/whisper/models/${modelId}`)
    showMessage('success', 'Model deleted')
    await loadWhisperModels()
    await checkWhisperDeps()
  } catch (e: any) {
    showMessage('error', e.response?.data?.detail || 'Delete failed')
  }
}

async function installDeps() {
  if (!confirm('Install Whisper dependencies (torch, transformers, faster-whisper)?')) return

  installStatus.value = { status: 'running', progress: 0, message: 'Starting installation...' }
  try {
    await api.post('/settings/whisper/install-deps')
    // Poll for status
    for (let i = 0; i < 300; i++) { // Max 5 minutes
      await new Promise(r => setTimeout(r, 1000))
      const statusResp = await api.get('/settings/whisper/install-status')
      const status = statusResp.data
      installStatus.value = status
      if (status.status === 'completed') {
        showMessage('success', 'Dependencies installed successfully')
        await checkWhisperDeps()
        break
      } else if (status.status === 'failed') {
        showMessage('error', status.message || 'Installation failed')
        break
      }
      // Still running, continue polling
    }
  } catch (e: any) {
    showMessage('error', e.response?.data?.detail || 'Installation failed')
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

function isLibraryEnabled(libId: string): boolean {
  return enabledLibraryIds.value.includes(libId)
}

function showMessage(type: 'success' | 'error', text: string) {
  message.value = { type, text }
  setTimeout(() => { message.value = null }, 4000)
}

// Load Whisper models when switching to whisper tab
async function onTabChange(tab: string) {
  activeTab.value = tab as typeof activeTab.value
  if (tab === 'whisper' && whisperModels.value.length === 0) {
    await Promise.all([checkWhisperDeps(), loadWhisperModels()])
  }
  if (tab === 'lada' && ladaDevices.value.length === 0) {
    await loadLadaInfo()
  }
}
</script>

<template>
  <div class="max-w-4xl mx-auto p-6">
    <h1 class="text-2xl font-bold mb-6">Settings</h1>

    <!-- Message -->
    <div v-if="message" :class="[
      'mb-4 p-3 rounded',
      message.type === 'success' ? 'bg-green-600' : 'bg-red-600'
    ]">
      {{ message.text }}
    </div>

    <!-- Tabs -->
    <div class="border-b border-gray-700 mb-6">
      <nav class="flex space-x-4">
        <button
          v-for="tab in ['system', 'storage', 'lada', 'whisper']"
          :key="tab"
          @click="onTabChange(tab)"
          :class="[
            'px-4 py-2 border-b-2 -mb-px text-sm font-medium transition-colors',
            activeTab === tab
              ? 'border-blue-500 text-blue-400'
              : 'border-transparent text-gray-400 hover:text-gray-300'
          ]"
        >
          {{ tab === 'system' ? 'System' : tab === 'storage' ? 'Storage' : tab === 'lada' ? 'LADA' : 'Whisper' }}
        </button>
      </nav>
    </div>

    <div v-if="loading" class="text-gray-400">Loading...</div>

    <div v-else>
      <!-- System Tab -->
      <div v-if="activeTab === 'system'" class="space-y-4">
        <div>
          <label class="block text-sm text-gray-400 mb-1">Emby Server</label>
          <input
            v-model="embyServer"
            type="text"
            placeholder="http://localhost:8096"
            class="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 focus:border-blue-500 focus:outline-none"
          />
        </div>
        <div>
          <label class="block text-sm text-gray-400 mb-1">Emby API Key</label>
          <input
            v-model="embyApiKey"
            type="password"
            placeholder="Your Emby API key"
            class="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 focus:border-blue-500 focus:outline-none"
          />
        </div>
        <div>
          <label class="block text-sm text-gray-400 mb-1">Emby User ID</label>
          <input
            v-model="embyUserId"
            type="text"
            placeholder="Emby User ID (for item details)"
            class="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 focus:border-blue-500 focus:outline-none"
          />
          <p class="text-xs text-gray-500 mt-1">Required for fetching item details - find it in Emby web URL or Settings &gt; Users</p>
        </div>

        <!-- Test Connection -->
        <div class="flex items-center gap-4">
          <button
            @click="testConnection"
            :disabled="testing || !embyServer || !embyApiKey"
            class="bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 px-4 py-2 rounded transition-colors flex items-center gap-2"
          >
            <svg v-if="testing" class="animate-spin h-4 w-4" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" fill="none" />
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
            {{ testing ? 'Testing...' : 'Test Connection' }}
          </button>
          <span v-if="connectionStatus" :class="connectionStatus.success ? 'text-green-400' : 'text-red-400'">
            {{ connectionStatus.success ? `Connected to ${connectionStatus.server_name}` : connectionStatus.error }}
          </span>
        </div>

        <!-- Library Selection -->
        <div v-if="availableLibraries.length > 0" class="mt-4">
          <label class="block text-sm text-gray-400 mb-2">Display Libraries</label>
          <p class="text-xs text-gray-500 mb-2">Select which libraries to show (leave empty to show all)</p>
          <div class="flex flex-wrap gap-2">
            <button
              v-for="lib in availableLibraries"
              :key="lib.id"
              @click="toggleLibrary(lib.id)"
              :class="[
                'px-3 py-1.5 rounded text-sm transition-colors',
                isLibraryEnabled(lib.id)
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
              ]"
            >
              {{ lib.name }}
            </button>
          </div>
          <p class="text-xs text-gray-500 mt-2">
            Selected: {{ enabledLibraryIds.length > 0 ? availableLibraries.filter(l => enabledLibraryIds.includes(l.id)).map(l => l.name).join(', ') : 'All' }}
          </p>
        </div>

        <button
          @click="saveSystem"
          :disabled="saving"
          class="bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 px-4 py-2 rounded transition-colors"
        >
          {{ saving ? 'Saving...' : 'Save' }}
        </button>

        <!-- Network Settings -->
        <div class="mt-6 pt-6 border-t border-gray-700">
          <h3 class="text-lg font-semibold mb-4">Network (China Acceleration)</h3>

          <div class="space-y-4">
            <div>
              <label class="block text-sm text-gray-400 mb-1">Acceleration Method</label>
              <select
                v-model="accelerationMode"
                class="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 focus:border-blue-500 focus:outline-none"
              >
                <option value="none">None (Direct connection)</option>
                <option value="proxy">HTTP Proxy (e.g., http://127.0.0.1:7890)</option>
                <option value="mirror">China Mirror (GitHub + HF + pip)</option>
              </select>
              <p class="text-xs text-gray-500 mt-1">
                <span v-if="accelerationMode === 'none'">No acceleration, direct connection</span>
                <span v-else-if="accelerationMode === 'proxy'">Uses your HTTP proxy for all downloads</span>
                <span v-else>Uses China mirrors for GitHub (ghproxy.com), HuggingFace (hf-mirror.com) and pip (tsinghua)</span>
              </p>
            </div>

            <div v-if="accelerationMode === 'proxy'">
              <label class="block text-sm text-gray-400 mb-1">Proxy Address</label>
              <input
                v-model="httpProxy"
                type="text"
                placeholder="http://127.0.0.1:7890"
                class="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 focus:border-blue-500 focus:outline-none"
              />
              <p class="text-xs text-gray-500 mt-1">Proxy for Git clone and all downloads</p>
            </div>

            <div v-if="accelerationMode === 'mirror'">
              <label class="block text-sm text-gray-400 mb-1">GitHub Mirror</label>
              <input
                v-model="githubMirror"
                type="text"
                placeholder="https://ghproxy.com"
                class="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 focus:border-blue-500 focus:outline-none"
              />
              <p class="text-xs text-gray-500 mt-1">GitHub clone mirror (default: ghproxy.com)</p>
            </div>

            <div v-if="accelerationMode === 'mirror'">
              <label class="block text-sm text-gray-400 mb-1">HuggingFace Mirror</label>
              <input
                v-model="hfMirror"
                type="text"
                placeholder="https://hf-mirror.com"
                class="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 focus:border-blue-500 focus:outline-none"
              />
              <p class="text-xs text-gray-500 mt-1">HuggingFace model download mirror (default: hf-mirror.com)</p>
            </div>

            <div v-if="accelerationMode === 'mirror'">
              <label class="block text-sm text-gray-400 mb-1">pip Mirror</label>
              <input
                v-model="pipMirror"
                type="text"
                placeholder="https://pypi.tuna.tsinghua.edu.cn/simple"
                class="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 focus:border-blue-500 focus:outline-none"
              />
              <p class="text-xs text-gray-500 mt-1">pip package install mirror (default: tsinghua)</p>
            </div>
          </div>

          <button
            @click="saveNetwork"
            :disabled="saving"
            class="mt-4 bg-purple-600 hover:bg-purple-700 disabled:bg-gray-600 px-4 py-2 rounded transition-colors"
          >
            {{ saving ? 'Saving...' : 'Save & Apply Network Settings' }}
          </button>
        </div>
      </div>

      <!-- Storage Tab -->
      <div v-if="activeTab === 'storage'" class="space-y-4">
        <div>
          <label class="block text-sm text-gray-400 mb-1">Source Directory</label>
          <input
            v-model="sourceDir"
            type="text"
            placeholder="/path/to/emby/media"
            class="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 focus:border-blue-500 focus:outline-none"
          />
          <p class="text-xs text-gray-500 mt-1">Emby media directory (where hardlinked files are stored)</p>
        </div>
        <div>
          <label class="block text-sm text-gray-400 mb-1">Output Directory</label>
          <input
            v-model="outputDir"
            type="text"
            placeholder="/path/to/lada/output"
            class="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 focus:border-blue-500 focus:outline-none"
          />
          <p class="text-xs text-gray-500 mt-1">Where LADA outputs will be saved (.restored-u.mp4)</p>
        </div>
        <div>
          <label class="block text-sm text-gray-400 mb-1">Whisper Model Directory</label>
          <input
            v-model="whisperModelDir"
            type="text"
            placeholder="~/.cache/whisper (default)"
            class="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 focus:border-blue-500 focus:outline-none"
          />
          <p class="text-xs text-gray-500 mt-1">Custom directory for Whisper models (leave empty for default)</p>
        </div>
        <div>
          <label class="block text-sm text-gray-400 mb-1">LADA Model Directory</label>
          <input
            v-model="ladaModelDir"
            type="text"
            placeholder="/path/to/lada/models (optional)"
            class="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 focus:border-blue-500 focus:outline-none"
          />
          <p class="text-xs text-gray-500 mt-1">Custom directory for LADA AI models (leave empty for default)</p>
        </div>
        <button
          @click="saveStorage"
          :disabled="saving"
          class="bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 px-4 py-2 rounded transition-colors"
        >
          {{ saving ? 'Saving...' : 'Save' }}
        </button>
      </div>

      <!-- LADA Tab -->
      <div v-if="activeTab === 'lada'" class="space-y-6">
        <!-- CLI Info Section -->
        <div class="bg-gray-800 rounded-lg p-4">
          <div class="flex justify-between items-center mb-4">
            <div>
              <p class="text-sm text-gray-400">Version</p>
              <p class="text-lg font-mono">{{ ladaVersion || 'Not found' }}</p>
            </div>
            <div class="text-right">
              <p class="text-sm text-gray-400">Running Mode</p>
              <p :class="ladaIsDocker ? 'text-green-400' : 'text-yellow-400'">
                {{ ladaIsDocker ? 'Docker' : 'Native' }}
              </p>
            </div>
          </div>

          <div class="grid grid-cols-2 gap-4">
            <div>
              <label class="block text-sm text-gray-400 mb-1">LADA CLI Path</label>
              <input
                v-model="ladaCliPath"
                type="text"
                placeholder="/usr/local/bin/lada-cli"
                class="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 focus:border-blue-500 focus:outline-none"
              />
            </div>
            <div>
              <label class="block text-sm text-gray-400 mb-1">Model Weights Directory</label>
              <div class="text-sm text-gray-300 bg-gray-700 rounded px-3 py-2 truncate">
                {{ ladaModelWeightsDir || 'Not configured' }}
              </div>
            </div>
          </div>

          <div class="flex space-x-3 mt-4">
            <button
              @click="saveLada"
              :disabled="saving"
              class="bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 px-4 py-2 rounded transition-colors"
            >
              {{ saving ? 'Saving...' : 'Save Path' }}
            </button>
            <button
              @click="upgradeLada"
              :disabled="upgrading"
              class="bg-green-600 hover:bg-green-700 disabled:bg-gray-600 px-4 py-2 rounded transition-colors"
            >
              {{ upgrading ? 'Upgrading...' : 'Upgrade LADA' }}
            </button>
          </div>
        </div>

        <!-- Default Settings Section -->
        <div class="bg-gray-800 rounded-lg p-4">
          <h3 class="text-lg font-semibold mb-4">Default Settings</h3>
          <p class="text-xs text-gray-500 mb-4">These settings will be used as defaults when running LADA restoration.</p>

          <div class="grid grid-cols-2 gap-4">
            <div>
              <label class="block text-sm text-gray-400 mb-1">Device</label>
              <select
                v-model="ladaDevice"
                class="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 focus:border-blue-500 focus:outline-none"
              >
                <option v-for="dev in ladaDevices" :key="dev.id" :value="dev.id">
                  {{ dev.name }} ({{ dev.id }})
                </option>
              </select>
            </div>

            <div>
              <label class="block text-sm text-gray-400 mb-1">FP16</label>
              <select
                v-model="ladaFp16"
                class="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 focus:border-blue-500 focus:outline-none"
              >
                <option :value="true">Enabled (Recommended - faster, less VRAM)</option>
                <option :value="false">Disabled (FP32)</option>
              </select>
            </div>

            <div>
              <label class="block text-sm text-gray-400 mb-1">Detection Model</label>
              <select
                v-model="ladaDetectionModel"
                class="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 focus:border-blue-500 focus:outline-none"
              >
                <option v-for="m in ladaDetectionModels" :key="m.id" :value="m.id">
                  {{ m.name }} {{ m.downloaded ? '✓' : '(not downloaded)' }}
                </option>
              </select>
            </div>

            <div>
              <label class="block text-sm text-gray-400 mb-1">Restoration Model</label>
              <select
                v-model="ladaRestorationModel"
                class="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 focus:border-blue-500 focus:outline-none"
              >
                <option v-for="m in ladaRestorationModels" :key="m.id" :value="m.id">
                  {{ m.name }} {{ m.downloaded ? '✓' : '(not downloaded)' }}
                </option>
              </select>
            </div>

            <div>
              <label class="block text-sm text-gray-400 mb-1">Encoding Preset</label>
              <select
                v-model="ladaEncodingPreset"
                class="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 focus:border-blue-500 focus:outline-none"
              >
                <option v-for="p in ladaEncodingPresets" :key="p.id" :value="p.id">
                  {{ p.name }}
                </option>
              </select>
            </div>

            <div>
              <label class="block text-sm text-gray-400 mb-1">Max Clip Length (frames)</label>
              <input
                v-model.number="ladaMaxClipLength"
                type="number"
                min="30"
                max="600"
                class="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 focus:border-blue-500 focus:outline-none"
              />
              <p class="text-xs text-gray-500 mt-1">Higher = better temporal stability, more VRAM</p>
            </div>
          </div>

          <div class="mt-4">
            <label class="flex items-center gap-3 cursor-pointer">
              <input
                type="checkbox"
                v-model="ladaDetectFaceMosaics"
                class="w-5 h-5 rounded bg-gray-700 border-gray-600 text-blue-600 focus:ring-blue-500"
              />
              <div>
                <span class="text-sm text-gray-300">Detect Face Mosaics</span>
                <p class="text-xs text-gray-500">Detect and ignore pixelated faces. May worsen NSFW detection.</p>
              </div>
            </label>
          </div>

          <button
            @click="saveLadaDefaults"
            :disabled="saving"
            class="mt-4 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 px-4 py-2 rounded transition-colors"
          >
            {{ saving ? 'Saving...' : 'Save Defaults' }}
          </button>
        </div>

        <!-- Detection Models Section -->
        <div class="bg-gray-800 rounded-lg p-4">
          <div class="flex justify-between items-center mb-4">
            <h3 class="text-lg font-semibold">Detection Models</h3>
            <button
              @click="loadLadaInfo"
              :disabled="loadingLadaInfo"
              class="bg-gray-700 hover:bg-gray-600 disabled:bg-gray-600 px-3 py-1.5 rounded text-sm transition-colors"
            >
              {{ loadingLadaInfo ? 'Loading...' : 'Refresh' }}
            </button>
          </div>

          <div class="space-y-2">
            <div v-for="model in ladaDetectionModels" :key="model.id"
              class="flex items-center justify-between bg-gray-700 rounded px-3 py-3"
            >
              <div>
                <div class="flex items-center gap-2">
                  <span class="font-medium">{{ model.name }}</span>
                  <span v-if="model.downloaded" class="text-green-400 text-sm">✓ Downloaded</span>
                  <span v-else class="text-red-400 text-sm">✗ Not downloaded</span>
                </div>
                <div class="text-xs text-gray-400 mt-1">
                  {{ model.size }} · {{ model.description || 'Mosaic detection' }}
                </div>
              </div>
            </div>
          </div>

          <p class="text-xs text-yellow-400 mt-3">
            ⚠ Models need to be downloaded from the LADA Release page (codeberg.org/ladaapp/lada/releases)
          </p>
        </div>

        <!-- Restoration Models Section -->
        <div class="bg-gray-800 rounded-lg p-4">
          <h3 class="text-lg font-semibold mb-4">Restoration Models</h3>

          <div class="space-y-2">
            <div v-for="model in ladaRestorationModels" :key="model.id"
              class="flex items-center justify-between bg-gray-700 rounded px-3 py-3"
            >
              <div>
                <div class="flex items-center gap-2">
                  <span class="font-medium">{{ model.name }}</span>
                  <span v-if="model.downloaded" class="text-green-400 text-sm">✓ Downloaded</span>
                  <span v-else class="text-red-400 text-sm">✗ Not downloaded</span>
                </div>
                <div class="text-xs text-gray-400 mt-1">
                  {{ model.size }} · {{ model.description || 'Mosaic restoration' }}
                </div>
              </div>
            </div>
          </div>

          <p class="text-xs text-yellow-400 mt-3">
            ⚠ The main restoration model (~11GB) must be downloaded from the LADA Release page
          </p>
        </div>
      </div>

      <!-- Whisper Tab -->
      <div v-if="activeTab === 'whisper'" class="space-y-6">
        <!-- Default Settings Section -->
        <div class="bg-gray-800 rounded-lg p-4">
          <h3 class="text-lg font-semibold mb-4">Default Settings</h3>
          <p class="text-xs text-gray-500 mb-4">These settings will be used as defaults when generating AI subtitles from the media library.</p>

          <div class="grid grid-cols-2 gap-4">
            <div>
              <label class="block text-sm text-gray-400 mb-1">Model</label>
              <select
                v-model="whisperModel"
                class="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 focus:border-blue-500 focus:outline-none"
              >
                <option value="anime-whisper">Anime-Whisper (推荐, 优化日语)</option>
                <option value="large-v3">Large V3 (最高质量)</option>
                <option value="large-v3-turbo">Large V3 Turbo (快速)</option>
                <option value="medium">Medium</option>
                <option value="small">Small</option>
                <option value="base">Base</option>
                <option value="tiny">Tiny (最快)</option>
              </select>
            </div>

            <div>
              <label class="block text-sm text-gray-400 mb-1">Pipeline Mode</label>
              <select
                v-model="whisperPipelineMode"
                class="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 focus:border-blue-500 focus:outline-none"
              >
                <option value="ensemble">Ensemble (两遍, 最佳质量)</option>
                <option value="single">Single (单遍, 快速)</option>
              </select>
            </div>

            <div>
              <label class="block text-sm text-gray-400 mb-1">Merge Strategy</label>
              <select
                v-model="whisperMergeStrategy"
                class="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 focus:border-blue-500 focus:outline-none"
              >
                <option value="smart_merge">Smart Merge (推荐)</option>
                <option value="pass1_primary">Pass1 Primary</option>
                <option value="pass2_primary">Pass2 Primary</option>
                <option value="full_merge">Full Merge</option>
                <option value="longest">Longest</option>
              </select>
            </div>

            <div>
              <label class="block text-sm text-gray-400 mb-1">Language</label>
              <select
                v-model="whisperLanguage"
                class="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 focus:border-blue-500 focus:outline-none"
              >
                <option value="ja">Japanese (日语)</option>
                <option value="zh">Chinese (中文)</option>
                <option value="en">English (英语)</option>
                <option value="auto">Auto Detect (自动检测)</option>
              </select>
            </div>

            <div>
              <label class="block text-sm text-gray-400 mb-1">Sensitivity</label>
              <select
                v-model="whisperSensitivity"
                class="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 focus:border-blue-500 focus:outline-none"
              >
                <option value="conservative">Conservative (保守)</option>
                <option value="balanced">Balanced (平衡)</option>
                <option value="aggressive">Aggressive (激进)</option>
              </select>
            </div>
          </div>

          <button
            @click="saveWhisper"
            :disabled="saving"
            class="mt-4 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 px-4 py-2 rounded transition-colors"
          >
            {{ saving ? 'Saving...' : 'Save Defaults' }}
          </button>
        </div>

        <!-- Dependencies Section -->
        <div class="bg-gray-800 rounded-lg p-4">
          <div class="flex justify-between items-center mb-4">
            <h3 class="text-lg font-semibold">Dependencies</h3>
            <button
              @click="checkWhisperDeps"
              :disabled="checkingDeps"
              class="bg-gray-700 hover:bg-gray-600 disabled:bg-gray-600 px-3 py-1.5 rounded text-sm transition-colors"
            >
              {{ checkingDeps ? 'Checking...' : 'Refresh' }}
            </button>
          </div>

          <div class="space-y-2">
            <div v-for="(info, name) in whisperDeps" :key="name"
              class="bg-gray-700 rounded px-3 py-2"
            >
              <div class="flex items-center justify-between mb-1">
                <span class="font-mono">{{ name }}</span>
                <span v-if="info.installed" class="text-green-400 text-sm">
                  ✓ {{ info.version || 'installed' }}
                </span>
                <span v-else-if="installStatus.status === 'running' && installStatus.message?.includes(name)" class="text-blue-400 text-sm animate-pulse">
                  Installing...
                </span>
                <span v-else class="text-red-400 text-sm">✗ Not installed</span>
              </div>
              <!-- Progress bar for this dependency when installing -->
              <div v-if="installStatus.status === 'running' && installStatus.message?.includes(name)" class="w-full bg-gray-600 rounded-full h-1.5">
                <div
                  class="bg-blue-500 h-1.5 rounded-full transition-all animate-pulse"
                  :style="{ width: installStatus.progress + '%' }"
                ></div>
              </div>
            </div>

            <div class="flex items-center justify-between bg-gray-700 rounded px-3 py-2">
              <span class="font-mono">CUDA (GPU)</span>
              <span v-if="whisperDeps.torch?.cuda" class="text-green-400">
                ✓ {{ whisperDeps.torch.cuda_info?.device_name || 'GPU Available' }}
              </span>
              <span v-else class="text-yellow-400">✗ CPU only</span>
            </div>
          </div>

          <p v-if="installStatus.status === 'running'" class="text-xs text-blue-400 mt-2">
            {{ installStatus.message }}
          </p>

          <button
            @click="installDeps"
            :disabled="installingDeps"
            class="mt-4 bg-green-600 hover:bg-green-700 disabled:bg-gray-600 px-4 py-2 rounded transition-colors flex items-center gap-2"
          >
            <svg v-if="installingDeps" class="animate-spin h-4 w-4" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" fill="none" />
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
            {{ installingDeps ? 'Installing...' : 'Install Dependencies' }}
          </button>
        </div>

        <!-- Models Section -->
        <div class="bg-gray-800 rounded-lg p-4">
          <div class="flex justify-between items-center mb-4">
            <h3 class="text-lg font-semibold">Models</h3>
            <button
              @click="loadWhisperModels"
              :disabled="checkingModels"
              class="bg-gray-700 hover:bg-gray-600 disabled:bg-gray-600 px-3 py-1.5 rounded text-sm transition-colors"
            >
              {{ checkingModels ? 'Loading...' : 'Refresh' }}
            </button>
          </div>

          <div class="space-y-2">
            <div v-for="model in whisperModels" :key="model.id"
              class="flex items-center justify-between bg-gray-700 rounded px-3 py-3"
            >
              <div>
                <div class="flex items-center gap-2">
                  <span class="font-medium">{{ model.name }}</span>
                  <span class="text-xs px-2 py-0.5 rounded"
                    :class="model.type === 'transformers' ? 'bg-purple-900 text-purple-300' : 'bg-blue-900 text-blue-300'"
                  >
                    {{ model.type }}
                  </span>
                </div>
                <div class="text-xs text-gray-400 mt-1">
                  {{ model.size }} · {{ model.description || (model.downloaded ? 'Downloaded' : 'Not downloaded') }}
                </div>
              </div>
              <div class="flex items-center gap-2">
                <span v-if="model.downloaded" class="text-green-400 text-sm">✓</span>
                <div v-else-if="downloadingModel === model.id" class="flex items-center gap-2">
                  <div class="w-20 bg-gray-600 rounded-full h-1.5">
                    <div class="bg-blue-500 h-1.5 rounded-full transition-all" :style="{ width: modelDownloadStatus.progress + '%' }"></div>
                  </div>
                  <span class="text-xs text-gray-400">{{ modelDownloadStatus.progress }}%</span>
                </div>
                <button
                  v-else
                  @click="downloadModel(model.id)"
                  :disabled="downloadingModel !== null"
                  class="bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 px-3 py-1.5 rounded text-sm transition-colors"
                >
                  Download
                </button>
                <button
                  v-if="model.downloaded"
                  @click="deleteModel(model.id)"
                  class="bg-red-600 hover:bg-red-700 px-3 py-1.5 rounded text-sm transition-colors ml-2"
                >
                  Delete
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
