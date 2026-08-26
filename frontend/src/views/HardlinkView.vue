
<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import api from '../api'
import { useMediaLibraryStore } from '../stores/mediaLibrary'
import { useToast } from '../composables/useToast'
import { useConfirm } from '../composables/useConfirm'
import { useI18n } from '../composables/useI18n'
import VuiButton from '../components/ui/Button/VuiButton.vue'
import VuiBadge from '../components/ui/Badge/VuiBadge.vue'
import BaseModal from '../components/ui/BaseModal.vue'
import BaseIcon from '../components/noor/BaseIcon.vue'
import NoorPagination from '../components/ui/Pagination.vue'
import type { HardlinkEntry, HardlinkGroup } from '../api/types'

type SortKey = 'code' | 'entryCount' | 'hardlinkCount' | 'sourceSize'
type SortDir = 'asc' | 'desc'
type FilterKey = 'all' | 'withSource' | 'withHardlink' | 'issueOnly' | 'multiSource' | 'multiHardlink' | 'onlySource' | 'onlyHardlink'

const mediaStore = useMediaLibraryStore()
const toast = useToast()
const router = useRouter()
const { confirm } = useConfirm()
const { t, i18nVersion } = useI18n()

const searchQuery = ref('')
const sortKey = ref<SortKey>('hardlinkCount')
const sortDir = ref<SortDir>('desc')
const filterKey = ref<FilterKey>('all')
const currentPage = ref(1)
const pageSize = 20
const deletingHardlinkPaths = ref<Set<string>>(new Set())
const deletingSourcePaths = ref<Set<string>>(new Set())
const deletingGroupCodes = ref<Set<string>>(new Set())
const reorganizingSourcePaths = ref<Set<string>>(new Set())
const previewVideoPath = ref('')
const mdcManualAvailable = ref(false)

const pageTitle = computed(() => { void i18nVersion.value; return t('hardlinks.title') })
const scanBtnLabel = computed(() => { void i18nVersion.value; return t('hardlinks.scan') })
const noGroupsLabel = computed(() => { void i18nVersion.value; return t('hardlinks.empty') })
const emptyDescLabel = computed(() => { void i18nVersion.value; return t('hardlinks.emptyDesc') })
const totalLabel = computed(() => { void i18nVersion.value; return t('hardlinks.total') })
const codeLabel = computed(() => { void i18nVersion.value; return t('hardlinks.code') })
const entryCountLabel = computed(() => { void i18nVersion.value; return t('hardlinks.entryCount') })
const hardlinkCountLabel = computed(() => { void i18nVersion.value; return t('hardlinks.hardlinkCount') })
const sourceSizeLabel = computed(() => { void i18nVersion.value; return t('hardlinks.sourceSize') })
const issueCountLabel = computed(() => { void i18nVersion.value; return t('hardlinks.issueCount') })
const searchPlaceholder = computed(() => { void i18nVersion.value; return t('hardlinks.searchPlaceholder') })
const lastScannedLabel = computed(() => { void i18nVersion.value; return t('hardlinks.lastScanned') })
const emptyFilteredLabel = computed(() => { void i18nVersion.value; return t('hardlinks.emptyFiltered') })
const deleteHardlinkLabel = computed(() => { void i18nVersion.value; return t('hardlinks.deleteHardlink') })
const deleteSourceChainLabel = computed(() => { void i18nVersion.value; return t('hardlinks.deleteSourceChain') })
const previewDeleteLabel = computed(() => { void i18nVersion.value; return t('hardlinks.previewDelete') })
const deleteGroupLabel = computed(() => { void i18nVersion.value; return t('hardlinks.deleteGroup') })
const processingLabel = computed(() => { void i18nVersion.value; return t('hardlinks.processing') })
const orphanSkippedLabel = computed(() => { void i18nVersion.value; return t('hardlinks.orphanSkipped') })
const reorganizeLabel = computed(() => { void i18nVersion.value; return t('hardlinks.reorganize') })
const previewPathLabel = computed(() => { void i18nVersion.value; return t('hardlinks.previewPath') })
const previewUnsupportedLabel = computed(() => { void i18nVersion.value; return t('hardlinks.previewUnsupported') })
const previewDeleteNote = computed(() => { void i18nVersion.value; return t('hardlinks.previewDeleteNote') })
const abnormalLabel = computed(() => { void i18nVersion.value; return t('hardlinks.status.issue') })
const orphanLabel = computed(() => { void i18nVersion.value; return t('hardlinks.status.orphan') })
const unparsedLabel = computed(() => { void i18nVersion.value; return t('hardlinks.status.unparsed') })
const goSettingsLabel = computed(() => { void i18nVersion.value; return t('library.goToSettings') })
const previewVideoName = computed(() => previewVideoPath.value.split('/').pop() || previewVideoPath.value)
const previewVideoUrl = computed(() => {
  if (!previewVideoPath.value) return ''
  return `/api/media-library/hardlinks/preview-file?path=${encodeURIComponent(previewVideoPath.value)}`
})

const filterTabs = computed(() => {
  void i18nVersion.value
  return [
    { key: 'all' as FilterKey, label: t('hardlinks.filter.all') },
    { key: 'multiSource' as FilterKey, label: t('hardlinks.filter.multiSource') },
    { key: 'multiHardlink' as FilterKey, label: t('hardlinks.filter.multiHardlink') },
    { key: 'onlySource' as FilterKey, label: t('hardlinks.filter.onlySource') },
    { key: 'onlyHardlink' as FilterKey, label: t('hardlinks.filter.onlyHardlink') },
  ]
})

const hasGroups = computed(() => mediaStore.hardlinkGroups.length > 0)

