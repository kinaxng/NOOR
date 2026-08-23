<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api/client'
import { useHardlinksStore } from '../stores/hardlinks'
import { useToast } from '../composables/useToast'
import { useConfirm } from '../composables/useConfirm'
import { useI18n } from '../composables/useI18n'
import type { HardlinkEntry, HardlinkGroup } from '../api/types'

const { t } = useI18n()
const store = useHardlinksStore()
const toast = useToast()
const router = useRouter()
const { confirm } = useConfirm()

type SortKey = 'code' | 'entryCount' | 'hardlinkCount' | 'sourceSize'
type SortDir = 'asc' | 'desc'
type FilterKey = 'all' | 'multiSource' | 'multiHardlink' | 'onlySource' | 'onlyHardlink'

const sortKey = ref<SortKey>('hardlinkCount')
const sortDir = ref<SortDir>('desc')
const filterKey = ref<FilterKey>('all')
const previewVideoPath = ref('')
const deletingHardlinks = ref<Set<string>>(new Set())
const deletingSources = ref<Set<string>>(new Set())
const deletingGroups = ref<Set<string>>(new Set())

const previewVideoName = computed(() => previewVideoPath.value.split('/').pop() || previewVideoPath.value)
const previewVideoUrl = computed(() => {
  if (!previewVideoPath.value) return ''
  return `/api/media-library/hardlinks/preview-file?path=${encodeURIComponent(previewVideoPath.value)}`
})

const lastScannedText = computed(() => {
  const v = store.lastScannedAt
  if (!v) return t('common.notAvailable')
  const d = new Date(v)
  return Number.isNaN(d.getTime()) ? t('common.notAvailable') : d.toLocaleString()
})

const sortTabs = computed(() => [
  { key: 'code' as SortKey, label: t('hardlinks.code') },
  { key: 'entryCount' as SortKey, label: t('hardlinks.entryCount') },
  { key: 'hardlinkCount' as SortKey, label: t('hardlinks.hardlinkCount') },
  { key: 'sourceSize' as SortKey, label: t('hardlinks.sourceSize') },
])

const filterTabs = computed(() => [
  { key: 'all' as FilterKey, label: t('hardlinks.filter.all') },
  { key: 'multiSource' as FilterKey, label: t('hardlinks.filter.multiSource') },
  { key: 'multiHardlink' as FilterKey, label: t('hardlinks.filter.multiHardlink') },
  { key: 'onlySource' as FilterKey, label: t('hardlinks.filter.onlySource') },
  { key: 'onlyHardlink' as FilterKey, label: t('hardlinks.filter.onlyHardlink') },
])

function groupSourceCount(g: HardlinkGroup) { return g.entries.filter(e => !!e.source_path).length }
function groupHardlinkCount(g: HardlinkGroup) { return g.entries.reduce((s, e) => s + e.hardlink_paths.length, 0) }
function groupSourceSize(g: HardlinkGroup) { return g.entries.reduce((max, e) => Math.max(max, e.source_size || 0), 0) }

const summary = computed(() => {
  const gs = store.groups
  return {
    total_groups: gs.length,
    total_entries: gs.reduce((s, g) => s + (g.entry_count || g.entries.length), 0),
    total_hardlinks: gs.reduce((s, g) => s + (g.hardlink_count || groupHardlinkCount(g)), 0),
    issue_groups: gs.filter(g => g.status === 'issue' || Number(g.issue_count || 0) > 0).length,
  }
})

const searchedGroups = computed(() => {
  const q = store.query.trim().toLowerCase()
  if (!q) return store.groups
  return store.groups.filter(g => {
    if (g.code.toLowerCase().includes(q)) return true
    return g.entries.some(e => {
      if (e.source_path?.toLowerCase().includes(q)) return true
      return e.hardlink_paths.some(p => p.toLowerCase().includes(q))
    })
  })
})

