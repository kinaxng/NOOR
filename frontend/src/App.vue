<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { RouterView } from 'vue-router'
import BaseToast from './components/noor/BaseToast.vue'
import ConfirmDialog from './components/noor/ConfirmDialog.vue'
import BaseIcon from './components/noor/BaseIcon.vue'
import AppSidebar from './components/noor/AppSidebar.vue'
import SystemLogPanel from './components/noor/SystemLogPanel.vue'
import GlobalSearch from './components/noor/GlobalSearch.vue'
import { useBlurCover } from './composables/useBlurCover'
import { useI18n } from './composables/useI18n'
import { useJobsStore } from './stores/jobs'
import { useSystemLog } from './composables/useSystemLog'
import { usePlugins } from './composables/usePlugins'
import api from './api'

const route = useRoute()
const { blurEnabled, globalBlurEnabled, browserBlurEnabled, syncGlobalBlur, toggleBrowserBlur } = useBlurCover()
const { currentLang, switchLang, t, i18nVersion, _currentLang, _initialized } = useI18n()
const jobsStore = useJobsStore()
const { show: showSystemLog, toggle: toggleSystemLog } = useSystemLog()
const { enabledPagePlugins, loadPlugins } = usePlugins()

const sidebarCollapsed = ref(false)
const mobileSidebarOpen = ref(false)
const globalSearchOpen = ref(false)

// Computed that always returns true but establishes reactive tracking of i18nVersion
// This forces Vue to re-render App.vue template when language changes
// App.vue is OUTSIDE RouterView, so it doesn't get re-rendered by RouterView's :key
const i18nReady = computed(() => {
  void _currentLang.value
  void _initialized.value
  void currentLang.value
  void i18nVersion.value
  return true
})

const navItems = computed(() => {
  void _currentLang.value  // Track the raw ref - t() reads this directly
  void _initialized.value  // Force re-eval after dictionaries load
  void currentLang.value
  void i18nVersion.value
  return [
    { path: '/', name: t('nav.overview'), icon: 'dashboard' },
    { path: '/library', name: t('nav.library'), icon: 'library' },
    { path: '/jobs', name: t('nav.jobs'), icon: 'jobs', badge: computed(() => {
      const running = jobsStore.jobs.filter(j => j.status === 'running').length
      const queued = jobsStore.jobs.filter(j => j.status === 'queued').length
      const blocked = jobsStore.jobs.filter(j => j.status === 'blocked').length
      const pending = jobsStore.jobs.filter(j => j.status === 'pending').length
      return running + queued + blocked + pending || null
    })},
    { path: '/history', name: t('nav.history'), icon: 'history' },
    { path: '/files', name: t('nav.files'), icon: 'folderOpen' },
    { path: '/settings', name: t('nav.settings'), icon: 'settings' },
  ]
})

const activeNavName = computed(() => {
  if (route.path.startsWith('/plugins/')) {
    const plugin = enabledPagePlugins.value.find(p => route.path === p.route || route.path.startsWith(`${p.route}/`))
    return plugin?.contributions?.sidebar?.label || plugin?.name || '插件'
  }
  if (route.name === 'actor-detail') return t('files.actors.title')
  if (route.path.startsWith('/search/resources')) return '资源搜索'
  if (route.path === '/plugins') return '插件'
  return navItems.value.find(n => route.path === n.path || route.path.startsWith(`${n.path}/`))?.name || t('nav.settings')
})

const blurTitle = computed(() => {
  void _currentLang.value
  void _initialized.value
  void currentLang.value
  void i18nVersion.value
  if (!globalBlurEnabled.value) return t('toolbar.blurUnavailable')
  return browserBlurEnabled.value ? t('toolbar.blurOff') : t('toolbar.blurOn')
})
const langTitle = computed(() => {
  void _currentLang.value
  void _initialized.value
  void currentLang.value
  void i18nVersion.value
  return t('toolbar.switchLang')
})
const langBadgeText = computed(() => {
  void _currentLang.value
  void _initialized.value
  void currentLang.value
  void i18nVersion.value
  return currentLang.value === 'zh' ? t('toolbar.langShortZh') : t('toolbar.langShortEn')
})

function toggleSidebar() {
  sidebarCollapsed.value = !sidebarCollapsed.value
}

function handleGlobalKeydown(event: KeyboardEvent) {
  const target = event.target as HTMLElement | null
  const tagName = target?.tagName?.toLowerCase()
  const isEditable = !!target?.isContentEditable || tagName === 'input' || tagName === 'textarea' || tagName === 'select'
  if (isEditable) return

  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
    event.preventDefault()
    globalSearchOpen.value = true
    return
  }

  if (!event.ctrlKey && !event.metaKey && !event.altKey && event.key.toLowerCase() === 'h') {
    event.preventDefault()
    toggleBrowserBlur()
  }
}