const summary = computed(() => {
  const backendSummary = mediaStore.hardlinkSummary
  const groups = mediaStore.hardlinkGroups
  const fallback = {
    total_groups: groups.length,
    total_entries: groups.reduce((sum, group) => sum + (group.entry_count || group.entries.length), 0),
    total_hardlinks: groups.reduce((sum, group) => sum + (group.hardlink_count || group.entries.reduce((s, entry) => s + (entry.hardlink_count || entry.hardlink_paths.length), 0)), 0),
    issue_groups: groups.filter((group) => group.status === 'issue' || (group.issue_count || 0) > 0).length,
    orphan_entries: groups.reduce((sum, group) => sum + (group.orphan_count || 0), 0),
  }

  if (!backendSummary || backendSummary.total_groups === 0 && groups.length > 0) {
    return fallback
  }

  return {
    total_groups: backendSummary.total_groups ?? fallback.total_groups,
    total_entries: backendSummary.total_entries ?? fallback.total_entries,
    total_hardlinks: backendSummary.total_hardlinks ?? fallback.total_hardlinks,
    issue_groups: backendSummary.issue_groups ?? fallback.issue_groups,
    orphan_entries: backendSummary.orphan_entries ?? fallback.orphan_entries,
  }
})

const lastScannedText = computed(() => {
  const value = mediaStore.hardlinkLastScannedAt
  if (!value) return t('common.notAvailable')
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return t('common.notAvailable')
  return date.toLocaleString()
})

const searchedGroups = computed<HardlinkGroup[]>(() => {
  const query = searchQuery.value.trim().toLowerCase()
  return mediaStore.hardlinkGroups.filter((group) => {
    const matchesSearch = !query || group.code.toLowerCase().includes(query) || group.entries.some((entry) => {
      const source = entry.source_path || ''
      return source.toLowerCase().includes(query) || entry.hardlink_paths.some((path) => path.toLowerCase().includes(query))
    })
    return matchesSearch
  })
})

const filterCounts = computed(() => {
  const groups = searchedGroups.value
  return {
    all: groups.length,
    withSource: groups.filter((group) => groupSourceCount(group) > 0).length,
    withHardlink: groups.filter((group) => groupHardlinkCount(group) > 0).length,
    issueOnly: groups.filter((group) => group.status === 'issue' || (group.issue_count || 0) > 0).length,
    multiSource: groups.filter((group) => (group.entry_count || group.entries.length) > 1).length,
    multiHardlink: groups.filter((group) => (group.hardlink_count || groupHardlinkCount(group)) > 1).length,
    onlySource: groups.filter((group) => groupHardlinkCount(group) === 0 && groupSourceCount(group) > 0).length,
    onlyHardlink: groups.filter((group) => {
      const entryCount = group.entry_count || group.entries.length
      return entryCount > 0 && (group.orphan_count || 0) >= entryCount
    }).length,
  }
})

const visibleGroups = computed<HardlinkGroup[]>(() => {
  const dir = sortDir.value === 'asc' ? 1 : -1

  const filtered = searchedGroups.value.filter((group) => {
    switch (filterKey.value) {
      case 'withSource':
        return groupSourceCount(group) > 0
      case 'withHardlink':
        return groupHardlinkCount(group) > 0
      case 'issueOnly':
        return group.status === 'issue' || (group.issue_count || 0) > 0
      case 'multiSource':
        return (group.entry_count || group.entries.length) > 1
      case 'multiHardlink':
        return (group.hardlink_count || groupHardlinkCount(group)) > 1
      case 'onlySource':
        return groupHardlinkCount(group) === 0 && groupSourceCount(group) > 0
      case 'onlyHardlink': {
        const entryCount = group.entry_count || group.entries.length
        return entryCount > 0 && (group.orphan_count || 0) >= entryCount
      }
      default:
        return true
    }
  })

  filtered.sort((a, b) => {
    if (sortKey.value === 'code') return dir * a.code.localeCompare(b.code, undefined, { numeric: true, sensitivity: 'base' })
    if (sortKey.value === 'entryCount') return dir * ((a.entry_count || 0) - (b.entry_count || 0))
    if (sortKey.value === 'sourceSize') return dir * (groupSourceSize(a) - groupSourceSize(b))
    return dir * ((a.hardlink_count || 0) - (b.hardlink_count || 0))
  })

  return filtered
})

const totalPages = computed(() => Math.max(1, Math.ceil(visibleGroups.value.length / pageSize)))


const pagedGroups = computed<HardlinkGroup[]>(() => {
  const start = (currentPage.value - 1) * pageSize
  return visibleGroups.value.slice(start, start + pageSize)
})

watch([searchQuery, sortKey, sortDir, filterKey], () => {
  currentPage.value = 1
})

watch(totalPages, (value) => {
  if (currentPage.value > value) currentPage.value = value
})

watch(pagedGroups, (groups) => {
  if (groups.length === 0 && currentPage.value > 1 && visibleGroups.value.length > 0) {
    currentPage.value = Math.min(currentPage.value - 1, totalPages.value)
  }
})

function setSort(key: SortKey) {
  if (sortKey.value === key) {
    sortDir.value = sortDir.value === 'asc' ? 'desc' : 'asc'
    return
  }
  sortKey.value = key
  sortDir.value = key === 'code' ? 'asc' : 'desc'
}

function sortArrow(key: SortKey) {
  if (sortKey.value !== key) return ''
  return sortDir.value === 'asc' ? '↑' : '↓'
}

function issueBadgeColor(group: HardlinkGroup) {
  if ((group.orphan_count || 0) > 0) return 'error'
  if (group.issues?.includes('unparsed_code')) return 'warning'
  return 'secondary'
}

function groupSourceCount(group: HardlinkGroup) {
  return group.entries.filter((entry) => !!entry.source_path).length
}

function groupHardlinkCount(group: HardlinkGroup) {
  return group.entries.reduce((sum, entry) => sum + entry.hardlink_paths.length, 0)
}

function groupSourceSize(group: HardlinkGroup) {
  return group.entries.reduce((max, entry) => Math.max(max, entry.source_size || 0), 0)
}

function formatBytes(value?: number | null) {
  if (value == null || Number.isNaN(value)) return ''
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let size = value
  let unitIndex = 0
  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024
    unitIndex += 1
  }
  const digits = size >= 100 || unitIndex === 0 ? 0 : size >= 10 ? 1 : 2
  return `${size.toFixed(digits)} ${units[unitIndex]}`
}

