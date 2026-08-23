<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { usePluginsStore } from '../stores/plugins'
import { createPluginUi } from '../runtime/sdkUi'

const route = useRoute()
const store = usePluginsStore()
const pluginId = computed(() => String(route.params.pluginId || ''))
const plugin = computed(() => store.plugins.find(item => item.id === pluginId.value))
const hostRef = ref<HTMLElement | null>(null)
const loading = ref(false)
const error = ref('')
const mounted = ref(false)

let cleanup: null | (() => void | Promise<void>) = null
let mountSeq = 0
const moduleCache = new Map<string, any>()
const styleCache = new Map<string, HTMLLinkElement>()

const toast = {
  success: (message: string) => console.info('[plugin:success]', message),
  error: (message: string) => console.error('[plugin:error]', message),
  info: (message: string) => console.info('[plugin:info]', message),
  warning: (message: string) => console.warn('[plugin:warning]', message),
}

async function dispose() {
  const oldCleanup = cleanup
  cleanup = null
  if (oldCleanup) await oldCleanup()
  if (hostRef.value) hostRef.value.innerHTML = ''
}

async function loadPluginPage() {
  if (!import.meta.client) return
  const id = pluginId.value
  const el = hostRef.value
  if (!id || !el) return
  const seq = ++mountSeq
  loading.value = true
  mounted.value = false
  error.value = ''
  try {
    await dispose()
    if (!store.plugins.length) await store.fetchPlugins()
    const cfgRes = await fetch(`/api/plugins/${encodeURIComponent(id)}/config`)
    const cfg = await cfgRes.json().catch(() => ({}))
    if (!cfgRes.ok) throw new Error(cfg?.detail || '插件配置加载失败')
    const frontend = cfg?.plugin?.frontend || {}
    const type = frontend.type || 'module'
    const entry = frontend.entry || 'frontend/page.js'
    const style = frontend.style || 'frontend/style.css'
    if (type !== 'module') throw new Error(`不支持的插件前端类型: ${type}`)

    if (style) {
      const styleHref = `/api/plugins/${encodeURIComponent(id)}/assets/${String(style).replace(/^frontend\//, '')}`
      if (!styleCache.has(styleHref)) {
        const link = document.createElement('link')
        link.rel = 'stylesheet'
        link.href = styleHref
        document.head.appendChild(link)
        styleCache.set(styleHref, link)
      }
    }

    const assetVersion = encodeURIComponent(cfg?.plugin?.version || 'dev')
    const entryHref = `/api/plugins/${encodeURIComponent(id)}/assets/${String(entry).replace(/^frontend\//, '')}?v=${assetVersion}`
    let mod = moduleCache.get(entryHref)
    if (!mod) {
      mod = await import(/* @vite-ignore */ entryHref)
      moduleCache.set(entryHref, mod)
    }
    if (seq !== mountSeq) return
    if (!mod || typeof mod.mount !== 'function') throw new Error('插件前端缺少 mount(el, sdk)')
    const maybeCleanup = await mod.mount(el, {
      pluginId: id,
      toast,
      ui: createPluginUi(),
      api: {
        fetch: (path: string, init?: RequestInit) => fetch(path, init),
        plugin: (path: string, init?: RequestInit) => fetch(`/api/plugins/${encodeURIComponent(id)}${path}`, init),
        wsUrl: (path: string) => `ws://127.0.0.1:9898/api/plugins/${encodeURIComponent(id)}${path}`,
      },
    })
    cleanup = typeof maybeCleanup === 'function' ? maybeCleanup : null
    mounted.value = true
  } catch (err: any) {
    error.value = err?.message || '插件页面加载失败'
    mounted.value = false
  } finally {
    if (seq === mountSeq) loading.value = false
  }
}

watch([pluginId, hostRef], async () => {
  await nextTick()
  void loadPluginPage()
}, { immediate: true })

onBeforeUnmount(() => {
  mountSeq++
  void dispose()
})
</script>

<template>
  <UDashboardPage>
    <UDashboardPanel grow>
      <UDashboardPanelContent class="p-0 sm:p-0 plugin-host-page-content" :ui="{ wrapper: 'h-full flex flex-col relative' }">
        <div v-if="error" class="flex flex-col items-center justify-center h-full p-8 text-center">
          <UIcon name="i-heroicons-exclamation-triangle-20-solid" class="w-12 h-12 text-red-500 mb-4" />
          <h2 class="text-lg font-medium text-gray-900 dark:text-white mb-2">插件加载错误</h2>
          <p class="text-red-500 max-w-md">{{ error }}</p>
        </div>
        
        <div v-if="loading && !mounted && !error" class="flex flex-col items-center justify-center h-full p-8 text-center text-gray-500">
          <UIcon name="i-heroicons-arrow-path-20-solid" class="w-12 h-12 animate-spin mb-4 text-primary-500" />
          <h2 class="text-lg font-medium text-gray-900 dark:text-white mb-2">正在加载插件...</h2>
          <p class="text-sm">{{ plugin?.name || pluginId }}</p>
        </div>
        
        <div v-show="!error && (mounted || !loading)" ref="hostRef" class="w-full h-full plugin-page-host" :aria-busy="loading && !mounted" />
        
        <div v-if="!loading && !error && !mounted && !plugin" class="flex flex-col items-center justify-center h-full p-8 text-center text-gray-500">
          <UIcon name="i-heroicons-puzzle-piece-20-solid" class="w-12 h-12 mb-4 opacity-50" />
          <h2 class="text-lg font-medium text-gray-900 dark:text-white mb-2">插件不可用</h2>
          <p class="text-sm">插件不存在或未启用</p>
        </div>
      </UDashboardPanelContent>
    </UDashboardPanel>
  </UDashboardPage>
</template>

<style>
.plugin-host-page-content {
  overflow: hidden !important;
}
.plugin-page-host {
  overflow-y: auto;
  height: 100%;
}
</style>
