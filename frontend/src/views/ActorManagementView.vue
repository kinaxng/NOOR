<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import api from '../api'
import BaseIcon from '../components/noor/BaseIcon.vue'
import VuiButton from '../components/ui/Button/VuiButton.vue'
import NoorPagination from '../components/ui/Pagination.vue'
import { useConfirm } from '../composables/useConfirm'
import { useI18n } from '../composables/useI18n'
import { useToast } from '../composables/useToast'
import type { MediaActor } from '../api/types'

type SortKey = 'SortName' | 'DateCreated'
type SortOrder = 'Ascending' | 'Descending'

const { t, i18nVersion, currentLang } = useI18n()
const toast = useToast()
const { confirm } = useConfirm()
const router = useRouter()

const actors = ref<MediaActor[]>([])
const loading = ref(false)
const duplicateLoading = ref(false)
const mappingUploading = ref(false)
const mappingMatching = ref(false)
const mappingStatus = ref<any | null>(null)
const mappingMatches = ref<any | null>(null)
const tmdbBackfill = ref<any | null>(null)
const nameSyncPreview = ref<any | null>(null)
const showMappingMatches = ref(false)
const showRejectedMatches = ref(false)
const mergePlans = ref<Record<string, any>>({})
const mergePlanLoading = ref<Record<string, boolean>>({})
const mergeExecuting = ref<Record<string, boolean>>({})
const batchMerging = ref(false)
const tmdbBackfillLoading = ref(false)
const tmdbBackfillApplying = ref(false)
const tmdbBackfillProgress = ref<any | null>(null)
const tmdbBackfillResult = ref<any | null>(null)
const tmdbBackfillReviewing = ref<Record<string, boolean>>({})
const nameSyncLoading = ref(false)
const nameSyncApplying = ref(false)
const nameSyncProgress = ref<any | null>(null)
const nameSyncResult = ref<any | null>(null)
const selectedMergeTargets = ref<Record<string, string>>({})
const query = ref('')
const page = ref(1)
const pageSize = 60
const total = ref(0)
const sortBy = ref<SortKey>('SortName')
const sortOrder = ref<SortOrder>('Ascending')
const actorNameLang = ref('zh-CN')

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize)))
const resultLabel = computed(() => {
  void i18nVersion.value
  return t('files.actors.resultCount', { count: total.value })
})
const mappingStats = computed(() => mappingStatus.value?.stats || null)
const rejectedMatches = computed(() => mappingMatches.value?.rejected_matches || [])
const tmdbBackfillCandidates = computed(() => tmdbBackfill.value?.candidates || [])
const nameSyncUpdates = computed(() => nameSyncPreview.value?.updates || [])
const nameSyncConflicts = computed(() => nameSyncPreview.value?.conflicts || [])
const nameSyncProgressPercent = computed(() => {
  const total = Number(nameSyncProgress.value?.total || 0)
  const processed = Number(nameSyncProgress.value?.processed || 0)
  if (!total) return nameSyncApplying.value ? 2 : 0
  return Math.max(2, Math.min(100, Math.round((processed / total) * 100)))
})
const tmdbBackfillProgressPercent = computed(() => {
  const total = Number(tmdbBackfillProgress.value?.total || 0)
  const processed = Number(tmdbBackfillProgress.value?.processed || 0)
  if (!total) return tmdbBackfillApplying.value ? 2 : 0
  return Math.max(2, Math.min(100, Math.round((processed / total) * 100)))
})

let searchTimer: number | null = null
let tmdbBackfillProgressTimer: number | null = null
let nameSyncProgressTimer: number | null = null

function actorInitial(name: string) {
  return (name || '?').trim().slice(0, 1).toUpperCase()
}

function actorName(actor: MediaActor) {
  return actor.display_name || actor.name
}

function actorRawName(actor: MediaActor) {
  return actor.name || actor.display_name
}

function actorDisplayAlias(actor: MediaActor) {
  const displayName = String(actor.display_name || '').trim()
  const rawName = String(actor.name || '').trim()
  return displayName && displayName !== rawName ? displayName : ''
}

function mappingGroupName(group: any) {
  if (!group) return ''
  const lang = String(actorNameLang.value || currentLang.value || '').toLowerCase()
  if (lang === 'zh-tw' || lang.includes('hant') || lang === 'tw') {
    return group.zh_tw || group.zh_cn || group.jp || group.display_name || group.canonical_name
  }
  if (lang.startsWith('zh') || lang === 'cn') {
    return group.zh_cn || group.zh_tw || group.jp || group.display_name || group.canonical_name
  }
  return group.jp || group.zh_cn || group.zh_tw || group.display_name || group.canonical_name
}

function actorHasConflict(group: any, actor: MediaActor) {
  if (!group?.tmdb_id || !actor.tmdb_id) return false
  return String(actor.tmdb_id) !== String(group.tmdb_id)
}

function selectedMergeTargetId(group: any) {
  const mappingId = String(group?.mapping_id || '')
  return selectedMergeTargets.value[mappingId] || String(group?.target_actor_id || '')
}

function selectedMergeTargetName(group: any) {
  const selectedId = selectedMergeTargetId(group)
  const actor = (group?.actors || []).find((item: any) => String(item?.id || '') === selectedId)
  if (!actor) return group?.target_actor_display_name || group?.target_actor_name || ''
  const alias = actorDisplayAlias(actor)
  return alias ? `${actorRawName(actor)} / ${alias}` : actorRawName(actor)
}

function selectMergeTarget(group: any, actor: MediaActor) {
  const mappingId = String(group?.mapping_id || '')
  const actorId = String(actor?.id || '')
  if (!mappingId || !actorId) return
  selectedMergeTargets.value = { ...selectedMergeTargets.value, [mappingId]: actorId }
  const nextPlans = { ...mergePlans.value }
  delete nextPlans[mappingId]
  mergePlans.value = nextPlans
}

function changedPeopleLabel(movie: any) {
  return (movie?.changed_people || []).map((person: any) => person.name).filter(Boolean).join(' / ')
}

function mergePlanActionable(plan: any) {
  return !!((plan?.movie_count || 0) > 0 || (plan?.empty_source_actor_ids || []).length)
}

function mergePlanEmptyActorCount(plan: any) {
  return (plan?.empty_source_actor_ids || []).length
}

function batchMergeableGroups() {
  return (mappingMatches.value?.groups || []).filter((group: any) => !group?.has_tmdb_conflict && selectedMergeTargetId(group))
}

function batchConflictCount() {
  return (mappingMatches.value?.groups || []).filter((group: any) => group?.has_tmdb_conflict).length
}

function rejectedReasonLabel(reason: string) {
  if (reason === 'tmdb_conflict_alias') return t('files.actors.rejectedReasonTmdbConflict')
  if (reason === 'ignored_empty_non_target_person') return t('files.actors.rejectedReasonIgnoredEmpty')
  if (reason === 'ignored_person') return t('files.actors.rejectedReasonIgnoredPerson')
  return reason || t('files.actors.rejectedReasonUnknown')
}

function deleteFailedSummary(items: any[]) {
  return (items || [])
    .slice(0, 3)
    .map((item: any) => `${item.id || '-'}: ${item.error || ''}`.trim())
    .join(' / ')
}

async function loadActors() {
  loading.value = true
  try {
    const resp = await api.get('/media-library/actors', {
      params: {
        limit: pageSize,
        offset: (page.value - 1) * pageSize,
        q: query.value.trim() || undefined,
        sort_by: sortBy.value,
        sort_order: sortOrder.value,
        lang: actorNameLang.value,
      },
    })
    actors.value = resp.data.actors || []
    total.value = resp.data.total || 0
  } catch (error: any) {
    actors.value = []
    total.value = 0
    toast.error(error?.response?.data?.detail || error?.message || t('files.actors.loadFailed'))
  } finally {
    loading.value = false
  }
}