async function handleScan() {
  const result = await mediaStore.scanHardlinks()
  if (result.ok) {
    toast.success(t('hardlinks.scanSuccess', { count: result.count, entryCount: result.totalEntries }))
  } else {
    toast.error(result.error || t('hardlinks.scanFailed'))
  }
}

async function refreshGroupsAfterDelete(resultPayload?: DeleteResultPayload) {
  if (resultPayload && mediaStore.applyHardlinkDeleteResult(resultPayload)) {
    return
  }

  const result = await mediaStore.scanHardlinks()
  if (!result.ok) {
    toast.error(result.error || t('hardlinks.scanFailed'))
  }
}

function openVideoPreview(path: string) {
  if (!path) return
  previewVideoPath.value = path
}

function closeVideoPreview() {
  previewVideoPath.value = ''
}

function applySummaryFilter(key: FilterKey) {
  if (key !== 'all' && filterCounts.value[key] === 0) return
  filterKey.value = key
  searchQuery.value = ''
  currentPage.value = 1
}

function isFilterDisabled(key: FilterKey) {
  return key !== 'all' && filterCounts.value[key] === 0
}

function isDeletingHardlink(path: string) {
  return deletingHardlinkPaths.value.has(path)
}

function isDeletingSource(path: string | null) {
  return !!path && deletingSourcePaths.value.has(path)
}

function isDeletingGroup(code: string) {
  return deletingGroupCodes.value.has(code)
}

function withDeletingState(setRef: typeof deletingHardlinkPaths, key: string, active: boolean) {
  const next = new Set(setRef.value)
  if (active) next.add(key)
  else next.delete(key)
  setRef.value = next
}


function buildDeletePreviewDetails(plannedDirs: string[], plannedFiles: string[]) {
  return [
    { label: `${t('hardlinks.previewDirs')} · ${plannedDirs.length}`, items: plannedDirs },
    { label: `${t('hardlinks.previewFiles')} · ${plannedFiles.length}`, items: plannedFiles },
  ].filter((section) => section.items.length > 0)
}

function isReorganizingSource(path?: string | null) {
  return !!path && reorganizingSourcePaths.value.has(path)
}

async function loadMdcManualAvailability() {
  mdcManualAvailable.value = false
  try {
    const pluginsResp = await api.get('/plugins')
    const plugins = Array.isArray(pluginsResp.data)
      ? pluginsResp.data
      : (Array.isArray(pluginsResp.data?.items) ? pluginsResp.data.items : [])
    const plugin = plugins.find((item: any) => item?.id === 'mdc-ng-manual')
    if (!plugin?.enabled) return
    const testResp = await api.post('/plugins/mdc-ng-manual/test')
    mdcManualAvailable.value = !!testResp.data?.ok
  } catch {
    mdcManualAvailable.value = false
  }
}

async function reorganizeSource(entry: HardlinkEntry) {
  const path = entry.source_path
  if (!path || isReorganizingSource(path)) return
  reorganizingSourcePaths.value = new Set(reorganizingSourcePaths.value).add(path)
  try {
    const { data } = await api.post('/plugins/mdc-ng-manual/actions/create', {
      payload: { source_paths: path },
    })
    if (!data?.ok) throw new Error(data?.message || t('hardlinks.reorganizeFailed'))
    toast.success(data?.message || t('hardlinks.reorganizeSuccess'))
  } catch (error: any) {
    toast.error(error?.response?.data?.detail || error?.message || t('hardlinks.reorganizeFailed'))
  } finally {
    const next = new Set(reorganizingSourcePaths.value)
    next.delete(path)
    reorganizingSourcePaths.value = next
  }
}

type DeleteResultPayload = {
  deleted_dirs?: string[]
  deleted_files?: string[]
  missing_dirs?: string[]
  missing_files?: string[]
  deleted_paths?: string[]
}

function buildDeleteResultDetails(result: DeleteResultPayload) {
  const deletedDirs = result.deleted_dirs || []
  const deletedFiles = result.deleted_files || result.deleted_paths || []
  const missingDirs = result.missing_dirs || []
  const missingFiles = result.missing_files || []

  return [
    { label: `${t('hardlinks.resultDeletedDirs')} · ${deletedDirs.length}`, items: deletedDirs },
    { label: `${t('hardlinks.resultDeletedFiles')} · ${deletedFiles.length}`, items: deletedFiles },
    { label: `${t('hardlinks.resultSkippedDirs')} · ${missingDirs.length}`, items: missingDirs },
    { label: `${t('hardlinks.resultSkippedFiles')} · ${missingFiles.length}`, items: missingFiles },
  ].filter((section) => section.items.length > 0)
}

async function showDeleteResult(code: string, result: DeleteResultPayload) {
  const deletedDirs = result.deleted_dirs || []
  const deletedFiles = result.deleted_files || result.deleted_paths || []
  const missingDirs = result.missing_dirs || []
  const missingFiles = result.missing_files || []

  await confirm({
    title: t('hardlinks.resultTitle', { code }),
    message: t('hardlinks.resultSummary', {
      dirs: deletedDirs.length,
      files: deletedFiles.length,
      skipped: missingDirs.length + missingFiles.length,
    }),
    confirmText: t('common.close'),
    hideCancel: true,
    danger: false,
    size: 'xl',
    details: buildDeleteResultDetails(result),
  })
}

