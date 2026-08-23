<script setup lang="ts">
import { onMounted, ref, computed } from 'vue'
import { useToast } from '../../composables/useToast'
import { useI18n } from '../../composables/useI18n'
import { NoorButton, NoorInput, NoorSelect, NoorState } from '../../components/noor-kit'

interface PluginItem {
  id: string
  name: string
  version: string
  type: 'rss_source' | 'downloader' | 'dashboard_widget' | 'subtitle_provider'
  description: string
  tags: string[]
  capabilities: string[]
  enabled: boolean
}

interface PluginConfigResponse {
  plugin: {
    id: string
    config_schema?: Record<string, any>
  }
  config: Record<string, any>
}

const { t } = useI18n()
const toast = useToast()

const loading = ref(false)
const reloading = ref(false)
const repoInput = ref('')
const repos = ref<{ url: string }[]>([])
const marketItems = ref<any[]>([])
const plugins = ref<PluginItem[]>([])

const selectedPluginId = ref('')
const configSchema = ref<Record<string, any>>({})
const configDraft = ref<Record<string, any>>({})
const configLoading = ref(false)
const configSaving = ref(false)
const configDialogOpen = ref(false)
const repoDialogOpen = ref(false)
const localIndexStatus = ref<any | null>(null)
const localRebuilding = ref(false)
const localRebuildResult = ref<any | null>(null)


const enabledCount = computed(() => plugins.value.filter(p => p.enabled).length)
const disabledCount = computed(() => plugins.value.filter(p => !p.enabled).length)
const pagePlugins = computed(() => [...plugins.value].sort((a, b) => Number(b.enabled) - Number(a.enabled) || a.name.localeCompare(b.name, 'zh-CN')))
const notInstalledMarketItems = computed(() => marketItems.value.filter(item => item && !item.error && item.id && !pluginsById.value.has(item.id)))
const selectedPlugin = computed(() => plugins.value.find(p => p.id === selectedPluginId.value))

function pluginTypeLabel(type: string) {
  const map: Record<string, string> = {
    rss_source: '订阅源',
    downloader: '下载器',
    dashboard_widget: '概览组件',
    subtitle_provider: '字幕源',
  }
  return map[type] || type
}

function capabilityLabel(cap: string) {
  const map: Record<string, string> = {
    network_outbound: '联网',
    download_submit: '下载推送',
    sidebar_page: '侧边栏页面',
    rss_fetch: 'RSS',
    subtitle_search: '字幕搜索',
    subtitle_search_local: '本地字幕',
    dashboard_widget: '概览卡片',
    local_metrics: '本机状态',
  }
  return map[cap] || cap
}

function schemaEntries() {
  return Object.entries(configSchema.value || {})
}

function selectOptions(meta: any) {
  const currentValue = configDraft.value[meta.__key]
  const options = (Array.isArray(meta?.options) ? meta.options : []).map((opt: any) => {
    const rawValue = opt?.value ?? opt?.id ?? opt
    const rawLabel = opt?.label ?? rawValue
    return {
      id: rawValue,
      label: String(rawLabel),
    }
  })
  if (currentValue !== undefined && currentValue !== null && !options.some((opt: any) => opt.id === currentValue)) {
    options.unshift({ id: currentValue, label: String(currentValue) })
  }
  return options
}

function fieldMeta(key: string, meta: any) {
  return { ...(meta || {}), __key: key }
}

function updateNumberConfig(key: string, value: string) {
  configDraft.value[key] = value === '' ? '' : Number(value)
}

const pluginsById = computed(() => {
  const m = new Map<string, PluginItem>()
  for (const p of plugins.value) m.set(p.id, p)
  return m
})

function pluginSummary(p: PluginItem) {
  const caps = (p.capabilities || []).filter(cap => !['network_outbound'].includes(cap)).map(capabilityLabel)
  return caps.slice(0, 2).join(' · ') || p.description || pluginTypeLabel(p.type)
}

function openRepoManager() {
  repoDialogOpen.value = true
}

onMounted(async () => {
  await refreshAll()
})

function notifyPluginsChanged() {
  window.dispatchEvent(new CustomEvent('noor:plugins-changed'))
}

