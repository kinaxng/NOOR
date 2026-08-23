<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import BaseIcon from '../components/noor/BaseIcon.vue'
import PluginIcon from '../components/noor/PluginIcon.vue'
import BaseModal from '../components/ui/BaseModal.vue'
import FieldRow from '../components/ui/FieldRow/FieldRow.vue'
import api from '../api'
import { useToast } from '../composables/useToast'

type PluginListItem = {
  id: string
  name: string
  version?: string
  type: string
  description?: string
  tags?: string[]
  capabilities?: string[]
  config?: Record<string, any>
  contributions?: {
    icon?: string
    sidebar?: {
      route?: string
      icon?: string
    }
  }
  enabled?: boolean
}

type MarketPluginItem = {
  id: string
  name?: string
  version?: string
  type?: string
  description?: string
  tags?: string[]
  capabilities?: string[]
  config?: Record<string, any>
  contributions?: {
    icon?: string
    sidebar?: {
      route?: string
      icon?: string
    }
  }
  repo_url?: string
  installed?: boolean
}

type PluginConfigField = {
  type?: string
  label?: string
  placeholder?: string
  description?: string
  default?: any
  min?: number
  max?: number
  step?: number
  options?: Array<{ label?: string; value: string }>; multi?: boolean
}

type PluginConfigResponse = {
  plugin: PluginListItem & {
    config_schema?: Record<string, PluginConfigField>
    default_config?: Record<string, any>
  }
  config: Record<string, any>
}

type PluginCardItem = {
  id: string
  name: string
  version: string
  type: string
  description: string
  tags: string[]
  capabilities: string[]
  config?: Record<string, any>
  contributions?: {
    icon?: string
    sidebar?: {
      route?: string
      icon?: string
    }
  }
  repoUrl: string
  installed: boolean
  enabled: boolean
  source: 'local' | 'market'
  status: 'enabled' | 'inactive' | 'uninstalled'
}

const toast = useToast()

const loading = ref(false)
const error = ref('')
const installedPlugins = ref<PluginListItem[]>([])
const marketPlugins = ref<MarketPluginItem[]>([])

const configModalOpen = ref(false)
const infoModalOpen = ref(false)
const configLoading = ref(false)
const configSaving = ref(false)
const configTesting = ref(false)
const pluginMetaLoading = ref(false)
const pluginMetaError = ref('')
const localSubtitleIndexStatus = ref<null | {
  index_exists: boolean
  indexed_count: number
  index_updated_at: number | null
  configured_paths: string[]
  index_enabled: boolean
}>(null)
const localSubtitleRebuilding = ref(false)
const localSubtitleRebuildResult = ref<null | {
  indexed_files: number
  elapsed_seconds: number
}>(null)
const configPlugin = ref<PluginCardItem | null>(null)
const configSchema = ref<Record<string, PluginConfigField>>({})
const configDraft = ref<Record<string, any>>({})

const activeDownloaderOptions = computed(() => {
  return installedPlugins.value
    .filter(plugin => plugin.enabled && plugin.type === 'downloader')
    .map(plugin => ({
      value: plugin.id,
      label: plugin.name || plugin.id,
      description: plugin.description || '',
    }))
    .sort((a, b) => a.label.localeCompare(b.label, 'zh-CN'))
})

const pluginCards = computed<PluginCardItem[]>(() => {
  const byId = new Map<string, PluginCardItem>()

  for (const item of installedPlugins.value) {
    byId.set(item.id, {
      id: item.id,
      name: item.name,
      version: item.version || '',
      type: item.type,
      description: item.description || '暂无说明',
      tags: item.tags || [],
      capabilities: item.capabilities || [],
      config: item.config || {},
      contributions: item.contributions,
      repoUrl: '',
      installed: true,
      enabled: !!item.enabled,
      source: 'local',
      status: item.enabled ? 'enabled' : 'inactive',
    })
  }

  for (const item of marketPlugins.value) {
    if (!item.id || !item.name) continue
    const existing = byId.get(item.id)
    if (existing) {
      existing.repoUrl = item.repo_url || existing.repoUrl
      existing.version = existing.version || item.version || ''
      existing.description = existing.description || item.description || '暂无说明'
      existing.tags = existing.tags.length ? existing.tags : (item.tags || [])
      existing.capabilities = existing.capabilities.length ? existing.capabilities : (item.capabilities || [])
      existing.config = existing.config || item.config || {}
      existing.contributions = existing.contributions || item.contributions
      continue
    }
    byId.set(item.id, {
      id: item.id,
      name: item.name,
      version: item.version || '',
      type: item.type || 'plugin',
      description: item.description || '暂无说明',
      tags: item.tags || [],
      capabilities: item.capabilities || [],
      config: item.config || {},
      contributions: item.contributions,
      repoUrl: item.repo_url || '',
      installed: false,
      enabled: false,
      source: 'market',
      status: 'uninstalled',
    })
  }

  return [...byId.values()].sort((a, b) => {
    const order = { enabled: 0, inactive: 1, uninstalled: 2 }
    return order[a.status] - order[b.status] || a.name.localeCompare(b.name, 'zh-CN')
  })
})

const stats = computed(() => {
  const enabled = pluginCards.value.filter(item => item.status === 'enabled').length
  const inactive = pluginCards.value.filter(item => item.status === 'inactive').length
  const uninstalled = pluginCards.value.filter(item => item.status === 'uninstalled').length
  return `仓库共 ${pluginCards.value.length} 个插件 · 已启用 ${enabled} 个 · 未激活 ${inactive} 个 · 未安装 ${uninstalled} 个`
})