async function deleteHardlink(path: string) {
  if (!path || isDeletingHardlink(path)) return
  const preview = await api.post('/media-library/hardlinks/delete-hardlink', {
    file_path: path,
    remove_nfo: true,
    dry_run: true,
  })
  const plannedFiles: string[] = preview.data?.planned_files || []
  const ok = await confirm({
    title: t('hardlinks.previewTitle', { code: path.split('/').pop() || path }),
    message: t('hardlinks.previewSummary', { dirs: 0, files: plannedFiles.length }),
    confirmText: t('common.delete'),
    danger: true,
    size: 'lg',
    note: previewDeleteNote.value,
    details: buildDeletePreviewDetails([], plannedFiles),
  })
  if (!ok) return

  withDeletingState(deletingHardlinkPaths, path, true)
  try {
    const resp = await api.post('/media-library/hardlinks/delete-hardlink', {
      file_path: path,
      remove_nfo: true,
    })
    toast.success(t('hardlinks.deleteHardlinkSuccess'))
    await showDeleteResult(path.split('/').pop() || path, resp.data || {})
    await refreshGroupsAfterDelete(resp.data || {})
  } catch (error: any) {
    toast.error(error?.response?.data?.detail || error?.message || t('hardlinks.deleteHardlinkFailed'))
  } finally {
    withDeletingState(deletingHardlinkPaths, path, false)
  }
}

async function deleteSourceChain(entry: HardlinkEntry) {
  if (!entry.source_path || isDeletingSource(entry.source_path)) return
  const preview = await api.post('/media-library/hardlinks/delete-source-chain', {
    source_path: entry.source_path,
    hardlink_paths: entry.hardlink_paths,
    code: extractCodeFromEntry(entry),
    dry_run: true,
  })
  const plannedDirs: string[] = preview.data?.planned_dirs || []
  const plannedFiles: string[] = preview.data?.planned_files || []
  const ok = await confirm({
    title: t('hardlinks.previewTitle', { code: extractCodeFromEntry(entry) || (entry.source_path.split('/').pop() || '') }),
    message: t('hardlinks.previewSummary', { dirs: plannedDirs.length, files: plannedFiles.length }),
    confirmText: t('common.delete'),
    danger: true,
    size: 'xl',
    note: previewDeleteNote.value,
    details: buildDeletePreviewDetails(plannedDirs, plannedFiles),
  })
  if (!ok) return

  withDeletingState(deletingSourcePaths, entry.source_path, true)
  try {
    const resp = await api.post('/media-library/hardlinks/delete-source-chain', {
      source_path: entry.source_path,
      hardlink_paths: entry.hardlink_paths,
      code: extractCodeFromEntry(entry),
    })
    toast.success(t('hardlinks.deleteSourceChainSuccess'))
    await showDeleteResult(extractCodeFromEntry(entry) || (entry.source_path.split('/').pop() || ''), resp.data || {})
    await refreshGroupsAfterDelete(resp.data || {})
  } catch (error: any) {
    toast.error(error?.response?.data?.detail || error?.message || t('hardlinks.deleteSourceChainFailed'))
  } finally {
    withDeletingState(deletingSourcePaths, entry.source_path, false)
  }
}

function extractCodeFromEntry(entry: HardlinkEntry): string | null {
  if (!entry.source_path) return null
  const base = entry.source_path.split('/').pop() || ''
  const match = base.match(/[A-Za-z]{2,6}[-_ ]?\d{2,6}|\d{6}-\d{3}/)
  return match ? match[0].replace(/[_ ]/g, '-').toUpperCase() : null
}

async function deleteGroup(group: HardlinkGroup) {
  if (!group.code || isDeletingGroup(group.code)) return
  const preview = await api.post('/media-library/hardlinks/delete-group', {
    code: group.code,
    entries: group.entries.map((entry) => ({
      source_path: entry.source_path,
      hardlink_paths: entry.hardlink_paths,
    })),
    dry_run: true,
  })
  const plannedDirs: string[] = preview.data?.planned_dirs || []
  const plannedFiles: string[] = preview.data?.planned_files || []
  const ok = await confirm({
    title: t('hardlinks.previewTitle', { code: group.code }),
    message: t('hardlinks.previewSummary', { dirs: plannedDirs.length, files: plannedFiles.length }),
    confirmText: t('common.delete'),
    danger: true,
    size: 'xl',
    note: previewDeleteNote.value,
    details: buildDeletePreviewDetails(plannedDirs, plannedFiles),
  })
  if (!ok) return

  withDeletingState(deletingGroupCodes, group.code, true)
  try {
    const resp = await api.post('/media-library/hardlinks/delete-group', {
      code: group.code,
      entries: group.entries.map((entry) => ({
        source_path: entry.source_path,
        hardlink_paths: entry.hardlink_paths,
      })),
    })
    toast.success(t('hardlinks.deleteGroupSuccess'))
    await showDeleteResult(group.code, resp.data || {})
    await refreshGroupsAfterDelete(resp.data || {})
  } catch (error: any) {
    toast.error(error?.response?.data?.detail || error?.message || t('hardlinks.deleteGroupFailed'))
  } finally {
    withDeletingState(deletingGroupCodes, group.code, false)
  }
}

async function previewGroupDelete(group: HardlinkGroup) {
  try {
    const resp = await api.post('/media-library/hardlinks/delete-group', {
      code: group.code,
      entries: group.entries.map((entry) => ({
        source_path: entry.source_path,
        hardlink_paths: entry.hardlink_paths,
      })),
      dry_run: true,
    })

    const plannedDirs: string[] = resp.data?.planned_dirs || []
    const plannedFiles: string[] = resp.data?.planned_files || []
    await confirm({
      title: t('hardlinks.previewTitle', { code: group.code }),
      message: t('hardlinks.previewSummary', { dirs: plannedDirs.length, files: plannedFiles.length }),
      confirmText: t('common.close'),
      cancelText: t('common.cancel'),
      danger: false,
      size: 'xl',
      note: previewDeleteNote.value,
      details: buildDeletePreviewDetails(plannedDirs, plannedFiles),
    })
  } catch (error: any) {
    toast.error(error?.response?.data?.detail || error?.message || t('hardlinks.previewFailed'))
  }
}

function goPage(page: number) {
  currentPage.value = Math.min(Math.max(1, page), totalPages.value)
}

function openSettings() {
  router.push('/settings')
}

onMounted(async () => {
  await Promise.all([
    mediaStore.loadHardlinkGroups(),
    loadMdcManualAvailability(),
  ])
})
</script>

