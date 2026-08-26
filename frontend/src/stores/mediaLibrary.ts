import { defineStore } from 'pinia'
import { ref, computed, shallowRef } from 'vue'
import api from '../api'
import { useI18n } from '../composables/useI18n'
import type { MediaLibrary, MediaItem, MediaItemDetail, HardlinkEntry, HardlinkGroup, HardlinkSummary } from '../api/types'

// Module-level cache for fire-and-forget preload
const _librariesCache: { data: MediaLibrary[]; enabledIds: string[]; loaded: boolean } = {
  data: [], enabledIds: [], loaded: false,
}
// Cache for items page 1 (optimistic rendering)
const _itemsCache: { items: MediaItem[]; total: number; key: string } = {
  items: [], total: 0, key: '',
}

let _librariesWarmupPromise: Promise<void> | null = null


type HardlinkDeleteResult = {
  deleted_dirs?: string[]
  deleted_files?: string[]
  missing_dirs?: string[]
  missing_files?: string[]
  deleted_paths?: string[]
}

function normalizePathSet(paths: string[] = []) {
  return new Set(paths.filter(Boolean))
}

function entryAfterDelete(entry: HardlinkEntry, deletedDirs: Set<string>, deletedFiles: Set<string>): HardlinkEntry | null {
  const sourceDeleted = !!entry.source_path && (deletedFiles.has(entry.source_path) || Array.from(deletedDirs).some((dir) => entry.source_path?.startsWith(`${dir}/`) || entry.source_path === dir))
  const hardlinkPaths = entry.hardlink_paths.filter((path) => !deletedFiles.has(path) && !Array.from(deletedDirs).some((dir) => path.startsWith(`${dir}/`) || path === dir))
  const nextSourcePath = sourceDeleted ? null : entry.source_path
  if (!nextSourcePath && hardlinkPaths.length === 0) return null

  const issues: string[] = []
  if (!nextSourcePath) issues.push('orphan_source')

  return {
    ...entry,
    source_path: nextSourcePath,
    hardlink_paths: hardlinkPaths,
    hardlink_count: hardlinkPaths.length,
    issues,
    status: issues.length > 0 ? 'issue' as const : 'healthy' as const,
  }
}

function summarizeHardlinkGroups(groups: HardlinkGroup[]): HardlinkSummary {
  return {
    total_groups: groups.length,
    total_entries: groups.reduce((sum, group) => sum + (group.entry_count || group.entries.length), 0),
    total_hardlinks: groups.reduce((sum, group) => sum + (group.hardlink_count || group.entries.reduce((s, entry) => s + entry.hardlink_paths.length, 0)), 0),
    issue_groups: groups.filter((group) => group.status === 'issue' || (group.issue_count || 0) > 0).length,
    orphan_entries: groups.reduce((sum, group) => sum + (group.orphan_count || 0), 0),
  }
}

function rebuildHardlinkGroup(group: HardlinkGroup, entries: HardlinkEntry[]): HardlinkGroup {
  const orphanCount = entries.filter((entry) => !entry.source_path).length
  const unparsed = group.issues?.includes('unparsed_code') || group.code === 'N/A'
  const issueCount = orphanCount + (unparsed ? 1 : 0)
  return {
    ...group,
    entries,
    entry_count: entries.length,
    hardlink_count: entries.reduce((sum, entry) => sum + entry.hardlink_paths.length, 0),
    orphan_count: orphanCount,
    issue_count: issueCount,
    status: issueCount > 0 ? 'issue' : 'healthy',
    issues: [
      ...(unparsed ? ['unparsed_code'] : []),
      ...(orphanCount ? ['orphan_source'] : []),
    ],
  }
}