async function loadDuplicates() {
  duplicateLoading.value = true
  await previewMappingMatches()
  duplicateLoading.value = false
}

async function loadMappingStatus() {
  try {
    const resp = await api.get('/media-library/actors/mapping/status')
    mappingStatus.value = resp.data.imported ? resp.data : null
  } catch {
    mappingStatus.value = null
  }
}

async function syncMdcNgMapping() {
  mappingUploading.value = true
  try {
    const resp = await api.post('/media-library/actors/mapping/sync-mdc-ng')
    mappingStatus.value = { imported: true, ...(resp.data.mapping || {}), mdc_ng: resp.data.mdc_ng || {} }
    toast.success(t('files.actors.mappingImportSuccess'))
    await loadMappingStatus()
    loadActors()
  } catch (error: any) {
    toast.error(error?.response?.data?.detail || error?.message || t('files.actors.mappingImportFailed'))
  } finally {
    mappingUploading.value = false
  }
}

async function clearMapping() {
  const ok = await confirm({
    title: t('files.actors.clearMapping'),
    message: t('files.actors.clearMappingConfirm'),
    confirmText: t('common.delete'),
    danger: true,
  })
  if (!ok) return
  mappingUploading.value = true
  try {
    await api.delete('/media-library/actors/mapping')
    mappingStatus.value = null
    mappingMatches.value = null
    showMappingMatches.value = false
    showRejectedMatches.value = false
    toast.success(t('files.actors.clearMappingSuccess'))
  } catch (error: any) {
    toast.error(error?.response?.data?.detail || error?.message || t('files.actors.clearMappingFailed'))
  } finally {
    mappingUploading.value = false
  }
}

async function previewMappingMatches() {
  mappingMatching.value = true
  try {
    const resp = await api.get('/media-library/actors/mapping/matches', {
      params: { only_candidates: true, lang: actorNameLang.value },
    })
    mappingMatches.value = resp.data || null
    showMappingMatches.value = true
    showRejectedMatches.value = false
  } catch (error: any) {
    toast.error(error?.response?.data?.detail || error?.message || t('files.actors.mappingMatchFailed'))
  } finally {
    mappingMatching.value = false
  }
}

async function previewTmdbBackfill() {
  tmdbBackfillLoading.value = true
  if (!tmdbBackfillApplying.value) tmdbBackfillResult.value = null
  try {
    const resp = await api.get('/media-library/actors/tmdb-backfill/preview', {
      params: { lang: actorNameLang.value },
    })
    tmdbBackfill.value = resp.data || null
  } catch (error: any) {
    toast.error(error?.response?.data?.detail || error?.message || t('files.actors.tmdbBackfillPreviewFailed'))
  } finally {
    tmdbBackfillLoading.value = false
  }
}

async function previewNameSync() {
  nameSyncLoading.value = true
  if (!nameSyncApplying.value) nameSyncResult.value = null
  try {
    const resp = await api.get('/media-library/actors/name-sync/preview', {
      params: { lang: actorNameLang.value },
    })
    nameSyncPreview.value = resp.data || null
  } catch (error: any) {
    toast.error(error?.response?.data?.detail || error?.message || t('files.actors.nameSyncPreviewFailed'))
  } finally {
    nameSyncLoading.value = false
  }
}

function stopNameSyncProgressPolling() {
  if (nameSyncProgressTimer) {
    window.clearInterval(nameSyncProgressTimer)
    nameSyncProgressTimer = null
  }
}

function startNameSyncProgressPolling(progressKey: string) {
  stopNameSyncProgressPolling()
  const poll = async () => {
    try {
      const resp = await api.get(`/media-library/actors/name-sync/progress/${encodeURIComponent(progressKey)}`)
      nameSyncProgress.value = resp.data || null
      const status = String(resp.data?.status || '')
      if (status === 'completed' || status === 'failed') stopNameSyncProgressPolling()
    } catch {
      // The apply request reports final success/failure.
    }
  }
  void poll()
  nameSyncProgressTimer = window.setInterval(poll, 900)
}

async function applyNameSync() {
  const count = nameSyncPreview.value?.summary?.safe_update_count || 0
  if (!count || nameSyncApplying.value) return
  const ok = await confirm({
    title: t('files.actors.nameSyncApplyTitle'),
    message: t('files.actors.nameSyncApplyConfirm', {
      count,
      conflicts: nameSyncPreview.value?.summary?.conflict_count || 0,
    }),
    confirmText: t('files.actors.nameSyncApply'),
    size: 'md',
  })
  if (!ok) return
  nameSyncApplying.value = true
  nameSyncResult.value = null
  nameSyncProgress.value = {
    status: 'running',
    processed: 0,
    total: count,
    applied_count: 0,
    skipped_count: 0,
    current_actor: '',
    current_target: '',
  }
  const progressKey = typeof crypto !== 'undefined' && 'randomUUID' in crypto
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(16).slice(2)}`
  startNameSyncProgressPolling(progressKey)
  try {
    const resp = await api.post('/media-library/actors/name-sync/apply', {
      skip_conflicts: true,
      dry_run: false,
      progress_key: progressKey,
    }, {
      params: { lang: actorNameLang.value },
    })
    nameSyncResult.value = resp.data || null
    toast.success(t('files.actors.nameSyncApplySuccess', { count: resp.data.applied_count || 0 }))
    await previewNameSync()
    loadActors()
  } catch (error: any) {
    toast.error(error?.response?.data?.detail || error?.message || t('files.actors.nameSyncApplyFailed'))
  } finally {
    nameSyncApplying.value = false
    stopNameSyncProgressPolling()
  }
}

function stopTmdbBackfillProgressPolling() {
  if (tmdbBackfillProgressTimer) {
    window.clearInterval(tmdbBackfillProgressTimer)
    tmdbBackfillProgressTimer = null
  }
}

function startTmdbBackfillProgressPolling(progressKey: string) {
  stopTmdbBackfillProgressPolling()
  const poll = async () => {
    try {
      const resp = await api.get(`/media-library/actors/tmdb-backfill/progress/${encodeURIComponent(progressKey)}`)
      tmdbBackfillProgress.value = resp.data || null
      const status = String(resp.data?.status || '')
      if (status === 'completed' || status === 'failed') stopTmdbBackfillProgressPolling()
    } catch {
      // The apply request still owns the final success/failure result.
    }
  }
  void poll()
  tmdbBackfillProgressTimer = window.setInterval(poll, 900)
}

async function applyTmdbBackfill() {
  const count = tmdbBackfill.value?.summary?.high_confidence_count || 0
  if (!count || tmdbBackfillApplying.value) return
  const ok = await confirm({
    title: t('files.actors.tmdbBackfillApplyTitle'),
    message: t('files.actors.tmdbBackfillApplyConfirm', { count }),
    confirmText: t('files.actors.tmdbBackfillApply'),
    size: 'md',
  })
  if (!ok) return
  tmdbBackfillApplying.value = true
  tmdbBackfillResult.value = null
  tmdbBackfillProgress.value = {
    status: 'running',
    processed: 0,
    total: count,
    applied_count: 0,
    skipped_count: 0,
    current_actor: '',
  }
  const progressKey = typeof crypto !== 'undefined' && 'randomUUID' in crypto
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(16).slice(2)}`
  startTmdbBackfillProgressPolling(progressKey)
  try {
    const resp = await api.post('/media-library/actors/tmdb-backfill/apply', {
      only_high_confidence: true,
      dry_run: false,
      progress_key: progressKey,
    }, {
      params: { lang: actorNameLang.value },
    })
    tmdbBackfillResult.value = resp.data || null
    toast.success(t('files.actors.tmdbBackfillApplySuccess', { count: resp.data.applied_count || 0 }))
    await previewTmdbBackfill()
    loadActors()
  } catch (error: any) {
    toast.error(error?.response?.data?.detail || error?.message || t('files.actors.tmdbBackfillApplyFailed'))
  } finally {
    tmdbBackfillApplying.value = false
    stopTmdbBackfillProgressPolling()
  }
}

