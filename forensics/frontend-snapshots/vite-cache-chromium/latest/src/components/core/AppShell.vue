<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { usePluginsStore } from '../../stores/plugins'

const route = useRoute()
const plugins = usePluginsStore()
const sidebarOpen = ref(false)

const coreLinks = computed(() => [
  { label: '概览', icon: 'i-lucide-layout-dashboard', to: '/', exact: true, onSelect: closeMobileSidebar },
  { label: '媒体库', icon: 'i-lucide-library', to: '/library', onSelect: closeMobileSidebar },
  { label: '任务', icon: 'i-lucide-list-checks', to: '/jobs', onSelect: closeMobileSidebar },
  { label: '历史', icon: 'i-lucide-history', to: '/history', onSelect: closeMobileSidebar },
  { label: '硬链接', icon: 'i-lucide-link', to: '/hardlinks', onSelect: closeMobileSidebar },
  { label: '插件', icon: 'i-lucide-puzzle', to: '/plugins', onSelect: closeMobileSidebar },
  { label: '设置', icon: 'i-lucide-settings', to: '/settings', onSelect: closeMobileSidebar },
])

const pluginLinks = computed(() => plugins.sidebarPlugins.map(plugin => {
  const sidebar = plugin.contributions?.sidebar as { route?: string; label?: string; icon?: string } | undefined
  return {
    label: sidebar?.label || plugin.name || plugin.id,
    icon: normalizeSidebarIcon(sidebar?.icon),
    to: sidebar?.route || `/plugins/${plugin.id}`,
    onSelect: closeMobileSidebar,
  }
}))

const searchGroups = computed(() => [{
  id: 'core',
  label: '主程序',
  items: coreLinks.value,
}, {
  id: 'plugins',
  label: '插件',
  items: pluginLinks.value,
}])

const routeTitle = computed(() => {
  const allLinks = [...coreLinks.value, ...pluginLinks.value]
  const exact = allLinks.find(item => item.to === route.path)
  if (exact) return exact.label
  if (route.path.startsWith('/plugins/')) return '插件'
  return 'NOOR'
})

function normalizeSidebarIcon(icon?: string) {
  if (!icon || icon === 'plugin') return 'i-lucide-box'
  if (icon.startsWith('i-')) return icon
  if (icon.includes(':')) return icon
  return `i-lucide-${icon}`
}

function closeMobileSidebar() {
  sidebarOpen.value = false
}

function handlePluginsChanged() {
  void plugins.fetchPlugins()
}

onMounted(() => {
  plugins.fetchPlugins()
  window.addEventListener('noor:plugins-changed', handlePluginsChanged)
})

onUnmounted(() => window.removeEventListener('noor:plugins-changed', handlePluginsChanged))
</script>

<template>
  <UDashboardGroup unit="rem">
    <UDashboardSidebar
      id="noor-sidebar"
      v-model:open="sidebarOpen"
      collapsible
      resizable
      class="noor-dashboard-sidebar bg-elevated/25"
      :ui="{ footer: 'lg:border-t lg:border-default' }"
    >
      <template #header="{ collapsed }">
        <div class="noor-sidebar-brand" :class="{ 'is-collapsed': collapsed }">
          <div class="noor-sidebar-brand__mark">N</div>
          <div v-if="!collapsed" class="noor-sidebar-brand__text">
            <strong>NOOR</strong>
            <span>Media AI</span>
          </div>
        </div>
      </template>

      <template #default="{ collapsed }">
        <UDashboardSearchButton :collapsed="collapsed" class="bg-transparent ring-default" />

        <UNavigationMenu
          :collapsed="collapsed"
          :items="coreLinks"
          orientation="vertical"
          tooltip
          popover
        />

        <div v-if="pluginLinks.length" class="noor-sidebar-section" :class="{ 'is-collapsed': collapsed }">
          <span v-if="!collapsed">插件</span>
        </div>

        <UNavigationMenu
          v-if="pluginLinks.length"
          :collapsed="collapsed"
          :items="pluginLinks"
          orientation="vertical"
          tooltip
          popover
        />
      </template>

      <template #footer="{ collapsed }">
        <div class="noor-sidebar-footer" :class="{ 'is-collapsed': collapsed }">
          <span v-if="!collapsed">开发环境</span>
          <strong>5173</strong>
        </div>
      </template>
    </UDashboardSidebar>

    <UDashboardSearch :groups="searchGroups" />

    <UDashboardPanel id="noor-main">
      <template #header>
        <UDashboardNavbar :title="routeTitle">
          <template #leading>
            <UDashboardSidebarCollapse />
          </template>
          <template #right>
            <UButton icon="i-lucide-file-text" color="neutral" variant="ghost" label="日志" />
            <UButton icon="i-lucide-languages" color="neutral" variant="ghost" label="语言" />
          </template>
        </UDashboardNavbar>
      </template>

      <template #body>
        <NuxtPage />
      </template>
    </UDashboardPanel>
  </UDashboardGroup>
</template>