<template>
  <div class="hardlinks-page w-full space-y-6 animate-fade-in">
    <div class="page-header">
      <div class="page-header__left">
        <div>
          <h1 class="page-title">{{ pageTitle }}</h1>
          <div class="page-meta">
            <span>{{ lastScannedLabel }}: {{ lastScannedText }}</span>
          </div>
        </div>
      </div>
      <div class="page-header__right header-actions">
        <div v-if="hasGroups" class="hardlinks-search-wrap hardlinks-search--header">
          <BaseIcon name="search" class="hardlinks-search__icon" />
          <input
            v-model="searchQuery"
            type="search"
            :placeholder="searchPlaceholder"
            class="hardlinks-search"
          />
        </div>
        <VuiButton
          variant="gradient"
          color="info"
          size="small"
          :loading="mediaStore.hardlinkScanning"
          @click="handleScan"
        >
          <BaseIcon name="refresh" class="w-4 h-4" />
          {{ scanBtnLabel }}
        </VuiButton>
      </div>
    </div>

    <div class="summary-grid">
      <button
        type="button"
        class="summary-card summary-card--button ui-card"
        :class="{ 'summary-card--active': filterKey === 'all' }"
        @click="applySummaryFilter('all')"
      >
        <span class="summary-card__label">{{ totalLabel }}</span>
        <span class="summary-card__value">{{ summary.total_groups }}</span>
      </button>
      <button
        type="button"
        class="summary-card summary-card--button ui-card"
        :class="{ 'summary-card--active': filterKey === 'withSource', 'summary-card--disabled': filterCounts.withSource === 0 }"
        :disabled="filterCounts.withSource === 0"
        @click="applySummaryFilter('withSource')"
      >
        <span class="summary-card__label">{{ entryCountLabel }}</span>
        <span class="summary-card__value">{{ summary.total_entries }}</span>
      </button>
      <button
        type="button"
        class="summary-card summary-card--button ui-card"
        :class="{ 'summary-card--active': filterKey === 'withHardlink', 'summary-card--disabled': filterCounts.withHardlink === 0 }"
        :disabled="filterCounts.withHardlink === 0"
        @click="applySummaryFilter('withHardlink')"
      >
        <span class="summary-card__label">{{ hardlinkCountLabel }}</span>
        <span class="summary-card__value">{{ summary.total_hardlinks }}</span>
      </button>
      <button
        type="button"
        class="summary-card summary-card--button ui-card"
        :class="{ 'summary-card--warn': summary.issue_groups > 0, 'summary-card--active': filterKey === 'issueOnly', 'summary-card--disabled': filterCounts.issueOnly === 0 }"
        :disabled="filterCounts.issueOnly === 0"
        @click="applySummaryFilter('issueOnly')"
      >
        <span class="summary-card__label">{{ issueCountLabel }}</span>
        <span class="summary-card__value">{{ summary.issue_groups }}</span>
      </button>
    </div>

    <div v-if="hasGroups" class="toolbar-card">
        <div class="toolbar-main">
          <div class="toolbar-block toolbar-block--controls">
            <div class="sort-controls">
              <span class="sort-label">{{ t('hardlinks.sortBy') }}:</span>
              <button type="button" class="sort-btn" :class="{ 'sort-btn--active': sortKey === 'code' }" @click="setSort('code')">
                {{ codeLabel }} {{ sortArrow('code') }}
              </button>
              <button type="button" class="sort-btn" :class="{ 'sort-btn--active': sortKey === 'entryCount' }" @click="setSort('entryCount')">
                {{ entryCountLabel }} {{ sortArrow('entryCount') }}
              </button>
              <button type="button" class="sort-btn" :class="{ 'sort-btn--active': sortKey === 'hardlinkCount' }" @click="setSort('hardlinkCount')">
                {{ hardlinkCountLabel }} {{ sortArrow('hardlinkCount') }}
              </button>
              <button type="button" class="sort-btn" :class="{ 'sort-btn--active': sortKey === 'sourceSize' }" @click="setSort('sourceSize')">
                {{ sourceSizeLabel }} {{ sortArrow('sourceSize') }}
              </button>
            </div>
            <div class="filter-controls">
              <span class="sort-label">{{ t('hardlinks.filterBy') }}:</span>
              <button
                v-for="tab in filterTabs"
                :key="tab.key"
                type="button"
                class="filter-btn"
                :class="{ 'filter-btn--active': filterKey === tab.key, 'filter-btn--disabled': isFilterDisabled(tab.key) }"
                :disabled="isFilterDisabled(tab.key)"
                @click="applySummaryFilter(tab.key)"
              >
                {{ tab.label }} ({{ filterCounts[tab.key] }})
              </button>
            </div>
          </div>
        </div>
    </div>

    <div v-if="!hasGroups" class="empty-state">
        <BaseIcon name="hardlink" class="hardlink-empty-icon" />
        <p class="empty-state__title">{{ noGroupsLabel }}</p>
        <p class="empty-state__desc">{{ emptyDescLabel }}</p>
        <VuiButton variant="text" color="secondary" size="small" @click="openSettings">
          {{ goSettingsLabel }}
        </VuiButton>
    </div>

    <div v-else-if="visibleGroups.length === 0" class="empty-state">
        <BaseIcon name="search" class="hardlink-empty-icon" />
        <p class="empty-state__title">{{ emptyFilteredLabel }}</p>
    </div>

    <div v-else class="groups-list">
        <div
          v-for="group in pagedGroups"
          :key="group.code"
          class="hl-group ui-card"
          :class="{ 'hl-group--issue': group.status === 'issue' }"
        >
          <div class="hl-group__header">
            <div class="hl-group__summary">
              <span class="hl-group__code font-mono">{{ group.code }}</span>
              <span class="hl-group__meta">
                {{ groupSourceCount(group) }} src · {{ groupHardlinkCount(group) }} hl
              </span>
            </div>
            <div class="hl-group__header-right">
              <div class="hl-group__actions">
                <button
                  type="button"
                  class="group-action-btn"
                  :disabled="isDeletingGroup(group.code)"
                  @click.stop="previewGroupDelete(group)"
                >
                  {{ isDeletingGroup(group.code) ? processingLabel : previewDeleteLabel }}
                </button>
                <button
                  type="button"
                  class="group-action-btn group-action-btn--danger"
                  :class="{ 'group-action-btn--loading': isDeletingGroup(group.code) }"
                  :disabled="isDeletingGroup(group.code)"
                  @click.stop="deleteGroup(group)"
                >
                  {{ isDeletingGroup(group.code) ? processingLabel : deleteGroupLabel }}
                </button>
              </div>
              <div class="hl-group__badges">
              <VuiBadge v-if="group.status === 'issue'" variant="gradient" color="warning" size="xs">
                {{ abnormalLabel }}
              </VuiBadge>
              <VuiBadge v-if="(group.orphan_count || 0) > 0" variant="gradient" :color="issueBadgeColor(group)" size="xs">
                {{ orphanLabel }} × {{ group.orphan_count }}
              </VuiBadge>
              <VuiBadge v-if="group.issues?.includes('unparsed_code')" variant="gradient" :color="issueBadgeColor(group)" size="xs">
                {{ unparsedLabel }}
              </VuiBadge>
              <VuiBadge
                v-if="(group.orphan_count || 0) >= (group.entry_count || group.entries.length)"
                variant="gradient"
                color="secondary"
                size="xs"
              >
                {{ orphanSkippedLabel }}
              </VuiBadge>
              </div>
            </div>
          </div>

          <div class="hl-group__entries">
            <div
              v-for="(entry, index) in group.entries"
              :key="`${group.code}-${entry.source_path || 'orphan'}-${index}`"
              class="hl-entry-row"
              :class="{ 'hl-entry--issue': entry.status === 'issue' }"
            >
              <div class="hl-col hl-col--source">
                <div class="hl-col__label">{{ t('hardlinks.mainFile') }}</div>
                <div class="hl-row hl-row--source" :class="{ 'hl-row--missing': entry.issues?.includes('orphan_source') }">
                  <span
                    v-if="entry.source_path"
                    class="hl-row__path"
                    :title="previewPathLabel"
                    @click="openVideoPreview(entry.source_path)"
                  >{{ entry.source_path }}</span>
                  <span v-if="entry.source_size != null" class="hl-row__size">{{ formatBytes(entry.source_size) }}</span>
                  <span v-else class="hl-row__empty">{{ t('hardlinks.missingSource') }}</span>
                  <button
                    v-if="entry.source_path && mdcManualAvailable"
                    type="button"
                    class="row-action-btn row-action-btn--secondary row-action-btn--hover-only"
                    :class="{ 'row-action-btn--loading': isReorganizingSource(entry.source_path) }"
                    :disabled="isReorganizingSource(entry.source_path)"
                    @click.stop="reorganizeSource(entry)"
                  >
                    {{ isReorganizingSource(entry.source_path) ? processingLabel : reorganizeLabel }}
                  </button>
                  <button
                    v-if="entry.source_path"
                    type="button"
                    class="row-action-btn row-action-btn--danger row-action-btn--hover-only"
                    :class="{ 'row-action-btn--loading': isDeletingSource(entry.source_path) }"
                    :disabled="isDeletingSource(entry.source_path)"
                    @click.stop="deleteSourceChain(entry)"
                  >
                    {{ isDeletingSource(entry.source_path) ? processingLabel : deleteSourceChainLabel }}
                  </button>
                </div>
              </div>
              <div class="hl-col hl-col--hardlinks">
                <div class="hl-col__label">{{ t('hardlinks.hardlinks') }}</div>
                <div
                  v-for="hl in entry.hardlink_paths"
                  :key="hl"
                  class="hl-row hl-row--hardlink"
                >
                  <span class="hl-row__hl-arrow">→</span>
                  <span
                    class="hl-row__path"
                    :title="previewPathLabel"
                    @click="openVideoPreview(hl)"
                  >{{ hl }}</span>
                  <button
                    type="button"
                    class="row-action-btn row-action-btn--danger row-action-btn--hover-only"
                    :class="{ 'row-action-btn--loading': isDeletingHardlink(hl) }"
                    :disabled="isDeletingHardlink(hl)"
                    @click.stop="deleteHardlink(hl)"
                  >
                    {{ isDeletingHardlink(hl) ? processingLabel : deleteHardlinkLabel }}
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
    </div>

    <NoorPagination
      v-if="visibleGroups.length > pageSize"
      :page="currentPage"
      :total-pages="totalPages"
      @page="goPage"
    />

    <div v-if="mediaStore.hardlinkScanning" class="scan-overlay">
      <div class="scan-overlay__card">
        <div class="scan-overlay__spinner"></div>
        <span>{{ scanBtnLabel }}</span>
      </div>
    </div>

    <BaseModal
      v-if="previewVideoPath"
      :title="previewVideoName"
      size="lg"
      @close="closeVideoPreview"
    >
      <div class="preview-modal">
        <div class="preview-modal__meta font-mono text-xs">{{ previewVideoPath }}</div>
        <video
          :key="previewVideoUrl"
          class="preview-modal__player"
          :src="previewVideoUrl"
          controls
          autoplay
          preload="metadata"
        />
        <p class="preview-modal__hint">{{ previewUnsupportedLabel }}</p>
      </div>
    </BaseModal>
  </div>