function tmdbBackfillReviewKey(item: any) {
  return `${item?.actor_id || ''}-${item?.tmdb_id || ''}`
}

async function reviewTmdbBackfillCandidate(item: any) {
  const actorId = String(item?.actor_id || '').trim()
  const tmdbId = String(item?.tmdb_id || '').trim()
  if (!actorId || !tmdbId) return
  const conflictActors = Array.isArray(item?.conflict_actors) ? item.conflict_actors : []
  const hasConflict = conflictActors.length > 0
  const ok = await confirm({
    title: t('files.actors.tmdbBackfillReviewTitle'),
    message: hasConflict
      ? t('files.actors.tmdbBackfillReviewConflictMessage', { name: item.display_name || item.actor_name || actorId, tmdb: tmdbId })
      : t('files.actors.tmdbBackfillReviewApplyMessage', { name: item.display_name || item.actor_name || actorId, tmdb: tmdbId }),
    confirmText: hasConflict ? t('files.actors.tmdbBackfillReviewOpenActor') : t('files.actors.tmdbBackfillReviewApply'),
    cancelText: t('common.cancel'),
    size: 'md',
    details: [
      {
        label: 'TMDB',
        items: [`${tmdbId} · ${item.mapping_name || item.matched_name || ''}`.trim()],
      },
      ...(hasConflict ? [{
        label: t('files.actors.tmdbBackfillReviewConflicts'),
        items: conflictActors.map((actor: any) => actor.display_name || actor.name || actor.id).filter(Boolean),
      }] : []),
    ],
  })
  if (!ok) return
  if (hasConflict) {
    openActor(item.actor)
    return
  }
  const key = tmdbBackfillReviewKey(item)
  tmdbBackfillReviewing.value = { ...tmdbBackfillReviewing.value, [key]: true }
  try {
    const resp = await api.post('/media-library/actors/tmdb-backfill/apply', {
      actor_ids: [actorId],
      only_high_confidence: false,
      dry_run: false,
    }, {
      params: { lang: actorNameLang.value },
    })
    if ((resp.data?.applied_count || 0) > 0) {
      toast.success(t('files.actors.tmdbBackfillReviewApplySuccess', { name: item.display_name || item.actor_name || actorId }))
      await previewTmdbBackfill()
      loadActors()
    } else {
      toast.warning(t('files.actors.tmdbBackfillReviewSkipped'))
    }
  } catch (error: any) {
    toast.error(error?.response?.data?.detail || error?.message || t('files.actors.tmdbBackfillApplyFailed'))
  } finally {
    const next = { ...tmdbBackfillReviewing.value }
    delete next[key]
    tmdbBackfillReviewing.value = next
  }
}

async function loadMergePlan(group: any) {
  const mappingId = String(group?.mapping_id || '')
  if (!mappingId) return
  mergePlanLoading.value = { ...mergePlanLoading.value, [mappingId]: true }
  try {
    const resp = await api.get('/media-library/actors/mapping/merge-plan', {
      params: { mapping_id: mappingId, target_actor_id: selectedMergeTargetId(group) || undefined, lang: actorNameLang.value },
    })
    mergePlans.value = { ...mergePlans.value, [mappingId]: resp.data }
  } catch (error: any) {
    toast.error(error?.response?.data?.detail || error?.message || t('files.actors.mergePlanFailed'))
  } finally {
    mergePlanLoading.value = { ...mergePlanLoading.value, [mappingId]: false }
  }
}

async function executeMergePlan(group: any) {
  const mappingId = String(group?.mapping_id || '')
  if (!mappingId) return
  const plan = mergePlans.value[mappingId]
  if (!mergePlanActionable(plan)) return
  const ok = await confirm({
    title: t('files.actors.mergeConfirmTitle'),
    message: t('files.actors.mergeConfirm', {
      count: plan.movie_count || 0,
      empty: mergePlanEmptyActorCount(plan),
      target: plan.target_name || mappingGroupName(group),
    }),
    confirmText: t('files.actors.executeMerge'),
    note: t('files.actors.mergeBackupNote'),
    size: 'md',
  })
  if (!ok) return
  mergeExecuting.value = { ...mergeExecuting.value, [mappingId]: true }
  try {
    const resp = await api.post('/media-library/actors/mapping/merge-execute', {
      mapping_id: mappingId,
      target_name: plan.target_name,
      target_actor_id: plan.target_actor_id || selectedMergeTargetId(group) || undefined,
      dry_run: false,
    }, {
      params: { lang: actorNameLang.value },
    })
    toast.success(t('files.actors.mergeSuccess', { count: resp.data.updated_count || 0 }))
    const deleteFailures = resp.data.delete_failed_actor_ids || []
    if (deleteFailures.length) {
      toast.error(`${t('files.actors.mergeDeleteFailed', { count: deleteFailures.length })}: ${deleteFailedSummary(deleteFailures)}`)
    }
    await previewMappingMatches()
    loadActors()
  } catch (error: any) {
    toast.error(error?.response?.data?.detail || error?.message || t('files.actors.mergeFailed'))
  } finally {
    mergeExecuting.value = { ...mergeExecuting.value, [mappingId]: false }
  }
}

async function executeBatchMerge() {
  const groups = batchMergeableGroups()
  if (!groups.length || batchMerging.value) return
  const conflictCount = batchConflictCount()
  const ok = await confirm({
    title: t('files.actors.batchMergeConfirmTitle'),
    message: t('files.actors.batchMergeConfirm', { count: groups.length, skipped: conflictCount }),
    confirmText: t('files.actors.batchMerge'),
    note: t('files.actors.batchMergeNote'),
    size: 'md',
    details: [{
      label: t('files.actors.batchMergeTargets'),
      items: groups.slice(0, 20).map((group: any) => `${mappingGroupName(group)} -> ${selectedMergeTargetName(group) || group.target_actor_name || ''}`),
    }],
  })
  if (!ok) return

  batchMerging.value = true
  try {
    const targetActorIds: Record<string, string> = {}
    for (const group of groups) {
      const mappingId = String(group?.mapping_id || '')
      const actorId = selectedMergeTargetId(group)
      if (mappingId && actorId) targetActorIds[mappingId] = actorId
    }
    const resp = await api.post('/media-library/actors/mapping/merge-batch', {
      target_actor_ids: targetActorIds,
      skip_conflicts: true,
      dry_run: false,
    }, {
      params: { lang: actorNameLang.value },
    })
    const result = resp.data || {}
    toast.success(t('files.actors.batchMergeSuccess', {
      groups: result.executed_count || 0,
      count: result.updated_count || 0,
      deleted: result.deleted_actor_count || 0,
      skipped: result.skipped_count || 0,
    }))
    const failures = result.failures || []
    if (failures.length) {
      toast.error(t('files.actors.batchMergeFailed', { count: failures.length }) + `: ${failures.slice(0, 3).map((item: any) => `${item.name || item.mapping_id}: ${item.error}`).join(' / ')}`)
    }
    const deleteFailures = result.delete_failed_actor_ids || []
    if (deleteFailures.length) {
      toast.error(`${t('files.actors.mergeDeleteFailed', { count: deleteFailures.length })}: ${deleteFailedSummary(deleteFailures)}`)
    }
    await previewMappingMatches()
    loadActors()
  } catch (error: any) {
    toast.error(error?.response?.data?.detail || error?.message || t('files.actors.mergeFailed'))
  } finally {
    batchMerging.value = false
  }
}

function setSort(key: SortKey, order: SortOrder) {
  sortBy.value = key
  sortOrder.value = order
  page.value = 1
  loadActors()
}

function openActor(actor: MediaActor) {
  if (!actor.id) return
  router.push({
    path: `/actors/${encodeURIComponent(actor.id)}`,
    query: { returnTo: '/files/actors', actorLang: actorNameLang.value },
  })
}