function reportClientDiagnostic(level: 'info' | 'warning' | 'error', message: string, stack?: string) {
  if (!showSystemLog.value) return
  const text = String(message || '').trim()
  if (!text) return
  if (isLifecycleCancelDiagnostic(text) || (stack && isLifecycleCancelDiagnostic(stack))) return
  void api.post('/system/logs/client', {
    level,
    source: 'frontend',
    message: text,
    stack: stack ? String(stack).slice(0, 8000) : undefined,
    route: window.location.pathname + window.location.search,
  }).catch(() => {})
}

function isLifecycleCancelDiagnostic(value: unknown) {
  const text = String(value || '').toLowerCase()
  if (!text) return false
  return [
    'aborterror',
    'err_canceled',
    'operation was aborted',
    'request aborted',
    'request canceled',
    'request cancelled',
    'is unmounted',
    'plugin unmounted',
    'cancelederror',
  ].some(token => text.includes(token))
}

function shouldLogMainApi(url?: string, level: 'info' | 'warning' | 'error' = 'info') {
  const value = String(url || '').toLowerCase()
  if (!value) return false
  if (value.includes('/system/logs')) return false
  if (value.includes('/system/metrics')) return false
  if (value.includes('/plugins/')) return false
  if (value.includes('/events')) return false
  if (value.includes('/jobs') && value.includes('/logs')) return false
  if (level !== 'info') return true
  return false
}

function installMainApiDiagnostics() {
  const requestId = api.interceptors.request.use((config: any) => {
    config.metadata = { startedAt: performance.now() }
    return config
  })
  const responseId = api.interceptors.response.use(
    (response: any) => {
      const startedAt = response.config?.metadata?.startedAt
      const cost = typeof startedAt === 'number' ? Math.round(performance.now() - startedAt) : 0
      const url = response.config?.url || ''
      if (showSystemLog.value && cost >= 1500 && shouldLogMainApi(url, 'warning')) {
        reportClientDiagnostic('warning', `[main-api] slow ${String(response.config?.method || 'GET').toUpperCase()} ${url} status=${response.status} cost=${cost}ms`)
      }
      return response
    },
    (error: any) => {
      const config = error?.config || {}
      const startedAt = config?.metadata?.startedAt
      const cost = typeof startedAt === 'number' ? Math.round(performance.now() - startedAt) : 0
      const url = config?.url || ''
      const message = error?.response?.data?.detail || error.message || 'request failed'
      if (showSystemLog.value && shouldLogMainApi(url, 'error') && !isLifecycleCancelDiagnostic(message) && !isLifecycleCancelDiagnostic(error?.code) && !isLifecycleCancelDiagnostic(error?.name)) {
        const status = error?.response?.status ? ` status=${error.response.status}` : ''
        reportClientDiagnostic('error', `[main-api] ${String(config?.method || 'GET').toUpperCase()} ${url} failed${status} cost=${cost}ms error=${message}`)
      }
      return Promise.reject(error)
    },
  )
  return () => {
    api.interceptors.request.eject(requestId)
    api.interceptors.response.eject(responseId)
  }
}

let uninstallMainApiDiagnostics: null | (() => void) = null

function normalizeDiagnosticMessage(value: unknown) {
  if (value instanceof Error) return { message: value.message, stack: value.stack }
  if (typeof value === 'string') return { message: value }
  try {
    return { message: JSON.stringify(value) }
  } catch {
    return { message: String(value) }
  }
}

function handleWindowError(event: ErrorEvent) {
  if (isLifecycleCancelDiagnostic(event.message) || isLifecycleCancelDiagnostic(event.error?.message) || isLifecycleCancelDiagnostic(event.error?.name)) return
  reportClientDiagnostic('error', event.message || 'Window error', event.error?.stack || `${event.filename}:${event.lineno}:${event.colno}`)
}

function handleUnhandledRejection(event: PromiseRejectionEvent) {
  const detail = normalizeDiagnosticMessage(event.reason)
  if (isLifecycleCancelDiagnostic(detail.message) || isLifecycleCancelDiagnostic(detail.stack) || isLifecycleCancelDiagnostic((event.reason as any)?.name) || isLifecycleCancelDiagnostic((event.reason as any)?.code)) return
  reportClientDiagnostic('error', `Unhandled promise rejection: ${detail.message}`, detail.stack)
}

const originalConsoleWarn = console.warn.bind(console)
const originalConsoleError = console.error.bind(console)