</template>

<style scoped>
.hardlinks-page {
  font-family: var(--font-body);
  font-size: var(--font-size-sm);
  line-height: 1.5;
}

.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
}

.page-header__left {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  min-width: 0;
}

.page-header__right {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  min-width: 0;
}

.header-actions {
  flex: 0 1 min(34rem, 100%);
  min-width: 0;
}

.header-actions {
  flex: 0 1 min(34rem, 100%);
  flex-wrap: nowrap;
  justify-content: flex-end;
}

.hardlinks-search--header {
  flex: 1 1 auto;
  width: auto;
  min-width: 0;
}

.hardlinks-search-wrap {
  position: relative;
  min-width: 0;
}

.hardlinks-search__icon {
  pointer-events: none;
  position: absolute;
  left: 0.75rem;
  top: 50%;
  width: 1rem;
  height: 1rem;
  transform: translateY(-50%);
  color: rgba(255, 255, 255, 0.25);
}

.page-title {
  font-family: var(--font-display);
  font-size: 1.25rem;
  font-weight: 700;
  color: var(--color-text-primary);
}

.page-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
  margin-top: 0.25rem;
  color: var(--color-text-muted);
  font-size: 0.75rem;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 0.75rem;
}

.summary-card {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  padding: 0.9rem 1rem;
  box-shadow: var(--shadow-md);
}

