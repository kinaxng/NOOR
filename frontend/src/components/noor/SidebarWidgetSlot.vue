<script setup lang="ts">
import { onMounted } from 'vue'
import { useSidebarWidgets } from '../../composables/useSidebarWidgets'
import PluginWidgetRenderer from './PluginWidgetRenderer.vue'

const props = defineProps<{ collapsed?: boolean }>()
const { activeWidget, loadPlugins } = useSidebarWidgets()

onMounted(() => { void loadPlugins() })
</script>

<template>
  <div v-if="activeWidget" class="sidebar-widget-slot" :class="{ 'is-collapsed': props.collapsed }">
    <PluginWidgetRenderer
      :plugin-id="activeWidget.plugin.id"
      slot-name="sidebar"
      :widget="activeWidget.widget"
      :collapsed="props.collapsed"
    />
  </div>
</template>

<style scoped>
.sidebar-widget-slot { min-height: 0; }
</style>
