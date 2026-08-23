<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import BaseIcon from './BaseIcon.vue'
import PluginIcon from './PluginIcon.vue'
import { useI18n } from '../../composables/useI18n'
import { usePlugins } from '../../composables/usePlugins'
import { useSidebarWidgets } from '../../composables/useSidebarWidgets'
import SidebarWidgetSlot from './SidebarWidgetSlot.vue'

const { t, currentLang, i18nVersion, _currentLang, _initialized } = useI18n()

defineProps<{
  collapsed?: boolean
  mobileOpen?: boolean
  i18nVersion: number
}>()

const emit = defineEmits<{
  toggle: []
  close: []
}>()

const route = useRoute()
const { enabledPagePlugins, loadPlugins } = usePlugins()
const { hasMultipleWidgets, selectNextWidget, activeWidget } = useSidebarWidgets()
onMounted(() => loadPlugins())

const navItems = computed(() => {
  void _currentLang.value
  void _initialized.value
  void currentLang.value
  void i18nVersion.value
  return [
    { path: '/', name: t('nav.overview'), icon: 'dashboard' },
    { path: '/library', name: t('nav.library'), icon: 'library' },
    { path: '/jobs', name: t('nav.jobs'), icon: 'jobs' },
    { path: '/history', name: t('nav.history'), icon: 'history' },
    { path: '/files', name: t('nav.files'), icon: 'folderOpen' },
    { path: '/settings', name: t('nav.settings'), icon: 'settings' },
  ]
})

const collapseLabel = computed(() => {
  void _currentLang.value
  void _initialized.value
  void currentLang.value
  void i18nVersion.value
  return t('toolbar.collapse')
})

function isActivePath(path: string) {
  if (path === '/') return route.path === '/'
  return route.path === path || route.path.startsWith(`${path}/`)
}
</script>