async function refreshAll() {
  loading.value = true
  try {
    const [p, r, m] = await Promise.all([
      fetch('/api/plugins').then(x => x.json()),
      fetch('/api/plugins/market/repos').then(x => x.json()),
      fetch('/api/plugins/market/items').then(x => x.json()),
    ])
    plugins.value = Array.isArray(p) ? p : []
    repos.value = Array.isArray(r) ? r : []
    marketItems.value = Array.isArray(m) ? m : []
    if (selectedPluginId.value && plugins.value.some(x => x.id === selectedPluginId.value)) {
      await loadConfig(selectedPluginId.value)
    }
  } catch (e: any) {
    toast.error(e?.message || t('settings.plugins.loadFailed'))
  } finally {
    loading.value = false
  }
}



async function reloadPlugins() {
  reloading.value = true
  try {
    await fetch('/api/plugins/reload', { method: 'POST' })
    toast.success(t('settings.plugins.reloaded'))
    await refreshAll()
    notifyPluginsChanged()
  } catch {
    toast.error(t('settings.plugins.reloadFailed'))
  } finally {
    reloading.value = false
  }
}

async function addRepo() {
  const url = repoInput.value.trim()
  if (!url) return
  try {
    const res = await fetch('/api/plugins/market/repos', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ repo_url: url }),
    })
    if (!res.ok) throw new Error((await res.json()).detail || 'add failed')
    repoInput.value = ''
    toast.success(t('settings.plugins.repoAdded'))
    await refreshAll()
  } catch (e: any) {
    toast.error(e?.message || t('settings.plugins.repoAddFailed'))
  }
}

async function removeRepo(url: string) {
  try {
    const res = await fetch('/api/plugins/market/repos', {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ repo_url: url }),
    })
    if (!res.ok) throw new Error('remove failed')
    await refreshAll()
  } catch {
    toast.error(t('settings.plugins.repoRemoveFailed'))
  }
}

async function install(item: any) {
  try {
    const res = await fetch('/api/plugins/market/install', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ repo_url: item.repo_url, plugin_id: item.id }),
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      throw new Error(err.detail || 'install failed')
    }
    toast.success(t('settings.plugins.installSuccess'))
    await refreshAll()
    notifyPluginsChanged()
  } catch (e: any) {
    toast.error(e?.message || t('settings.plugins.installFailed'))
  }
}

async function toggle(plugin: PluginItem) {
  try {
    const action = plugin.enabled ? 'disable' : 'enable'
    const res = await fetch(`/api/plugins/${plugin.id}/${action}`, { method: 'POST' })
    if (!res.ok) throw new Error('toggle failed')
    await refreshAll()
    notifyPluginsChanged()
  } catch {
    toast.error(t('settings.plugins.toggleFailed'))
  }
}

async function testPlugin(plugin: PluginItem) {
  try {
    const res = await fetch(`/api/plugins/${plugin.id}/test`, { method: 'POST' })
    const data = await res.json()
    if (!res.ok || !data?.ok) {
      throw new Error(data?.detail || data?.message || 'test failed')
    }
    toast.success(`${plugin.name}: ${data.message}`)
  } catch (e: any) {
    toast.error(e?.message || t('settings.plugins.testFailed'))
  }
}

async function loadConfig(pluginId: string) {
  selectedPluginId.value = pluginId
  configLoading.value = true
  try {
    const res = await fetch(`/api/plugins/${pluginId}/config`)
    if (!res.ok) throw new Error('load config failed')
    const data = await res.json() as PluginConfigResponse
    configSchema.value = data.plugin.config_schema || {}
    configDraft.value = { ...(data.config || {}) }
    if (pluginId === 'qbittorrent') await hydrateQbConfigOptions()
    configDialogOpen.value = true
    localRebuildResult.value = null
    if (pluginId === 'local-subtitle-library') await fetchLocalIndexStatus()
  } catch {
    configSchema.value = {}
    configDraft.value = {}
    toast.error(t('settings.plugins.configLoadFailed'))
  } finally {
    configLoading.value = false
  }
}