function routeOf(plugin: PluginCardItem) {
  const route = plugin.contributions?.sidebar?.route
  if (typeof route === 'string' && route) return route
  return plugin.capabilities.includes('sidebar_page') ? `/plugins/${plugin.id}` : ''
}

function pluginCapabilitySummary(plugin: PluginCardItem) {
  const caps = new Set(plugin.capabilities || [])
  const labels = [
    caps.has('sidebar_page') ? '独立页面' : '',
    caps.has('subtitle_search') ? '字幕源' : '',
    caps.has('download_submit') ? '下载器' : '',
    caps.has('dashboard_widget') ? '概览组件' : '',
  ].filter(Boolean)
  return labels.join(' · ') || plugin.type || '扩展能力'
}

function statusLabel(status: PluginCardItem['status']) {
  return status === 'enabled' ? '已启用' : status === 'inactive' ? '未激活' : '未安装'
}

async function loadData(force = false) {
  if (loading.value && !force) return
  loading.value = true
  error.value = ''
  try {
    const [pluginsRes, marketRes] = await Promise.all([
      api.get('/plugins'),
      api.get('/plugins/market/items').catch(() => ({ data: [] })),
    ])
    installedPlugins.value = Array.isArray(pluginsRes.data)
      ? pluginsRes.data
      : (Array.isArray(pluginsRes.data?.items) ? pluginsRes.data.items : [])
    marketPlugins.value = Array.isArray(marketRes.data)
      ? marketRes.data.filter((item: any) => item && item.id && !item.error)
      : []
  } catch (e: any) {
    error.value = e?.response?.data?.detail || e?.message || '插件加载失败'
  } finally {
    loading.value = false
  }
}

async function setEnabled(plugin: PluginCardItem, enabled: boolean) {
  try {
    await api.post(`/plugins/${plugin.id}/${enabled ? 'enable' : 'disable'}`)
    toast.success(enabled ? '插件已启用' : '插件已停用')
    await loadData(true)
  } catch (e: any) {
    toast.error(e?.response?.data?.detail || e?.message || '操作失败')
  }
}

async function installPlugin(plugin: PluginCardItem) {
  if (!plugin.repoUrl) {
    toast.error('缺少插件仓库来源，无法安装')
    return
  }
  try {
    await api.post('/plugins/market/install', {
      repo_url: plugin.repoUrl,
      plugin_id: plugin.id,
    })
    toast.success('插件已安装')
    await loadData(true)
  } catch (e: any) {
    toast.error(e?.response?.data?.detail || e?.message || '安装失败')
  }
}

function emptyDraftFromSchema(schema: Record<string, PluginConfigField>, current: Record<string, any>) {
  const out: Record<string, any> = {}
  for (const [key, meta] of Object.entries(schema)) {
    let val = current[key]

    // If it's a multi-select field, ensure it's an array
    if (meta.multi) {
      if (val === undefined || val === null) {
        val = meta.default || []
      }
      if (!Array.isArray(val)) {
        val = val ? (Array.isArray(val) ? val : [val]) : []
      }
    } else {
      if (val === undefined || val === null) {
        val = meta.default !== undefined ? meta.default : (meta.type === 'boolean' ? false : '')
      }
    }

    out[key] = val
  }
  return out
}

function normalizeDownloaderDraft() {
  if (configPlugin.value?.id !== 'javdb') return
  const activeIds = new Set(activeDownloaderOptions.value.map(item => item.value))
  const bindings = Array.isArray(configDraft.value.downloader_binding)
    ? configDraft.value.downloader_binding.map((item: any) => String(item || '').trim()).filter(Boolean)
    : String(configDraft.value.downloader_binding || '').trim()
      ? [String(configDraft.value.downloader_binding).trim()]
      : []
  const normalizedBindings = bindings.filter((id: string, index: number) => activeIds.has(id) && bindings.indexOf(id) === index)
  configDraft.value.downloader_binding = normalizedBindings
  const currentDefault = String(configDraft.value.default_downloader || 'none')
  configDraft.value.default_downloader = normalizedBindings.includes(currentDefault)
    ? currentDefault
    : (normalizedBindings[0] || 'none')
}

async function openConfig(plugin: PluginCardItem) {
  configPlugin.value = plugin
  configModalOpen.value = true
  configLoading.value = true
  configSchema.value = {}
  configDraft.value = {}
  pluginMetaLoading.value = false
  pluginMetaError.value = ''
  localSubtitleIndexStatus.value = null
  localSubtitleRebuildResult.value = null
  try {
    const { data } = await api.get<PluginConfigResponse>(`/plugins/${plugin.id}/config`)
    configSchema.value = data?.plugin?.config_schema || {}
    configDraft.value = emptyDraftFromSchema(configSchema.value, data?.config || {})
    normalizeDownloaderDraft()
    await loadPluginMeta(plugin)
  } catch (e: any) {
    toast.error(e?.response?.data?.detail || e?.message || '读取插件配置失败')
    closeConfig()
  } finally {
    configLoading.value = false
  }
}

function closeConfig() {
  configModalOpen.value = false
  infoModalOpen.value = false
  configLoading.value = false
  configSaving.value = false
  configTesting.value = false
  pluginMetaLoading.value = false
  pluginMetaError.value = ''
  localSubtitleIndexStatus.value = null
  localSubtitleRebuilding.value = false
  localSubtitleRebuildResult.value = null
  configPlugin.value = null
  configSchema.value = {}
  configDraft.value = {}
}

