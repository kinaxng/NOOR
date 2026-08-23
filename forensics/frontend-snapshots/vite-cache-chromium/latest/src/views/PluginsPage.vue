<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { usePluginsStore } from '../stores/plugins'
import NoorBadge from '../noor-kit/NoorBadge.vue'
import NoorButton from '../noor-kit/NoorButton.vue'
import NoorInput from '../noor-kit/NoorInput.vue'
import NoorSelect from '../noor-kit/NoorSelect.vue'
import NoorState from '../noor-kit/NoorState.vue'
import NoorTextarea from '../noor-kit/NoorTextarea.vue'
import NoorToggle from '../noor-kit/NoorToggle.vue'

const store = usePluginsStore()
const configOpen = ref(false)
const configLoading = ref(false)
const configSaving = ref(false)
const selectedPluginId = ref('')
const selectedPluginName = ref('')
const configSchema = ref<Record<string, any>>({})
const configDraft = ref<Record<string, any>>({})
const configError = ref('')
const configMessage = ref('')
const repoOpen = ref(false)
const repoInput = ref('')
const repos = ref<Array<{ url: string }>>([])
const marketItems = ref<any[]>([])
const marketLoading = ref(false)
const marketError = ref('')
const actionMessage = ref('')
const localIndexStatus = ref<any | null>(null)
const localRebuilding = ref(false)

const installedIds = computed(() => new Set(store.plugins.map(plugin => plugin.id)))
const notInstalledMarketItems = computed(() => marketItems.value.filter(item => item && !item.error && item.id && !installedIds.value.has(item.id)))
const sortedPlugins = computed(() => [...store.plugins].sort((a, b) => Number(!!b.enabled) - Number(!!a.enabled) || String(a.name).localeCompare(String(b.name), 'zh-CN')))
const schemaEntries = computed(() => Object.entries(configSchema.value || {}))

function fieldType(meta: any) {
  const type = String(meta?.type || 'string').toLowerCase()
  if (['boolean', 'bool', 'switch'].includes(type)) return 'boolean'
  if (['number', 'integer', 'float'].includes(type)) return 'number'
  if (type === 'password') return 'password'
  if (['textarea', 'multiline'].includes(type)) return 'textarea'
  return 'text'
}

function selectOptions(key: string, meta: any) {
  const currentValue = configDraft.value[key]
  const options = (Array.isArray(meta?.options) ? meta.options : []).map((opt: any) => ({
    value: String(opt?.value ?? opt?.id ?? opt),
    label: String(opt?.label ?? opt?.name ?? opt?.value ?? opt?.id ?? opt),
  }))
  if (currentValue !== undefined && currentValue !== null && currentValue !== '' && !options.some((opt: any) => opt.value === String(currentValue))) {
    options.unshift({ value: String(currentValue), label: String(currentValue) })
  }
  return options
}

function updateNumberConfig(key: string, value: string) {
  configDraft.value[key] = value === '' ? '' : Number(value)
}

async function fetchMarket() {
  marketLoading.value = true
  marketError.value = ''
  try {
    const [repoRes, itemRes] = await Promise.all([fetch('/api/plugins/market/repos'), fetch('/api/plugins/market/items')])
    repos.value = await repoRes.json().catch(() => [])
    marketItems.value = await itemRes.json().catch(() => [])
    if (!repoRes.ok || !itemRes.ok) throw new Error('插件仓库加载失败')
  } catch (err: any) {
    marketError.value = err?.message || '插件仓库加载失败'
  } finally {
    marketLoading.value = false
  }
}

async function openRepoManager() {
  repoOpen.value = true
  await fetchMarket()
}

async function addRepo() {
  const url = repoInput.value.trim()
  if (!url) return
  marketError.value = ''
  try {
    const res = await fetch('/api/plugins/market/repos', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ repo_url: url }),
    })
    const data = await res.json().catch(() => ({}))
    if (!res.ok) throw new Error(data?.detail || '添加仓库失败')
    repoInput.value = ''
    await fetchMarket()
  } catch (err: any) {
    marketError.value = err?.message || '添加仓库失败'
  }
}

async function removeRepo(url: string) {
  marketError.value = ''
  try {
    const res = await fetch('/api/plugins/market/repos', {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ repo_url: url }),
    })
    const data = await res.json().catch(() => ({}))
    if (!res.ok) throw new Error(data?.detail || '删除仓库失败')
    await fetchMarket()
  } catch (err: any) {
    marketError.value = err?.message || '删除仓库失败'
  }
}

