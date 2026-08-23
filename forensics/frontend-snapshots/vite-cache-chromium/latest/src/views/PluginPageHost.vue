<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useToast } from '../composables/useToast'
import { createPluginUi } from '../plugins/sdkUi'

const route = useRoute()
const toast = useToast()
const pluginId = computed(() => String(route.params.pluginId || ''))
const hostRef = ref<HTMLElement | null>(null)
const loading = ref(false)
const error = ref('')
const mounted = ref(false)
let cleanup: null | (() => void | Promise<void>) = null
const moduleCache = new Map<string, any>()
const styleCache = new Map<string, HTMLLinkElement>()
let mountSeq = 0

async function dispose() {
  const oldCleanup = cleanup
  cleanup = null
  if (oldCleanup) await oldCleanup()
  if (hostRef.value) hostRef.value.innerHTML = ''
}

async function loadPluginPage() {
  const id = pluginId.value
  const el = hostRef.value
  if (!id || !el) return
  const seq = ++mountSeq
  loading.value = true
  mounted.value = false
  error.value = ''
  try {
    await dispose()
    const cfgRes = await fetch(`/api/plugins/${encodeURIComponent(id)}/config`)
    const cfg = await cfgRes.json()
    if (!cfgRes.ok) throw new Error(cfg?.detail || '插件配置加载失败')
    const frontend = cfg?.plugin?.frontend || {}
    const type = frontend.type || 'module'
    const entry = frontend.entry || 'frontend/page.js'
    const style = frontend.style || 'frontend/style.css'
    if (style) {
      const styleHref = `/api/plugins/${encodeURIComponent(id)}/assets/${style.replace(/^frontend\//, '')}`
      if (!styleCache.has(styleHref)) {
        const link = document.createElement('link')
        link.rel = 'stylesheet'
        link.href = styleHref
        document.head.appendChild(link)
        styleCache.set(styleHref, link)
      }
    }
    if (type !== 'module') throw new Error(`不支持的插件前端类型: ${type}`)
    const entryHref = `/api/plugins/${encodeURIComponent(id)}/assets/${entry.replace(/^frontend\//, '')}`
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
      },
    })
    cleanup = typeof maybeCleanup === 'function' ? maybeCleanup : null
    mounted.value = true
  } catch (e: any) {
    error.value = e?.message || '插件页面加载失败'
    mounted.value = false
  } finally {
    if (seq === mountSeq) {
      loading.value = false
    }
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
  <div class="plugin-page-host">
    <div v-if="error" class="plugin-page-host__overlay">
      <div class="plugin-page-host__status plugin-page-host__status--error">{{ error }}</div>
    </div>
    <div ref="hostRef" class="plugin-page-host__mount" :aria-busy="loading && !mounted" />
  </div>
</template>

<style scoped>
.plugin-page-host{min-height:calc(100vh - 6rem);position:relative}.plugin-page-host__mount{min-height:inherit}.plugin-page-host__overlay{position:absolute;inset:0;z-index:2;display:flex;align-items:flex-start;justify-content:center;padding-top:18vh;pointer-events:none}.plugin-page-host__status{display:inline-flex;align-items:center;min-height:38px;padding:0 14px;border:1px solid var(--color-border-default);border-radius:var(--radius-button);background:rgba(26,31,55,.86);box-shadow:var(--shadow-md);backdrop-filter:blur(10px);color:var(--color-text-secondary);font-size:var(--font-size-sm);font-weight:var(--font-weight-semibold)}.plugin-page-host__status--error{color:#fff;border-color:rgba(227,26,26,.35);background:rgba(227,26,26,.14)}
</style>
