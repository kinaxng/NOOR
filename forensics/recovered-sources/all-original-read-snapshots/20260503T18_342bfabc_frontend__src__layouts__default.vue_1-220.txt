<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { usePluginsStore } from '../stores/plugins'
import { useI18n } from '../composables/useI18n'

const { t } = useI18n()
const route = useRoute()
const plugins = usePluginsStore()
const sidebarOpen = ref(false)

const coreLinks = computed(() => [
  { label: t('nav.overview'), icon: 'i-lucide-layout-dashboard', to: '/' },
  { label: t('nav.library'), icon: 'i-lucide-library', to: '/library' },
  { label: t('nav.jobs'), icon: 'i-lucide-list-checks', to: '/jobs' },
  { label: t('nav.history'), icon: 'i-lucide-history', to: '/history' },
  { label: t('nav.hardlinks'), icon: 'i-lucide-link', to: '/hardlinks' },
  { label: t('nav.plugins'), icon: 'i-lucide-puzzle', to: '/plugins' },
  { label: t('nav.settings'), icon: 'i-lucide-settings', to: '/settings' },
])

const pluginLinks = computed(() => plugins.sidebarPlugins.map(plugin => {
  const sidebar = plugin.contributions?.sidebar as { route?: string; label?: string; icon?: string } | undefined
  return {
    label: sidebar?.label || plugin.name || plugin.id,
    icon: normalizeSidebarIcon(sidebar?.icon),
    to: sidebar?.route || `/plugins/${plugin.id}`,
  }
}))

const allNavItems = computed(() => {
  if (!pluginLinks.value.length) return [coreLinks.value]
  return [
    coreLinks.value,
    pluginLinks.value,
  ]
})

const searchGroups = computed(() => {
  const groups: Array<{ id: string; label: string; items: Array<{ id: string; label: string; icon: string; to: string }> }> = [
    {
      id: 'core',
      label: t('search.group.nav'),
      items: coreLinks.value.map(item => ({
        id: item.to,
        label: item.label,
        icon: item.icon,
        to: item.to,
      })),
    },
  ]
  if (pluginLinks.value.length) {
    groups.push({
      id: 'plugins',
      label: t('search.group.plugins'),
      items: pluginLinks.value.map(item => ({
        id: item.to,
        label: item.label,
        icon: item.icon,
        to: item.to,
      })),
    })
  }
  return groups
})

function normalizeSidebarIcon(icon?: string) {
  if (!icon || icon === 'plugin') return 'i-lucide-box'
  if (icon.startsWith('i-')) return icon
  if (icon.includes(':')) return icon
  return `i-lucide-${icon}`
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
      class="bg-elevated/25"
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

        <template v-if="pluginLinks.length">
          <UNavigationMenu
            :collapsed="collapsed"
            :items="pluginLinks"
            orientation="vertical"
            tooltip
            popover
          />
        </template>
      </template>

      <template #footer="{ collapsed }">
        <div class="noor-sidebar-footer" :class="{ 'is-collapsed': collapsed }">
          <span v-if="!collapsed">NOOR v2.0</span>
          <strong>5173</strong>
        </div>
      </template>
    </UDashboardSidebar>

    <UDashboardSearch :groups="searchGroups" />

    <slot />
  </UDashboardGroup>
</template>