async function loadPluginMeta(plugin: PluginCardItem) {
  pluginMetaLoading.value = false
  pluginMetaError.value = ''
  localSubtitleIndexStatus.value = null
  localSubtitleRebuildResult.value = null
  if (plugin.id !== 'local-subtitle-library') return
  pluginMetaLoading.value = true
  try {
    const { data } = await api.post(`/plugins/${plugin.id}/actions/index_status`, { payload: {} })
    localSubtitleIndexStatus.value = data
  } catch (e: any) {
    pluginMetaError.value = e?.response?.data?.detail || e?.message || '读取索引状态失败'
  } finally {
    pluginMetaLoading.value = false
  }
}

function openInfo() {
  infoModalOpen.value = true
}

function closeInfo() {
  infoModalOpen.value = false
}

async function saveConfig() {
  if (!configPlugin.value || configSaving.value) return
  configSaving.value = true
  try {
    normalizeDownloaderDraft()
    await api.put(`/plugins/${configPlugin.value.id}/config`, { config: configDraft.value })
    toast.success('插件配置已保存')
    await loadData(true)
  } catch (e: any) {
    toast.error(e?.response?.data?.detail || e?.message || '保存失败')
  } finally {
    configSaving.value = false
  }
}

async function testConfig() {
  if (!configPlugin.value || configTesting.value) return
  configTesting.value = true
  try {
    normalizeDownloaderDraft()
    await api.put(`/plugins/${configPlugin.value.id}/config`, { config: configDraft.value })
    const { data } = await api.post(`/plugins/${configPlugin.value.id}/test`)
    if (data?.ok === false) {
      throw new Error(data?.message || '连接测试失败')
    }
    toast.success(data?.message || '连接测试通过')
  } catch (e: any) {
    toast.error(e?.response?.data?.detail || e?.message || '连接测试失败')
  } finally {
    configTesting.value = false
  }
}

async function rebuildLocalSubtitleIndex() {
  if (!configPlugin.value || configPlugin.value.id !== 'local-subtitle-library' || localSubtitleRebuilding.value) return
  localSubtitleRebuilding.value = true
  localSubtitleRebuildResult.value = null
  try {
    const { data } = await api.post(`/plugins/${configPlugin.value.id}/actions/rebuild_index`, { payload: {} })
    localSubtitleRebuildResult.value = data
    toast.success('字幕索引已重建')
    await loadPluginMeta(configPlugin.value)
  } catch (e: any) {
    toast.error(e?.response?.data?.detail || e?.message || '重建索引失败')
  } finally {
    localSubtitleRebuilding.value = false
  }
}

function isPasswordField(meta: PluginConfigField) {
  return meta.type === 'password'
}

function isTextareaField(meta: PluginConfigField) {
  return meta.type === 'textarea'
}

function isBooleanField(meta: PluginConfigField) {
  return meta.type === 'boolean'
}

function isNumberField(meta: PluginConfigField) {
  return meta.type === 'number'
}

function isSelectField(meta: PluginConfigField) {
  return Array.isArray(meta.options) && meta.options.length > 0
}

function isJavdbDownloaderBindingField(key: string | number) {
  return configPlugin.value?.id === 'javdb' && String(key) === 'downloader_binding'
}

function isHiddenJavdbDefaultDownloaderField(key: string | number) {
  return configPlugin.value?.id === 'javdb' && String(key) === 'default_downloader'
}

function boundDownloaders() {
  return Array.isArray(configDraft.value.downloader_binding) ? configDraft.value.downloader_binding : []
}

function isDownloaderBound(id: string) {
  return boundDownloaders().includes(id)
}

function toggleDownloaderBinding(id: string, checked: boolean) {
  const current = boundDownloaders()
  const next = checked
    ? [...current, id].filter((value, index, array) => array.indexOf(value) === index)
    : current.filter(value => value !== id)
  configDraft.value.downloader_binding = next
  if (!next.length) {
    configDraft.value.default_downloader = 'none'
  } else if (!next.includes(String(configDraft.value.default_downloader || 'none'))) {
    configDraft.value.default_downloader = next[0]
  }
}

function setDefaultDownloader(id: string) {
  if (!isDownloaderBound(id)) toggleDownloaderBinding(id, true)
  configDraft.value.default_downloader = id
}

function formatTimestamp(ts: number | null) {
  if (!ts) return '从未建立'
  return new Date(ts * 1000).toLocaleString('zh-CN')
}