watch(query, () => {
  if (searchTimer) window.clearTimeout(searchTimer)
  searchTimer = window.setTimeout(() => {
    page.value = 1
    loadActors()
  }, 260)
})

watch(page, () => {
  loadActors()
})

watch(currentLang, () => {
  loadActors()
})

watch(actorNameLang, () => {
  page.value = 1
  loadActors()
  if (showMappingMatches.value) void previewMappingMatches()
  if (tmdbBackfill.value) void previewTmdbBackfill()
  if (nameSyncPreview.value) void previewNameSync()
})

onMounted(() => {
  loadActors()
  loadMappingStatus()
})

onUnmounted(() => {
  stopTmdbBackfillProgressPolling()
  stopNameSyncProgressPolling()
})
</script>

<template>
  <div class="actor-management">
    <div class="page-header">
      <div class="page-header__left">
        <div>
          <h1 class="page-title">{{ t('files.actors.title') }}</h1>
          <div class="page-meta">
            <span>{{ resultLabel }}</span>
          </div>
        </div>
      </div>
      <div class="actor-actions">
        <div class="actor-language-switch" :aria-label="t('files.actors.nameLanguage')">
          <button type="button" :class="{ 'is-active': actorNameLang === 'zh-CN' }" @click="actorNameLang = 'zh-CN'">{{ t('files.actors.nameLangZhCn') }}</button>
          <button type="button" :class="{ 'is-active': actorNameLang === 'zh-TW' }" @click="actorNameLang = 'zh-TW'">{{ t('files.actors.nameLangZhTw') }}</button>
          <button type="button" :class="{ 'is-active': actorNameLang === 'ja-JP' }" @click="actorNameLang = 'ja-JP'">{{ t('files.actors.nameLangJa') }}</button>
        </div>
        <div class="actor-search">
          <BaseIcon name="search" class="actor-search__icon" />
          <input v-model="query" type="search" :placeholder="t('files.actors.searchPlaceholder')" class="actor-search__input" />
        </div>
        <VuiButton variant="outlined" color="secondary" size="small" :disabled="duplicateLoading" @click="loadDuplicates">
          <BaseIcon name="user" class="w-4 h-4" />
          {{ t('files.actors.detectDuplicates') }}
        </VuiButton>
        <VuiButton variant="outlined" color="secondary" size="small" :disabled="tmdbBackfillLoading" @click="previewTmdbBackfill">
          <BaseIcon name="brandTmdb" class="w-4 h-4" />
          {{ t('files.actors.tmdbBackfillPreview') }}
        </VuiButton>
        <VuiButton variant="outlined" color="secondary" size="small" :disabled="nameSyncLoading" @click="previewNameSync">
          <BaseIcon name="edit" class="w-4 h-4" />
          {{ t('files.actors.nameSyncPreview') }}
        </VuiButton>
        <VuiButton variant="outlined" color="secondary" size="small" :disabled="mappingUploading" @click="syncMdcNgMapping">
          <BaseIcon name="refresh" class="w-4 h-4" />
          {{ t('files.actors.importMapping') }}
        </VuiButton>
        <VuiButton v-if="mappingStatus" variant="outlined" color="secondary" size="small" :disabled="mappingUploading" customClass="actor-action-button--danger" @click="clearMapping">
          <BaseIcon name="trash" class="w-4 h-4" />
          {{ t('files.actors.clearMapping') }}
        </VuiButton>
        <div v-if="mappingStats" class="mapping-status" :title="mappingStatus?.updated_at || ''">
          <span>{{ t('files.actors.mappingImportedTotal') }} <strong>{{ mappingStats.total || 0 }}</strong></span>
          <span>TMDB <strong>{{ mappingStats.with_tmdb || 0 }}</strong></span>
          <span>Verified <strong>{{ mappingStats.verified || 0 }}</strong></span>
        </div>
      </div>
    </div>

    <section v-if="nameSyncPreview" class="name-sync-panel ui-card">
      <div class="duplicate-panel__head">
        <div>
          <h2>{{ t('files.actors.nameSyncTitle') }}</h2>
          <span>{{ t('files.actors.nameSyncSummary', {
            scanned: nameSyncPreview.summary?.actors_scanned || 0,
            updates: nameSyncPreview.summary?.update_count || 0,
            safe: nameSyncPreview.summary?.safe_update_count || 0,
            conflicts: nameSyncPreview.summary?.conflict_count || 0,
          }) }}</span>
        </div>
        <div class="duplicate-panel__tools">
          <VuiButton
            variant="gradient"
            color="primary"
            size="small"
            :disabled="nameSyncApplying || !(nameSyncPreview.summary?.safe_update_count || 0)"
            @click="applyNameSync"
          >
            <BaseIcon name="check" class="w-4 h-4" />
            {{ nameSyncApplying ? t('files.actors.nameSyncApplying') : t('files.actors.nameSyncApply') }}
          </VuiButton>
          <button type="button" class="duplicate-panel__close" :disabled="nameSyncApplying" @click="nameSyncPreview = null">
            <BaseIcon name="close" />
          </button>
        </div>
      </div>

      <div v-if="nameSyncApplying || nameSyncResult" class="name-sync-progress">
        <div class="name-sync-progress__head">
          <strong>
            {{ nameSyncApplying ? t('files.actors.nameSyncProgressRunning') : t('files.actors.nameSyncProgressDone') }}
          </strong>
          <span>
            {{ t('files.actors.nameSyncProgressCounts', {
              processed: nameSyncProgress?.processed || nameSyncResult?.applied_count || 0,
              total: nameSyncProgress?.total || nameSyncResult?.applied_count || 0,
              applied: nameSyncProgress?.applied_count || nameSyncResult?.applied_count || 0,
              skipped: nameSyncProgress?.skipped_count || nameSyncResult?.skipped_count || 0,
            }) }}
          </span>
        </div>
        <div class="name-sync-progress__bar" role="progressbar" :aria-valuenow="nameSyncProgressPercent" aria-valuemin="0" aria-valuemax="100">
          <span :style="{ width: `${nameSyncApplying ? nameSyncProgressPercent : 100}%` }"></span>
        </div>
        <em v-if="nameSyncApplying && nameSyncProgress?.current_actor">
          {{ t('files.actors.nameSyncProgressCurrent', {
            name: nameSyncProgress.current_actor,
            target: nameSyncProgress.current_target || '-',
          }) }}
        </em>
      </div>

      <div v-if="nameSyncConflicts.length" class="name-sync-conflicts">
        <strong>{{ t('files.actors.nameSyncConflictsTitle') }}</strong>
        <article v-for="item in nameSyncConflicts" :key="item.actor_id" class="name-sync-row is-conflict">
          <button type="button" class="name-sync-row__actor" @click="openActor(item.actor)">
            <span>{{ item.current_name }}</span>
            <em>{{ item.current_name }} -> {{ item.target_name }}</em>
          </button>
          <div class="name-sync-row__meta">
            <span>{{ item.target_source }}</span>
            <em>{{ t('files.actors.nameSyncConflictWith', { names: (item.conflict_actors || []).map((actor: any) => actor.display_name || actor.name || actor.id).join(' / ') }) }}</em>
          </div>
        </article>
      </div>

      <div v-if="nameSyncUpdates.length" class="name-sync-list">
        <article v-for="item in nameSyncUpdates" :key="item.actor_id" class="name-sync-row" :class="{ 'is-conflict': item.has_conflict }">
          <button type="button" class="name-sync-row__actor" @click="openActor(item.actor)">
            <span>{{ item.current_name }}</span>
            <em>{{ item.target_name }}</em>
          </button>
          <div class="name-sync-row__meta">
            <span>{{ item.target_source }}</span>
            <em>{{ item.has_conflict ? t('files.actors.nameSyncConflict') : t('files.actors.nameSyncSafe') }}</em>
          </div>
        </article>
      </div>
      <div v-else class="actor-empty actor-empty--compact">{{ t('files.actors.nameSyncEmpty') }}</div>
    </section>

    <section v-if="tmdbBackfill" class="tmdb-backfill-panel ui-card">
      <div class="duplicate-panel__head">
        <div>
          <h2>{{ t('files.actors.tmdbBackfillTitle') }}</h2>
          <span>{{ t('files.actors.tmdbBackfillSummary', {
            candidates: tmdbBackfill.summary?.candidate_count || 0,
            high: tmdbBackfill.summary?.high_confidence_count || 0,
            conflicts: tmdbBackfill.summary?.conflict_count || 0,
          }) }}</span>
        </div>
        <div class="duplicate-panel__tools">
          <VuiButton
            variant="gradient"
            color="primary"
            size="small"
            :disabled="tmdbBackfillApplying || !(tmdbBackfill.summary?.high_confidence_count || 0)"
            @click="applyTmdbBackfill"
          >
            <BaseIcon name="check" class="w-4 h-4" />
            {{ tmdbBackfillApplying ? t('files.actors.tmdbBackfillApplying') : t('files.actors.tmdbBackfillApply') }}
          </VuiButton>
          <button type="button" class="duplicate-panel__close" :disabled="tmdbBackfillApplying" @click="tmdbBackfill = null">
            <BaseIcon name="close" />
          </button>
        </div>
      </div>
      <div v-if="tmdbBackfillApplying || tmdbBackfillResult" class="tmdb-backfill-progress">
        <div class="tmdb-backfill-progress__head">
          <strong>
            {{ tmdbBackfillApplying ? t('files.actors.tmdbBackfillProgressRunning') : t('files.actors.tmdbBackfillProgressDone') }}
          </strong>
          <span>
            {{ t('files.actors.tmdbBackfillProgressCounts', {
              processed: tmdbBackfillProgress?.processed || tmdbBackfillResult?.applied_count || 0,
              total: tmdbBackfillProgress?.total || tmdbBackfillResult?.applied_count || 0,
              applied: tmdbBackfillProgress?.applied_count || tmdbBackfillResult?.applied_count || 0,
              skipped: tmdbBackfillProgress?.skipped_count || tmdbBackfillResult?.skipped_count || 0,
            }) }}
          </span>
        </div>
        <div class="tmdb-backfill-progress__bar" role="progressbar" :aria-valuenow="tmdbBackfillProgressPercent" aria-valuemin="0" aria-valuemax="100">
          <span :style="{ width: `${tmdbBackfillApplying ? tmdbBackfillProgressPercent : 100}%` }"></span>
        </div>
        <em v-if="tmdbBackfillApplying && tmdbBackfillProgress?.current_actor">
          {{ t('files.actors.tmdbBackfillProgressCurrent', { name: tmdbBackfillProgress.current_actor }) }}
        </em>
      </div>
      <div v-if="tmdbBackfillCandidates.length" class="tmdb-backfill-list">
        <article v-for="item in tmdbBackfillCandidates" :key="`${item.actor_id}-${item.tmdb_id}`" class="tmdb-backfill-row" :class="{ 'is-review': item.confidence !== 'high' }">
          <button type="button" class="tmdb-backfill-row__actor" @click="openActor(item.actor)">
            <span>{{ item.display_name || item.actor_name }}</span>
            <em>{{ item.actor_name }} · {{ item.matched_name }}</em>
          </button>
          <div class="tmdb-backfill-row__meta">
            <a :href="`https://www.themoviedb.org/person/${encodeURIComponent(String(item.tmdb_id || ''))}`" target="_blank" rel="noopener noreferrer">TMDB {{ item.tmdb_id }}</a>
            <span>{{ item.mapping_name }}</span>
            <em v-if="item.confidence === 'high'">{{ t('files.actors.tmdbBackfillHigh') }}</em>
            <button
              v-else
              type="button"
              class="tmdb-backfill-row__review"
              :disabled="tmdbBackfillReviewing[tmdbBackfillReviewKey(item)]"
              @click="reviewTmdbBackfillCandidate(item)"
            >
              {{ tmdbBackfillReviewing[tmdbBackfillReviewKey(item)] ? t('files.actors.tmdbBackfillReviewing') : t('files.actors.tmdbBackfillReview') }}
            </button>
          </div>
        </article>
      </div>
      <div v-else class="actor-empty actor-empty--compact">{{ t('files.actors.tmdbBackfillEmpty') }}</div>
    </section>

    <section v-if="showMappingMatches && mappingMatches" class="duplicate-panel ui-card">
      <div class="duplicate-panel__head">
        <div>
          <h2>{{ t('files.actors.mappingMatchesTitle') }}</h2>
          <span>
            {{ t('files.actors.mappingMatchesSummary', {
              candidates: mappingMatches.candidate_groups || 0,
              conflicts: mappingMatches.conflict_groups || 0,
              rejected: mappingMatches.rejected_actors || 0,
              matched: mappingMatches.matched_actors || 0,
              unmatched: mappingMatches.unmatched_actors || 0,
            }) }}
          </span>
        </div>
        <div class="duplicate-panel__tools">
          <VuiButton
            v-if="mappingMatches.groups?.length"
            variant="gradient"
            color="primary"
            size="small"
            :disabled="batchMerging || !batchMergeableGroups().length"
            @click="executeBatchMerge"
          >
            <BaseIcon name="check" class="w-4 h-4" />
            {{ t('files.actors.batchMerge') }}
          </VuiButton>
          <VuiButton
            v-if="rejectedMatches.length"
            variant="outlined"
            color="secondary"
            size="small"
            @click="showRejectedMatches = !showRejectedMatches"
          >
            <BaseIcon name="info" class="w-4 h-4" />
            {{ showRejectedMatches ? t('files.actors.hideRejectedMatches') : t('files.actors.showRejectedMatches', { count: rejectedMatches.length }) }}
          </VuiButton>
          <button type="button" class="duplicate-panel__close" @click="showMappingMatches = false">
            <BaseIcon name="close" />
          </button>
        </div>
      </div>

      <div v-if="showRejectedMatches" class="rejected-panel">
        <article v-for="actor in rejectedMatches" :key="`${actor.id}-${actor.rejected_mapping_id}-${actor.rejected_reason}`" class="rejected-row">
          <button type="button" class="rejected-row__actor" @click="openActor(actor)">
            <span class="duplicate-member__avatar">
              <img v-if="actor.image_url" :src="actor.image_url" :alt="actor.name" loading="lazy" />
              <span v-else>{{ actorInitial(actor.name) }}</span>
            </span>
            <span class="duplicate-member__body">
              <span>{{ actorRawName(actor) }}</span>
              <em>
                <template v-if="actorDisplayAlias(actor)">{{ actorDisplayAlias(actor) }}</template>
                <template v-if="actor.tmdb_id"> · Emby TMDB {{ actor.tmdb_id }}</template>
              </em>
            </span>
          </button>
          <div class="rejected-row__mapping">
            <strong>{{ actor.rejected_mapping_name || actor.rejected_mapping_id || '-' }}</strong>
            <span>{{ rejectedReasonLabel(actor.rejected_reason) }}</span>
            <em v-if="actor.rejected_mapping_tmdb_id">Mapping TMDB {{ actor.rejected_mapping_tmdb_id }}</em>
          </div>
        </article>
      </div>

      <div v-if="mappingMatches.groups?.length" class="duplicate-groups">
        <article v-for="group in mappingMatches.groups" :key="group.mapping_id" class="duplicate-group" :class="{ 'has-conflict': group.has_tmdb_conflict }">
          <div class="duplicate-group__title">
            <div>
              <strong>{{ mappingGroupName(group) }}</strong>
              <em v-if="selectedMergeTargetName(group)">{{ t('files.actors.mergeTarget') }} {{ selectedMergeTargetName(group) }}</em>
            </div>
            <span>{{ group.count }}</span>
          </div>
          <div class="mapping-alias-line">
            <span v-if="group.has_tmdb_conflict" class="is-danger">{{ t('files.actors.tmdbConflict') }}</span>
            <span v-if="group.jp">{{ group.jp }}</span>
            <span v-if="group.zh_tw">{{ group.zh_tw }}</span>
            <span v-if="group.tmdb_id">TMDB {{ group.tmdb_id }}</span>
            <span v-if="group.missing_tmdb_count">{{ t('files.actors.missingTmdb', { count: group.missing_tmdb_count }) }}</span>
            <span v-if="group.missing_image_count">{{ t('files.actors.missingImage', { count: group.missing_image_count }) }}</span>
          </div>
          <div class="merge-actions">
            <VuiButton variant="outlined" color="secondary" size="small" :disabled="mergePlanLoading[group.mapping_id]" @click="loadMergePlan(group)">
              <BaseIcon name="search" class="w-4 h-4" />
              {{ t('files.actors.previewMergePlan') }}
            </VuiButton>
            <VuiButton
              v-if="mergePlanActionable(mergePlans[group.mapping_id])"
              variant="gradient"
              color="primary"
              size="small"
              :disabled="mergeExecuting[group.mapping_id]"
              @click="executeMergePlan(group)"
            >
              <BaseIcon name="check" class="w-4 h-4" />
              {{ t('files.actors.executeMerge') }}
            </VuiButton>
          </div>
          <div v-if="mergePlans[group.mapping_id]" class="merge-plan">
            <div class="merge-plan__summary">
              <span>{{ t('files.actors.mergePlanTarget') }} <strong>{{ mergePlans[group.mapping_id].target_name }}</strong></span>
              <span>{{ t('files.actors.mergePlanMovies', { count: mergePlans[group.mapping_id].movie_count || 0 }) }}</span>
              <span v-if="mergePlanEmptyActorCount(mergePlans[group.mapping_id])">{{ t('files.actors.mergePlanEmptyActors', { count: mergePlanEmptyActorCount(mergePlans[group.mapping_id]) }) }}</span>
            </div>
            <div v-if="mergePlans[group.mapping_id].movies?.length" class="merge-plan__movies">
              <article v-for="movie in mergePlans[group.mapping_id].movies.slice(0, 8)" :key="movie.id" class="merge-movie">
                <strong>{{ movie.name }}</strong>
                <span>{{ changedPeopleLabel(movie) }} -> {{ movie.target_name }}</span>
              </article>
              <div v-if="mergePlans[group.mapping_id].movies.length > 8" class="merge-plan__more">
                {{ t('files.actors.mergePlanMore', { count: mergePlans[group.mapping_id].movies.length - 8 }) }}
              </div>
            </div>
            <div v-else class="merge-plan__empty">{{ t('files.actors.mergePlanEmpty') }}</div>
          </div>
          <div class="duplicate-members">
            <button
              v-for="actor in group.actors"
              :key="actor.id"
              type="button"
              class="duplicate-member"
              :class="{ 'is-target': String(actor.id) === selectedMergeTargetId(group), 'has-conflict': actorHasConflict(group, actor) }"
              @click="selectMergeTarget(group, actor)"
            >
              <span class="duplicate-member__avatar">
                <img v-if="actor.image_url" :src="actor.image_url" :alt="actor.name" loading="lazy" />
                <span v-else>{{ actorInitial(actor.name) }}</span>
              </span>
              <span class="duplicate-member__body">
                <span>{{ actorRawName(actor) }}</span>
                <em>
                  <template v-if="actorDisplayAlias(actor)">{{ actorDisplayAlias(actor) }}</template>
                  <template v-else>{{ actor.name }}</template>
                  <template v-if="actor.tmdb_id"> · TMDB {{ actor.tmdb_id }}</template>
                  <template v-if="actor.mapping_warning_reason"> · {{ rejectedReasonLabel(actor.mapping_warning_reason) }}</template>
                </em>
              </span>
            </button>
          </div>
        </article>
      </div>
      <div v-else class="actor-empty actor-empty--compact">{{ t('files.actors.noMappingCandidates') }}</div>
    </section>

    <section class="noor-control-panel actor-filter-panel">
      <div class="noor-control-panel__row noor-control-panel__row--primary">
        <div class="noor-control-panel__group">
          <span class="noor-control-panel__group-label">{{ t('files.actors.sortBy') }}</span>
          <div class="noor-control-panel__group-items">
            <button type="button" class="actor-chip" :class="{ 'is-active': sortBy === 'SortName' && sortOrder === 'Ascending' }" @click="setSort('SortName', 'Ascending')">
              {{ t('files.actors.sortNameAsc') }}
            </button>
            <button type="button" class="actor-chip" :class="{ 'is-active': sortBy === 'DateCreated' && sortOrder === 'Descending' }" @click="setSort('DateCreated', 'Descending')">
              {{ t('files.actors.sortRecent') }}
            </button>
          </div>
        </div>
      </div>
    </section>

    <div v-if="loading" class="actor-loading">
      <BaseIcon name="loading" class="actor-loading__icon" />
    </div>

    <div v-else-if="!actors.length" class="actor-empty ui-card">
      <BaseIcon name="user" class="actor-empty__icon" />
      <span>{{ t('files.actors.empty') }}</span>
    </div>

    <div v-else class="actor-grid">
      <article v-for="actor in actors" :key="actor.id" class="actor-card ui-card" @click="openActor(actor)">
        <div class="actor-card__avatar">
          <img v-if="actor.image_url" :src="actor.image_url" :alt="actorName(actor)" loading="lazy" />
          <span v-else>{{ actorInitial(actorName(actor)) }}</span>
        </div>
        <div class="actor-card__body">
          <h3>{{ actorName(actor) }}</h3>
        </div>
      </article>
    </div>

    <NoorPagination v-model:page="page" :total-pages="totalPages" />
  </div>