export const useMediaLibraryStore = defineStore('media-library', () => {
  const { t } = useI18n()
  const allLibraries = ref<MediaLibrary[]>([])
  const enabledLibraryIds = ref<string[]>([])
  const items = ref<MediaItem[]>([])
  const selectedLibrary = ref<MediaLibrary | null>(null)
  const selectedItem = ref<MediaItemDetail | null>(null)
  const loading = ref(false)
  const detailLoading = ref(false)
  const error = ref<string | null>(null)
  const total = ref(0)
  const currentPage = ref(1)
  const pageSize = ref(18)
  const filterTag = ref<string | null>(null)
  const searchQuery = ref('')

  async function _fetchLibrariesBg() {
    // Background refresh - does NOT trigger loading state
    try {
      // First check if adapter is available (this endpoint always returns 200)
      const statusResp = await api.get('/media-library')
      if (!statusResp.data.available) {
        error.value = statusResp.data.message || t('library.adapterUnavailable')
        return
      }
      const [libsResp, configResp] = await Promise.all([
        api.get('/media-library/libraries'),
        api.get('/media-library/config').catch(() => ({ data: { config: {} } })),
      ])
      const cfg = configResp.data.config || {}
      const enabledIds = cfg.enabled_library_ids
        ? String(cfg.enabled_library_ids).split(',').map((s: string) => s.trim()).filter(Boolean)
        : []
      allLibraries.value = libsResp.data.libraries
      enabledLibraryIds.value = enabledIds
      _librariesCache.data = libsResp.data.libraries
      _librariesCache.enabledIds = enabledIds
      _librariesCache.loaded = true
    } catch (e: any) {
      // Check 503 to show the adapter disabled message even in background refresh
      if (e.response?.status === 503) {
        error.value = t('library.adapterUnavailable')
      }
      // Silently fail for other errors - foreground fetch will retry
    }
  }

  async function fetchLibraries() {
    loading.value = true
    error.value = null
    try {
      if (!_librariesCache.loaded && _librariesWarmupPromise) {
        await _librariesWarmupPromise
        if (_librariesCache.loaded) {
          allLibraries.value = _librariesCache.data
          enabledLibraryIds.value = _librariesCache.enabledIds
          loading.value = false
          return
        }
      }
      // First check if adapter is available (always returns 200)
      const statusResp = await api.get('/media-library')
      if (!statusResp.data.available) {
        error.value = statusResp.data.message || t('library.adapterUnavailable')
        loading.value = false
        return
      }
      // Adapter available: use cache if loaded, else fetch fresh
      if (_librariesCache.loaded) {
        allLibraries.value = _librariesCache.data
        enabledLibraryIds.value = _librariesCache.enabledIds
        // Refresh in background
        _fetchLibrariesBg()
        loading.value = false
        return
      }
      const [libsResp, configResp] = await Promise.all([
        api.get('/media-library/libraries'),
        api.get('/media-library/config').catch(() => ({ data: { config: {} } })),
      ])
      const cfg = configResp.data.config || {}
      const enabledIds = cfg.enabled_library_ids
        ? String(cfg.enabled_library_ids).split(',').map((s: string) => s.trim()).filter(Boolean)
        : []
      allLibraries.value = libsResp.data.libraries
      enabledLibraryIds.value = enabledIds
      _librariesCache.data = libsResp.data.libraries
      _librariesCache.enabledIds = enabledIds
      _librariesCache.loaded = true
    } catch (e: any) {
      // Check 503 specifically (axios throws on non-2xx)
      if (e.response?.status === 503) {
        error.value = t('library.adapterUnavailable')
      } else {
        error.value = e.message || t('library.fetchFailed')
      }
    } finally {
      loading.value = false
    }
  }

  // Fire-and-forget preload: call immediately when store is first imported
  if (!_librariesCache.loaded) {
    _librariesWarmupPromise = _fetchLibrariesBg().finally(() => {
      _librariesWarmupPromise = null
    })
  } else {
    allLibraries.value = _librariesCache.data
    enabledLibraryIds.value = _librariesCache.enabledIds
  }

  // Filter libraries based on enabled IDs (empty = show all)
  const libraries = computed(() => {
    if (enabledLibraryIds.value.length === 0) {
      return allLibraries.value
    }
    return allLibraries.value.filter(lib => enabledLibraryIds.value.includes(lib.id))
  })

  async function _fetchItemsBg(libraryId: string, page: number, cacheKey: string, filterOverride?: string | null, searchOverride?: string, forceRefresh = false) {
    try {
      const offset = (page - 1) * pageSize.value
      const effectiveFilter = filterOverride !== undefined ? filterOverride : filterTag.value
      const effectiveSearch = searchOverride !== undefined ? searchOverride : searchQuery.value
      const resp = await api.get('/media-library/items', {
        params: {
          library_id: libraryId || undefined,
          limit: pageSize.value,
          offset,
          filter: effectiveFilter || undefined,
          q: effectiveSearch.trim() || undefined,
          force_refresh: forceRefresh || undefined,
        }
      })
      items.value = resp.data.items
      total.value = resp.data.total
      currentPage.value = page
      if (page === 1) {
        _itemsCache.items = resp.data.items
        _itemsCache.total = resp.data.total
        _itemsCache.key = cacheKey
      }
    } catch {
      // Silently fail
    }
  }

  async function fetchItems(libraryId: string, page: number = 1, filterOverride?: string | null, searchOverride?: string, forceRefresh = false) {
    const effectiveFilter = filterOverride !== undefined ? filterOverride : filterTag.value
    const effectiveSearch = searchOverride !== undefined ? searchOverride : searchQuery.value
    const cacheKey = `lib:${libraryId}:${effectiveFilter || 'all'}:${effectiveSearch.trim() || 'all'}:${page}`
    // Optimistic: if page 1 and we have cache, show immediately
    if (!forceRefresh && page === 1 && _itemsCache.key === cacheKey && _itemsCache.items.length > 0) {
      items.value = _itemsCache.items
      total.value = _itemsCache.total
      currentPage.value = page
      // Refresh in background
      _fetchItemsBg(libraryId, page, cacheKey, effectiveFilter, effectiveSearch)
      return
    }
    loading.value = true
    error.value = null
    if (forceRefresh) {
      _itemsCache.items = []
      _itemsCache.key = ''
    }
    await _fetchItemsBg(libraryId, page, cacheKey, effectiveFilter, effectiveSearch, forceRefresh)
    loading.value = false
  }

  async function _fetchAllItemsBg(page: number, cacheKey: string, searchOverride?: string, forceRefresh = false) {
    try {
      const offset = (page - 1) * pageSize.value
      const effectiveSearch = searchOverride !== undefined ? searchOverride : searchQuery.value
      const resp = await api.get('/media-library/items', {
        params: {
          limit: pageSize.value,
          offset,
          filter: filterTag.value || undefined,
          q: effectiveSearch.trim() || undefined,
          force_refresh: forceRefresh || undefined,
        }
      })
      items.value = resp.data.items
      total.value = resp.data.total
      currentPage.value = page
      if (page === 1) {
        _itemsCache.items = resp.data.items
        _itemsCache.total = resp.data.total
        _itemsCache.key = cacheKey
      }
    } catch {
      // Silently fail
    }
  }

  async function fetchAllItems(page: number = 1, searchOverride?: string, forceRefresh = false) {
    const effectiveSearch = searchOverride !== undefined ? searchOverride : searchQuery.value
    const cacheKey = `all:${filterTag.value || 'all'}:${effectiveSearch.trim() || 'all'}:${page}`
    // Optimistic: if page 1 and we have cache, show immediately
    if (!forceRefresh && page === 1 && _itemsCache.key === cacheKey && _itemsCache.items.length > 0) {
      items.value = _itemsCache.items
      total.value = _itemsCache.total
      currentPage.value = page
      // Refresh in background
      _fetchAllItemsBg(page, cacheKey, effectiveSearch)
      return
    }
    loading.value = true
    error.value = null
    if (forceRefresh) {
      _itemsCache.items = []
      _itemsCache.key = ''
    }
    await _fetchAllItemsBg(page, cacheKey, effectiveSearch, forceRefresh)
    loading.value = false
  }

  async function fetchItemDetail(itemId: string) {
    detailLoading.value = true
    error.value = null
    try {
      const resp = await api.get(`/media-library/item/${itemId}`)
      selectedItem.value = resp.data
      return resp.data as MediaItemDetail
    } catch (e: any) {
      error.value = e.message || t('library.itemDetailFailed')
      throw e
    } finally {
      detailLoading.value = false
    }
  }

  function selectLibrary(library: MediaLibrary | null) {
    selectedLibrary.value = library
    items.value = []
    total.value = 0
    currentPage.value = 1
  }

  function clearSelectedItem() {
    selectedItem.value = null
  }

  function invalidateCache() {
    _librariesCache.loaded = false
    _itemsCache.items = []
    _itemsCache.key = ''
  }

  function setFilter(tag: string | null) {
    filterTag.value = tag
    currentPage.value = 1
    if (selectedLibrary.value) {
      fetchItems(selectedLibrary.value.id, 1, tag, searchQuery.value)
      return
    }
    const fallbackLibrary = libraries.value[0] || null
    if (fallbackLibrary) {
      selectLibrary(fallbackLibrary)
      fetchItems(fallbackLibrary.id, 1, tag, searchQuery.value)
    }
  }

  function setPageSize(size: number) {
    const next = Math.max(1, Math.min(160, Math.floor(size || 18)))
    if (pageSize.value === next) return false
    pageSize.value = next
    currentPage.value = 1
    _itemsCache.items = []
    _itemsCache.key = ''
    return true
  }

  function nextPage() {
    if (selectedLibrary.value && currentPage.value * pageSize.value < total.value) {
      fetchItems(selectedLibrary.value.id, currentPage.value + 1, filterTag.value, searchQuery.value)
    }
  }

  function prevPage() {
    if (currentPage.value > 1 && selectedLibrary.value) {
      fetchItems(selectedLibrary.value.id, currentPage.value - 1, filterTag.value, searchQuery.value)
    }
  }

  const totalPages = computed(() => Math.ceil(total.value / pageSize.value))

  // Hardlink groups
  const hardlinkGroups = shallowRef<HardlinkGroup[]>([])
  const hardlinkScanning = ref(false)
  const hardlinkLastScannedAt = ref<string | null>(null)
  const hardlinkSummary = ref<HardlinkSummary>({
    total_groups: 0,
    total_entries: 0,
    total_hardlinks: 0,
    issue_groups: 0,
    orphan_entries: 0,
  })

  async function loadHardlinkGroups() {
    try {
      const resp = await api.get('/media-library/hardlinks/groups')
      hardlinkGroups.value = resp.data.groups || []
      hardlinkLastScannedAt.value = resp.data.last_scanned_at || null
      hardlinkSummary.value = resp.data.summary || {
        total_groups: 0,
        total_entries: 0,
        total_hardlinks: 0,
        issue_groups: 0,
        orphan_entries: 0,
      }
    } catch {
      hardlinkGroups.value = []
      hardlinkLastScannedAt.value = null
      hardlinkSummary.value = {
        total_groups: 0,
        total_entries: 0,
        total_hardlinks: 0,
        issue_groups: 0,
        orphan_entries: 0,
      }
    }
  }

  function applyHardlinkDeleteResult(result: HardlinkDeleteResult) {
    const deletedDirs = normalizePathSet(result.deleted_dirs || [])
    const deletedFiles = normalizePathSet([...(result.deleted_files || []), ...(result.deleted_paths || [])])
    if (deletedDirs.size === 0 && deletedFiles.size === 0) {
      return false
    }

    const nextGroups = hardlinkGroups.value
      .map((group) => {
        const nextEntries = group.entries
          .map((entry) => entryAfterDelete(entry, deletedDirs, deletedFiles))
          .filter((entry): entry is HardlinkEntry => entry !== null)
        if (nextEntries.length === 0) return null
        return rebuildHardlinkGroup(group, nextEntries)
      })
      .filter((group): group is HardlinkGroup => !!group)

    hardlinkGroups.value = nextGroups
    hardlinkSummary.value = summarizeHardlinkGroups(nextGroups)
    hardlinkLastScannedAt.value = new Date().toISOString()
    return true
  }

  async function scanHardlinks() {
    hardlinkScanning.value = true
    try {
      const resp = await api.post('/media-library/hardlinks/scan')
      hardlinkGroups.value = resp.data.groups || []
      hardlinkLastScannedAt.value = resp.data.last_scanned_at || null
      const summary = resp.data.summary || {
        total_groups: 0,
        total_entries: 0,
        total_hardlinks: 0,
        issue_groups: 0,
        orphan_entries: 0,
      }
      hardlinkSummary.value = summary
      return {
        ok: true,
        count: summary.total_groups ?? resp.data.total_count ?? 0,
        totalEntries: summary.total_entries ?? resp.data.total_entries ?? 0,
      }
    } catch (e: any) {
      return { ok: false, error: e?.response?.data?.detail || e.message }
    } finally {
      hardlinkScanning.value = false
    }
  }

  const filteredItems = computed(() => {
    if (!filterTag.value) return items.value

    return items.value.filter(item => {
      const tags = item.tags
      if (!tags) return false

      switch (filterTag.value) {
        case 'cracked':
          return tags.is_cracked
        case 'chinese':
          return tags.has_chinese
        case 'leaked':
          return tags.release_type_key === 'leaked'
        case 'uncensored':
          return tags.release_type_key === 'uncensored'
        default:
          return true
      }
    })
  })

  // Tag counts for dashboard stats (same filter logic as filteredItems)
  const tagCounts = computed(() => {
    const all = items.value
    return {
      total: total.value,
      cracked: all.filter(i => i.tags?.is_cracked).length,
      chinese: all.filter(i => i.tags?.has_chinese).length,
      leaked: all.filter(i => i.tags?.release_type_key === 'leaked').length,
      uncensored: all.filter(i => i.tags?.release_type_key === 'uncensored').length,
    }
  })

  function setSearch(query: string) {
    searchQuery.value = query
    currentPage.value = 1
    if (selectedLibrary.value) {
      fetchItems(selectedLibrary.value.id, 1, filterTag.value, query)
      return
    }
    const fallbackLibrary = libraries.value[0] || null
    if (fallbackLibrary) {
      selectLibrary(fallbackLibrary)
      fetchItems(fallbackLibrary.id, 1, filterTag.value, query)
    }
  }


  return {
    allLibraries,
    libraries,
    enabledLibraryIds,
    items,
    selectedLibrary,
    selectedItem,
    loading,
    detailLoading,
    error,
    total,
    currentPage,
    pageSize,
    setPageSize,
    filterTag,
    searchQuery,
    totalPages,
    filteredItems,
    tagCounts,
    fetchLibraries,
    fetchItems,
    fetchAllItems,
    fetchItemDetail,
    selectLibrary,
    clearSelectedItem,
    setFilter,
    setSearch,
    nextPage,
    prevPage,
    invalidateCache,
    hardlinkGroups,
    hardlinkScanning,
    hardlinkLastScannedAt,
    hardlinkSummary,
    loadHardlinkGroups,
    scanHardlinks,
    applyHardlinkDeleteResult,
  }
})