onMounted(() => {
  void loadData(true)
})
</script>
<template>
  <section class="plugin-page">
    <header class="plugin-page__header">
      <div class="plugin-page__title-wrap">
        <h2>插件管理</h2>
        <p>{{ stats }}</p>
      </div>
      <button class="plugin-action plugin-action--primary" type="button" @click="loadData(true)">
        <BaseIcon name="refresh" class="w-4 h-4" />
        <span>刷新</span>
      </button>
    </header>

    <div v-if="loading" class="plugin-state">插件加载中</div>
    <div v-else-if="error" class="plugin-state plugin-state--error">{{ error }}</div>

    <div v-else class="plugin-grid">
      <article
        v-for="plugin in pluginCards"
        :key="plugin.id"
        class="plugin-card"
        :class="`plugin-card--${plugin.status}`"
      >
        <div class="plugin-card__head">
          <div class="plugin-card__identity">
            <div class="plugin-card__icon">
              <PluginIcon
                :plugin-id="plugin.id"
                :icon="plugin.contributions?.sidebar?.icon || plugin.contributions?.icon"
                class="w-5 h-5"
              />
            </div>
            <div class="plugin-card__name-wrap">
              <div class="plugin-card__title-row">
                <h4>{{ plugin.name }}</h4>
                <span v-if="plugin.version" class="plugin-card__version">v{{ plugin.version }}</span>
              </div>
              <span class="plugin-card__summary">{{ pluginCapabilitySummary(plugin) }}</span>
            </div>
          </div>
          <span class="plugin-status-dot" :class="`plugin-status-dot--${plugin.status}`" :title="statusLabel(plugin.status)"></span>
        </div>

        <p class="plugin-card__desc">{{ plugin.description }}</p>

        <div class="plugin-card__meta">
          <span class="plugin-card__meta-item plugin-card__meta-item--status" :class="`plugin-card__meta-item--${plugin.status}`">
            {{ statusLabel(plugin.status) }}
          </span>
          <span class="plugin-card__meta-item">{{ plugin.source === 'market' ? '仓库插件' : '本地插件' }}</span>
          <span v-if="plugin.tags.length" class="plugin-card__meta-item">{{ plugin.tags.slice(0, 2).join(' · ') }}</span>
          <span v-else class="plugin-card__meta-item">{{ plugin.type || 'plugin' }}</span>
        </div>

        <div class="plugin-card__actions">
          <div class="plugin-card__actions-main">
            <button
              v-if="plugin.status !== 'uninstalled'"
              class="plugin-action plugin-action--ghost"
              type="button"
              @click="openConfig(plugin)"
            >
              设置
            </button>

            <RouterLink
              v-if="routeOf(plugin) && plugin.status === 'enabled'"
              class="plugin-action plugin-action--ghost"
              :to="routeOf(plugin)"
            >
              打开
            </RouterLink>
          </div>

          <div class="plugin-card__actions-main">
            <button
              v-if="plugin.status === 'enabled'"
              class="plugin-action plugin-action--danger"
              type="button"
              @click="setEnabled(plugin, false)"
            >
              停用
            </button>

            <button
              v-else-if="plugin.status === 'inactive'"
              class="plugin-action plugin-action--primary"
              type="button"
              @click="setEnabled(plugin, true)"
            >
              启用
            </button>

            <button
              v-else
              class="plugin-action plugin-action--primary"
              type="button"
              @click="installPlugin(plugin)"
            >
              安装
            </button>
          </div>
        </div>
      </article>

      <div v-if="pluginCards.length === 0" class="plugin-empty">当前没有可展示的插件</div>
    </div>

    <BaseModal
      v-if="configModalOpen && configPlugin"
      :title="`${configPlugin.name} 设置`"
      size="xl"
      @close="closeConfig"
    >
      <template #header-actions>
        <button class="plugin-icon-button" type="button" title="插件信息" @click="openInfo">
          <BaseIcon name="info" class="w-4 h-4" />
        </button>
      </template>

      <div v-if="configLoading" class="plugin-state">读取配置中</div>
      <div v-else-if="Object.keys(configSchema).length === 0" class="plugin-empty">这个插件没有可编辑配置。</div>
      <div v-else class="plugin-config-layout">
        <div v-if="configPlugin.id === 'local-subtitle-library'" class="plugin-inline-status">
          <div v-if="pluginMetaLoading" class="plugin-inline-status__loading">读取索引状态中</div>
          <div v-else-if="pluginMetaError" class="plugin-inline-status__error">{{ pluginMetaError }}</div>
          <template v-else-if="localSubtitleIndexStatus">
            <div class="plugin-inline-status__stats">
              <div class="plugin-inline-status__item">
                <span class="plugin-inline-status__label">索引</span>
                <span class="plugin-inline-status__value">
                  <span class="plugin-status-dot" :class="localSubtitleIndexStatus.index_exists ? 'plugin-status-dot--enabled' : 'plugin-status-dot--uninstalled'"></span>
                  {{ localSubtitleIndexStatus.index_exists ? '已建立' : '未建立' }}
                </span>
              </div>
              <div class="plugin-inline-status__item">
                <span class="plugin-inline-status__label">文件</span>
                <span class="plugin-inline-status__value">{{ localSubtitleIndexStatus.indexed_count.toLocaleString() }}</span>
              </div>
              <div class="plugin-inline-status__item">
                <span class="plugin-inline-status__label">路径</span>
                <span class="plugin-inline-status__value">{{ localSubtitleIndexStatus.configured_paths.length }}</span>
              </div>
              <div class="plugin-inline-status__item">
                <span class="plugin-inline-status__label">更新于</span>
                <span class="plugin-inline-status__value">{{ formatTimestamp(localSubtitleIndexStatus.index_updated_at) }}</span>
              </div>
            </div>
            <div class="plugin-inline-status__actions">
              <button class="plugin-action plugin-action--ghost" type="button" :disabled="localSubtitleRebuilding" @click="rebuildLocalSubtitleIndex">
                {{ localSubtitleRebuilding ? '重建中' : '重建索引' }}
              </button>
            </div>
            <div v-if="localSubtitleRebuildResult" class="plugin-inline-status__result">
              已重建 {{ localSubtitleRebuildResult.indexed_files.toLocaleString() }} 个文件，用时 {{ localSubtitleRebuildResult.elapsed_seconds }} 秒
            </div>
          </template>
        </div>

        <div class="plugin-config-form">
          <FieldRow
            v-for="(meta, key) in configSchema"
            :key="key"
            v-show="!isHiddenJavdbDefaultDownloaderField(key)"
            :label="meta.label || key"
            :description="isBooleanField(meta) ? '' : meta.description || ''"
          >
            <div v-if="isJavdbDownloaderBindingField(key)" class="plugin-downloader-binding">
              <div v-if="!activeDownloaderOptions.length" class="plugin-downloader-binding__empty">
                当前没有已激活的下载器。请先启用 qBittorrent、Transmission 或迅雷远程等下载器插件。
              </div>
              <label
                v-for="option in activeDownloaderOptions"
                v-else
                :key="option.value"
                class="plugin-downloader-binding__item"
                :class="{ 'is-bound': isDownloaderBound(option.value), 'is-default': configDraft.default_downloader === option.value }"
              >
                <input
                  class="plugin-field__checkbox"
                  type="checkbox"
                  :checked="isDownloaderBound(option.value)"
                  @change="toggleDownloaderBinding(option.value, ($event.target as HTMLInputElement).checked)"
                />
                <span class="plugin-downloader-binding__main">
                  <strong>{{ option.label }}</strong>
                  <small>{{ option.description || option.value }}</small>
                </span>
                <button
                  class="plugin-downloader-binding__default"
                  type="button"
                  :disabled="!isDownloaderBound(option.value)"
                  :title="isDownloaderBound(option.value) ? '设为默认下载器' : '先勾选绑定后才能设为默认'"
                  @click.prevent="setDefaultDownloader(option.value)"
                >
                  {{ configDraft.default_downloader === option.value ? '默认' : '设默认' }}
                </button>
              </label>
              <div class="plugin-downloader-binding__hint">
                只显示已激活的下载器；勾选表示 JavDB 可以推送到该下载器，“默认”表示资源兼容多个下载器时优先使用它。
              </div>
            </div>

            <div v-else-if="isSelectField(meta) && meta.multi" class="plugin-field__checkbox-group">
              <label v-for="option in meta.options" :key="option.value" class="plugin-field__checkbox-item">
                <input
                  type="checkbox"
                  :value="option.value"
                  v-model="configDraft[key]"
                  class="plugin-field__checkbox"
                />
                <span>{{ option.label || option.value }}</span>
              </label>
            </div>

            <select
              v-else-if="isSelectField(meta)"
              v-model="configDraft[key]"
              class="plugin-field__control"
            >
              <option v-for="option in meta.options" :key="option.value" :value="option.value">
                {{ option.label || option.value }}
              </option>
            </select>

            <textarea
              v-else-if="isTextareaField(meta)"
              v-model="configDraft[key]"
              class="plugin-field__control plugin-field__control--textarea"
              :placeholder="meta.placeholder || ''"
            />

            <label
              v-else-if="isBooleanField(meta)"
              class="plugin-field__toggle"
            >
              <input
                v-model="configDraft[key]"
                class="plugin-field__checkbox"
                type="checkbox"
              />
              <span>{{ meta.description || '启用此项配置' }}</span>
            </label>

            <input
              v-else
              v-model="configDraft[key]"
              class="plugin-field__control"
              :type="isPasswordField(meta) ? 'password' : isNumberField(meta) ? 'number' : 'text'"
              :placeholder="meta.placeholder || ''"
              :min="meta.min"
              :max="meta.max"
              :step="meta.step"
            />
          </FieldRow>
        </div>
      </div>

      <template #footer>
        <div class="plugin-modal-actions">
          <button
            class="plugin-action"
            type="button"
            :disabled="configTesting || configSaving"
            @click="testConfig"
          >
            {{ configTesting ? '测试中' : '测试连接' }}
          </button>
          <button
            class="plugin-action plugin-action--primary"
            type="button"
            :disabled="configSaving || configTesting"
            @click="saveConfig"
          >
            {{ configSaving ? '保存中' : '保存' }}
          </button>
        </div>
      </template>
    </BaseModal>

    <BaseModal
      v-if="infoModalOpen && configPlugin"
      :title="`${configPlugin.name} 信息`"
      size="lg"
      @close="closeInfo"
    >
      <div class="plugin-info-sheet">
        <FieldRow label="插件名称">
          <div class="plugin-info-value">{{ configPlugin.name }}</div>
        </FieldRow>
        <FieldRow label="状态">
          <div class="plugin-info-value">
            <span class="plugin-status" :class="`plugin-status--${configPlugin.status}`">{{ statusLabel(configPlugin.status) }}</span>
          </div>
        </FieldRow>
        <FieldRow label="能力摘要">
          <div class="plugin-info-value">{{ pluginCapabilitySummary(configPlugin) }}</div>
        </FieldRow>
        <FieldRow label="插件标识">
          <div class="plugin-info-value">{{ configPlugin.id }}</div>
        </FieldRow>
        <FieldRow label="版本">
          <div class="plugin-info-value">{{ configPlugin.version || '—' }}</div>
        </FieldRow>
        <FieldRow label="来源">
          <div class="plugin-info-value plugin-info-value--wrap">{{ configPlugin.repoUrl || '本地已安装插件 / 未记录来源' }}</div>
        </FieldRow>
        <FieldRow label="能力列表">
          <div class="plugin-info-value plugin-info-value--wrap">{{ configPlugin.capabilities.length ? configPlugin.capabilities.join(' · ') : '—' }}</div>
        </FieldRow>
        <FieldRow label="标签">
          <div class="plugin-info-value">{{ configPlugin.tags.length ? configPlugin.tags.join(' · ') : '—' }}</div>
        </FieldRow>
        <FieldRow label="说明">
          <div class="plugin-info-value plugin-info-value--wrap">{{ configPlugin.description }}</div>
        </FieldRow>
      </div>
    </BaseModal>
  </section>