</template>

<style scoped>
.actor-management {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.actor-actions {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex-wrap: wrap;
}

:deep(.actor-action-button--danger) {
  border-color: color-mix(in srgb, var(--color-danger, #ff4d6d) 60%, transparent);
  color: var(--color-danger, #ff6b81);
}

.actor-file-input {
  display: none;
}

.actor-language-switch {
  display: inline-flex;
  align-items: center;
  gap: 0.2rem;
  min-height: 2.25rem;
  padding: 0.18rem;
  border: 1px solid var(--color-border-subtle);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.045);
}

.actor-language-switch button {
  min-width: 3rem;
  height: 1.8rem;
  border: 0;
  border-radius: 999px;
  padding: 0 0.65rem;
  background: transparent;
  color: var(--color-text-muted);
  font-size: 0.76rem;
  font-weight: 850;
  cursor: pointer;
}

.actor-language-switch button.is-active {
  background: rgba(0, 117, 255, 0.18);
  color: var(--color-text-primary);
}

.actor-search {
  position: relative;
  min-width: min(22rem, 100%);
}

.actor-search__icon {
  position: absolute;
  left: 0.75rem;
  top: 50%;
  width: 1rem;
  height: 1rem;
  transform: translateY(-50%);
  color: var(--color-text-muted);
}

.actor-search__input {
  width: 100%;
  min-height: 2.25rem;
  padding: 0 0.8rem 0 2.2rem;
  border-radius: var(--radius-md);
  border: 1px solid var(--color-border-subtle);
  background: rgba(255, 255, 255, 0.05);
  color: var(--color-text-primary);
  font-size: 0.86rem;
  outline: none;
}

.actor-search__input:focus {
  border-color: rgba(0, 117, 255, 0.52);
  box-shadow: 0 0 0 3px rgba(0, 117, 255, 0.16);
}

.mapping-status {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.4rem;
}

.mapping-status span {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  min-height: 1.55rem;
  padding: 0 0.6rem;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.06);
  color: var(--color-text-secondary);
  font-size: 0.74rem;
  font-weight: 800;
}

.mapping-status strong {
  color: var(--color-text-primary);
}

.actor-filter-panel {
  padding: 0.7rem 0.85rem;
}

.actor-chip {
  min-height: 2rem;
  padding: 0 0.78rem;
  border-radius: 999px;
  border: 1px solid var(--color-border-subtle);
  background: rgba(255, 255, 255, 0.04);
  color: var(--color-text-secondary);
  font-size: 0.78rem;
  font-weight: 700;
}

.actor-chip:hover,
.actor-chip.is-active {
  color: var(--color-text-primary);
  border-color: rgba(0, 117, 255, 0.48);
  background: rgba(0, 117, 255, 0.16);
}

.duplicate-panel {
  padding: 1rem;
}

.duplicate-panel__head {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  align-items: flex-start;
  margin-bottom: 0.85rem;
}

.duplicate-panel__head h2 {
  margin: 0;
  font-size: 1rem;
  font-weight: 800;
  color: var(--color-text-primary);
}

.duplicate-panel__head span {
  display: block;
  margin-top: 0.2rem;
  font-size: 0.78rem;
  color: var(--color-text-muted);
}

.duplicate-panel__tools {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  flex: 0 0 auto;
}

.duplicate-panel__close {
  width: 2rem;
  height: 2rem;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-md);
  color: var(--color-text-muted);
  background: rgba(255, 255, 255, 0.04);
}

.duplicate-panel__close svg {
  width: 1rem;
  height: 1rem;
}

.duplicate-groups {
  display: grid;
  gap: 0.7rem;
}

.rejected-panel {
  display: grid;
  gap: 0.55rem;
  margin-bottom: 0.85rem;
  padding: 0.7rem;
  border: 1px solid rgba(255, 181, 71, 0.22);
  border-radius: var(--radius-md);
  background: rgba(255, 181, 71, 0.045);
}

.rejected-row {
  display: grid;
  grid-template-columns: minmax(0, 1.1fr) minmax(0, 1fr);
  gap: 0.65rem;
  align-items: center;
  padding: 0.55rem;
  border: 1px solid var(--color-border-subtle);
  border-radius: var(--radius-md);
  background: rgba(255, 255, 255, 0.035);
}

.rejected-row__actor {
  min-width: 0;
  display: grid;
  grid-template-columns: 2.5rem minmax(0, 1fr);
  gap: 0.55rem;
  align-items: center;
  color: inherit;
  text-align: left;
}

.rejected-row__mapping {
  min-width: 0;
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
  align-items: center;
  justify-content: flex-end;
}

.rejected-row__mapping strong,
.rejected-row__mapping span,
.rejected-row__mapping em {
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  padding: 0.18rem 0.45rem;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.06);
  color: var(--color-text-muted);
  font-size: 0.7rem;
  font-style: normal;
  font-weight: 750;
}

