<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { usePluginsStore } from '../../stores/plugins'

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

function updateNumberConfig(key: string, value: string) { configDraft.value[key] = value === '' ? '' : Number(value) }

async function fetchMarket() {
  marketLoading.value = true; marketError.value = ''
  try {
    const [repoRes, itemRes] = await Promise.all([fetch('/api/plugins/market/repos'), fetch('/api/plugins/market/items')])
    repos.value = await repoRes.json().catch(() => [])
    marketItems.value = await itemRes.json().catch(() => [])
    if (!repoRes.ok || !itemRes.ok) throw new Error('插件仓库加载失败')
  } catch (err: any) { marketError.value = err?.message || '插件仓库加载失败' }
  finally { marketLoading.value = false }
}

async function openRepoManager() { repoOpen.value = true; await fetchMarket() }

async function addRepo() {
  const url = repoInput.value.trim(); if (!url) return
  marketError.value = ''
  try {
    const res = await fetch('/api/plugins/market/repos', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ repo_url: url }) })
    const data = await res.json().catch(() => ({}))
    if (!res.ok) throw new Error(data?.detail || '添加仓库失败')
    repoInput.value = ''; await fetchMarket()
  } catch (err: any) { marketError.value = err?.message || '添加仓库失败' }
}

async function removeRepo(url: string) {
  marketError.value = ''
  try {
    const res = await fetch('/api/plugins/market/repos', { method: 'DELETE', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ repo_url: url }) })
    const data = await res.json().catch(() => ({}))
    if (!res.ok) throw new Error(data?.detail || '删除仓库失败')
    await fetchMarket()
  } catch (err: any) { marketError.value = err?.message || '删除仓库失败' }
}

async function installMarketItem(item: any) {
  actionMessage.value = ''; marketError.value = ''
  try {
    const res = await fetch('/api/plugins/market/install', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ repo_url: item.repo_url, plugin_id: item.id }) })
    const data = await res.json().catch(() => ({}))
    if (!res.ok) throw new Error(data?.detail || '安装插件失败')
    actionMessage.value = `已安装 ${item.name || item.id}`; await store.fetchPlugins(); store.notifyPluginsChanged(); await fetchMarket()
  } catch (err: any) { marketError.value = err?.message || '安装插件失败' }
}

async function uninstallPlugin(plugin: any) {
  if (!window.confirm(`卸载 ${plugin.name || plugin.id}？`)) return
  actionMessage.value = ''
  try {
    const res = await fetch(`/api/plugins/${encodeURIComponent(plugin.id)}`, { method: 'DELETE' })
    const data = await res.json().catch(() => ({}))
    if (!res.ok) throw new Error(data?.detail || '卸载插件失败')
    actionMessage.value = `已卸载 ${plugin.name || plugin.id}`; await store.fetchPlugins(); store.notifyPluginsChanged(); await fetchMarket()
  } catch (err: any) { actionMessage.value = err?.message || '卸载插件失败' }
}