.summary-card--button {
  appearance: none;
  border: 1px solid var(--color-border-subtle);
  text-align: left;
  cursor: pointer;
  transition: transform var(--transition-fast), border-color var(--transition-fast), background var(--transition-fast);
}

.summary-card--button:hover {
  background: var(--color-bg-elevated);
  border-color: var(--color-border-default);
  transform: translateY(-1px);
}

.summary-card--warn {
  border-color: rgba(255, 181, 71, 0.24);
}

.summary-card--active {
  border-color: rgba(0, 117, 255, 0.32);
  background: var(--color-bg-elevated);
}

.summary-card--disabled {
  cursor: default;
  opacity: 0.5;
}

.summary-card__label {
  color: var(--color-text-muted);
  font-size: 0.75rem;
}

.summary-card__value {
  color: var(--color-text-primary);
  font-family: var(--font-display);
  font-size: 1.5rem;
  font-weight: 700;
}

.toolbar-card {
  display: block;
  padding: 0;
  border-bottom: 1px solid rgba(255, 255, 255, 0.03);
}

.toolbar-main {
  display: flex;
  gap: 0.5rem;
  align-items: flex-start;
  justify-content: flex-start;
  flex-wrap: wrap;
  padding: 0.45rem 0;
}

.toolbar-block {
  min-width: 0;
}

.toolbar-block--controls {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-start;
  gap: 0.5rem 1rem;
}

.hardlinks-search {
  display: block;
  width: 100%;
  min-width: 0;
  background: rgba(255,255,255,0.04);
  border: 1px solid var(--color-border-default);
  border-radius: var(--radius-lg);
  padding: 0.56rem 0.8rem 0.56rem 2.2rem;
  font-family: var(--font-display);
  font-size: 0.875rem;
  color: var(--color-text-primary);
}

.hardlinks-search:focus {
  outline: none;
  border-color: rgba(0,117,255,0.42);
  background: rgba(255,255,255,0.055);
}

.sort-controls,
.filter-controls {
  display: flex;
  flex-wrap: wrap;
  gap: 0.25rem 0.5rem;
  align-items: center;
}

.filter-controls {
  justify-content: flex-start;
}

.sort-label {
  color: rgba(113, 128, 150, 0.72);

  letter-spacing: 0.01em;
  white-space: nowrap;
}

.sort-btn,
.filter-btn {
  border: none;
  border-radius: 0;
  font-family: var(--font-display);
  font-size: 0.75rem;
  font-weight: 600;
  line-height: 1.2;
  padding: 0.125rem 0;
  transition: color var(--transition-fast), opacity var(--transition-fast);
  background: transparent;
  color: var(--color-text-secondary);
  opacity: 0.72;
}

.sort-btn:hover,
.filter-btn:hover {
  color: var(--color-text-primary);
  opacity: 1;
}

.sort-btn:disabled,
.filter-btn--disabled {
  opacity: 0.38;
  cursor: default;
}

.sort-btn--active,
.filter-btn--active {
  color: var(--color-text-primary);
  opacity: 1;
  text-decoration: underline;
  text-decoration-color: rgba(0, 117, 255, 0.65);
  text-underline-offset: 0.28rem;
  text-decoration-thickness: 2px;
}