function installConsoleDiagnostics() {
  console.warn = (...args: unknown[]) => {
    originalConsoleWarn(...args)
    const message = args.map(arg => normalizeDiagnosticMessage(arg).message).join(' ')
    if (isLifecycleCancelDiagnostic(message)) return
    reportClientDiagnostic('warning', `[console.warn] ${message}`)
  }
  console.error = (...args: unknown[]) => {
    originalConsoleError(...args)
    const normalized = args.map(arg => normalizeDiagnosticMessage(arg))
    const message = normalized.map(item => item.message).join(' ')
    const stack = normalized.find(item => item.stack)?.stack
    if (isLifecycleCancelDiagnostic(message) || isLifecycleCancelDiagnostic(stack)) return
    reportClientDiagnostic('error', `[console.error] ${message}`, stack)
  }
}

function uninstallConsoleDiagnostics() {
  console.warn = originalConsoleWarn
  console.error = originalConsoleError
}

watch(blurEnabled, (enabled) => {
  document.body.classList.toggle('noor-blur-images', enabled)
}, { immediate: true })

watch(() => route.fullPath, (to, from) => {
  if (!from || to === from) return
  reportClientDiagnostic('info', `[main-route] ${from} -> ${to}`)
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleGlobalKeydown)
  window.removeEventListener('error', handleWindowError)
  window.removeEventListener('unhandledrejection', handleUnhandledRejection)
  uninstallMainApiDiagnostics?.()
  uninstallConsoleDiagnostics()
})

onMounted(() => {
  loadPlugins()
  api.get('/settings/ui').then(resp => {
    const value = resp.data?.cover_blur_enabled
    if (typeof value === 'boolean') syncGlobalBlur(value)
  }).catch(() => {})
  window.addEventListener('keydown', handleGlobalKeydown)
  window.addEventListener('error', handleWindowError)
  window.addEventListener('unhandledrejection', handleUnhandledRejection)
  installConsoleDiagnostics()
  uninstallMainApiDiagnostics = installMainApiDiagnostics()
  // Don't auto-poll; only poll when user opens the log panel
})
</script>

<template>
  <div :class="['app-root min-h-screen', { 'noor-blur-images': blurEnabled }]" style="background-color: var(--color-bg-base);">
    <!-- Mobile overlay backdrop -->
    <div
      v-if="mobileSidebarOpen"
      class="fixed inset-0 bg-black/60 z-40 lg:hidden"
      @click="mobileSidebarOpen = false"
    />

    <!-- Vision UI Sidebar -->
    <AppSidebar
      :collapsed="sidebarCollapsed"
      :mobile-open="mobileSidebarOpen"
      :i18n-version="i18nVersion"
      @toggle="toggleSidebar"
      @close="mobileSidebarOpen = false"
    />

    <!-- Main Content Area -->
    <main
      class="app-main transition-all duration-300"
      :class="[
        sidebarCollapsed ? 'lg:ml-[76px]' : 'lg:ml-[274px]',
        showSystemLog ? 'app-main--with-log' : '',
      ]"
    >
      <!-- Top Navbar -->
      <header
        v-if="i18nReady"
        class="sticky top-0 z-30 h-16 flex items-center justify-between px-4 md:px-6"
        style="background: linear-gradient(123.64deg, rgba(255,255,255,0) -22.38%, rgba(255,255,255,0.039) 70.38%); backdrop-filter: blur(20px); border-bottom: 1px solid rgba(255,255,255,0.04);"
      >
        <!-- Left: Mobile menu + Page title -->
        <div class="flex items-center gap-3">
          <!-- Hamburger (mobile only) -->
          <button
            class="navbar-icon-btn hidden lg:hidden"
            @click="mobileSidebarOpen = true"
          >
            <BaseIcon name="menu" class="w-4 h-4" />
          </button>
          <h1 class="text-base font-semibold text-white font-display">
            {{ activeNavName }}
          </h1>
        </div>

        <!-- Right: Controls -->
        <div class="flex items-center gap-2 md:gap-3">
          <!-- Global Search -->
          <button
            @click="globalSearchOpen = true"
            class="navbar-search-trigger"
            title="全局搜索 Ctrl/⌘ K"
          >
            <BaseIcon name="search" class="w-4 h-4" />
            <span class="navbar-search-trigger__text">搜索</span>
            <span class="navbar-search-trigger__kbd">⌘K</span>
          </button>

          <!-- Blur toggle -->
          <button
            @click="toggleBrowserBlur"
            class="navbar-icon-btn"
            :class="{ 'navbar-icon-btn--active': browserBlurEnabled }"
            :title="blurTitle"
          >
            <BaseIcon :name="browserBlurEnabled ? 'eye-off' : 'eye'" class="w-4 h-4" />
          </button>

          <!-- Language toggle -->
          <button
            @click="switchLang(currentLang === 'zh' ? 'en' : 'zh')"
            class="navbar-icon-btn"
            :title="langTitle"
          >
            <span class="text-xs font-bold font-display">{{ langBadgeText }}</span>
          </button>

          <!-- System Log toggle -->
          <button
            @click="toggleSystemLog"
            class="navbar-icon-btn"
            :class="{ 'navbar-icon-btn--active': showSystemLog }"
            :title="showSystemLog ? t('toolbar.logsOff') : t('toolbar.logs')"
          >
            <BaseIcon name="terminal" class="w-4 h-4" />
          </button>

          <!-- User menu -->
          <button class="navbar-user-btn">
            <div class="navbar-user-avatar">
              <BaseIcon name="user" class="w-4 h-4" />
            </div>
          </button>
        </div>
      </header>

      <!-- Page Content -->
      <div class="p-4 md:p-6">
        <RouterView :key="currentLang" />
      </div>
    </main>

    <!-- Global Toast -->
    <BaseToast />

    <!-- Global Confirm Dialog -->
    <ConfirmDialog />

    <!-- System Log Panel -->
    <SystemLogPanel />

    <!-- Global Search -->
    <GlobalSearch :open="globalSearchOpen" @close="globalSearchOpen = false" />
  </div>