async function hydrateQbConfigOptions() {
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
          options: [

            ...categories.map((c: any) => ({
              label: c.save_path ? `${c.name} · ${c.save_path}` : String(c.name || ''),
              id: String(c.name || ''),
            })),
          ],
        },
      }
    }
    if (configSchema.value.savepath && data.default_savepath && !configDraft.value.savepath) {
      configDraft.value.savepath = data.default_savepath
    }
  } catch {
    // 配置弹窗不能因为 qB 在线选项读取失败而打不开。
  }
}

function fieldType(meta: any) {
  const t = String(meta?.type || 'string').toLowerCase()
  if (['number', 'integer'].includes(t)) return 'number'
  if (['boolean', 'switch', 'bool'].includes(t)) return 'boolean'
  if (['password'].includes(t)) return 'password'
  if (['textarea', 'multiline'].includes(t)) return 'textarea'
  return 'text'
}

async function saveConfig(showToast = true) {
  if (!selectedPluginId.value) return
  configSaving.value = true
  try {
    const res = await fetch(`/api/plugins/${selectedPluginId.value}/config`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ config: configDraft.value }),
    })
    if (!res.ok) throw new Error('save config failed')
    if (showToast) toast.success(t('settings.saveSuccess'))
  } catch {
    if (showToast) toast.error(t('settings.saveFailed', { error: '' }))
  } finally {
    configSaving.value = false
  }
}

function isLocalSubtitleConfig() {
  return selectedPluginId.value === 'local-subtitle-library'
}

function formatPluginTime(ts: number | null): string {
  if (!ts) return '从未'
  return new Date(ts * 1000).toLocaleString('zh-CN')
}

