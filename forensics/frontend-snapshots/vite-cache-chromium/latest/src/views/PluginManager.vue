<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { RouterLink } from 'vue-router'
import BaseIcon from '../components/noor/BaseIcon.vue'
import { usePlugins } from '../composables/usePlugins'
import api from '../api'
import { useToast } from '../composables/useToast'

type PluginItem = {
  id: string
  name: string
  description?: string
  enabled?: boolean
  tags?: string[]
  capabilities?: string[]
  contributions?: {
    sidebar?: {
      route?: string
    }
  }
}

const toast = useToast()
const { plugins, loading, error, loadPlugins } = usePlugins()

const enabledPlugins = computed(() => normalizePlugins().filter(plugin => plugin.enabled))
const disabledPlugins = computed(() => normalizePlugins().filter(plugin => !plugin.enabled))
const stats = computed(() => {
  const total = plugins.value.length
  const enabled = enabledPlugins.value.length
  return `仓库共 ${total} 个插件 · 已启用 ${enabled} 个 · 未启用 ${total - enabled} 个`
})

function normalizePlugins() {
  return [...plugins.value].sort((a, b) => Number(b.enabled) - Number(a.enabled) || a.name.localeCompare(b.name, 'zh-CN')) as PluginItem[]
}

function routeOf(plugin: PluginItem) {
  return plugin.contributions?.sidebar?.route || (plugin.capabilities?.includes('sidebar_page') ? `/plugins/${plugin.id}` : '')
}

function pluginCapabilitySummary(plugin: PluginItem) {
  const caps = new Set(plugin.capabilities || [])
  const labels = [
    caps.has('sidebar_page') ? '独立页面' : '',
    caps.has('subtitle_provider') ? '字幕源' : '',
    caps.has('downloader') ? '下载器' : '',
    caps.has('dashboard_widget') ? '概览组件' : '',
  ].filter(Boolean)
  if (labels.length) return labels.join(' · ')
  return plugin.tags?.slice(0, 2).join(' · ') || '扩展能力'
}

function pluginTags(plugin: PluginItem) {
  return (plugin.tags || []).slice(0, 3)
}

async function setEnabled(plugin: PluginItem, enabled: boolean) {
  try {
    await api.post(`/plugins/${plugin.id}/${enabled ? 'enable' : 'disable'}`)
    toast.success(enabled ? '插件已启用' : '插件已停用')
    await loadPlugins(true)
  } catch (e: any) {
    toast.error(e?.response?.data?.detail || e?.message || '操作失败')
  }
}

onMounted(() => loadPlugins(true))
</script>

<template>
  <section class="plugin-page">
    <header class="plugin-page__header">
      <div class="plugin-page__title-wrap">
        <h2>插件管理</h2>
        <p>{{ stats }}</p>
      </div>
      <button class="plugin-action plugin-action--primary" type="button" @click="loadPlugins(true)">
        <BaseIcon name="refresh" class="w-4 h-4" />
        <span>刷新</span>
      </button>
    </header>

    <div v-if="loading" class="plugin-state">插件加载中</div>
    <div v-else-if="error" class="plugin-state plugin-state--error">{{ error }}</div>

    <div v-else class="plugin-layout">
      <section class="plugin-section plugin-section--enabled">
        <div class="plugin-section__head">
          <h3>已启用</h3>
          <span>{{ enabledPlugins.length }}</span>
        </div>
        <div class="plugin-list">
          <article v-for="plugin in enabledPlugins" :key="plugin.id" class="plugin-card plugin-card--enabled">
            <div class="plugin-card__icon"><BaseIcon name="plugin" class="w-5 h-5" /></div>
            <div class="plugin-card__main">
              <div class="plugin-card__topline">
                <div class="plugin-card__name-wrap">
                  <h4>{{ plugin.name }}</h4>
                  <span>{{ pluginCapabilitySummary(plugin) }}</span>
                </div>
                <span class="plugin-status plugin-status--enabled">已启用</span>
              </div>
              <p class="plugin-card__desc">{{ plugin.description || '暂无说明' }}</p>
              <div class="plugin-card__footer">
                <div class="plugin-card__tags">
                  <span v-for="tag in pluginTags(plugin)" :key="tag">{{ tag }}</span>
                </div>
                <div class="plugin-card__actions">
                  <RouterLink v-if="routeOf(plugin)" class="plugin-action plugin-action--primary" :to="routeOf(plugin)">打开</RouterLink>
                  <button class="plugin-action" type="button" @click="setEnabled(plugin, false)">停用</button>
                </div>
              </div>
            </div>
          </article>
          <div v-if="enabledPlugins.length === 0" class="plugin-empty">暂无启用插件</div>
        </div>
      </section>

      <section class="plugin-section plugin-section--available">
        <div class="plugin-section__head">
          <h3>可用插件</h3>
          <span>{{ disabledPlugins.length }}</span>
        </div>
        <div class="plugin-list">
          <article v-for="plugin in disabledPlugins" :key="plugin.id" class="plugin-card plugin-card--disabled">
            <div class="plugin-card__icon"><BaseIcon name="plugin" class="w-5 h-5" /></div>
            <div class="plugin-card__main">
              <div class="plugin-card__topline">
                <div class="plugin-card__name-wrap">
                  <h4>{{ plugin.name }}</h4>
                  <span>{{ pluginCapabilitySummary(plugin) }}</span>
                </div>
                <span class="plugin-status">未启用</span>
              </div>
              <p class="plugin-card__desc">{{ plugin.description || '暂无说明' }}</p>
              <div class="plugin-card__footer">
                <div class="plugin-card__tags">
                  <span v-for="tag in pluginTags(plugin)" :key="tag">{{ tag }}</span>
                </div>
                <button class="plugin-action plugin-action--primary" type="button" @click="setEnabled(plugin, true)">启用</button>
              </div>
            </div>
          </article>
          <div v-if="disabledPlugins.length === 0" class="plugin-empty">没有未启用插件</div>
        </div>
      </section>
    </div>
  </section>