const filterCounts = computed(() => {
  const gs = searchedGroups.value
  return {
    all: gs.length,
    multiSource: gs.filter(g => (g.entry_count || g.entries.length) > 1).length,
    multiHardlink: gs.filter(g => (g.hardlink_count || groupHardlinkCount(g)) > 1).length,
    onlySource: gs.filter(g => groupHardlinkCount(g) === 0 && groupSourceCount(g) > 0).length,
    onlyHardlink: gs.filter(g => {
      const ec = g.entry_count || g.entries.length
      return ec > 0 && (g.orphan_count || 0) >= ec
    }).length,
  }
})

const visibleGroups = computed(() => {
  const dir = sortDir.value === 'asc' ? 1 : -1
  const filtered = searchedGroups.value.filter(g => {
    switch (filterKey.value) {
      case 'multiSource': return (g.entry_count || g.entries.length) > 1
      case 'multiHardlink': return (g.hardlink_count || groupHardlinkCount(g)) > 1
      case 'onlySource': return groupHardlinkCount(g) === 0 && groupSourceCount(g) > 0
      case 'onlyHardlink': {
        const ec = g.entry_count || g.entries.length
        return ec > 0 && (g.orphan_count || 0) >= ec
      }
      default: return true
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

const pagedGroups = computed(() => {
  const start = (store.page - 1) * store.pageSize
  return visibleGroups.value.slice(start, start + store.pageSize)
})

const totalPages = computed(() => Math.max(1, Math.ceil(visibleGroups.value.length / store.pageSize)))

watch([() => store.query, sortKey, sortDir, filterKey], () => { store.page = 1 })

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

function applyFilter(key: FilterKey) {
  if (key !== 'all' && filterCounts.value[key] === 0) return
  filterKey.value = key
  store.query = ''
}

function isFilterDisabled(key: FilterKey) { return key !== 'all' && filterCounts.value[key] === 0 }

function formatBytes(value?: number | null) {
  if (value == null || Number.isNaN(value)) return ''
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let size = value; let ui = 0
  while (size >= 1024 && ui < units.length - 1) { size /= 1024; ui++ }
  const digits = size >= 100 || ui === 0 ? 0 : size >= 10 ? 1 : 2
  return `${size.toFixed(digits)} ${units[ui]}`
}

function openVideoPreview(path: string) { if (path) previewVideoPath.value = path }

function buildDeleteDetails(dirs: string[], files: string[]) {
  return [
    { label: `${t('hardlinks.previewDirs')} · ${dirs.length}`, items: dirs },
    { label: `${t('hardlinks.previewFiles')} · ${files.length}`, items: files },
  ].filter(s => s.items.length > 0)
}

function buildResultDetails(result: { deleted_dirs?: string[]; deleted_files?: string[]; deleted_paths?: string[]; missing_dirs?: string[]; missing_files?: string[] }) {
  const dd = result.deleted_dirs || []
  const df = result.deleted_files || result.deleted_paths || []
  const md = result.missing_dirs || []
  const mf = result.missing_files || []
  return [
    { label: `${t('hardlinks.resultDeletedDirs')} · ${dd.length}`, items: dd },
    { label: `${t('hardlinks.resultDeletedFiles')} · ${df.length}`, items: df },
    { label: `${t('hardlinks.resultSkippedDirs')} · ${md.length}`, items: md },
    { label: `${t('hardlinks.resultSkippedFiles')} · ${mf.length}`, items: mf },
  ].filter(s => s.items.length > 0)
}

async function showDeleteResult(code: string, result: any) {
  const dd = result.deleted_dirs || []
  const df = result.deleted_files || result.deleted_paths || []
  const md = result.missing_dirs || []
  const mf = result.missing_files || []
  await confirm({
    title: t('hardlinks.resultTitle', { code }),
    message: t('hardlinks.resultSummary', { dirs: dd.length, files: df.length, skipped: md.length + mf.length }),
    confirmText: t('common.close'),
    hideCancel: true,
    size: 'xl',
    details: buildResultDetails(result),
  })
}

async function handleScan() {
  const result = await store.scan()
  if (result.ok) {
    toast.success(t('hardlinks.scanSuccess', { count: String(result.count || 0), entryCount: String(result.total_entries || 0) }))
  } else {
    toast.error(result.error || t('hardlinks.scanFailed'))
  }
}

async function deleteHardlink(path: string) {
  if (!path || deletingHardlinks.value.has(path)) return
  const preview = await api.post<{ planned_files?: string[] }>('/media-library/hardlinks/delete-hardlink', { file_path: path, remove_nfo: true, dry_run: true })
  const files: string[] = preview.planned_files || []
  const ok = await confirm({
    title: t('hardlinks.previewTitle', { code: path.split('/').pop() || path }),
    message: t('hardlinks.previewSummary', { dirs: '0', files: String(files.length) }),
    confirmText: t('common.delete'),
    danger: true,
    size: 'lg',
    note: t('hardlinks.previewDeleteNote'),
    details: buildDeleteDetails([], files),
  })
  if (!ok) return

  const next = new Set(deletingHardlinks.value); next.add(path); deletingHardlinks.value = next
  try {
    const resp = await api.post('/media-library/hardlinks/delete-hardlink', { file_path: path, remove_nfo: true })
    toast.success(t('hardlinks.deleteHardlinkSuccess'))
    await showDeleteResult(path.split('/').pop() || path, resp)
    await store.fetchGroups()
  } catch (e: any) {
    toast.error(e?.response?.data?.detail || e?.message || t('hardlinks.deleteHardlinkFailed'))
  } finally {
    const n = new Set(deletingHardlinks.value); n.delete(path); deletingHardlinks.value = n
  }
}

function extractCode(entry: HardlinkEntry): string | null {
  if (!entry.source_path) return null
  const base = entry.source_path.split('/').pop() || ''
  const m = base.match(/[A-Za-z]{2,6}[-_ ]?\d{2,6}|\d{6}-\d{3}/)
  return m ? m[0].replace(/[_ ]/g, '-').toUpperCase() : null
}

async function deleteSourceChain(entry: HardlinkEntry, group: HardlinkGroup) {
  if (!entry.source_path || deletingSources.value.has(entry.source_path)) return
  const code = extractCode(entry) || group.code
  const preview = await api.post<{ planned_dirs?: string[]; planned_files?: string[] }>('/media-library/hardlinks/delete-source-chain', {
    source_path: entry.source_path, hardlink_paths: entry.hardlink_paths, code, dry_run: true,
  })
  const dirs: string[] = preview.planned_dirs || []
  const files: string[] = preview.planned_files || []
  const ok = await confirm({
    title: t('hardlinks.previewTitle', { code: code || (entry.source_path.split('/').pop() || '') }),
    message: t('hardlinks.previewSummary', { dirs: String(dirs.length), files: String(files.length) }),
    confirmText: t('common.delete'),
    danger: true,
    size: 'xl',
    note: t('hardlinks.previewDeleteNote'),
    details: buildDeleteDetails(dirs, files),
  })
  if (!ok) return

  const next = new Set(deletingSources.value); next.add(entry.source_path); deletingSources.value = next
  try {
    const resp = await api.post('/media-library/hardlinks/delete-source-chain', {
      source_path: entry.source_path, hardlink_paths: entry.hardlink_paths, code,
    })
    toast.success(t('hardlinks.deleteSourceChainSuccess'))
    await showDeleteResult(code || (entry.source_path.split('/').pop() || ''), resp)
    await store.fetchGroups()
  } catch (e: any) {
    toast.error(e?.response?.data?.detail || e?.message || t('hardlinks.deleteSourceChainFailed'))
  } finally {
    const n = new Set(deletingSources.value); n.delete(entry.source_path); deletingSources.value = n
  }
}

async function deleteGroup(group: HardlinkGroup) {
  if (!group.code || deletingGroups.value.has(group.code)) return
  const preview = await api.post<{ planned_dirs?: string[]; planned_files?: string[] }>('/media-library/hardlinks/delete-group', {
    code: group.code,
    entries: group.entries.map(e => ({ source_path: e.source_path, hardlink_paths: e.hardlink_paths })),
    dry_run: true,
  })
  const dirs: string[] = preview.planned_dirs || []
  const files: string[] = preview.planned_files || []
  const ok = await confirm({
    title: t('hardlinks.previewTitle', { code: group.code }),
    message: t('hardlinks.previewSummary', { dirs: String(dirs.length), files: String(files.length) }),
    confirmText: t('common.delete'),
    danger: true,
    size: 'xl',
    note: t('hardlinks.previewDeleteNote'),
    details: buildDeleteDetails(dirs, files),
  })
  if (!ok) return

  const next = new Set(deletingGroups.value); next.add(group.code); deletingGroups.value = next
  try {
    const resp = await api.post('/media-library/hardlinks/delete-group', {
      code: group.code,
      entries: group.entries.map(e => ({ source_path: e.source_path, hardlink_paths: e.hardlink_paths })),
    })
    toast.success(t('hardlinks.deleteGroupSuccess'))
    await showDeleteResult(group.code, resp)
    await store.fetchGroups()
  } catch (e: any) {
    toast.error(e?.response?.data?.detail || e?.message || t('hardlinks.deleteGroupFailed'))
  } finally {
    const n = new Set(deletingGroups.value); n.delete(group.code); deletingGroups.value = n
  }
}

async function previewGroupDelete(group: HardlinkGroup) {
  try {
    const resp = await api.post<{ planned_dirs?: string[]; planned_files?: string[] }>('/media-library/hardlinks/delete-group', {
      code: group.code,
      entries: group.entries.map(e => ({ source_path: e.source_path, hardlink_paths: e.hardlink_paths })),
      dry_run: true,
    })
    const dirs: string[] = resp.planned_dirs || []
    const files: string[] = resp.planned_files || []
    await confirm({
      title: t('hardlinks.previewTitle', { code: group.code }),
      message: t('hardlinks.previewSummary', { dirs: String(dirs.length), files: String(files.length) }),
      confirmText: t('common.close'),
      danger: false,
      size: 'xl',
      note: t('hardlinks.previewDeleteNote'),
      details: buildDeleteDetails(dirs, files),
    })
  } catch (e: any) {
    toast.error(e?.response?.data?.detail || e?.message || t('hardlinks.previewFailed'))
  }
}

onMounted(() => store.fetchGroups())
</script>

<template>
  <UDashboardPanel id="hardlinks" grow>
    <template #header>
      <UDashboardNavbar :title="t('hardlinks.title')">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #right>
          <div class="flex items-center gap-2">
            <UInput v-model="store.query" icon="i-heroicons-magnifying-glass-20-solid" :placeholder="t('hardlinks.searchPlaceholder')" clearable />
            <UButton color="primary" :loading="store.scanning" @click="handleScan">{{ t('hardlinks.scan') }}</UButton>
          </div>
        </template>
      </UDashboardNavbar>

      <UDashboardToolbar>
        <div class="text-xs text-(--ui-text-muted)">{{ t('hardlinks.lastScanned') }}: {{ lastScannedText }}</div>
      </UDashboardToolbar>
    </template>

    <template #body>
      <!-- Summary stat cards -->
      <div class="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-6">
        <UCard
          class="cursor-pointer transition-all"
          :class="filterKey === 'all' ? 'ring-1 ring-(--color-noor-500) bg-(--color-noor-600)/10' : ''"
          :ui="{ body: { padding: 'p-3' } }"
          @click="applyFilter('all')"
        >
          <div class="text-xs text-(--ui-text-muted)">{{ t('hardlinks.total') }}</div>
          <div class="text-2xl font-bold">{{ summary.total_groups }}</div>
        </UCard>
        <UCard
          class="cursor-pointer transition-all"
          :class="[filterKey === 'multiSource' ? 'ring-1 ring-(--color-noor-500) bg-(--color-noor-600)/10' : '', filterCounts.multiSource === 0 ? 'opacity-45' : '']"
          :ui="{ body: { padding: 'p-3' } }"
          @click="applyFilter('multiSource')"
        >
          <div class="text-xs text-(--ui-text-muted)">{{ t('hardlinks.entryCount') }}</div>
          <div class="text-2xl font-bold">{{ summary.total_entries }}</div>
        </UCard>
        <UCard
          class="cursor-pointer transition-all"
          :class="[filterKey === 'multiHardlink' ? 'ring-1 ring-(--color-noor-500) bg-(--color-noor-600)/10' : '', filterCounts.multiHardlink === 0 ? 'opacity-45' : '']"
          :ui="{ body: { padding: 'p-3' } }"
          @click="applyFilter('multiHardlink')"
        >
          <div class="text-xs text-(--ui-text-muted)">{{ t('hardlinks.hardlinkCount') }}</div>
          <div class="text-2xl font-bold">{{ summary.total_hardlinks }}</div>
        </UCard>
        <UCard
          class="cursor-pointer transition-all"
          :class="[summary.issue_groups > 0 ? 'border-amber-400/40' : '', filterKey === 'all' && summary.issue_groups === 0 ? '' : '', filterCounts.all === 0 ? 'opacity-45' : '']"
          :ui="{ body: { padding: 'p-3' } }"
        >
          <div class="text-xs text-(--ui-text-muted)">{{ t('hardlinks.issueCount') }}</div>
          <div class="text-2xl font-bold text-amber-400">{{ summary.issue_groups }}</div>
        </UCard>
      </div>

      <!-- Loading / Error / Empty -->
      <div v-if="store.loading" class="flex flex-col items-center justify-center py-12 text-(--ui-text-muted)">
        <UIcon name="i-heroicons-arrow-path-20-solid" class="w-8 h-8 animate-spin mb-4" />
        <p>{{ t('common.loading') }}</p>
      </div>

      <div v-else-if="store.error" class="flex flex-col items-center justify-center py-12">
        <UIcon name="i-heroicons-exclamation-triangle-20-solid" class="w-12 h-12 text-(--ui-error) mb-4" />
        <p class="text-(--ui-error) font-medium">{{ store.error }}</p>
      </div>

      <div v-else-if="!store.groups.length" class="flex flex-col items-center justify-center py-12 text-(--ui-text-muted)">
        <UIcon name="i-heroicons-link-slash-20-solid" class="w-12 h-12 mb-4 opacity-50" />
        <p>{{ t('hardlinks.empty') }}</p>
        <p class="text-xs mt-1">{{ t('hardlinks.emptyDesc') }}</p>
        <UButton color="neutral" variant="soft" size="sm" class="mt-4" @click="router.push('/settings')">{{ t('library.goToSettings') }}</UButton>
      </div>

      <template v-else>
        <!-- Sort & filter controls -->
        <UCard class="mb-4" :ui="{ body: { padding: 'p-3' } }">
          <div class="flex flex-wrap items-center gap-2 mb-2">
            <span class="text-xs text-(--ui-text-muted)">{{ t('hardlinks.sortBy') }}:</span>
            <UButton
              v-for="st in sortTabs" :key="st.key"
              :color="sortKey === st.key ? 'primary' : 'neutral'"
              variant="soft" size="xs"
              @click="setSort(st.key)"
            >
              {{ st.label }} {{ sortArrow(st.key) }}
            </UButton>
          </div>
          <div class="flex flex-wrap items-center gap-2">
            <span class="text-xs text-(--ui-text-muted)">{{ t('hardlinks.filterBy') }}:</span>
            <UButton
              v-for="ft in filterTabs" :key="ft.key"
              :color="filterKey === ft.key ? 'primary' : 'neutral'"
              variant="soft" size="xs"
              :disabled="isFilterDisabled(ft.key)"
              :class="isFilterDisabled(ft.key) ? 'opacity-45' : ''"
              @click="applyFilter(ft.key)"
            >
              {{ ft.label }} ({{ filterCounts[ft.key] }})
            </UButton>
          </div>
        </UCard>

        <!-- Empty filtered -->
        <div v-if="!visibleGroups.length" class="flex flex-col items-center justify-center py-12 text-(--ui-text-muted)">
          <UIcon name="i-heroicons-magnifying-glass-20-solid" class="w-12 h-12 mb-4 opacity-50" />
          <p>{{ t('hardlinks.emptyFiltered') }}</p>
        </div>

        <!-- Group cards -->
        <div v-else class="space-y-4">
          <UCard v-for="group in pagedGroups" :key="group.code" :class="group.status === 'issue' ? 'border-amber-400/30' : ''">
            <template #header>
              <div class="flex items-start justify-between gap-2">
                <div class="flex items-center gap-2">
                  <span class="font-mono text-sm font-semibold">{{ group.code }}</span>
                  <span class="text-xs text-(--ui-text-muted)">{{ groupSourceCount(group) }} src · {{ groupHardlinkCount(group) }} hl</span>
                </div>
                <div class="flex items-center gap-2">
                  <div class="flex items-center gap-1 flex-wrap">
                    <UBadge v-if="group.status === 'issue'" color="warning" variant="subtle" size="xs">{{ t('hardlinks.status.issue') }}</UBadge>
                    <UBadge v-if="(group.orphan_count || 0) > 0" color="error" variant="subtle" size="xs">{{ t('hardlinks.status.orphan') }} × {{ group.orphan_count }}</UBadge>
                    <UBadge v-if="group.issues?.includes('unparsed_code')" color="warning" variant="subtle" size="xs">{{ t('hardlinks.status.unparsed') }}</UBadge>
                    <UBadge v-if="(group.orphan_count || 0) >= (group.entry_count || group.entries.length)" color="neutral" variant="subtle" size="xs">{{ t('hardlinks.orphanSkipped') }}</UBadge>
                  </div>
                  <UButton color="neutral" variant="ghost" size="xs" :disabled="deletingGroups.has(group.code)" @click="previewGroupDelete(group)">
                    {{ deletingGroups.has(group.code) ? t('hardlinks.processing') : t('hardlinks.previewDelete') }}
                  </UButton>
                  <UButton color="error" variant="soft" size="xs" :disabled="deletingGroups.has(group.code)" @click="deleteGroup(group)">
                    {{ deletingGroups.has(group.code) ? t('hardlinks.processing') : t('hardlinks.deleteGroup') }}
                  </UButton>
                </div>
              </div>
            </template>

            <div class="space-y-3">
              <div
                v-for="(entry, idx) in group.entries"
                :key="`${group.code}-${entry.source_path || 'orphan'}-${idx}`"
                class="grid grid-cols-1 xl:grid-cols-2 gap-3 rounded-md border border-(--ui-border) bg-(--ui-bg-elevated)/50 p-3"
              >
                <!-- Source -->
                <div class="space-y-1.5">
                  <div class="text-xs text-(--ui-text-muted) uppercase tracking-wider">{{ t('hardlinks.mainFile') }}</div>
                  <div class="group flex items-center gap-2 rounded border border-(--ui-border) bg-(--ui-bg)/50 p-2">
                    <span
                      v-if="entry.source_path"
                      class="font-mono text-xs text-(--ui-text-dimmed) cursor-pointer flex-1 truncate hover:text-(--ui-text)"
                      :title="t('hardlinks.previewPath')"
                      @click="openVideoPreview(entry.source_path)"
                    >{{ entry.source_path }}</span>
                    <span v-if="entry.source_size != null" class="text-[11px] text-(--ui-text-muted) shrink-0">{{ formatBytes(entry.source_size) }}</span>
                    <span v-else class="font-mono text-xs text-amber-400">{{ t('hardlinks.missingSource') }}</span>
                    <UButton
                      v-if="entry.source_path"
                      color="error"
                      variant="ghost"
                      size="xs"
                      class="opacity-0 group-hover:opacity-100 transition-opacity"
                      :disabled="deletingSources.has(entry.source_path)"
                      @click="deleteSourceChain(entry, group)"
                    >
                      {{ deletingSources.has(entry.source_path) ? t('hardlinks.processing') : t('hardlinks.deleteSourceChain') }}
                    </UButton>
                  </div>
                </div>

                <!-- Hardlinks -->
                <div class="space-y-1.5">
                  <div class="text-xs text-(--ui-text-muted) uppercase tracking-wider">{{ t('hardlinks.hardlinks') }}</div>
                  <div
                    v-for="hl in entry.hardlink_paths"
                    :key="hl"
                    class="group flex items-center gap-2 rounded border border-(--ui-border) bg-(--ui-bg)/50 p-2"
                  >
                    <span class="text-xs text-(--ui-text-muted)">→</span>
                    <span
                      class="font-mono text-xs text-(--ui-text-dimmed) cursor-pointer flex-1 truncate hover:text-(--ui-text)"
                      :title="t('hardlinks.previewPath')"
                      @click="openVideoPreview(hl)"
                    >{{ hl }}</span>
                    <UButton
                      color="error"
                      variant="ghost"
                      size="xs"
                      class="opacity-0 group-hover:opacity-100 transition-opacity"
                      :disabled="deletingHardlinks.has(hl)"
                      @click="deleteHardlink(hl)"
                    >
                      {{ deletingHardlinks.has(hl) ? t('hardlinks.processing') : t('hardlinks.deleteHardlink') }}
                    </UButton>
                  </div>
                </div>
              </div>
            </div>
          </UCard>
        </div>

        <!-- Pagination -->
        <div v-if="totalPages > 1" class="mt-4 flex justify-center">
          <UPagination v-model="store.page" :total="visibleGroups.length" :items-per-page="store.pageSize" />
        </div>
      </template>

      <!-- Scanning overlay -->
      <div v-if="store.scanning" class="fixed inset-0 z-40 bg-black/40 flex items-center justify-center">
        <UCard :ui="{ body: { padding: 'p-4' } }">
          <div class="flex items-center gap-3">
            <UIcon name="i-heroicons-arrow-path-20-solid" class="w-5 h-5 animate-spin" />
            <span>{{ t('hardlinks.scan') }}...</span>
          </div>
        </UCard>
      </div>

      <!-- Video preview modal -->
      <UModal :open="!!previewVideoPath" @update:open="(v: boolean) => { if (!v) previewVideoPath = '' }">
        <UCard :ui="{ body: { padding: 'p-0' } }">
          <template #header>
            <div class="flex items-center justify-between">
              <h3 class="text-base font-semibold truncate">{{ previewVideoName }}</h3>
              <UButton color="neutral" variant="ghost" icon="i-heroicons-x-mark-20-solid" @click="previewVideoPath = ''" />
            </div>
          </template>
          <div class="space-y-2 p-4">
            <div class="font-mono text-xs text-(--ui-text-muted) break-all">{{ previewVideoPath }}</div>
            <video
              v-if="previewVideoPath"
              :key="previewVideoUrl"
              class="w-full max-h-[70vh] rounded border border-(--ui-border)"
              :src="previewVideoUrl"
              controls
              autoplay
              preload="metadata"
            />
            <p class="text-xs text-(--ui-text-muted)">{{ t('hardlinks.previewUnsupported') }}</p>
          </div>
        </UCard>
      </UModal>
    </template>
  </UDashboardPanel>
</template>