<template>
  <!-- Desktop sidebar (visible on lg+, always hidden below lg) -->
  <aside
    v-if="_initialized"
    class="app-sidebar--desktop hidden lg:flex lg:flex-col"
    :class="{ 'app-sidebar--collapsed': collapsed }"
    style="background: var(--color-bg-elevated);"
  >
    <!-- Logo -->
    <div class="app-sidebar__logo">
      <RouterLink to="/" class="app-sidebar__logo-link">
        <div class="app-sidebar__logo-icon">
          <span class="app-sidebar__logo-letter">N</span>
        </div>
        <span v-if="!collapsed" class="app-sidebar__logo-text">NOOR</span>
      </RouterLink>
    </div>

    <!-- Navigation -->
    <nav class="app-sidebar__nav">
      <RouterLink
        v-for="item in navItems"
        :key="item.path"
        :to="item.path"
        class="app-sidebar__nav-item"
        :class="{ 'app-sidebar__nav-item--active': isActivePath(item.path) }"
        @click="emit('close')"
      >
        <span v-if="isActivePath(item.path)" class="app-sidebar__active-bar" />
        <span class="app-sidebar__nav-icon">
          <BaseIcon :name="item.icon" class="w-5 h-5" />
        </span>
        <span v-if="!collapsed" class="app-sidebar__nav-label">{{ item.name }}</span>
      </RouterLink>
      <template v-if="enabledPagePlugins.length">
        <div class="app-sidebar__divider" />
        <RouterLink
          v-for="plugin in enabledPagePlugins"
          :key="plugin.id"
          :to="plugin.route"
          class="app-sidebar__nav-item app-sidebar__nav-item--plugin"
          :class="{ 'app-sidebar__nav-item--active': isActivePath(plugin.route) }"
          @click="emit('close')"
        >
          <span v-if="isActivePath(plugin.route)" class="app-sidebar__active-bar" />
          <span class="app-sidebar__nav-icon">
            <PluginIcon :plugin-id="plugin.id" :icon="plugin.contributions?.sidebar?.icon || plugin.contributions?.icon" class="app-sidebar__plugin-icon" />
          </span>
          <span v-if="!collapsed" class="app-sidebar__nav-label">{{ plugin.contributions?.sidebar?.label || plugin.name }}</span>
        </RouterLink>
      </template>
    </nav>

    <!-- Bottom -->
    <div class="app-sidebar__bottom">
      <SidebarWidgetSlot :collapsed="collapsed" />
      <div class="app-sidebar__bottom-controls">
        <button
          v-if="hasMultipleWidgets"
          class="app-sidebar__widget-next"
          type="button"
          :title="activeWidget?.widget?.label || '切换 Sidebar 插件卡片'"
          @click="selectNextWidget"
        >
          <BaseIcon name="chevronDown" class="w-4 h-4" />
        </button>
        <span v-else class="app-sidebar__widget-spacer" />
        <button class="app-sidebar__collapse-btn" :title="collapseLabel" @click="emit('toggle')">
          <BaseIcon :name="collapsed ? 'chevronRight' : 'chevronLeft'" class="w-4 h-4" />
        </button>
      </div>
    </div>
  </aside>

  <!-- Mobile sidebar (drawer, hidden by default) -->
  <aside
    v-if="_initialized"
    class="app-sidebar--mobile flex flex-col"
    :class="{ 'app-sidebar--mobile-open': mobileOpen }"
    style="background: var(--color-bg-elevated);"
  >
    <!-- Logo -->
    <div class="app-sidebar__logo">
      <RouterLink to="/" class="app-sidebar__logo-link" @click="emit('close')">
        <div class="app-sidebar__logo-icon">
          <span class="app-sidebar__logo-letter">N</span>
        </div>
        <span class="app-sidebar__logo-text">NOOR</span>
      </RouterLink>
    </div>

    <!-- Navigation -->
    <nav class="app-sidebar__nav">
      <RouterLink
        v-for="item in navItems"
        :key="item.path"
        :to="item.path"
        class="app-sidebar__nav-item"
        :class="{ 'app-sidebar__nav-item--active': isActivePath(item.path) }"
        @click="emit('close')"
      >
        <span v-if="isActivePath(item.path)" class="app-sidebar__active-bar" />
        <span class="app-sidebar__nav-icon">
          <BaseIcon :name="item.icon" class="w-5 h-5" />
        </span>
        <span class="app-sidebar__nav-label">{{ item.name }}</span>
      </RouterLink>
      <template v-if="enabledPagePlugins.length">
        <div class="app-sidebar__divider" />
        <RouterLink
          v-for="plugin in enabledPagePlugins"
          :key="plugin.id"
          :to="plugin.route"
          class="app-sidebar__nav-item app-sidebar__nav-item--plugin"
          :class="{ 'app-sidebar__nav-item--active': isActivePath(plugin.route) }"
          @click="emit('close')"
        >
          <span v-if="isActivePath(plugin.route)" class="app-sidebar__active-bar" />
          <span class="app-sidebar__nav-icon">
            <PluginIcon :plugin-id="plugin.id" :icon="plugin.contributions?.sidebar?.icon || plugin.contributions?.icon" class="app-sidebar__plugin-icon" />
          </span>
          <span class="app-sidebar__nav-label">{{ plugin.contributions?.sidebar?.label || plugin.name }}</span>
        </RouterLink>
      </template>
    </nav>

    <!-- Bottom -->
    <div class="app-sidebar__bottom">
      <SidebarWidgetSlot />
    </div>
  </aside>
</template>

<style scoped>
/* Desktop sidebar */
.app-sidebar--desktop {
  position: fixed;
  left: 0;
  top: 0;
  bottom: 0;
  width: 274px;
  border-right: 1px solid rgba(255, 255, 255, 0.04);
  z-index: var(--z-sidebar);
  transition: width var(--transition-slow);
  overflow: hidden;
}

.app-sidebar--collapsed {
  width: 76px;
}

/* Mobile sidebar drawer - always fixed, hidden by default */
.app-sidebar--mobile {
  position: fixed;
  left: 0;
  top: 0;
  bottom: 0;
  width: 274px;
  border-right: 1px solid rgba(255, 255, 255, 0.04);
  z-index: var(--z-sidebar);
  transform: translateX(-100%);
  transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  pointer-events: none;
  visibility: hidden;
}