</template>
<style scoped>
.plugin-page {
  display: grid;
  gap: 0.9rem;
}

.plugin-page__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding: 0.95rem 1.05rem;
  border-radius: var(--radius-lg);
  background: rgba(24, 29, 50, 0.9);
  border: 1px solid rgba(255, 255, 255, 0.06);
  box-shadow: var(--shadow-card);
}

.plugin-page__title-wrap h2 {
  color: #fff;
  font-family: var(--font-display);
  font-size: 0.96rem;
  font-weight: 800;
}

.plugin-page__title-wrap p {
  margin-top: 0.18rem;
  color: rgba(255, 255, 255, 0.38);
  font-size: 0.74rem;
}

.plugin-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
  gap: 0.9rem;
}

.plugin-card {
  display: grid;
  gap: 0.82rem;
  padding: 1rem;
  border-radius: var(--radius-lg);
  border: 1px solid rgba(255, 255, 255, 0.06);
  background: rgba(18, 22, 40, 0.92);
  box-shadow: var(--shadow-card);
  transition: background var(--transition-fast), border-color var(--transition-fast), transform var(--transition-fast), opacity var(--transition-fast), box-shadow var(--transition-fast);
  position: relative;
  overflow: hidden;
}

.plugin-card:hover {
  transform: translateY(-1px);
}

