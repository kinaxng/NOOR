<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { loadPluginRendererModule, makePluginSdk } from '../../composables/usePluginRenderers'

const props = defineProps<{
  pluginId: string
  slotName: 'sidebar' | 'dashboard'
  widget?: any
  payload?: any
  collapsed?: boolean
}>()

const host = ref<HTMLElement | null>(null)
let dispose: null | (() => void) = null
let sdkDispose: null | (() => void) = null
let token = 0
const documentVisible = ref(document.visibilityState !== 'hidden')

function handleVisibilityChange() {
  documentVisible.value = document.visibilityState !== 'hidden'
}

function clear() {
  if (dispose) {
    try { dispose() } catch {}
    dispose = null
  }
  if (sdkDispose) {
    try { sdkDispose() } catch {}
    sdkDispose = null
  }
  if (host.value) host.value.innerHTML = ''
}

async function mount() {
  if (!documentVisible.value) return
  const current = ++token
  clear()
  if (!host.value || !props.pluginId) return
  try {
    const mod = await loadPluginRendererModule(props.pluginId)
    if (current !== token || !host.value || !documentVisible.value) return
    const fn = props.slotName === 'sidebar' ? mod.renderSidebarWidget : mod.renderDashboardWidget
    if (typeof fn !== 'function') return
    const sdk = makePluginSdk(props.pluginId) as any
    sdkDispose = typeof sdk.__dispose === 'function' ? sdk.__dispose : null
    const ret = await fn(host.value, {
      pluginId: props.pluginId,
      widget: props.widget,
      payload: props.payload,
      collapsed: props.collapsed,
      sdk,
    })
    if (typeof ret === 'function') dispose = ret
  } catch (error) {
    if (host.value) host.value.innerHTML = ''
    console.warn('plugin widget render failed', props.pluginId, props.slotName, error)
  }
}

onMounted(() => {
  document.addEventListener('visibilitychange', handleVisibilityChange)
  mount()
})
watch(() => [props.pluginId, props.slotName, props.widget, props.payload, props.collapsed], mount, { deep: true, flush: 'post' })
watch(documentVisible, value => {
  if (value) void mount()
  else clear()
})
onBeforeUnmount(() => {
  document.removeEventListener('visibilitychange', handleVisibilityChange)
  clear()
})
</script>

<template>
  <div ref="host" class="plugin-widget-renderer" />
</template>