async function installMarketItem(item: any) {
  actionMessage.value = ''
  marketError.value = ''
  try {
    const res = await fetch('/api/plugins/market/install', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ repo_url: item.repo_url, plugin_id: item.id }),
    })
    const data = await res.json().catch(() => ({}))
    if (!res.ok) throw new Error(data?.detail || '安装插件失败')
    actionMessage.value = `已安装 ${item.name || item.id}`
    await store.fetchPlugins()
    store.notifyPluginsChanged()
    await fetchMarket()
  } catch (err: any) {
    marketError.value = err?.message || '安装插件失败'
  }
}

async function uninstallPlugin(plugin: any) {
  if (!window.confirm(`卸载 ${plugin.name || plugin.id}？`)) return
  actionMessage.value = ''
  try {
    const res = await fetch(`/api/plugins/${encodeURIComponent(plugin.id)}`, { method: 'DELETE' })
    const data = await res.json().catch(() => ({}))
    if (!res.ok) throw new Error(data?.detail || '卸载插件失败')
    actionMessage.value = `已卸载 ${plugin.name || plugin.id}`
    await store.fetchPlugins()
    store.notifyPluginsChanged()
    await fetchMarket()
  } catch (err: any) {
    actionMessage.value = err?.message || '卸载插件失败'
  }
}