.plugin-card::before {
  content: '';
  position: absolute;
  inset: 0 auto auto 0;
  width: 100%;
  height: 1px;
  background: rgba(255, 255, 255, 0.08);
}

.plugin-card--enabled {
  background:
    linear-gradient(180deg, rgba(0, 117, 255, 0.14), rgba(18, 22, 40, 0.94) 58%),
    rgba(18, 22, 40, 0.94);
  border-color: rgba(0, 117, 255, 0.22);
  box-shadow: 0 16px 40px rgba(0, 0, 0, 0.24), inset 0 1px 0 rgba(255, 255, 255, 0.03);
}

.plugin-card--enabled:hover {
  border-color: rgba(0, 117, 255, 0.34);
}

.plugin-card--enabled::before {
  background: linear-gradient(90deg, rgba(0, 117, 255, 0.95), rgba(0, 184, 255, 0.72));
}

.plugin-card--inactive {
  background: rgba(20, 24, 42, 0.9);
  border-color: rgba(255, 255, 255, 0.09);
}

.plugin-card--inactive:hover {
  border-color: rgba(255, 255, 255, 0.15);
}

.plugin-card--inactive::before {
  background: rgba(255, 255, 255, 0.18);
}

.plugin-card--uninstalled {
  background: rgba(14, 18, 32, 0.78);
  border-color: rgba(255, 255, 255, 0.045);
  opacity: 0.82;
}

.plugin-card--uninstalled:hover {
  border-color: rgba(255, 255, 255, 0.085);
  opacity: 0.9;
}

.plugin-card--uninstalled::before {
  background: rgba(255, 255, 255, 0.08);
}

.plugin-card__head,
.plugin-card__actions,
.plugin-card__actions-main,
.plugin-field__toggle,
.plugin-modal-actions {
  display: flex;
  align-items: center;
  gap: 0.65rem;
}

.plugin-card__head,
.plugin-card__actions {
  justify-content: space-between;
}

.plugin-card__head {
  gap: 0.85rem;
}