async function pluginAction(action: string, payload: Record<string, any> = {}) {
  if (!selectedPluginId.value) return null
  const res = await fetch(`/api/plugins/${selectedPluginId.value}/actions/${action}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ payload }),
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(data?.detail || `${action} failed`)
  return data
}

async function fetchLocalIndexStatus() {
  if (!isLocalSubtitleConfig()) return
  try {
    localIndexStatus.value = await pluginAction('index_status')
  } catch {
    localIndexStatus.value = null
  }
}

async function rebuildLocalIndex() {
  if (!isLocalSubtitleConfig()) return
  localRebuilding.value = true
  localRebuildResult.value = null
  try {
    await saveConfig(false)
    localRebuildResult.value = await pluginAction('rebuild_index')
    await fetchLocalIndexStatus()
    toast.success('索引已重建')
  } catch (e: any) {
    toast.error(e?.message || '重建索引失败')
  } finally {
    localRebuilding.value = false
  }
}

async function clearImageCache() {
  if (!selectedPluginId.value) return
  try {
    const res = await fetch(`/api/plugins/${selectedPluginId.value}/images/cache`, { method: 'DELETE' })
    const data = await res.json().catch(() => ({}))
    if (!res.ok) throw new Error(data?.detail || 'clear failed')
    toast.success(`已清空图片缓存：${data.deleted_files || 0} 个文件`)
  } catch (e: any) {
    toast.error(e?.message || '清空图片缓存失败')
  }
}

async function uninstall(plugin: PluginItem) {
  if (!window.confirm(`${t('settings.plugins.uninstall')} ${plugin.name}?`)) return
  try {
    const res = await fetch(`/api/plugins/${plugin.id}`, { method: 'DELETE' })
    if (!res.ok) throw new Error('uninstall failed')
    if (selectedPluginId.value === plugin.id) {
      selectedPluginId.value = ''
      configSchema.value = {}
      configDraft.value = {}
    }
    toast.success(t('settings.plugins.uninstallSuccess'))
    await refreshAll()
    notifyPluginsChanged()
  } catch {
    toast.error(t('settings.plugins.uninstallFailed'))
  }
}
</script>

<template>
  <div class="plugins-page">
    <section class="plugins-section">
      <div class="plugins-section__head plugins-section__head--compact">
        <div class="plugins-title-row">
          <h4>插件管理</h4>
          <span>仓库共 {{ marketItems.length }} 插件 · 已启用 {{ enabledCount }} 个 · 未启用 {{ disabledCount }} 个 · 未安装 {{ notInstalledMarketItems.length }} 个</span>
        </div>
      </div>

      <NoorState v-if="loading" type="loading" :title="t('common.loading')" />
      <div v-else class="plugin-card-grid">
        <article class="plugin-card plugin-card--repo is-enabled">
          <div class="plugin-card__top">
            <div class="plugin-card__identity">
              <div class="plugin-card__icon">仓</div>
              <div>
                <h5>插件仓库</h5>
                <p>marketplace · system</p>
              </div>
            </div>
            <span class="plugin-status is-on">内置</span>
          </div>
          <p class="plugin-card__desc">管理插件仓库，并发现尚未安装的插件。</p>
          <div class="plugin-card__meta plugin-card__meta--text">{{ repos.length }} 个仓库 · {{ notInstalledMarketItems.length }} 个可安装</div>
          <div class="plugin-card__actions">
            <NoorButton tone="primary" size="sm" @click="openRepoManager">管理仓库</NoorButton>
            <NoorButton tone="secondary" size="sm" :disabled="reloading" @click="reloadPlugins">{{ t('settings.plugins.reload') }}</NoorButton>
          </div>
        </article>

        <article v-for="p in pagePlugins" :key="p.id" class="plugin-card" :class="{ 'is-enabled': p.enabled, 'is-disabled': !p.enabled }">
          <div class="plugin-card__top">
            <div class="plugin-card__identity">
              <div class="plugin-card__icon">{{ p.name.slice(0, 1).toUpperCase() }}</div>
              <div>
                <h5>{{ p.name }}</h5>
                <p>{{ p.id }} · v{{ p.version }}</p>
              </div>
            </div>
            <span class="plugin-status" :class="p.enabled ? 'is-on' : 'is-off'">{{ p.enabled ? '已启用' : '未启用' }}</span>
          </div>

          <p class="plugin-card__desc">{{ p.description || '-' }}</p>

          <div class="plugin-card__meta plugin-card__meta--text">
            <span>{{ pluginTypeLabel(p.type) }}</span>
            <em v-if="pluginSummary(p)">{{ pluginSummary(p) }}</em>
          </div>

          <div class="plugin-card__actions">
            <NoorButton :tone="p.enabled ? 'secondary' : 'primary'" size="sm" @click="toggle(p)">{{ p.enabled ? t('settings.plugins.disable') : t('settings.plugins.enable') }}</NoorButton>
            <NoorButton tone="secondary" size="sm" @click="loadConfig(p.id)">{{ t('settings.plugins.config') }}</NoorButton>
            <NoorButton tone="secondary" size="sm" @click="testPlugin(p)">{{ t('common.test') }}</NoorButton>
            <NoorButton tone="danger" size="sm" @click="uninstall(p)">{{ t('settings.plugins.uninstall') }}</NoorButton>
          </div>
        </article>

        <article v-for="item in notInstalledMarketItems" :key="`${item.repo_url}:${item.id}`" class="plugin-card plugin-card--market">
          <div class="plugin-card__top">
            <div class="plugin-card__identity">
              <div class="plugin-card__icon">{{ String(item.name || item.id).slice(0, 1).toUpperCase() }}</div>
              <div>
                <h5>{{ item.name || item.id }}</h5>
                <p>{{ item.id }} · v{{ item.version || '0.1.0' }}</p>
              </div>
            </div>
            <span class="plugin-status is-remote">未下载</span>
          </div>
          <p class="plugin-card__desc">{{ item.description || '-' }}</p>
          <div class="plugin-card__meta plugin-card__meta--text">插件仓库</div>
          <div class="plugin-card__actions">
            <NoorButton tone="primary" size="sm" @click="install(item)">{{ t('settings.plugins.install') }}</NoorButton>
          </div>
        </article>
      </div>
    </section>

    <div v-if="repoDialogOpen" class="plugin-modal-mask" @click.self="repoDialogOpen = false">
      <div class="plugin-modal plugin-modal--repo">
        <header class="plugin-modal__header">
          <div class="plugin-modal__title">
            <h3>插件仓库</h3>
            <span class="plugin-modal__meta">管理仓库源与可安装插件</span>
          </div>
          <button class="plugin-modal__close" @click="repoDialogOpen = false">×</button>
        </header>

        <div class="repo-modal-body">
          <div class="repo-row">
            <NoorInput v-model="repoInput" :placeholder="t('settings.plugins.repoPlaceholder')" />
            <NoorButton tone="primary" size="sm" @click="addRepo">{{ t('settings.plugins.addRepo') }}</NoorButton>
          </div>

          <div v-if="repos.length" class="repo-list">
            <div v-for="r in repos" :key="r.url" class="repo-item">
              <span>{{ r.url }}</span>
              <button @click="removeRepo(r.url)">{{ t('common.delete') }}</button>
            </div>
          </div>
          <NoorState v-else title="暂无插件仓库" />

          <div v-if="marketItems.some(item => item.error)" class="market-list">
            <div v-for="item in marketItems.filter(item => item.error)" :key="`${item.repo_url}:${item.error}`" class="market-item">
              <strong>{{ item.repo_url }}</strong>
              <span class="market-error">{{ item.error }}</span>
            </div>
          </div>
        </div>

        <footer class="plugin-modal__footer">
          <NoorButton tone="secondary" size="sm" @click="repoDialogOpen = false">{{ t('common.close') }}</NoorButton>
        </footer>
      </div>
    </div>

    <div v-if="configDialogOpen" class="plugin-modal-mask" @click.self="configDialogOpen = false">
      <div class="plugin-modal">
        <header class="plugin-modal__header">
          <div class="plugin-modal__title">
            <h3>{{ selectedPlugin?.name || selectedPluginId }}</h3>
            <span v-if="selectedPlugin" class="plugin-modal__meta">{{ selectedPluginId }} · {{ pluginTypeLabel(selectedPlugin.type) }}</span>
            <span v-if="selectedPlugin" :class="selectedPlugin.enabled ? 'is-on' : 'is-off'" class="plugin-status plugin-status--compact">{{ selectedPlugin.enabled ? '已启用' : '未启用' }}</span>
          </div>
          <button class="plugin-modal__close" @click="configDialogOpen = false">×</button>
        </header>

        <NoorState v-if="configLoading" type="loading" :title="t('common.loading')" />
        <NoorState v-else-if="!schemaEntries().length" title="该插件没有可配置项" />
        <div v-else class="config-form config-form--rows">
          <section v-if="isLocalSubtitleConfig() && configDraft['index_enabled']" class="plugin-index-section">
            <div class="plugin-index-section__header">
              <span class="plugin-index-section__title">字幕索引</span>
              <button class="inline-action" :disabled="localRebuilding" @click="rebuildLocalIndex">
                {{ localRebuilding ? '重建中' : '重建索引' }}
              </button>
            </div>
            <div v-if="localIndexStatus" class="plugin-index-stats">
              <div class="plugin-index-stat"><span>索引状态</span><strong>{{ localIndexStatus.index_exists ? '已建立' : '未建立' }}</strong></div>
              <div class="plugin-index-stat"><span>已索引文件</span><strong>{{ Number(localIndexStatus.indexed_count || 0).toLocaleString() }}</strong></div>
              <div class="plugin-index-stat"><span>更新时间</span><strong>{{ formatPluginTime(localIndexStatus.index_updated_at) }}</strong></div>
              <div class="plugin-index-stat"><span>配置路径</span><strong>{{ (localIndexStatus.configured_paths || []).length }}</strong></div>
            </div>
            <div v-if="localRebuildResult" class="plugin-rebuild-result">
              已完成：{{ Number(localRebuildResult.indexed_files || 0).toLocaleString() }} 个文件，{{ localRebuildResult.elapsed_seconds }} 秒
            </div>
          </section>

          <div v-for="([key, meta]) in schemaEntries()" :key="key" class="config-field" :class="{ 'config-field--boolean': fieldType(meta) === 'boolean' }">
            <div class="config-field__label">
              <label>{{ meta.label || key }}</label>
              <p v-if="meta.description" class="config-field__desc">{{ meta.description }}</p>
            </div>

            <div class="config-field__control">
              <NoorSelect v-if="Array.isArray(meta.options) && meta.options.length" v-model="configDraft[key]" :options="selectOptions(fieldMeta(key, meta))" value-key="id" />
              <textarea
                v-else-if="fieldType(meta) === 'textarea'"
                v-model="configDraft[key]"
                class="plugins-input plugins-textarea"
                :placeholder="meta.placeholder || ''"
                rows="5"
              />
              <label v-else-if="fieldType(meta) === 'boolean'" class="plugin-switch">
                <input type="checkbox" v-model="configDraft[key]" />
                <span></span>
                <em>{{ configDraft[key] ? '开启' : '关闭' }}</em>
              </label>
              <NoorInput
                v-else-if="fieldType(meta) === 'number'"
                :model-value="configDraft[key]"
                type="number"
                :placeholder="meta.placeholder || ''"
                @update:model-value="updateNumberConfig(key, $event)"
              />
              <NoorInput
                v-else
                v-model="configDraft[key]"
                :type="fieldType(meta)"
                :placeholder="meta.placeholder || ''"
              />
              <button v-if="key === 'cache_days'" class="inline-danger" @click="clearImageCache">清空图片缓存</button>
            </div>
          </div>
        </div>

        <footer class="plugin-modal__footer">
          <NoorButton tone="secondary" size="sm" @click="configDialogOpen = false">{{ t('common.close') }}</NoorButton>
          <NoorButton tone="primary" size="sm" :disabled="configSaving" @click="saveConfig()">{{ t('common.save') }}</NoorButton>
        </footer>
      </div>
    </div>
  </div>
</template>

<style scoped>
.plugins-page{display:flex;flex-direction:column;gap:14px}.plugins-section{border:1px solid rgba(255,255,255,.06);background:var(--color-bg-surface);border-radius:var(--radius-lg);padding:16px}.plugins-section h4{margin:0;color:#fff;font-size:16px;font-weight:700}.plugin-chip,.plugin-type{height:26px;display:inline-flex;align-items:center;border-radius:999px;border:1px solid rgba(255,255,255,.06);background:rgba(255,255,255,.035);color:var(--color-text-secondary);padding:0 10px;font-size:12px;font-weight:600}.plugins-section__head{display:flex;align-items:flex-start;justify-content:space-between;gap:12px;margin-bottom:12px}.plugins-section__head--compact{margin-bottom:14px}.plugins-title-row{display:flex;align-items:baseline;gap:10px;flex-wrap:wrap}.plugins-title-row span{color:var(--color-text-muted);font-size:12px;font-weight:600}.plugin-card-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:12px}.plugin-card{display:flex;flex-direction:column;gap:12px;min-height:210px;border:1px solid rgba(255,255,255,.06);background:rgba(255,255,255,.025);border-radius:var(--radius-lg);padding:14px;transition:all var(--transition-fast)}.plugin-card:hover{transform:translateY(-1px);border-color:rgba(0,117,255,.28);background:var(--color-bg-elevated)}.plugin-card.is-enabled{border-color:rgba(0,117,255,.28);background:rgba(0,117,255,.045)}.plugin-card.is-disabled{opacity:.72}.plugin-card.is-disabled:hover{opacity:.92}.plugin-card--market{opacity:.48;background:rgba(255,255,255,.018)}.plugin-card--market:hover{opacity:.76}.plugin-card--repo{order:-10}.plugin-card__top,.plugin-card__identity,.plugin-card__actions{display:flex;align-items:center;gap:10px}.plugin-card__top{justify-content:space-between}.plugin-card__identity{min-width:0}.plugin-card__icon{width:38px;height:38px;border-radius:var(--radius-md);display:flex;align-items:center;justify-content:center;background:rgba(0,117,255,.16);color:#fff;font-weight:800;flex:0 0 auto}.plugin-card__icon--modal{width:42px;height:42px}.plugin-card h5{margin:0;color:#fff;font-size:14px;font-weight:700}.plugin-card__identity p{margin:3px 0 0;color:var(--color-text-muted);font-size:11px}.plugin-status{height:24px;display:inline-flex;align-items:center;border-radius:999px;padding:0 9px;font-size:11px;font-weight:700;border:1px solid transparent;white-space:nowrap}.plugin-status.is-on{background:rgba(1,181,116,.15);border-color:rgba(1,181,116,.25);color:#fff}.plugin-status.is-off{background:rgba(98,117,148,.12);border-color:rgba(98,117,148,.18);color:var(--color-text-muted)}.plugin-status.is-remote{background:rgba(255,255,255,.045);border-color:rgba(255,255,255,.06);color:var(--color-text-muted)}.plugin-card__desc{min-height:38px;margin:0;color:var(--color-text-secondary);font-size:12px;line-height:1.55;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}.plugin-card__meta{display:flex;gap:6px;flex-wrap:wrap}.plugin-card__meta--text{display:flex;align-items:center;gap:8px;color:var(--color-text-muted);font-size:11px;line-height:1.4}.plugin-card__meta--text span{color:var(--color-text-secondary);font-weight:700}.plugin-card__meta--text em{font-style:normal;color:var(--color-text-muted)}.plugin-type{background:rgba(0,117,255,.12);border-color:rgba(0,117,255,.22);color:#fff}.plugin-chip{height:24px;font-size:11px;padding:0 8px}.plugin-card__actions{margin-top:auto;flex-wrap:wrap}.plugin-card__actions :deep(.noor-button){font-size:.71rem}.plugin-card.is-disabled .plugin-card__actions :deep(.noor-button){opacity:.75}.plugin-card__actions :deep(.noor-button:hover){opacity:1}.plugins-state{min-height:42px;display:flex;align-items:center;justify-content:center;gap:10px;border:1px solid var(--color-border-default);border-radius:var(--radius-button);background:rgba(255,255,255,.025);color:var(--color-text-secondary);font-size:13px;font-weight:600}.plugins-spinner{width:14px;height:14px;border-radius:999px;border:2px solid rgba(255,255,255,.16);border-top-color:var(--color-brand);animation:plugin-spin .8s linear infinite}@keyframes plugin-spin{to{transform:rotate(360deg)}}.repo-row{display:flex;gap:8px}.plugins-input{width:100%;height:38px;border-radius:var(--radius-md);border:1px solid var(--color-border-default);background:rgba(255,255,255,.04);color:#fff;padding:0 12px;outline:none;font-size:13px}.plugins-input:focus{border-color:var(--color-border-focus);box-shadow:0 0 0 3px rgba(0,117,255,.1)}select.plugins-input{appearance:none;background-color:rgba(255,255,255,.04);background-image:linear-gradient(45deg,transparent 50%,rgba(255,255,255,.55) 50%),linear-gradient(135deg,rgba(255,255,255,.55) 50%,transparent 50%);background-position:calc(100% - 15px) 16px,calc(100% - 10px) 16px;background-size:5px 5px,5px 5px;background-repeat:no-repeat;padding-right:30px}select.plugins-input option{background:var(--color-bg-elevated);color:#fff}.plugins-textarea{height:auto;min-height:112px;resize:vertical;line-height:1.5;padding-top:10px;padding-bottom:10px}.repo-modal-body{padding:16px;overflow:auto}.repo-list,.market-list{margin-top:10px;display:flex;flex-direction:column;gap:8px}.repo-item,.market-item{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:10px 12px;border-radius:var(--radius-md);background:rgba(255,255,255,.025);border:1px solid rgba(255,255,255,.06);color:var(--color-text-secondary);font-size:12px}.repo-item span{word-break:break-all}.repo-item button{border:0;background:transparent;color:rgba(255,138,138,.9);cursor:pointer}.market-item strong{display:block;color:#fff;font-size:13px}.market-item span{display:block;margin-top:3px;color:var(--color-text-secondary);font-size:12px}.market-item em{display:block;margin-top:3px;color:var(--color-text-muted);font-size:11px;font-style:normal}.market-error{color:rgba(255,138,138,.9)!important}.plugin-modal-mask{position:fixed;inset:0;z-index:100;display:flex;align-items:center;justify-content:center;padding:16px;background:rgba(0,0,0,.62);backdrop-filter:blur(8px)}.plugin-modal{width:min(920px,96vw);max-height:86vh;display:flex;flex-direction:column;overflow:hidden;border:1px solid var(--color-border-default);border-radius:var(--radius-lg);background:var(--color-bg-elevated);box-shadow:var(--shadow-lg)}.plugin-modal__header{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:14px 16px;border-bottom:1px solid rgba(255,255,255,.06)}.plugin-modal__title{display:flex;align-items:center;gap:10px;min-width:0;flex-wrap:wrap}.plugin-modal__title h3{margin:0;color:#fff;font-size:15px;font-weight:800}.plugin-modal__meta{color:var(--color-text-muted);font-size:12px}.plugin-status--compact{height:22px;font-size:11px;padding:0 8px}.plugin-modal__close{width:30px;height:30px;border-radius:var(--radius-md);border:1px solid rgba(255,255,255,.08);background:rgba(255,255,255,.035);color:#fff;font-size:18px;line-height:1;cursor:pointer}.config-form{padding:16px;overflow:auto;display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.config-form--rows{display:flex;flex-direction:column;gap:0;padding:8px 16px 16px}.config-field{padding:12px;border-radius:var(--radius-md);border:1px solid rgba(255,255,255,.06);background:rgba(255,255,255,.025);display:flex;flex-direction:column;gap:8px}.config-form--rows .config-field{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:16px;align-items:flex-start;border:0;border-bottom:1px solid rgba(255,255,255,.06);border-radius:0;background:transparent;padding:14px 0}.config-field--boolean{justify-content:space-between}.config-field__label{display:flex;flex-direction:column;gap:4px;align-items:flex-start}.config-field__label label{color:#fff;font-size:13px;font-weight:700}.config-field__desc{margin:0;color:var(--color-text-muted);font-size:11px;line-height:1.45}.config-field__control{min-width:0;display:flex;flex-direction:column;gap:8px}.plugin-index-section{margin:4px 0 10px;padding:12px;border-radius:var(--radius-md);border:1px solid rgba(255,255,255,.06);background:rgba(255,255,255,.025)}.plugin-index-section__header{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:10px}.plugin-index-section__title{color:#fff;font-size:13px;font-weight:700}.inline-action{height:28px;border-radius:999px;border:1px solid rgba(0,117,255,.25);background:rgba(0,117,255,.14);color:#fff;padding:0 11px;font-size:12px;cursor:pointer}.inline-action:disabled{opacity:.5;cursor:not-allowed}.plugin-index-stats{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px}.plugin-index-stat{border-radius:var(--radius-sm);background:rgba(255,255,255,.035);padding:9px 10px;display:flex;flex-direction:column;gap:4px}.plugin-index-stat span{color:var(--color-text-muted);font-size:11px}.plugin-index-stat strong{color:#fff;font-size:12px;font-weight:700;word-break:break-all}.plugin-rebuild-result{margin-top:8px;color:var(--color-text-secondary);font-size:12px}.plugin-switch{display:flex;align-items:center;gap:10px;color:var(--color-text-secondary);font-size:12px}.plugin-switch input{display:none}.plugin-switch span{width:40px;height:22px;border-radius:999px;background:rgba(255,255,255,.1);position:relative;transition:all var(--transition-fast)}.plugin-switch span:before{content:'';position:absolute;width:16px;height:16px;border-radius:999px;left:3px;top:3px;background:#fff;transition:transform var(--transition-fast)}.plugin-switch input:checked+span{background:var(--color-brand)}.plugin-switch input:checked+span:before{transform:translateX(18px)}.plugin-switch em{font-style:normal}.inline-danger{align-self:flex-start;border:0;background:transparent;color:rgba(255,138,138,.9);font-size:12px;cursor:pointer;padding:0}.plugin-modal__footer{display:flex;justify-content:flex-end;gap:8px;padding:12px 16px;border-top:1px solid rgba(255,255,255,.06);background:rgba(3,12,29,.22)}@media(max-width:760px){.plugins-section__head,.repo-row,.market-item{flex-direction:column;align-items:stretch}.plugin-card-grid,.config-form{grid-template-columns:1fr}.config-form--rows .config-field{grid-template-columns:1fr;gap:8px}.plugin-index-stats{grid-template-columns:repeat(2,minmax(0,1fr))}.plugin-card__top{align-items:flex-start}.plugin-modal{max-height:92vh}}
</style>