async function pluginAction(action: string, payload: Record<string, any> = {}) {
  if (!selectedPluginId.value) return null
  const res = await fetch(`/api/plugins/${encodeURIComponent(selectedPluginId.value)}/actions/${action}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ payload }),
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(data?.detail || `${action} failed`)
  return data
}

async function fetchLocalIndexStatus() {
  if (selectedPluginId.value !== 'local-subtitle-library') return
  try {
    localIndexStatus.value = await pluginAction('index_status')
  } catch {
    localIndexStatus.value = null
  }
}

async function rebuildLocalIndex() {
  if (selectedPluginId.value !== 'local-subtitle-library') return
  localRebuilding.value = true
  configError.value = ''
  configMessage.value = ''
  try {
    await saveConfig(false)
    const result = await pluginAction('rebuild_index')
    configMessage.value = `索引已重建：${Number(result?.indexed_files || 0).toLocaleString()} 个文件`
    await fetchLocalIndexStatus()
  } catch (err: any) {
    configError.value = err?.message || '重建索引失败'
  } finally {
    localRebuilding.value = false
  }
}

function formatPluginTime(ts?: number | null) {
  if (!ts) return '从未'
  return new Date(ts * 1000).toLocaleString('zh-CN')
}

async function hydrateQbConfigOptions() {
  if (selectedPluginId.value !== 'qbittorrent') return
  try {
    const res = await fetch('/api/plugins/qbittorrent/actions/download_options', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ payload: {} }),
    })
    const data = await res.json().catch(() => ({}))
    if (!res.ok || data?.ok === false) return
    const categories = Array.isArray(data.categories) ? data.categories : []
    if (configSchema.value.category && categories.length) {
      configSchema.value = {
        ...configSchema.value,
        category: {
          ...configSchema.value.category,
          options: categories.map((c: any) => ({
            label: c.save_path ? `${c.name} · ${c.save_path}` : String(c.name || ''),
            value: String(c.name || ''),
          })),
        },
      }
    }
    if (configSchema.value.savepath && data.default_savepath && !configDraft.value.savepath) configDraft.value.savepath = data.default_savepath
  } catch {}
}

async function openConfig(plugin: any) {
  selectedPluginId.value = plugin.id
  selectedPluginName.value = plugin.name || plugin.id
  configOpen.value = true
  configLoading.value = true
  configError.value = ''
  configMessage.value = ''
  try {
    const res = await fetch(`/api/plugins/${encodeURIComponent(plugin.id)}/config`)
    const data = await res.json().catch(() => ({}))
    if (!res.ok) throw new Error(data?.detail || '插件配置加载失败')
    configSchema.value = data.plugin?.config_schema || {}
    configDraft.value = { ...(data.config || {}) }
    localIndexStatus.value = null
    await hydrateQbConfigOptions()
    await fetchLocalIndexStatus()
  } catch (err: any) {
    configError.value = err?.message || '插件配置加载失败'
    configSchema.value = {}
    configDraft.value = {}
  } finally {
    configLoading.value = false
  }
}

async function saveConfig(showMessage = true) {
  if (!selectedPluginId.value) return
  configSaving.value = true
  configError.value = ''
  configMessage.value = ''
  try {
    const res = await fetch(`/api/plugins/${encodeURIComponent(selectedPluginId.value)}/config`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ config: configDraft.value }),
    })
    const data = await res.json().catch(() => ({}))
    if (!res.ok) throw new Error(data?.detail || '保存失败')
    if (showMessage) configMessage.value = '配置已保存'
  } catch (err: any) {
    configError.value = err?.message || '保存失败'
  } finally {
    configSaving.value = false
  }
}

async function testPlugin(plugin: any) {
  try {
    await fetch(`/api/plugins/${encodeURIComponent(plugin.id)}/test`, { method: 'POST' })
  } catch {}
}

onMounted(async () => {
  await store.fetchPlugins()
  await fetchMarket()
})
</script>

<template>
  <section class="page stack">
    <div class="page-heading">
      <div>
        <h1>插件管理</h1>
        <p>仓库共 {{ marketItems.length }} 插件 · 已启用 {{ store.enabledPlugins.length }} 个 · 未启用 {{ store.disabledPlugins.length }} 个 · 未安装 {{ notInstalledMarketItems.length }} 个</p>
      </div>
      <div class="actions"><NoorButton @click="openRepoManager()">仓库</NoorButton><NoorButton tone="primary" @click="store.reload()">重载插件</NoorButton></div>
    </div>

    <NoorState v-if="store.loading" type="loading" title="加载插件" />
    <NoorState v-else-if="store.error" type="error" :title="store.error" />
    <NoorState v-else-if="!store.plugins.length" type="empty" title="暂无插件" />

    <div v-else class="plugin-grid">
      <article class="plugin-card plugin-card--repo">
        <div class="plugin-card__head">
          <div><h2>插件仓库</h2><p>marketplace · system</p></div>
          <NoorBadge tone="info">内置</NoorBadge>
        </div>
        <p class="plugin-desc">管理插件源、发现可安装插件。</p>
        <div class="actions"><NoorButton tone="primary" @click="openRepoManager()">管理仓库</NoorButton><NoorButton @click="store.reload()">重载插件</NoorButton></div>
      </article>

      <article v-for="plugin in sortedPlugins" :key="plugin.id" class="plugin-card" :class="{ 'is-disabled': !plugin.enabled, 'is-enabled': plugin.enabled }">
        <div class="plugin-card__head">
          <div>
            <h2>{{ plugin.name }}</h2>
            <p>{{ plugin.id }} · {{ plugin.version || '-' }}</p>
          </div>
          <NoorBadge :tone="plugin.enabled ? 'success' : 'muted'">{{ plugin.enabled ? '已启用' : '未启用' }}</NoorBadge>
        </div>
        <p class="plugin-desc">{{ plugin.description || '-' }}</p>
        <div class="chip-row">
          <NoorBadge v-for="cap in (plugin.capabilities || []).slice(0, 3)" :key="cap">{{ cap }}</NoorBadge>
        </div>
        <div class="actions">
          <RouterLink v-if="(plugin.contributions?.sidebar as any)?.route" class="link-button" :to="`/plugins/${plugin.id}`">打开</RouterLink>
          <NoorButton @click="openConfig(plugin)">配置</NoorButton>
          <NoorButton @click="testPlugin(plugin)">测试</NoorButton>
          <NoorButton :tone="plugin.enabled ? 'ghost' : 'primary'" @click="store.setEnabled(plugin.id, !plugin.enabled)">{{ plugin.enabled ? '停用' : '启用' }}</NoorButton>
          <NoorButton tone="danger" @click="uninstallPlugin(plugin)">卸载</NoorButton>
        </div>
      </article>

      <article v-for="item in notInstalledMarketItems" :key="`${item.repo_url}:${item.id}`" class="plugin-card is-disabled">
        <div class="plugin-card__head">
          <div><h2>{{ item.name || item.id }}</h2><p>{{ item.id }} · {{ item.version || '-' }}</p></div>
          <NoorBadge tone="muted">未下载</NoorBadge>
        </div>
        <p class="plugin-desc">{{ item.description || '-' }}</p>
        <div class="chip-row"><NoorBadge>market</NoorBadge></div>
        <div class="actions"><NoorButton tone="primary" @click="installMarketItem(item)">安装</NoorButton></div>
      </article>
    </div>

    <NoorState v-if="actionMessage" type="empty" :title="actionMessage" />


    <div v-if="repoOpen" class="modal-mask" @click.self="repoOpen = false">
      <section class="delete-dialog plugin-config-dialog">
        <div class="delete-dialog__head">
          <div><h2>插件仓库</h2><p>管理仓库源与可安装插件</p></div>
          <NoorButton @click="repoOpen = false">关闭</NoorButton>
        </div>
        <div class="repo-add-row">
          <NoorInput v-model="repoInput" placeholder="GitHub 插件仓库 URL" />
          <NoorButton tone="primary" @click="addRepo()">添加仓库</NoorButton>
        </div>
        <NoorState v-if="marketLoading" type="loading" title="加载插件仓库" />
        <NoorState v-if="marketError" type="error" :title="marketError" />
        <div class="repo-list">
          <div v-for="repo in repos" :key="repo.url" class="repo-row">
            <span>{{ repo.url }}</span>
            <NoorButton tone="danger" @click="removeRepo(repo.url)">删除</NoorButton>
          </div>
          <NoorState v-if="!repos.length && !marketLoading" type="empty" title="暂无插件仓库" />
        </div>
        <div v-if="marketItems.some(item => item.error)" class="repo-list">
          <div v-for="item in marketItems.filter(item => item.error)" :key="`${item.repo_url}:${item.error}`" class="repo-row is-error">
            <span>{{ item.repo_url }}</span><em>{{ item.error }}</em>
          </div>
        </div>
      </section>
    </div>

    <div v-if="configOpen" class="modal-mask" @click.self="configOpen = false">
      <section class="delete-dialog plugin-config-dialog">
        <div class="delete-dialog__head">
          <div><h2>{{ selectedPluginName }}</h2><p>{{ selectedPluginId }} · 插件配置</p></div>
          <NoorButton @click="configOpen = false">关闭</NoorButton>
        </div>
        <NoorState v-if="configLoading" type="loading" title="加载配置" />
        <NoorState v-else-if="configError" type="error" :title="configError" />
        <NoorState v-else-if="!schemaEntries.length" type="empty" title="该插件没有可配置项" />
        <section v-if="selectedPluginId === 'local-subtitle-library' && localIndexStatus" class="plugin-index-panel">
          <div><strong>字幕索引</strong><span>状态：{{ localIndexStatus.index_exists ? '已建立' : '未建立' }} · 文件 {{ Number(localIndexStatus.indexed_count || 0).toLocaleString() }} · 更新 {{ formatPluginTime(localIndexStatus.index_updated_at) }}</span></div>
          <NoorButton tone="primary" :disabled="localRebuilding" @click="rebuildLocalIndex()">{{ localRebuilding ? '重建中' : '重建索引' }}</NoorButton>
        </section>
        <div v-if="schemaEntries.length && !configLoading && !configError" class="plugin-config-form">
          <label v-for="([key, meta]) in schemaEntries" :key="key" class="plugin-config-field">
            <span>
              <strong>{{ (meta as any).label || key }}</strong>
              <em v-if="(meta as any).description">{{ (meta as any).description }}</em>
            </span>
            <NoorSelect v-if="Array.isArray((meta as any).options) && (meta as any).options.length" v-model="configDraft[key]" :options="selectOptions(key, meta)" />
            <NoorToggle v-else-if="fieldType(meta) === 'boolean'" v-model="configDraft[key]" :label="configDraft[key] ? '开启' : '关闭'" />
            <NoorTextarea v-else-if="fieldType(meta) === 'textarea'" v-model="configDraft[key]" :placeholder="(meta as any).placeholder || ''" />
            <NoorInput v-else-if="fieldType(meta) === 'number'" :model-value="configDraft[key]" type="number" :placeholder="(meta as any).placeholder || ''" @update:model-value="updateNumberConfig(key, $event)" />
            <NoorInput v-else v-model="configDraft[key]" :type="fieldType(meta)" :placeholder="(meta as any).placeholder || ''" />
          </label>
        </div>
        <NoorState v-if="configMessage" type="empty" :title="configMessage" />
        <div class="delete-dialog__actions">
          <NoorButton @click="configOpen = false">取消</NoorButton>
          <NoorButton tone="primary" :disabled="configSaving" @click="saveConfig()">{{ configSaving ? '保存中' : '保存' }}</NoorButton>
        </div>
      </section>
    </div>
  </section>
</template>
