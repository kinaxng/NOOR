import api from '../api'

type RendererModule = Record<string, any>
const moduleCache = new Map<string, Promise<RendererModule>>()
const styleCache = new Set<string>()

async function pluginInfo(pluginId: string) {
  const { data } = await api.get(`/plugins/${pluginId}/config`)
  return data?.plugin || {}
}

function ensureStyle(pluginId: string, style: string) {
  if (!style) return
  const key = `${pluginId}:${style}`
  if (styleCache.has(key)) return
  const link = document.createElement('link')
  link.rel = 'stylesheet'
  link.href = `/api/plugins/${pluginId}/assets/${style.replace(/^frontend\//, '')}`
  document.head.appendChild(link)
  styleCache.add(key)
}

export async function loadPluginRendererModule(pluginId: string): Promise<RendererModule> {
  if (!moduleCache.has(pluginId)) {
    moduleCache.set(pluginId, (async () => {
      const info = await pluginInfo(pluginId)
      const renderer = info?.frontend?.renderer || info?.frontend?.entry || 'frontend/page.js'
      const style = info?.frontend?.renderer_style || info?.frontend?.style || ''
      ensureStyle(pluginId, style)
      return await import(/* @vite-ignore */ `/api/plugins/${pluginId}/assets/${String(renderer).replace(/^frontend\//, '')}?t=${Date.now()}`)
    })())
  }
  return moduleCache.get(pluginId)!
}

export function makePluginSdk(pluginId: string) {
  const controller = new AbortController()
  const cleanupFns: Array<() => void> = []
  const onUnmount = (fn: () => void) => {
    if (typeof fn !== 'function') return () => {}
    cleanupFns.push(fn)
    return () => {
      const index = cleanupFns.indexOf(fn)
      if (index >= 0) cleanupFns.splice(index, 1)
    }
  }
  const ensureActive = () => {
    if (controller.signal.aborted) throw new DOMException('The operation was aborted.', 'AbortError')
  }
  const pluginFetch = (path: string, init?: RequestInit) => {
    ensureActive()
    return fetch(`/api/plugins/${pluginId}${path}`, { ...(init || {}), signal: init?.signal || controller.signal })
  }
  const dispose = () => {
    try { controller.abort() } catch {}
    for (const cleanup of cleanupFns.splice(0)) {
      try { cleanup() } catch {}
    }
  }
  return {
    pluginId,
    api: {
      plugin: pluginFetch,
      get: (path: string, config?: any) => {
        ensureActive()
        return api.get(path, { ...(config || {}), signal: config?.signal || controller.signal })
      },
      post: (path: string, data?: any, config?: any) => {
        ensureActive()
        return api.post(path, data, { ...(config || {}), signal: config?.signal || controller.signal })
      },
      wsUrl: (path: string) => `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/api/plugins/${pluginId}${path}`,
    },
    lifecycle: {
      signal: controller.signal,
      get aborted() { return controller.signal.aborted },
      onUnmount,
    },
    timers: {
      setTimeout: (handler: TimerHandler, timeout?: number, ...args: any[]) => {
        ensureActive()
        const timer = window.setTimeout(handler, timeout, ...args)
        const off = onUnmount(() => window.clearTimeout(timer))
        return { id: timer, clear: () => { window.clearTimeout(timer); off() } }
      },
      setInterval: (handler: TimerHandler, timeout?: number, ...args: any[]) => {
        ensureActive()
        const timer = window.setInterval(handler, timeout, ...args)
        const off = onUnmount(() => window.clearInterval(timer))
        return { id: timer, clear: () => { window.clearInterval(timer); off() } }
      },
    },
    events: {
      on: (target: EventTarget, type: string, listener: EventListenerOrEventListenerObject, options?: AddEventListenerOptions | boolean) => {
        ensureActive()
        target.addEventListener(type, listener, options)
        const cleanup = () => target.removeEventListener(type, listener, options)
        const off = onUnmount(cleanup)
        return () => { cleanup(); off() }
      },
    },
    net: {
      webSocket: (path: string) => {
        ensureActive()
        const url = `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/api/plugins/${pluginId}${path}`
        const ws = new WebSocket(url)
        onUnmount(() => {
          try { ws.close() } catch {}
        })
        return ws
      },
    },
    __dispose: dispose,
  }
}
