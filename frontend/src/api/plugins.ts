import api from './index'

export interface PluginListItem {
  id: string
  name: string
  version: string
  type: string
  description: string
  tags: string[]
  capabilities: string[]
  contributions: Record<string, any>
  config?: Record<string, any>
  enabled: boolean
}

export async function fetchPlugins(): Promise<PluginListItem[]> {
  const res = await api.get('/plugins')
  return Array.isArray(res.data?.items) ? res.data.items : (Array.isArray(res.data) ? res.data : [])
}

export function pluginPageRoute(plugin: PluginListItem): string | null {
  const route = plugin.contributions?.sidebar?.route
  if (typeof route === 'string' && route.startsWith('/plugins/')) return route
  if (plugin.capabilities?.includes('sidebar_page')) return `/plugins/${plugin.id}`
  return null
}
