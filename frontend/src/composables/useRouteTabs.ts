import { computed, watch, type WritableComputedRef } from 'vue'
import type { RouteLocationNormalizedLoaded, Router } from 'vue-router'

type RouteTabsOptions<T extends string> = {
  route: RouteLocationNormalizedLoaded
  router: Router
  basePath: string
  paramName: string
  tabs: readonly T[]
  defaultTab: T
}

function firstParam(value: unknown) {
  return Array.isArray(value) ? value[0] : value
}

export function useRouteTabs<T extends string>(options: RouteTabsOptions<T>): WritableComputedRef<T> {
  const tabs = new Set<string>(options.tabs)
  const basePath = options.basePath.replace(/\/+$/g, '')

  const normalize = (value: unknown): T => {
    const raw = String(firstParam(value) || '')
    return tabs.has(raw) ? raw as T : options.defaultTab
  }

  const pathFor = (tab: T) => `${basePath}/${tab}`

  const activeTab = computed<T>({
    get() {
      return normalize(options.route.params[options.paramName])
    },
    set(value) {
      const next = tabs.has(value) ? value : options.defaultTab
      const path = pathFor(next)
      if (options.route.path === path) return
      void options.router.push({ path, query: options.route.query })
    },
  })

  watch(
    () => options.route.params[options.paramName],
    value => {
      const raw = String(firstParam(value) || '')
      if (raw && tabs.has(raw)) return
      void options.router.replace({ path: pathFor(options.defaultTab), query: options.route.query })
    },
    { immediate: true },
  )

  return activeTab
}