.plugin-card__identity {
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.plugin-card__icon {
  width: 2rem;
  height: 2rem;
  display: grid;
  place-items: center;
  flex: none;
  color: rgba(255, 255, 255, 0.86);
}

.plugin-card--inactive .plugin-card__icon {
  color: rgba(255, 255, 255, 0.68);
}

.plugin-card__name-wrap {
  min-width: 0;
  display: grid;
  gap: 0.15rem;
}

.plugin-card__title-row {
  display: flex;
  align-items: center;
  gap: 0.45rem;
  min-width: 0;
}

.plugin-card__name-wrap h4 {
  color: #fff;
  font-size: 0.91rem;
  font-weight: 800;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.plugin-card__version {
  flex: none;
  min-height: 1.25rem;
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  padding: 0 0.42rem;
  background: rgba(255, 255, 255, 0.055);
  color: rgba(255, 255, 255, 0.42);
  font-size: 0.64rem;
}

.plugin-card__summary,
.plugin-card__desc {
  color: rgba(255, 255, 255, 0.48);
  font-size: 0.72rem;
  line-height: 1.5;
}

.plugin-card--uninstalled .plugin-card__name-wrap h4 {
  color: rgba(255, 255, 255, 0.82);
}

.plugin-card__desc {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.plugin-card__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 0.38rem 0.45rem;
  align-items: center;
}

.plugin-card__meta-item,
.plugin-status {
  min-height: 1.35rem;
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  padding: 0 0.55rem;
  border: 1px solid rgba(255, 255, 255, 0.06);
  background: rgba(255, 255, 255, 0.045);
  color: rgba(255, 255, 255, 0.48);
  font-size: 0.68rem;
  white-space: nowrap;
}

.plugin-card__meta-item {
  background: transparent;
  border-color: rgba(255, 255, 255, 0.05);
  color: rgba(255, 255, 255, 0.4);
}

.plugin-card__meta-item--status {
  border-color: transparent;
  padding-left: 0;
  font-weight: 700;
}

.plugin-card__meta-item--enabled {
  color: rgba(126, 224, 255, 0.96);
}

.plugin-card__meta-item--inactive {
  color: rgba(255, 255, 255, 0.68);
}

.plugin-card__meta-item--uninstalled {
  color: rgba(255, 255, 255, 0.38);
}

.plugin-status-dot {
  width: 0.6rem;
  height: 0.6rem;
  flex: none;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.22);
  box-shadow: 0 0 0 4px rgba(255, 255, 255, 0.03);
}

.plugin-status-dot--enabled {
  background: #35b7ff;
  box-shadow: 0 0 0 4px rgba(0, 117, 255, 0.1);
}

.plugin-status-dot--inactive {
  background: rgba(255, 255, 255, 0.54);
  box-shadow: 0 0 0 4px rgba(255, 255, 255, 0.04);
}

.plugin-status-dot--uninstalled {
  background: rgba(255, 255, 255, 0.24);
  box-shadow: 0 0 0 4px rgba(255, 255, 255, 0.02);
}

.plugin-status--enabled {
  color: rgba(126, 224, 255, 0.96);
  border-color: rgba(0, 117, 255, 0.22);
  background: rgba(0, 117, 255, 0.14);
}

.plugin-status--inactive {
  color: rgba(255, 255, 255, 0.7);
  border-color: rgba(255, 255, 255, 0.12);
  background: rgba(255, 255, 255, 0.06);
}

.plugin-status--uninstalled {
  color: rgba(255, 255, 255, 0.4);
  border-color: rgba(255, 255, 255, 0.05);
  background: rgba(255, 255, 255, 0.03);
}

.plugin-action {
  min-height: 1.9rem;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.4rem;
  padding: 0 0.8rem;
  border-radius: 0.55rem;
  border: 1px solid rgba(255, 255, 255, 0.09);
  background: rgba(255, 255, 255, 0.045);
  color: rgba(255, 255, 255, 0.76);
  font-size: 0.75rem;
  font-weight: 700;
  transition: transform var(--transition-fast), background var(--transition-fast), border-color var(--transition-fast), opacity var(--transition-fast);
}

.plugin-action:hover:not(:disabled) {
  transform: translateY(-1px);
  background: rgba(255, 255, 255, 0.07);
  border-color: rgba(255, 255, 255, 0.14);
}

.plugin-card__actions {
  padding-top: 0.1rem;
  border-top: 1px solid rgba(255, 255, 255, 0.045);
  margin-top: 0.05rem;
  padding-top: 0.68rem;
}

.plugin-card__actions-main {
  flex-wrap: wrap;
  gap: 0.42rem;
}

.plugin-action:disabled {
  opacity: 0.56;
  cursor: not-allowed;
}

.plugin-action--primary {
  color: #fff;
  border-color: rgba(0, 117, 255, 0.35);
  background: linear-gradient(135deg, #0075ff, #00b8ff);
}

.plugin-action--primary:hover:not(:disabled) {
  background: linear-gradient(135deg, #1880ff, #28c2ff);
  border-color: rgba(0, 117, 255, 0.45);
}

.plugin-action--ghost {
  background: rgba(255, 255, 255, 0.03);
  color: rgba(255, 255, 255, 0.66);
}

.plugin-action--ghost:hover:not(:disabled) {
  background: rgba(255, 255, 255, 0.06);
  color: rgba(255, 255, 255, 0.88);
}

.plugin-action--danger {
  color: rgba(255, 218, 224, 0.96);
  border-color: rgba(255, 94, 135, 0.22);
  background: rgba(255, 94, 135, 0.12);
}

.plugin-action--danger:hover:not(:disabled) {
  background: rgba(255, 94, 135, 0.18);
  border-color: rgba(255, 94, 135, 0.32);
}

.plugin-state,
.plugin-empty {
  border-radius: var(--radius-lg);
  background: rgba(255, 255, 255, 0.035);
  border: 1px solid rgba(255, 255, 255, 0.06);
  padding: 0.95rem 1rem;
  color: rgba(255, 255, 255, 0.45);
  font-size: 0.8rem;
}

.plugin-state--error {
  color: var(--color-error);
  border-color: rgba(255, 80, 120, 0.18);
}

.plugin-config-layout {
  display: grid;
  gap: 0.85rem;
}

.plugin-icon-button {
  width: 2rem;
  height: 2rem;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 0.6rem;
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(255, 255, 255, 0.04);
  color: rgba(255, 255, 255, 0.68);
  transition: background var(--transition-fast), border-color var(--transition-fast), color var(--transition-fast), transform var(--transition-fast);
}

.plugin-icon-button:hover {
  background: rgba(255, 255, 255, 0.08);
  border-color: rgba(255, 255, 255, 0.14);
  color: #fff;
  transform: translateY(-1px);
}

.plugin-inline-status {
  display: grid;
  gap: 0.6rem;
  padding: 0.85rem 0.95rem;
  border-radius: var(--radius-lg);
  border: 1px solid rgba(255, 255, 255, 0.06);
  background: rgba(255, 255, 255, 0.025);
}

.plugin-inline-status__stats {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 0.6rem;
}

.plugin-inline-status__item {
  min-width: 0;
  display: grid;
  gap: 0.18rem;
}

.plugin-inline-status__label {
  color: rgba(255, 255, 255, 0.38);
  font-size: 0.67rem;
}

.plugin-inline-status__value {
  min-width: 0;
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  color: rgba(255, 255, 255, 0.82);
  font-size: 0.76rem;
  line-height: 1.45;
}

.plugin-inline-status__actions {
  display: flex;
  justify-content: flex-start;
}

.plugin-inline-status__loading,
.plugin-inline-status__result {
  color: rgba(255, 255, 255, 0.54);
  font-size: 0.76rem;
}

.plugin-inline-status__error {
  color: var(--color-error);
  font-size: 0.76rem;
}

.plugin-config-form {
  display: grid;
  align-content: start;
  gap: 0;
}

.plugin-config-form :deep(.field-row) {
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: 1.5rem;
  padding: 0.85rem 0;
}

.plugin-config-form :deep(.field-row__label-col) {
  padding-top: 0.45rem;
}

.plugin-config-form :deep(.field-row__input-col) {
  min-width: 0;
}

.plugin-config-form :deep(.field-row__label) {
  font-size: 0.79rem;
}

.plugin-config-form :deep(.field-row__desc) {
  font-size: 0.66rem;
}

.plugin-field {
  display: grid;
  gap: 0.42rem;
  min-width: 0;
}

.plugin-field--boolean {
  gap: 0.55rem;
}

.plugin-field__label {
  color: #fff;
  font-size: 0.78rem;
  font-weight: 700;
}

.plugin-field__control {
  min-height: 2.5rem;
  width: 100%;
  min-height: 2.5rem;
  border-radius: 0.75rem;
  border: 1px solid rgba(255, 255, 255, 0.09);
  background: rgba(255, 255, 255, 0.04);
  color: #fff;
  padding: 0 0.8rem;
  font-size: 0.8rem;
  outline: none;
}

.plugin-field__control:focus {
  border-color: rgba(0, 117, 255, 0.35);
  box-shadow: 0 0 0 3px rgba(0, 117, 255, 0.12);
}

.plugin-field__control--multiple {
  height: auto;
  padding: 0.5rem;
  min-height: 5rem;
}

.plugin-field__checkbox-group {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 0.75rem;
  padding: 0.5rem 0;
}

.plugin-field__checkbox-item {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  padding: 0.6rem 0.8rem;
  border-radius: 0.6rem;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.06);
  cursor: pointer;
  transition: all 0.2s;
}

.plugin-field__checkbox-item:hover {
  background: rgba(255, 255, 255, 0.06);
}

.plugin-field__checkbox-item span {
  font-size: 0.8rem;
  color: rgba(255, 255, 255, 0.8);
}

.plugin-downloader-binding {
  display: grid;
  gap: 0.65rem;
}

.plugin-downloader-binding__item {
  min-height: 3.25rem;
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  gap: 0.75rem;
  padding: 0.65rem 0.75rem;
  border: 1px solid rgba(255, 255, 255, 0.065);
  border-radius: 0.75rem;
  background: rgba(255, 255, 255, 0.035);
  transition: background var(--transition-fast), border-color var(--transition-fast);
}

.plugin-downloader-binding__item:hover,
.plugin-downloader-binding__item.is-bound {
  border-color: rgba(255, 255, 255, 0.12);
  background: rgba(255, 255, 255, 0.06);
}

.plugin-downloader-binding__item.is-default {
  border-color: rgba(0, 117, 255, 0.28);
  background: rgba(0, 117, 255, 0.11);
}

.plugin-downloader-binding__main {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
}

.plugin-downloader-binding__main strong {
  color: rgba(255, 255, 255, 0.9);
  font-size: 0.82rem;
  font-weight: 700;
}

.plugin-downloader-binding__main small,
.plugin-downloader-binding__hint,
.plugin-downloader-binding__empty {
  color: rgba(255, 255, 255, 0.44);
  font-size: 0.72rem;
  line-height: 1.45;
}

.plugin-downloader-binding__default {
  height: 1.8rem;
  padding: 0 0.65rem;
  border-radius: 999px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(255, 255, 255, 0.045);
  color: rgba(255, 255, 255, 0.62);
  font-size: 0.7rem;
  font-weight: 700;
}

.plugin-downloader-binding__default:not(:disabled):hover,
.plugin-downloader-binding__item.is-default .plugin-downloader-binding__default {
  border-color: rgba(0, 117, 255, 0.32);
  background: rgba(0, 117, 255, 0.18);
  color: #fff;
}

.plugin-downloader-binding__default:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.plugin-downloader-binding__empty {
  min-height: 2.6rem;
  display: flex;
  align-items: center;
  padding: 0.7rem 0.8rem;
  border-radius: 0.75rem;
  border: 1px dashed rgba(255, 255, 255, 0.08);
  background: rgba(255, 255, 255, 0.025);
}

.plugin-field__control--textarea {
  min-height: 6.5rem;
  padding-top: 0.75rem;
  padding-bottom: 0.75rem;
  resize: vertical;
}

.plugin-field__checkbox {
  width: 1rem;
  height: 1rem;
  accent-color: #0075ff;
}

.plugin-field__toggle {
  min-height: 2.5rem;
  justify-content: flex-start;
  border-radius: 0.75rem;
  border: 1px solid rgba(255, 255, 255, 0.09);
  background: rgba(255, 255, 255, 0.04);
  padding: 0 0.8rem;
  color: rgba(255, 255, 255, 0.78);
  font-size: 0.78rem;
}

.plugin-field__hint {
  color: rgba(255, 255, 255, 0.42);
  font-size: 0.72rem;
  line-height: 1.45;
}

.plugin-info-sheet {
  display: grid;
  gap: 0;
}

.plugin-info-sheet :deep(.field-row) {
  padding: 0.8rem 0;
}

.plugin-info-sheet :deep(.field-row__label) {
  font-size: 0.79rem;
}

.plugin-info-value {
  min-height: 2.5rem;
  display: flex;
  align-items: center;
  color: rgba(255, 255, 255, 0.84);
  font-size: 0.8rem;
}

.plugin-info-value--wrap {
  line-height: 1.55;
  word-break: break-word;
}

@media (max-width: 900px) {
  .plugin-inline-status__stats {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .plugin-config-form :deep(.field-row) {
    grid-template-columns: 1fr;
    gap: 0.5rem;
  }
}

@media (max-width: 640px) {
  .plugin-page__header,
  .plugin-card__head,
  .plugin-card__actions {
    align-items: flex-start;
    flex-direction: column;
  }

  .plugin-status-dot {
    display: none;
  }

  .plugin-card__actions-main {
    width: 100%;
    flex-wrap: wrap;
  }

  .plugin-page__header {
    padding: 0.9rem;
  }

  .plugin-grid {
    grid-template-columns: 1fr;
  }

  .plugin-config-form :deep(.field-row) {
    padding: 0.72rem 0;
  }
}
</style>