</template>

<style scoped>
.plugin-page {
  display: grid;
  gap: 1rem;
}

.plugin-page__header,
.plugin-section {
  border-radius: var(--radius-lg);
  background: rgb(26, 31, 55);
  border: 1px solid rgba(255, 255, 255, .06);
  box-shadow: var(--shadow-card);
}

.plugin-page__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding: 1rem 1.125rem;
}

.plugin-page__title-wrap h2 {
  color: #fff;
  font-family: var(--font-display);
  font-size: 1rem;
  font-weight: 800;
}

.plugin-page__title-wrap p {
  margin-top: .22rem;
  color: rgba(255,255,255,.42);
  font-size: .78rem;
}

.plugin-layout {
  display: grid;
  grid-template-columns: minmax(0, 1.2fr) minmax(320px, .8fr);
  gap: 1rem;
}

.plugin-section {
  overflow: hidden;
}

.plugin-section--available {
  background: rgba(26, 31, 55, .72);
}

.plugin-section__head {
  min-height: 3.2rem;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: .9rem 1rem;
  border-bottom: 1px solid rgba(255,255,255,.055);
}

.plugin-section__head h3 {
  color: #fff;
  font-size: .88rem;
  font-weight: 800;
}

.plugin-section__head span {
  min-width: 1.7rem;
  height: 1.35rem;
  display: inline-grid;
  place-items: center;
  border-radius: 999px;
  background: rgba(255,255,255,.06);
  color: rgba(255,255,255,.55);
  font-size: .72rem;
}

.plugin-list {
  display: grid;
  gap: .75rem;
  padding: .85rem;
}

.plugin-card {
  display: flex;
  gap: .85rem;
  padding: .9rem;
  border-radius: var(--radius-md);
  background: rgba(255,255,255,.035);
  border: 1px solid rgba(255,255,255,.055);
  transition: background var(--transition-fast), border-color var(--transition-fast), opacity var(--transition-fast);
}

.plugin-card:hover {
  background: rgba(255,255,255,.05);
  border-color: rgba(0,117,255,.16);
}

.plugin-card--disabled {
  opacity: .68;
}

.plugin-card__icon {
  width: 2.4rem;
  height: 2.4rem;
  display: grid;
  place-items: center;
  flex: none;
  border-radius: var(--radius-md);
  background: rgba(0,117,255,.14);
  color: #0075ff;
}

.plugin-card__main {
  min-width: 0;
  flex: 1;
  display: grid;
  gap: .62rem;
}

.plugin-card__topline,
.plugin-card__footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: .8rem;
}

.plugin-card__name-wrap {
  min-width: 0;
}

.plugin-card__name-wrap h4 {
  color: #fff;
  font-size: .88rem;
  font-weight: 800;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.plugin-card__name-wrap span,
.plugin-card__desc {
  color: rgba(255,255,255,.45);
  font-size: .74rem;
  line-height: 1.45;
}

.plugin-card__desc {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.plugin-card__tags,
.plugin-card__actions {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: .45rem;
}

.plugin-card__tags span,
.plugin-status {
  min-height: 1.35rem;
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  padding: 0 .55rem;
  border: 1px solid rgba(255,255,255,.06);
  background: rgba(255,255,255,.045);
  color: rgba(255,255,255,.44);
  font-size: .68rem;
  white-space: nowrap;
}

.plugin-status--enabled {
  color: rgba(0,212,255,.86);
  background: rgba(0,212,255,.1);
  border-color: rgba(0,212,255,.18);
}

.plugin-action {
  min-height: 1.85rem;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: .4rem;
  padding: 0 .78rem;
  border-radius: .55rem;
  border: 1px solid rgba(255,255,255,.09);
  background: rgba(255,255,255,.045);
  color: rgba(255,255,255,.72);
  font-size: .75rem;
  font-weight: 700;
  transition: transform var(--transition-fast), background var(--transition-fast), border-color var(--transition-fast);
}

.plugin-action:hover {
  transform: translateY(-1px);
  background: rgba(255,255,255,.07);
}

.plugin-action--primary {
  color: #fff;
  border-color: rgba(0,117,255,.35);
  background: linear-gradient(135deg, #0075ff, #00d4ff);
}

.plugin-state,
.plugin-empty {
  border-radius: var(--radius-lg);
  background: rgba(255,255,255,.035);
  border: 1px solid rgba(255,255,255,.06);
  padding: 1rem;
  color: rgba(255,255,255,.45);
  font-size: .82rem;
}

.plugin-state--error {
  color: var(--color-error);
  border-color: rgba(255,80,120,.18);
}

@media (max-width: 980px) {
  .plugin-layout {
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
    padding: .9rem;
  }
}
</style>