.rejected-row__mapping strong {
  color: var(--color-text-primary);
}

.rejected-row__mapping span {
  background: rgba(255, 181, 71, 0.14);
  color: rgb(255, 216, 154);
}

.tmdb-backfill-panel {
  display: grid;
  gap: 0.75rem;
}

.name-sync-panel {
  display: grid;
  gap: 0.75rem;
  padding: 1rem;
}

.name-sync-list,
.name-sync-conflicts {
  display: grid;
  gap: 0.5rem;
  max-height: min(70vh, 48rem);
  overflow-y: auto;
  padding-right: 0.2rem;
}

.name-sync-conflicts {
  padding: 0.7rem;
  border: 1px solid rgba(255, 181, 71, 0.24);
  border-radius: var(--radius-md);
  background: rgba(255, 181, 71, 0.045);
}

.name-sync-conflicts > strong {
  color: rgb(255, 216, 154);
  font-size: 0.8rem;
  font-weight: 850;
}

.name-sync-progress {
  display: grid;
  gap: 0.45rem;
  padding: 0.65rem 0.75rem;
  border: 1px solid rgba(0, 117, 255, 0.22);
  border-radius: var(--radius-md);
  background: rgba(0, 117, 255, 0.06);
}

.name-sync-progress__head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
}

.name-sync-progress__head strong {
  color: var(--color-text-primary);
  font-size: 0.82rem;
  font-weight: 850;
}

