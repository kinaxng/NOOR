<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import BaseIcon from '../components/noor/BaseIcon.vue'
import BaseModal from '../components/ui/BaseModal.vue'
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
  contributions?: {
    sidebar?: {
      route?: string
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
  contributions?: {
    sidebar?: {
      route?: string
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
  options?: Array<{ label?: string; value: string }>
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
  contributions?: {
    sidebar?: {
      route?: string
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
const configLoading = ref(false)
const configSaving = ref(false)
const configTesting = ref(false)
const configPlugin = ref<PluginCardItem | null>(null)
const configSchema = ref<Record<string, PluginConfigField>>({})
const configDraft = ref<Record<string, any>>({})

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
    installedPlugins.value = Array.isArray(pluginsRes.data) ? pluginsRes.data : []
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
    if (key in current) {
      out[key] = current[key]
      continue
    }
    if (meta.default !== undefined) {
      out[key] = meta.default
      continue
    }
    if (meta.type === 'boolean') {
      out[key] = false
      continue
    }
    out[key] = ''
  }
  return out
}

async function openConfig(plugin: PluginCardItem) {
  configPlugin.value = plugin
  configModalOpen.value = true
  configLoading.value = true
  configSchema.value = {}
  configDraft.value = {}
  try {
    const { data } = await api.get<PluginConfigResponse>(`/plugins/${plugin.id}/config`)
    configSchema.value = data?.plugin?.config_schema || {}
    configDraft.value = emptyDraftFromSchema(configSchema.value, data?.config || {})
  } catch (e: any) {
    toast.error(e?.response?.data?.detail || e?.message || '读取插件配置失败')
    closeConfig()
  } finally {
    configLoading.value = false
  }
}

function closeConfig() {
  configModalOpen.value = false
  configLoading.value = false
  configSaving.value = false
  configTesting.value = false
  configPlugin.value = null
  configSchema.value = {}
  configDraft.value = {}
}

async function saveConfig() {
  if (!configPlugin.value || configSaving.value) return
  configSaving.value = true
  try {
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
        :class="[
          `plugin-card--${plugin.status}`,
          { 'plugin-card--page': !!routeOf(plugin) }
        ]"
      >
        <div class="plugin-card__icon">
          <BaseIcon name="plugin" class="w-5 h-5" />
        </div>

        <div class="plugin-card__main">
          <div class="plugin-card__topline">
            <div class="plugin-card__name-wrap">
              <h4>{{ plugin.name }}</h4>
              <span>{{ pluginCapabilitySummary(plugin) }}</span>
            </div>
            <span class="plugin-status" :class="`plugin-status--${plugin.status}`">{{ statusLabel(plugin.status) }}</span>
          </div>

          <p class="plugin-card__desc">{{ plugin.description }}</p>

          <div class="plugin-card__footer">
            <div class="plugin-card__tags">
              <span v-for="tag in plugin.tags.slice(0, 3)" :key="tag">{{ tag }}</span>
            </div>

            <div class="plugin-card__actions">
              <button
                v-if="plugin.status !== 'uninstalled'"
                class="plugin-action"
                type="button"
                @click="openConfig(plugin)"
              >
                设置
              </button>

              <RouterLink
                v-if="routeOf(plugin) && plugin.status === 'enabled'"
                class="plugin-action"
                :to="routeOf(plugin)"
              >
                打开
              </RouterLink>

              <button
                v-if="plugin.status === 'enabled'"
                class="plugin-action plugin-action--primary"
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
        </div>
      </article>

      <div v-if="pluginCards.length === 0" class="plugin-empty">当前没有可展示的插件</div>
    </div>

    <BaseModal
      v-if="configModalOpen && configPlugin"
      :title="`${configPlugin.name} 设置`"
      size="lg"
      @close="closeConfig"
    >
      <div v-if="configLoading" class="plugin-state">读取配置中</div>
      <div v-else-if="Object.keys(configSchema).length === 0" class="plugin-empty">这个插件没有可编辑配置。</div>
      <div v-else class="plugin-config">
        <label
          v-for="(meta, key) in configSchema"
          :key="key"
          class="plugin-field"
        >
          <span class="plugin-field__label">{{ meta.label || key }}</span>

          <select
            v-if="isSelectField(meta)"
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

          <input
            v-else-if="isBooleanField(meta)"
            v-model="configDraft[key]"
            class="plugin-field__checkbox"
            type="checkbox"
          />

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

          <small v-if="meta.description" class="plugin-field__hint">{{ meta.description }}</small>
        </label>
      </div>

      <template #footer>
        <div class="plugin-modal-actions">
          <button class="plugin-action" type="button" @click="closeConfig">关闭</button>
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
  </section>
</template>

<style scoped>
.plugin-page {
  display: grid;
  gap: 1rem;
}

.plugin-page__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding: 1rem 1.125rem;
  border-radius: var(--radius-lg);
  background: rgb(26, 31, 55);
  border: 1px solid rgba(255, 255, 255, 0.06);
  box-shadow: var(--shadow-card);
}

.plugin-page__title-wrap h2 {
  color: #fff;
  font-family: var(--font-display);
  font-size: 1rem;
  font-weight: 800;
}

.plugin-page__title-wrap p {
  margin-top: 0.22rem;
  color: rgba(255, 255, 255, 0.42);
  font-size: 0.78rem;
}

.plugin-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 0.9rem;
}

.plugin-card {
  display: flex;
  gap: 0.85rem;
  padding: 0.95rem;
  border-radius: var(--radius-lg);
  border: 1px solid rgba(255, 255, 255, 0.06);
  background: rgba(255, 255, 255, 0.03);
  box-shadow: var(--shadow-card);
  transition: background var(--transition-fast), border-color var(--transition-fast), transform var(--transition-fast), opacity var(--transition-fast);
}

.plugin-card:hover {
  transform: translateY(-1px);
}

.plugin-card--enabled {
  background: linear-gradient(180deg, rgba(0, 117, 255, 0.1), rgba(255, 255, 255, 0.035));
  border-color: rgba(0, 117, 255, 0.24);
}

.plugin-card--enabled:hover {
  background: linear-gradient(180deg, rgba(0, 117, 255, 0.13), rgba(255, 255, 255, 0.05));
  border-color: rgba(0, 117, 255, 0.34);
}

.plugin-card--inactive {
  background: rgba(255, 255, 255, 0.026);
  border-color: rgba(255, 255, 255, 0.09);
}

.plugin-card--inactive:hover {
  background: rgba(255, 255, 255, 0.04);
  border-color: rgba(255, 255, 255, 0.15);
}

.plugin-card--uninstalled {
  background: rgba(255, 255, 255, 0.015);
  border-color: rgba(255, 255, 255, 0.045);
  opacity: 0.76;
}

.plugin-card--uninstalled:hover {
  background: rgba(255, 255, 255, 0.024);
  border-color: rgba(255, 255, 255, 0.085);
  opacity: 0.92;
}

.plugin-card__icon {
  width: 2.4rem;
  height: 2.4rem;
  display: grid;
  place-items: center;
  flex: none;
  border-radius: var(--radius-md);
  background: rgba(0, 117, 255, 0.12);
  color: #6fbaff;
}

.plugin-card--inactive .plugin-card__icon {
  background: rgba(255, 255, 255, 0.07);
  color: rgba(255, 255, 255, 0.68);
}

.plugin-card--uninstalled .plugin-card__icon {
  background: rgba(255, 255, 255, 0.045);
  color: rgba(255, 255, 255, 0.5);
}

.plugin-card__main {
  min-width: 0;
  flex: 1;
  display: grid;
  gap: 0.62rem;
}

.plugin-card__topline,
.plugin-card__footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.8rem;
}

.plugin-card__name-wrap {
  min-width: 0;
}

.plugin-card__name-wrap h4 {
  color: #fff;
  font-size: 0.9rem;
  font-weight: 800;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.plugin-card__name-wrap span,
.plugin-card__desc {
  color: rgba(255, 255, 255, 0.46);
  font-size: 0.74rem;
  line-height: 1.45;
}

.plugin-card--uninstalled .plugin-card__name-wrap h4 {
  color: rgba(255, 255, 255, 0.82);
}

.plugin-card--uninstalled .plugin-card__name-wrap span,
.plugin-card--uninstalled .plugin-card__desc {
  color: rgba(255, 255, 255, 0.36);
}

.plugin-card__desc {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.plugin-card__tags,
.plugin-card__actions,
.plugin-modal-actions {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.45rem;
}

.plugin-card__tags span,
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

.plugin-state,
.plugin-empty {
  border-radius: var(--radius-lg);
  background: rgba(255, 255, 255, 0.035);
  border: 1px solid rgba(255, 255, 255, 0.06);
  padding: 1rem;
  color: rgba(255, 255, 255, 0.45);
  font-size: 0.82rem;
}

.plugin-state--error {
  color: var(--color-error);
  border-color: rgba(255, 80, 120, 0.18);
}

.plugin-config {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.9rem;
}

.plugin-field {
  display: grid;
  gap: 0.42rem;
  min-width: 0;
}

.plugin-field__label {
  color: #fff;
  font-size: 0.78rem;
  font-weight: 700;
}

.plugin-field__control {
  width: 100%;
  min-height: 2.6rem;
  border-radius: 0.8rem;
  border: 1px solid rgba(255, 255, 255, 0.09);
  background: rgba(255, 255, 255, 0.04);
  color: #fff;
  padding: 0 0.85rem;
  font-size: 0.82rem;
  outline: none;
}

.plugin-field__control:focus {
  border-color: rgba(0, 117, 255, 0.35);
  box-shadow: 0 0 0 3px rgba(0, 117, 255, 0.12);
}

.plugin-field__control--textarea {
  min-height: 7rem;
  padding-top: 0.8rem;
  padding-bottom: 0.8rem;
  resize: vertical;
}

.plugin-field__checkbox {
  width: 1rem;
  height: 1rem;
  margin-top: 0.25rem;
}

.plugin-field__hint {
  color: rgba(255, 255, 255, 0.42);
  font-size: 0.72rem;
  line-height: 1.45;
}

@media (max-width: 900px) {
  .plugin-config {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 640px) {
  .plugin-page__header,
  .plugin-card__topline,
  .plugin-card__footer {
    align-items: flex-start;
    flex-direction: column;
  }

  .plugin-page__header {
    padding: 0.9rem;
  }

  .plugin-grid {
    grid-template-columns: 1fr;
  }
}
</style>