</template>

<style scoped>
.app-main {
  min-width: 0;
}

@media (min-width: 1024px) {
  .app-main--with-log {
    margin-right: 380px;
  }
}

.navbar-search {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 0.875rem;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: var(--radius-button);
  transition: all var(--transition-fast);
}

.navbar-search:hover {
  background: rgba(255, 255, 255, 0.08);
  border-color: rgba(255, 255, 255, 0.12);
}

.navbar-search__icon {
  color: rgba(255, 255, 255, 0.4);
  flex-shrink: 0;
}

.navbar-search__input {
  background: transparent;
  border: none;
  outline: none;
  font-family: var(--font-display);
  font-size: 0.875rem;
  color: #FFFFFF;
  width: 120px;
}

@media (min-width: 768px) {
  .navbar-search__input {
    width: 180px;
  }
}

.navbar-search__input::placeholder {
  color: rgba(255, 255, 255, 0.4);
}

.navbar-search-trigger {
  width: 2.375rem;
  height: 2.375rem;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: .5rem;
  padding: 0;
  border: 1px solid rgba(255,255,255,.08);
  border-radius: var(--radius-md);
  background: rgba(255,255,255,.05);
  color: rgba(255,255,255,.52);
  transition: background var(--transition-fast), color var(--transition-fast), border-color var(--transition-fast);
}
.navbar-search-trigger:hover {
  background: rgba(255,255,255,.09);
  color: rgba(255,255,255,.82);
  border-color: rgba(255,255,255,.12);
}
.navbar-search-trigger__text {
  flex: 1;
  text-align: left;
  font-size: .78rem;
  display: none;
}
.navbar-search-trigger__kbd {
  display: none;
  border: 1px solid rgba(255,255,255,.08);
  border-radius: .42rem;
  padding: .08rem .32rem;
  color: rgba(255,255,255,.34);
  font-size: .62rem;
}
@media (min-width: 768px) {
  .navbar-search-trigger {
    width: auto;
    min-width: 10rem;
    justify-content: flex-start;
    padding: 0 .72rem;
  }

  .navbar-search-trigger__text,
  .navbar-search-trigger__kbd {
    display: inline-flex;
  }
}

.navbar-icon-btn {
  position: relative;
  width: 2.375rem;
  height: 2.375rem;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: var(--radius-md);
  color: rgba(255, 255, 255, 0.5);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.navbar-icon-btn:hover {
  background: rgba(255, 255, 255, 0.1);
  color: rgba(255, 255, 255, 0.8);
}

.navbar-icon-btn--active {
  background: rgba(0, 117, 255, 0.15);
  border-color: rgba(0, 117, 255, 0.3);
  color: #0075FF;
}

.navbar-badge {
  position: absolute;
  top: -4px;
  right: -4px;
  min-width: 1rem;
  height: 1rem;
  padding: 0 0.25rem;
  background: #0075FF;
  border-radius: 9999px;
  font-family: var(--font-display);
  font-size: 0.625rem;
  font-weight: 700;
  color: #FFFFFF;
  display: flex;
  align-items: center;
  justify-content: center;
}

.navbar-user-btn {
  background: transparent;
  border: none;
  cursor: pointer;
  padding: 0;
}

.navbar-user-avatar {
  width: 2.375rem;
  height: 2.375rem;
  border-radius: 9999px;
  background: #0075FF;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #FFFFFF;
  transition: all var(--transition-fast);
}

.navbar-user-btn:hover .navbar-user-avatar {
  box-shadow: 0 4px 12px rgba(0, 117, 255, 0.4);
  transform: scale(1.05);
}
</style>