.name-sync-progress__head span,
.name-sync-progress em {
  color: var(--color-text-muted);
  font-size: 0.72rem;
  font-style: normal;
  font-weight: 750;
}

.name-sync-progress__bar {
  width: 100%;
  height: 0.45rem;
  overflow: hidden;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.08);
}

.name-sync-progress__bar span {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, rgba(0, 117, 255, 0.86), rgba(86, 211, 255, 0.9));
  transition: width 0.24s ease;
}

.name-sync-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1.2fr);
  gap: 0.65rem;
  align-items: center;
  padding: 0.6rem;
  border: 1px solid rgba(0, 117, 255, 0.2);
  border-radius: var(--radius-md);
  background: rgba(0, 117, 255, 0.055);
}

.name-sync-row.is-conflict {
  border-color: rgba(255, 181, 71, 0.24);
  background: rgba(255, 181, 71, 0.05);
}

.name-sync-row__actor {
  min-width: 0;
  display: grid;
  gap: 0.2rem;
  color: inherit;
  text-align: left;
}

.name-sync-row__actor span,
.name-sync-row__actor em {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.name-sync-row__actor span {
  color: var(--color-text-primary);
  font-size: 0.82rem;
  font-weight: 850;
}

.name-sync-row__actor em {
  color: var(--color-text-muted);
  font-size: 0.72rem;
  font-style: normal;
}

.name-sync-row__meta {
  min-width: 0;
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 0.35rem;
}

.name-sync-row__meta span,
.name-sync-row__meta em {
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  padding: 0.18rem 0.5rem;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.06);
  color: var(--color-text-secondary);
  font-size: 0.7rem;
  font-style: normal;
  font-weight: 800;
}

.name-sync-row.is-conflict .name-sync-row__meta em {
  color: rgb(255, 216, 154);
  background: rgba(255, 181, 71, 0.14);
}

.tmdb-backfill-list {
  display: grid;
  gap: 0.5rem;
  max-height: min(70vh, 48rem);
  overflow-y: auto;
  padding-right: 0.2rem;
}

.tmdb-backfill-progress {
  display: grid;
  gap: 0.45rem;
  padding: 0.65rem 0.75rem;
  border: 1px solid rgba(0, 117, 255, 0.22);
  border-radius: var(--radius-md);
  background: rgba(0, 117, 255, 0.06);
}

.tmdb-backfill-progress__head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
}

.tmdb-backfill-progress__head strong {
  color: var(--color-text-primary);
  font-size: 0.82rem;
  font-weight: 850;
}

.tmdb-backfill-progress__head span,
.tmdb-backfill-progress em {
  color: var(--color-text-muted);
  font-size: 0.72rem;
  font-style: normal;
  font-weight: 750;
}

.tmdb-backfill-progress__bar {
  width: 100%;
  height: 0.45rem;
  overflow: hidden;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.08);
}

.tmdb-backfill-progress__bar span {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, rgba(0, 117, 255, 0.86), rgba(86, 211, 255, 0.9));
  transition: width 0.24s ease;
}

.tmdb-backfill-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1.2fr);
  gap: 0.65rem;
  align-items: center;
  padding: 0.6rem;
  border: 1px solid rgba(0, 117, 255, 0.2);
  border-radius: var(--radius-md);
  background: rgba(0, 117, 255, 0.055);
}

.tmdb-backfill-row.is-review {
  border-color: rgba(255, 181, 71, 0.22);
  background: rgba(255, 181, 71, 0.045);
}

