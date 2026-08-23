<script setup lang="ts">
import { computed, onMounted, onUnmounted } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import { usePluginsStore } from '../../stores/plugins'

const route = useRoute()
const plugins = usePluginsStore()
const items = [
  { to: '/', label: '概览' },
  { to: '/library', label: '媒体库' },
  { to: '/jobs', label: '任务' },
  { to: '/history', label: '历史' },
  { to: '/hardlinks', label: '硬链接' },
  { to: '/plugins', label: '插件' },
  { to: '/settings', label: '设置' },
]


const sidebarPlugins = computed(() => plugins.sidebarPlugins.map(plugin => {
  const sidebar = plugin.contributions?.sidebar as { route?: string; label?: string; icon?: string } | undefined
  return {
    id: plugin.id,
    to: sidebar?.route || `/plugins/${plugin.id}`,
    label: sidebar?.label || plugin.name || plugin.id,
    icon: sidebar?.icon || 'plugin',
  }
}))

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
  <aside class="sidebar">
    <div class="brand">NOOR</div>
    <nav class="nav">
      <RouterLink
        v-for="item in items"
        :key="item.to"
        :to="item.to"
        class="nav-link"
        :class="{ 'is-active': route.path === item.to }"
      >
        {{ item.label }}
      </RouterLink>
      <div v-if="sidebarPlugins.length" class="nav-separator" />
      <RouterLink
        v-for="plugin in sidebarPlugins"
        :key="plugin.id"
        :to="plugin.to"
        class="nav-link"
        :class="{ 'is-active': route.path === plugin.to }"
      >
        {{ plugin.label }}
      </RouterLink>
    </nav>
  </aside>
</template>
