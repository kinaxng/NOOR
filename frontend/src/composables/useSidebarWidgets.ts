import { computed, ref, watch } from 'vue'
import { usePlugins } from './usePlugins'

const STORAGE_KEY = 'noor-sidebar-widget-index'
const selectedIndex = ref(Number(localStorage.getItem(STORAGE_KEY) || 0) || 0)

export function useSidebarWidgets() {
  const { plugins, loadPlugins } = usePlugins()

  const widgets = computed(() => plugins.value
    .filter(plugin => plugin.enabled && plugin.capabilities?.includes('sidebar_widget') && plugin.contributions?.sidebar_widget)
    .filter(plugin => plugin.config?.show_sidebar_widget !== false)
    .map(plugin => ({
      plugin,
      widget: plugin.contributions.sidebar_widget,
      key: `${plugin.id}:${plugin.contributions.sidebar_widget?.key || 'default'}`,
    })))

  const activeIndex = computed(() => {
    const total = widgets.value.length
    if (!total) return -1
    return Math.max(0, Math.min(selectedIndex.value, total - 1))
  })

  const activeWidget = computed(() => activeIndex.value >= 0 ? widgets.value[activeIndex.value] : null)
  const hasMultipleWidgets = computed(() => widgets.value.length > 1)

  function selectNextWidget() {
    const total = widgets.value.length
    if (total <= 1) return
    selectedIndex.value = (activeIndex.value + 1) % total
  }

  watch(selectedIndex, value => {
    localStorage.setItem(STORAGE_KEY, String(value))
  })

  watch(widgets, list => {
    if (list.length && selectedIndex.value >= list.length) selectedIndex.value = 0
  })

  return { widgets, activeWidget, activeIndex, hasMultipleWidgets, selectedIndex, selectNextWidget, loadPlugins }
}