.tmdb-backfill-row__actor {
  min-width: 0;
  display: grid;
  gap: 0.2rem;
  color: inherit;
  text-align: left;
}

.tmdb-backfill-row__actor span,
.tmdb-backfill-row__actor em {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tmdb-backfill-row__actor span {
  color: var(--color-text-primary);
  font-size: 0.82rem;
  font-weight: 850;
}

.tmdb-backfill-row__actor em {
  color: var(--color-text-muted);
  font-size: 0.72rem;
  font-style: normal;
}

.tmdb-backfill-row__meta {
  min-width: 0;
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 0.35rem;
}

.tmdb-backfill-row__meta a,
.tmdb-backfill-row__meta span,
.tmdb-backfill-row__meta em,
.tmdb-backfill-row__review {
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  padding: 0.18rem 0.5rem;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.06);
  color: var(--color-text-secondary);
  font-size: 0.7rem;
  font-style: normal;
  font-weight: 800;
}

.tmdb-backfill-row__meta a {
  color: var(--color-text-primary);
  text-decoration: none;
}

.tmdb-backfill-row__meta a:hover {
  border-color: rgba(0, 117, 255, 0.35);
  background: rgba(0, 117, 255, 0.14);
}

.tmdb-backfill-row__review {
  color: rgb(255, 216, 154);
  background: rgba(255, 181, 71, 0.14);
  cursor: pointer;
}

.tmdb-backfill-row__review:hover:not(:disabled) {
  background: rgba(255, 181, 71, 0.22);
}

.tmdb-backfill-row__review:disabled {
  cursor: progress;
  opacity: 0.65;
}

.duplicate-group {
  padding: 0.75rem;
  border: 1px solid var(--color-border-subtle);
  border-radius: var(--radius-md);
  background: rgba(255, 255, 255, 0.035);
}

.duplicate-group.has-conflict {
  border-color: rgba(255, 87, 87, 0.38);
  background: rgba(255, 87, 87, 0.055);
}

.duplicate-group__title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  margin-bottom: 0.6rem;
}

.duplicate-group__title div {
  min-width: 0;
  display: grid;
  gap: 0.18rem;
}

.duplicate-group__title strong {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--color-text-primary);
  font-size: 0.88rem;
}

.duplicate-group__title em {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--color-text-muted);
  font-size: 0.72rem;
  font-style: normal;
  font-weight: 700;
}

.duplicate-group__title span {
  flex: 0 0 auto;
  min-width: 1.45rem;
  height: 1.45rem;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.08);
  color: var(--color-text-secondary);
  font-size: 0.72rem;
  font-weight: 800;
}

.mapping-alias-line {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
  margin: -0.2rem 0 0.6rem;
}

.mapping-alias-line span {
  max-width: 14rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  padding: 0.18rem 0.45rem;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.06);
  color: var(--color-text-muted);
  font-size: 0.7rem;
  font-weight: 700;
}

.mapping-alias-line span.is-danger {
  background: rgba(255, 87, 87, 0.14);
  color: rgb(255, 164, 164);
}

.merge-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.45rem;
  margin: 0.65rem 0;
}

.merge-plan {
  display: grid;
  gap: 0.55rem;
  margin: 0.65rem 0;
  padding: 0.65rem;
  border: 1px solid var(--color-border-subtle);
  border-radius: var(--radius-md);
  background: rgba(0, 0, 0, 0.16);
}

.merge-plan__summary {
  display: flex;
  flex-wrap: wrap;
  gap: 0.45rem;
}

.merge-plan__summary span,
.merge-plan__more,
.merge-plan__empty {
  min-height: 1.45rem;
  display: inline-flex;
  align-items: center;
  width: fit-content;
  padding: 0 0.5rem;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.06);
  color: var(--color-text-secondary);
  font-size: 0.7rem;
  font-weight: 800;
}

.merge-plan__summary strong {
  margin-left: 0.25rem;
  color: var(--color-text-primary);
}

.merge-plan__movies {
  display: grid;
  gap: 0.4rem;
}

.merge-movie {
  display: grid;
  gap: 0.2rem;
  padding: 0.45rem 0.55rem;
  border-radius: var(--radius-md);
  background: rgba(255, 255, 255, 0.04);
}

.merge-movie strong,
.merge-movie span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.merge-movie strong {
  color: var(--color-text-primary);
  font-size: 0.78rem;
}

.merge-movie span {
  color: var(--color-text-muted);
  font-size: 0.7rem;
  font-weight: 700;
}

.duplicate-members {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(13rem, 1fr));
  gap: 0.5rem;
}

.duplicate-member {
  display: flex;
  align-items: center;
  gap: 0.55rem;
  padding: 0.45rem;
  border: 1px solid transparent;
  border-radius: var(--radius-md);
  background: rgba(255, 255, 255, 0.04);
  text-align: left;
}

.duplicate-member.is-target {
  border-color: rgba(0, 117, 255, 0.42);
  background: rgba(0, 117, 255, 0.1);
}

.duplicate-member.has-conflict {
  border-color: rgba(255, 87, 87, 0.38);
  background: rgba(255, 87, 87, 0.08);
}

.duplicate-member__avatar,
.actor-card__avatar {
  flex: 0 0 auto;
  overflow: hidden;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, rgba(0, 117, 255, 0.28), rgba(255, 255, 255, 0.08));
  color: var(--color-text-primary);
  font-weight: 800;
}

.duplicate-member__avatar {
  width: 2.25rem;
  height: 2.25rem;
  border-radius: 999px;
}

.duplicate-member__avatar img,
.actor-card__avatar img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.duplicate-member__body {
  min-width: 0;
  display: grid;
}

.duplicate-member__body span,
.duplicate-member__body em {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.duplicate-member__body span {
  color: var(--color-text-primary);
  font-size: 0.82rem;
  font-weight: 700;
}

.duplicate-member__body em {
  color: var(--color-text-muted);
  font-size: 0.72rem;
  font-style: normal;
}

.actor-loading {
  min-height: 18rem;
  display: flex;
  align-items: center;
  justify-content: center;
}

.actor-loading__icon {
  width: 2rem;
  height: 2rem;
  color: var(--color-text-muted);
}

.actor-empty {
  min-height: 18rem;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.55rem;
  color: var(--color-text-muted);
}

.actor-empty--compact {
  min-height: 4rem;
  border: 1px dashed var(--color-border-subtle);
  border-radius: var(--radius-md);
}

.actor-empty__icon {
  width: 1.1rem;
  height: 1.1rem;
}

.actor-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(17rem, 1fr));
  gap: 0.85rem;
}

.actor-card {
  display: grid;
  grid-template-columns: 4.5rem minmax(0, 1fr);
  align-items: center;
  gap: 0.8rem;
  padding: 0.8rem;
  cursor: pointer;
  transition: transform var(--transition-fast), border-color var(--transition-fast), background var(--transition-fast);
}

.actor-card:hover {
  transform: translateY(-1px);
  border-color: rgba(0, 117, 255, 0.42);
  background: rgba(255, 255, 255, 0.06);
}

.actor-card__avatar {
  width: 4.5rem;
  height: 4.5rem;
  border-radius: var(--radius-md);
  font-size: 1.35rem;
}

.actor-card__body {
  min-width: 0;
}

.actor-card__body h3 {
  margin: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--color-text-primary);
  font-size: 0.94rem;
  font-weight: 800;
}

@media (max-width: 720px) {
  .page-header,
  .actor-actions,
  .duplicate-panel__head {
    align-items: stretch;
    flex-direction: column;
  }

  .actor-search {
    width: 100%;
  }

  .duplicate-panel__tools {
    justify-content: space-between;
    width: 100%;
  }

  .rejected-row {
    grid-template-columns: 1fr;
  }

  .rejected-row__mapping {
    justify-content: flex-start;
  }

  .actor-grid {
    grid-template-columns: 1fr;
  }
}
</style>
