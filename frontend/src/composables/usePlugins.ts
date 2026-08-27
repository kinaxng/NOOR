import { computed, ref } from 'vue'
import { fetchPlugins, pluginPageRoute, type PluginListItem } from '../api/plugins'

const plugins = ref<PluginListItem[]>([])
const loading = ref(false)
const loaded = ref(false)
const error = ref('')

export function usePlugins() {
  async function loadPlugins(force = false) {
    if (loading.value) return plugins.value
    if (loaded.value && !force) return plugins.value
    loading.value = true
    error.value = ''
    try {
      plugins.value = await fetchPlugins()
      loaded.value = true
    } catch (e: any) {
      error.value = e?.response?.data?.detail || e?.message || '插件加载失败'
    } finally {
      loading.value = false
    }
    return plugins.value
  }

  const enabledPagePlugins = computed(() => plugins.value
    .filter(p => p.enabled && pluginPageRoute(p))
    .map(p => ({ ...p, route: pluginPageRoute(p)! })))

  return { plugins, loading, loaded, error, enabledPagePlugins, loadPlugins }
}