.pagination-bar {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.pagination-bar--bottom {
  padding-top: 0.5rem;
  flex-direction: column;
}

.pagination-bar__meta {
  color: var(--color-text-muted);
  font-size: 0.75rem;
}

.pagination-bar__actions {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
}


.empty-state {
  min-height: 18rem;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.75rem;
  padding: 3rem 1.5rem;
  text-align: center;
}

.hardlink-empty-icon {
  width: 4rem;
  height: 4rem;
  margin-bottom: 0.25rem;
  color: rgba(255, 255, 255, 0.1);
  flex: 0 0 auto;
}

.empty-state__title {
  color: var(--color-text-secondary);
}

.empty-state__desc {
  max-width: 32rem;
  color: var(--color-text-muted);
  font-size: 0.75rem;
}

.scan-overlay {
  position: fixed;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(8, 12, 20, 0.44);
  backdrop-filter: blur(4px);
  z-index: 40;
}

.scan-overlay__card {
  display: inline-flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.9rem 1.1rem;
  border-radius: var(--radius-lg);
  border: 1px solid var(--color-border-default);
  background: rgba(10, 16, 26, 0.94);
  color: var(--color-text-primary);
  box-shadow: var(--shadow-lg);
}

.scan-overlay__spinner {
  width: 1rem;
  height: 1rem;
  border: 2px solid rgba(255, 255, 255, 0.22);
  border-top-color: var(--color-brand);
  border-radius: 999px;
  animation: spin 0.9s linear infinite;
}

.groups-list {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.hl-group {
  border: 1px solid var(--color-border-subtle);
  border-radius: var(--radius-lg);
  background: var(--color-bg-surface);
  overflow: hidden;
  padding: 0.85rem;
}

.hl-group--issue {
  border-color: rgba(255, 181, 71, 0.2);
}

.hl-group__header {
  width: 100%;
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  text-align: left;
  gap: 0.55rem;
  padding: 0 0 0.65rem;
  background: transparent;
  border-bottom: 1px solid rgba(255, 255, 255, 0.03);
}


.hl-group__summary,
.hl-group__badges {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  min-width: 0;
  flex-wrap: wrap;
}

.hl-group__summary {
  flex: 1 1 18rem;
}

.hl-group__header-right {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 0.4rem;
  min-width: 0;
}

.hl-group__badges {
  justify-content: flex-end;
}

.hl-group__actions {
  display: inline-flex;
  gap: 0.55rem;
  opacity: 0;
  pointer-events: none;
  transform: translateX(4px);
  transition: all var(--transition-fast);
}

.hl-group:hover .hl-group__actions,
.hl-group:focus-within .hl-group__actions {
  opacity: 1;
  pointer-events: auto;
  transform: translateX(0);
}

.hl-group__chevron {
  color: var(--color-text-muted);
}

.hl-group__code {
  color: var(--color-text-primary);
  font-size: 0.9rem;
  font-weight: 700;
}

.hl-group__meta {
  color: var(--color-text-secondary);
  font-size: 0.8125rem;
  line-height: 1.5;
}

.hl-group__entries {
  padding: 0.7rem 0 0;
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
}

.hl-entry-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: 0.55rem;
  padding: 0.55rem 0.6rem;
  border-radius: var(--radius-md);
  background: rgba(255, 255, 255, 0.015);
}

.hl-entry--issue {
  background: rgba(227, 26, 26, 0.04);
  box-shadow: inset 0 0 0 1px rgba(227, 26, 26, 0.12);
}

.hl-entry__count,
.hl-col__label {
  color: var(--color-text-muted);
  font-size: 0.8125rem;
  line-height: 1.5;
}

.hl-entry__cols {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: 0.75rem;
}

.hl-col {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.hl-row {
  display: flex;
  gap: 0.4rem;
  align-items: flex-start;
  padding: 0.3rem 0.35rem;
  border-radius: var(--radius-sm);
  transition: background var(--transition-fast);
  min-width: 0;
}

.hl-row:hover {
  background: rgba(255, 255, 255, 0.02);
}

.hl-row__path {
  cursor: pointer;
}

.hl-row__path,
.hl-row__empty {
  font-family: var(--font-mono);
  font-size: 0.8125rem;
  line-height: 1.5;
}

.hl-row__size,
.hl-row__hl-arrow {
  font-size: 0.75rem;
  line-height: 1.5;
}

.hl-row__path:hover {
  color: rgba(255, 255, 255, 0.96);
  text-decoration: underline;
  text-decoration-color: rgba(0, 117, 255, 0.5);
}

.row-action-btn {
  flex-shrink: 0;
  border: 1px solid var(--color-border-default);
  border-radius: var(--radius-button);
  background: rgba(255, 255, 255, 0.03);
  color: var(--color-text-primary);
  font-size: 0.75rem;
  font-weight: 600;
  padding: 0.15rem 0.38rem;
  transition: all var(--transition-fast);
}

.row-action-btn:hover:not(:disabled) {
  background: rgba(255, 255, 255, 0.08);
  color: var(--color-text-primary);
}

.row-action-btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.row-action-btn--danger {
  border-color: rgba(227, 26, 26, 0.3);
  background: rgba(227, 26, 26, 0.12);
}

.row-action-btn--danger:hover:not(:disabled) {
  background: rgba(227, 26, 26, 0.22);
}

.group-action-btn {
  flex-shrink: 0;
  border: none;
  border-radius: 0;
  background: transparent;
  color: var(--color-text-secondary);
  font-size: 0.75rem;
  font-weight: 600;
  line-height: 1;
  padding: 0;
  opacity: 0.78;
  transition: color var(--transition-fast), opacity var(--transition-fast);
}

.group-action-btn:hover:not(:disabled) {
  color: var(--color-text-primary);
  opacity: 1;
}

.group-action-btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.row-action-btn--loading,
.group-action-btn--loading {
  position: relative;
}

.row-action-btn--loading::before,
.group-action-btn--loading::before {
  content: '';
  display: inline-block;
  width: 0.5rem;
  height: 0.5rem;
  margin-right: 0.3rem;
  border-radius: 999px;
  border: 1px solid currentColor;
  border-right-color: transparent;
  vertical-align: -0.05rem;
  animation: spin 0.8s linear infinite;
}

.group-action-btn--danger {
  color: rgba(227, 26, 26, 0.92);
}

.group-action-btn--danger:hover:not(:disabled) {
  color: rgba(227, 26, 26, 1);
}

.row-action-btn--hover-only {
  opacity: 0;
  pointer-events: none;
  transform: translateX(4px);
}

.hl-row:hover .row-action-btn--hover-only,
.hl-row:focus-within .row-action-btn--hover-only {
  opacity: 1;
  pointer-events: auto;
  transform: translateX(0);
}

.preview-modal {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.preview-modal__meta {
  color: var(--color-text-muted);
  word-break: break-all;
}

.preview-modal__player {
  width: 100%;
  max-height: 70vh;
  border-radius: var(--radius-md);
  background: #000;
}

.preview-modal__hint {
  margin: 0;
  color: var(--color-text-muted);
  font-size: 0.75rem;
}

@media (max-width: 1024px) {
  .summary-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .toolbar-main,
  .toolbar-block--controls {
    flex-direction: column;
    align-items: stretch;
  }

  .filter-controls {
    justify-content: flex-start;
  }

  .toolbar-summary {
    flex-direction: column;
    gap: 0.35rem;
  }

  .pagination-bar {
    align-items: flex-start;
    flex-direction: column;
  }

  .hl-entry__cols {
    grid-template-columns: 1fr;
  }

  .hl-entry-row {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 640px) {
  .page-header {
    flex-direction: column;
    align-items: stretch;
  }

  .page-header__right {
    justify-content: flex-start;
  }

  .sort-controls {
    align-items: flex-start;
  }

  .hl-group__header {
    flex-direction: column;
  }

  .hl-group__header-right,
  .hl-group__badges {
    justify-content: flex-start;
  }

  .hl-group__actions {
    opacity: 1;
    pointer-events: auto;
    transform: none;
  }

  .summary-grid {
    grid-template-columns: 1fr;
  }
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