async function pluginAction(action: string, payload: Record<string, any> = {}) {
  if (!selectedPluginId.value) return null
  const res = await fetch(`/api/plugins/${encodeURIComponent(selectedPluginId.value)}/actions/${action}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ payload }) })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(data?.detail || `${action} failed`)
  return data
}

async function fetchLocalIndexStatus() {
  if (selectedPluginId.value !== 'local-subtitle-library') return
  try { localIndexStatus.value = await pluginAction('index_status') } catch { localIndexStatus.value = null }
}

async function rebuildLocalIndex() {
  if (selectedPluginId.value !== 'local-subtitle-library') return
  localRebuilding.value = true; configError.value = ''; configMessage.value = ''
  try {
    await saveConfig(false)
    const result = await pluginAction('rebuild_index')
    configMessage.value = `索引已重建：${Number(result?.indexed_files || 0).toLocaleString()} 个文件`; await fetchLocalIndexStatus()
  } catch (err: any) { configError.value = err?.message || '重建索引失败' }
  finally { localRebuilding.value = false }
}

function formatPluginTime(ts?: number | null) {
  if (!ts) return '从未'; return new Date(ts * 1000).toLocaleString('zh-CN')
}

async function hydrateQbConfigOptions() {
  if (selectedPluginId.value !== 'qbittorrent') return
  try {
    const res = await fetch('/api/plugins/qbittorrent/actions/download_options', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ payload: {} }) })
    const data = await res.json().catch(() => ({}))
    if (!res.ok || data?.ok === false) return
    const categories = Array.isArray(data.categories) ? data.categories : []
    if (configSchema.value.category && categories.length) {
      configSchema.value = { ...configSchema.value, category: { ...configSchema.value.category, options: categories.map((c: any) => ({ label: c.save_path ? `${c.name} · ${c.save_path}` : String(c.name || ''), value: String(c.name || '') })) } }
    }
    if (configSchema.value.savepath && data.default_savepath && !configDraft.value.savepath) configDraft.value.savepath = data.default_savepath
  } catch {}
}

async function openConfig(plugin: any) {
  selectedPluginId.value = plugin.id; selectedPluginName.value = plugin.name || plugin.id; configOpen.value = true; configLoading.value = true; configError.value = ''; configMessage.value = ''
  try {
    const res = await fetch(`/api/plugins/${encodeURIComponent(plugin.id)}/config`); const data = await res.json().catch(() => ({}))
    if (!res.ok) throw new Error(data?.detail || '插件配置加载失败')
    configSchema.value = data.plugin?.config_schema || {}; configDraft.value = { ...(data.config || {}) }; localIndexStatus.value = null
    await hydrateQbConfigOptions(); await fetchLocalIndexStatus()
  } catch (err: any) { configError.value = err?.message || '插件配置加载失败'; configSchema.value = {}; configDraft.value = {} }
  finally { configLoading.value = false }
}

async function saveConfig(showMessage = true) {
  if (!selectedPluginId.value) return; configSaving.value = true; configError.value = ''; configMessage.value = ''
  try {
    const res = await fetch(`/api/plugins/${encodeURIComponent(selectedPluginId.value)}/config`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ config: configDraft.value }) })
    const data = await res.json().catch(() => ({}))
    if (!res.ok) throw new Error(data?.detail || '保存失败')
    if (showMessage) configMessage.value = '配置已保存'
  } catch (err: any) { configError.value = err?.message || '保存失败' }
  finally { configSaving.value = false }
}

async function testPlugin(plugin: any) {
  try { await fetch(`/api/plugins/${encodeURIComponent(plugin.id)}/test`, { method: 'POST' }) } catch {}
}

onMounted(async () => { await store.fetchPlugins(); await fetchMarket() })
</script>

<template>
  <UDashboardPanel id="plugins" grow>
    <template #header>
      <UDashboardNavbar title="插件管理">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #right>
          <div class="flex items-center gap-2">
            <UButton color="neutral" variant="ghost" @click="openRepoManager()">仓库</UButton>
            <UButton color="neutral" variant="ghost" icon="i-heroicons-arrow-path-20-solid" @click="store.reload()">重载插件</UButton>
          </div>
        </template>
      </UDashboardNavbar>

      <UDashboardToolbar>
        <template #left>
          <div class="text-sm text-(--ui-text-muted)">
            仓库共 {{ marketItems.length }} 插件 · 已启用 {{ store.enabledPlugins.length }} · 未启用 {{ store.disabledPlugins.length }} · 未安装 {{ notInstalledMarketItems.length }}
          </div>
        </template>
      </UDashboardToolbar>
    </template>

    <template #body>
      <div v-if="store.loading" class="flex flex-col items-center justify-center py-12 text-(--ui-text-muted)">
        <UIcon name="i-heroicons-arrow-path-20-solid" class="w-8 h-8 animate-spin mb-4" />
        <p>加载插件中...</p>
      </div>

      <div v-else-if="store.error" class="flex flex-col items-center justify-center py-12">
        <UIcon name="i-heroicons-exclamation-triangle-20-solid" class="w-12 h-12 text-(--ui-error) mb-4" />
        <p class="text-(--ui-error) font-medium">{{ store.error }}</p>
      </div>

      <div v-else-if="!store.plugins.length" class="flex flex-col items-center justify-center py-12 text-(--ui-text-muted)">
        <UIcon name="i-heroicons-puzzle-piece-20-solid" class="w-12 h-12 mb-4 opacity-50" />
        <p>暂无插件</p>
      </div>

      <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        <!-- Built-in marketplace card -->
        <UCard class="flex flex-col">
          <template #header>
            <div class="flex items-start justify-between">
              <div>
                <h3 class="text-base font-semibold">插件仓库</h3>
                <p class="text-sm text-(--ui-text-muted) mt-1">marketplace · system</p>
              </div>
              <UBadge color="info" variant="subtle">内置</UBadge>
            </div>
          </template>
          <p class="text-sm text-(--ui-text-dimmed) flex-1">管理插件源、发现可安装插件。</p>
          <template #footer>
            <div class="flex justify-end gap-2">
              <UButton color="primary" variant="soft" @click="openRepoManager()">管理仓库</UButton>
              <UButton color="neutral" variant="ghost" @click="store.reload()">重载插件</UButton>
            </div>
          </template>
        </UCard>

        <UCard v-for="plugin in sortedPlugins" :key="plugin.id" class="flex flex-col" :class="{ 'opacity-75': !plugin.enabled }">
          <template #header>
            <div class="flex items-start justify-between">
              <div>
                <h3 class="text-base font-semibold">{{ plugin.name }}</h3>
                <p class="text-sm text-(--ui-text-muted) mt-1">{{ plugin.id }} · {{ plugin.version || '-' }}</p>
              </div>
              <UBadge :color="plugin.enabled ? 'success' : 'neutral'" variant="subtle">{{ plugin.enabled ? '已启用' : '未启用' }}</UBadge>
            </div>
          </template>

          <p class="text-sm text-(--ui-text-dimmed) flex-1 mb-4">{{ plugin.description || '-' }}</p>

          <div class="flex flex-wrap gap-2 mb-4">
            <UBadge v-for="cap in (plugin.capabilities || []).slice(0, 3)" :key="cap" color="neutral" variant="solid" size="xs">{{ cap }}</UBadge>
          </div>

          <template #footer>
            <div class="flex flex-wrap items-center justify-end gap-2">
              <UButton v-if="(plugin.contributions?.sidebar as any)?.route" color="primary" variant="soft" :to="`/plugins/${plugin.id}`">打开</UButton>
              <UButton color="neutral" variant="ghost" @click="openConfig(plugin)">配置</UButton>
              <UButton color="neutral" variant="ghost" @click="testPlugin(plugin)">测试</UButton>
              <UButton :color="plugin.enabled ? 'neutral' : 'primary'" :variant="plugin.enabled ? 'ghost' : 'solid'" @click="store.setEnabled(plugin.id, !plugin.enabled)">{{ plugin.enabled ? '停用' : '启用' }}</UButton>
              <UButton color="error" variant="ghost" @click="uninstallPlugin(plugin)">卸载</UButton>
            </div>
          </template>
        </UCard>

        <UCard v-for="item in notInstalledMarketItems" :key="`${item.repo_url}:${item.id}`" class="flex flex-col opacity-60 border-dashed">
          <template #header>
            <div class="flex items-start justify-between">
              <div>
                <h3 class="text-base font-semibold">{{ item.name || item.id }}</h3>
                <p class="text-sm text-(--ui-text-muted) mt-1">{{ item.id }} · {{ item.version || '-' }}</p>
              </div>
              <UBadge color="neutral" variant="subtle">未下载</UBadge>
            </div>
          </template>
          <p class="text-sm text-(--ui-text-dimmed) flex-1 mb-4">{{ item.description || '-' }}</p>
          <div class="flex flex-wrap gap-2 mb-4">
            <UBadge color="neutral" variant="solid" size="xs">market</UBadge>
          </div>
          <template #footer>
            <div class="flex justify-end gap-2">
              <UButton color="primary" @click="installMarketItem(item)">安装</UButton>
            </div>
          </template>
        </UCard>
      </div>

      <div v-if="actionMessage" class="mt-6 flex flex-col items-center justify-center p-4 rounded-lg bg-(--ui-bg-elevated)/50">
        <p>{{ actionMessage }}</p>
      </div>

      <!-- Repo Manager Modal -->
      <UModal v-model="repoOpen" prevent-close>
        <UCard>
          <template #header>
            <div class="flex items-center justify-between">
              <div>
                <h3 class="text-base font-semibold">插件仓库</h3>
                <p class="text-sm text-(--ui-text-muted)">管理仓库源与可安装插件</p>
              </div>
              <UButton color="neutral" variant="ghost" icon="i-heroicons-x-mark-20-solid" class="-my-1" @click="repoOpen = false" />
            </div>
          </template>
          <div class="space-y-4">
            <div class="flex gap-2">
              <UInput v-model="repoInput" placeholder="GitHub 插件仓库 URL" class="flex-1" />
              <UButton color="primary" @click="addRepo()">添加仓库</UButton>
            </div>
            <div v-if="marketLoading" class="flex justify-center p-4">
              <UIcon name="i-heroicons-arrow-path-20-solid" class="w-6 h-6 animate-spin text-(--ui-text-muted)" />
            </div>
            <UAlert v-else-if="marketError" title="错误" :description="marketError" color="error" variant="soft" />
            <div class="space-y-2">
              <div v-for="repo in repos" :key="repo.url" class="flex items-center justify-between p-3 rounded-lg bg-(--ui-bg-elevated)/50">
                <span class="text-sm truncate max-w-[80%]" :title="repo.url">{{ repo.url }}</span>
                <UButton color="error" variant="ghost" size="xs" @click="removeRepo(repo.url)">删除</UButton>
              </div>
              <div v-if="!repos.length && !marketLoading" class="text-center p-4 text-(--ui-text-muted) text-sm">暂无插件仓库</div>
            </div>
            <div v-if="marketItems.some(item => item.error)" class="space-y-2 pt-4 border-t border-(--ui-border)">
              <h4 class="text-sm font-medium text-(--ui-error)">加载失败的仓库</h4>
              <div v-for="item in marketItems.filter(item => item.error)" :key="`${item.repo_url}:${item.error}`" class="p-3 rounded-lg border border-(--ui-error)/20 text-sm">
                <div class="text-(--ui-error) truncate mb-1" :title="item.repo_url">{{ item.repo_url }}</div>
                <div class="text-(--ui-text-muted) text-xs">{{ item.error }}</div>
              </div>
            </div>
          </div>
          <template #footer>
            <div class="flex justify-end">
              <UButton color="neutral" variant="ghost" @click="repoOpen = false">关闭</UButton>
            </div>
          </template>
        </UCard>
      </UModal>

      <!-- Config Modal -->
      <UModal v-model="configOpen" prevent-close>
        <UCard :ui="{ body: { padding: 'sm:p-6 p-4 max-h-[70vh] overflow-y-auto' } }">
          <template #header>
            <div class="flex items-center justify-between">
              <div>
                <h3 class="text-base font-semibold">{{ selectedPluginName }}</h3>
                <p class="text-sm text-(--ui-text-muted)">{{ selectedPluginId }} · 插件配置</p>
              </div>
              <UButton color="neutral" variant="ghost" icon="i-heroicons-x-mark-20-solid" class="-my-1" @click="configOpen = false" />
            </div>
          </template>

          <div v-if="configLoading" class="flex justify-center p-8">
            <UIcon name="i-heroicons-arrow-path-20-solid" class="w-8 h-8 animate-spin text-(--ui-text-muted)" />
          </div>
          <div v-else-if="configError" class="p-4">
            <UAlert title="加载错误" :description="configError" color="error" variant="soft" />
          </div>
          <div v-else-if="!schemaEntries.length" class="flex flex-col items-center justify-center p-8 text-(--ui-text-muted)">
            <UIcon name="i-heroicons-cog-6-tooth-20-solid" class="w-12 h-12 mb-4 opacity-50" />
            <p>该插件没有可配置项</p>
          </div>
          <div v-else class="space-y-6">
            <div v-if="selectedPluginId === 'local-subtitle-library' && localIndexStatus" class="p-4 rounded-lg border border-(--ui-border-accented)">
              <div class="flex flex-col sm:flex-row gap-4 items-start sm:items-center justify-between">
                <div>
                  <h4 class="text-sm font-semibold">字幕索引</h4>
                  <p class="text-xs text-(--ui-text-muted) mt-1">状态：{{ localIndexStatus.index_exists ? '已建立' : '未建立' }} · 文件 {{ Number(localIndexStatus.indexed_count || 0).toLocaleString() }} · 更新 {{ formatPluginTime(localIndexStatus.index_updated_at) }}</p>
                </div>
                <UButton :loading="localRebuilding" @click="rebuildLocalIndex()">重建索引</UButton>
              </div>
            </div>

            <div class="space-y-4">
              <UFormField v-for="([key, meta]) in schemaEntries" :key="key" :label="(meta as any).label || key" :description="(meta as any).description">
                <USelect v-if="Array.isArray((meta as any).options) && (meta as any).options.length" v-model="configDraft[key]" :items="selectOptions(key, meta)" />
                <UCheckbox v-else-if="fieldType(meta) === 'boolean'" v-model="configDraft[key]" :label="configDraft[key] ? '开启' : '关闭'" />
                <UTextarea v-else-if="fieldType(meta) === 'textarea'" v-model="configDraft[key]" :placeholder="(meta as any).placeholder || ''" autoresize :rows="3" />
                <UInput v-else-if="fieldType(meta) === 'number'" :model-value="configDraft[key]" type="number" :placeholder="(meta as any).placeholder || ''" @update:model-value="updateNumberConfig(key, $event)" />
                <UInput v-else v-model="configDraft[key]" :type="fieldType(meta) === 'password' ? 'password' : 'text'" :placeholder="(meta as any).placeholder || ''" />
              </UFormField>
            </div>

            <UAlert v-if="configMessage" :title="configMessage" color="success" variant="soft" />
          </div>

          <template #footer>
            <div class="flex justify-end gap-3">
              <UButton color="neutral" variant="ghost" @click="configOpen = false">取消</UButton>
              <UButton color="primary" :loading="configSaving" :disabled="configLoading || !!configError" @click="saveConfig()">保存</UButton>
            </div>
          </template>
        </UCard>
      </UModal>
    </template>
  </UDashboardPanel>
</template>