.app-sidebar--mobile-open {
  transform: translateX(0);
  pointer-events: auto;
  visibility: visible;
}

/* Logo */
.app-sidebar__logo {
  height: 64px;
  display: flex;
  align-items: center;
  padding: 0 1.25rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.04);
  flex-shrink: 0;
}

.app-sidebar__logo-link {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  text-decoration: none;
}

.app-sidebar__logo-icon {
  width: 2.25rem;
  height: 2.25rem;
  border-radius: 0.625rem;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--color-brand);
  box-shadow: 0 4px 12px rgba(0, 117, 255, 0.4);
  flex-shrink: 0;
}

.app-sidebar__logo-letter {
  color: #FFFFFF;
  font-family: var(--font-display);
  font-size: 1rem;
  font-weight: 700;
  line-height: 1;
}

.app-sidebar__logo-text {
  font-family: var(--font-display);
  font-size: 1rem;
  font-weight: 700;
  letter-spacing: 0.05em;
  color: #FFFFFF;
  white-space: nowrap;
}

/* Navigation */
.app-sidebar__nav {
  flex: 1;
  padding: 1rem 0.625rem;
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  overflow-y: auto;
}

.app-sidebar__nav-item {
  position: relative;
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.625rem 0.875rem;
  border-radius: var(--radius-md);
  text-decoration: none;
  color: rgba(255, 255, 255, 0.5);
  font-family: var(--font-display);
  font-size: 0.875rem;
  font-weight: 500;
  transition: all var(--transition-fast);
  overflow: hidden;
  white-space: nowrap;
}

.app-sidebar__nav-item:hover {
  background: rgba(255, 255, 255, 0.04);
  color: rgba(255, 255, 255, 0.8);
}

.app-sidebar__nav-item--active {
  background: rgba(0, 117, 255, 0.15);
  color: #FFFFFF;
}

.app-sidebar__divider {
  height: 1px;
  margin: 0.55rem 0.25rem;
  background: rgba(255, 255, 255, 0.06);
}

.app-sidebar__nav-item--plugin {
  color: rgba(255, 255, 255, 0.58);
}


.app-sidebar__active-bar {
  position: absolute;
  left: 0;
  top: 50%;
  transform: translateY(-50%);
  width: 3px;
  height: 1.5rem;
  border-radius: 0 4px 4px 0;
  background: var(--color-brand);
}

.app-sidebar__nav-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  width: 1.75rem;
  height: 1.75rem;
}

.app-sidebar__plugin-icon {
  width: 1.65rem;
  height: 1.65rem;
}

.app-sidebar__nav-label {
  flex: 1;
}

/* Bottom */
.app-sidebar__bottom {
  padding: 0.625rem;
  flex-shrink: 0;
}

.app-sidebar__bottom::before {
  content: '';
  display: block;
  height: 1px;
  margin: 0 0.25rem 0.875rem;
  background: rgba(255, 255, 255, 0.06);
}

.app-sidebar__bottom-controls {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: .5rem;
  width: 100%;
  padding: .2rem .125rem 0;
}

.app-sidebar__collapse-btn,
.app-sidebar__widget-next {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 1.5rem;
  height: 1.5rem;
  padding: 0;
  border-radius: 0;
  border: none;
  background: transparent;
  color: rgba(255, 255, 255, 0.4);
  cursor: pointer;
  transition: color var(--transition-fast);
}

.app-sidebar__widget-spacer {
  width: 1.5rem;
  height: 1.5rem;
}

.app-sidebar__collapse-btn:hover,
.app-sidebar__widget-next:hover {
  background: transparent;
  color: rgba(255, 255, 255, 0.7);
}

.app-sidebar--collapsed .app-sidebar__logo {
  padding: 0;
  justify-content: center;
}

.app-sidebar--collapsed .app-sidebar__nav {
  padding-left: 0.625rem;
  padding-right: 0.625rem;
}

.app-sidebar--collapsed .app-sidebar__nav-item {
  justify-content: center;
  padding-left: 0;
  padding-right: 0;
}

.app-sidebar--collapsed .app-sidebar__divider {
  margin-left: 0.1rem;
  margin-right: 0.1rem;
}
</style>
