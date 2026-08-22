<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '../api'
import BaseIcon from '../components/noor/BaseIcon.vue'
import MediaCard from '../components/noor/MediaCard.vue'
import BaseModal from '../components/ui/BaseModal.vue'
import VuiButton from '../components/ui/Button/VuiButton.vue'
import NoorPagination from '../components/ui/Pagination.vue'
import { useI18n } from '../composables/useI18n'
import { useConfirm } from '../composables/useConfirm'
import { useToast } from '../composables/useToast'
import type { MediaActor, MediaItem } from '../api/types'

const route = useRoute()
const router = useRouter()
const toast = useToast()
const { confirm } = useConfirm()
const { t, currentLang } = useI18n()

const actor = ref<MediaActor | null>(null)
const movies = ref<MediaItem[]>([])
const loading = ref(false)
const saving = ref(false)
const editMode = ref(false)
const deleting = ref(false)
const overviewExpanded = ref(false)
const uploadingAvatar = ref(false)
const tmdbLoading = ref(false)
const tmdbApplying = ref(false)
const tmdbModalOpen = ref(false)
const tmdbPreview = ref<any | null>(null)
const tmdbApplyName = ref(false)
const tmdbApplyAvatar = ref(false)
const avatarModalOpen = ref(false)
const avatarCandidatesLoading = ref(false)
const avatarCandidates = ref<any[]>([])
const moviesLoading = ref(false)
const deleteDiagnosticsLoading = ref(false)
const deleteDiagnostics = ref<any | null>(null)
const providerRemoving = ref<Record<string, boolean>>({})
const fileInput = ref<HTMLInputElement | null>(null)
const page = ref(1)
const pageSize = 48
const total = ref(0)
let actorLoadSeq = 0
const form = ref({
  selected_name: '',
  name: '',
  sort_name: '',
  jp_name: '',
  zh_cn_name: '',
  zh_tw_name: '',
  aliases: '',
  overview: '',
  tmdb: '',
  imdb: '',
  birthday: '',
  deathday: '',
  place_of_birth: '',
  gender: '',
  known_for_department: '',
  popularity: '',
  homepage: '',
})

const actorId = computed(() => String(route.params.actorId || ''))
const actorNameLang = computed(() => String(route.query.actorLang || currentLang.value || 'zh-CN'))
const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize)))
const displayName = computed(() => actor.value?.identity_names?.selected_name || actor.value?.display_name || actor.value?.name || '')
const mediaServerName = computed(() => actor.value?.media_server?.name || 'Emby / Jellyfin')
const externalUrls = computed(() => actor.value?.external_urls || {})
const backTarget = computed(() => {
  const value = String(route.query.returnTo || '')
  return value.startsWith('/') ? value : '/files/actors'
})
const tmdbUrl = computed(() => externalUrls.value.tmdb || (actor.value?.tmdb_id ? `https://www.themoviedb.org/person/${encodeURIComponent(actor.value.tmdb_id)}` : ''))
const imdbUrl = computed(() => externalUrls.value.imdb || (actor.value?.imdb_id ? `https://www.imdb.com/name/${encodeURIComponent(actor.value.imdb_id)}/` : ''))
const socialLinks = computed(() => [
  { key: 'media-server', label: mediaServerName.value, icon: 'brandEmby', url: actor.value?.emby_url },
  { key: 'tmdb', label: 'TMDB', icon: 'brandTmdb', url: tmdbUrl.value },
  { key: 'imdb', label: 'IMDB', icon: 'brandImdb', url: imdbUrl.value },
  { key: 'x', label: 'X', icon: 'brandX', url: externalUrls.value.x },
  { key: 'instagram', label: 'Instagram', icon: 'brandInstagram', url: externalUrls.value.instagram },
  { key: 'tiktok', label: 'TikTok', icon: 'brandTiktok', url: externalUrls.value.tiktok },
  { key: 'youtube', label: 'YouTube', icon: 'brandYoutube', url: externalUrls.value.youtube },
  { key: 'facebook', label: 'Facebook', icon: 'brandFacebook', url: externalUrls.value.facebook },
  { key: 'wikidata', label: 'Wikidata', icon: 'brandWikidata', url: externalUrls.value.wikidata },
  { key: 'homepage', label: 'Homepage', icon: 'externalLink', url: externalUrls.value.homepage || actor.value?.homepage },
].filter(item => !!item.url))
const canFetchTmdb = computed(() => !!(form.value.tmdb.trim() || form.value.imdb.trim() || actor.value?.tmdb_id || actor.value?.imdb_id))
const overviewTooLong = computed(() => (form.value.overview || '').length > 180)
const gfriendsSearchName = computed(() => actor.value?.identity_names?.jp || form.value.jp_name || displayName.value || form.value.name)
const aliasTags = computed(() => form.value.aliases.split(/\n|,/).map(item => item.trim()).filter(Boolean))
const actorAliases = computed(() => {
  const names = [
    actor.value?.display_name,
    actor.value?.identity_names?.jp,
    actor.value?.identity_names?.zh_cn,
    actor.value?.identity_names?.zh_tw,
    ...(actor.value?.identity_names?.aliases || []),
    actor.value?.name,
    form.value.name,
    form.value.sort_name,
  ].filter(Boolean) as string[]
  return Array.from(new Set(names.filter(name => name !== displayName.value)))
})
const providerIdEntries = computed(() => Object.entries(actor.value?.provider_ids || {}).filter(([_key, value]) => String(value || '').trim()))
const diagnosticTypeLabels: Record<string, string> = {
  Movie: 'Movie',
  Series: 'Series',
  Episode: 'Episode',
  MusicVideo: 'MusicVideo',
  Video: 'Video',
  Trailer: 'Trailer',
  BoxSet: 'BoxSet',
  Playlist: 'Playlist',
}

function actorInitial(name: string) {
  return (name || '?').trim().slice(0, 1).toUpperCase()
}

function syncForm(nextActor: MediaActor | null) {
  form.value = {
    selected_name: nextActor?.identity_names?.selected_name || nextActor?.display_name || nextActor?.name || '',
    name: nextActor?.name || '',
    sort_name: nextActor?.sort_name || nextActor?.name || '',
    jp_name: nextActor?.identity_names?.jp || '',
    zh_cn_name: nextActor?.identity_names?.zh_cn || '',
    zh_tw_name: nextActor?.identity_names?.zh_tw || '',
    aliases: (nextActor?.identity_names?.aliases || []).join('\n'),
    overview: nextActor?.overview || '',
    tmdb: nextActor?.tmdb_id || '',
    imdb: nextActor?.imdb_id || '',
    birthday: normalizeDate(nextActor?.birthday || nextActor?.premiere_date || ''),
    deathday: normalizeDate(nextActor?.deathday || ''),
    place_of_birth: nextActor?.place_of_birth || '',
    gender: nextActor?.gender || '',
    known_for_department: nextActor?.known_for_department || '',
    popularity: nextActor?.popularity != null ? String(nextActor.popularity) : '',
    homepage: nextActor?.homepage || nextActor?.external_urls?.homepage || '',
  }
}

function normalizeDate(value?: string) {
  const text = String(value || '').trim()
  return text ? text.slice(0, 10) : ''
}

function actorAge(birthday?: string, deathday?: string) {
  const birth = normalizeDate(birthday)
  if (!birth) return ''
  const start = new Date(`${birth}T00:00:00`)
  if (Number.isNaN(start.getTime())) return ''
  const endText = normalizeDate(deathday)
  const end = endText ? new Date(`${endText}T00:00:00`) : new Date()
  let age = end.getFullYear() - start.getFullYear()
  const monthDelta = end.getMonth() - start.getMonth()
  if (monthDelta < 0 || (monthDelta === 0 && end.getDate() < start.getDate())) age -= 1
  return age >= 0 ? String(age) : ''
}

function birthdayLabel() {
  const birthday = form.value.birthday
  if (!birthday) return '-'
  const age = actorAge(birthday, form.value.deathday)
  return age ? `${birthday} (${age})` : birthday
}

function goBack() {
  router.push(backTarget.value)
}

async function loadActor() {
  if (!actorId.value) return
  const seq = ++actorLoadSeq
  loading.value = true
  try {
    const resp = await api.get(`/media-library/actor/${encodeURIComponent(actorId.value)}`, {
      params: { lang: actorNameLang.value },
    })
    actor.value = resp.data.actor || null
    syncForm(actor.value)
    editMode.value = false
    overviewExpanded.value = false
    deleteDiagnostics.value = null
    void enrichActorFromTmdb(seq)
  } catch (error: any) {
    actor.value = null
    toast.error(error?.response?.data?.detail || error?.message || t('files.actors.detailLoadFailed'))
  } finally {
    loading.value = false
  }
}

function mergeMissingActorMetadata(current: MediaActor, proposal: any): MediaActor {
  const nextExternalUrls = {
    ...(proposal?.external_urls || {}),
    ...(current.external_urls || {}),
  }
  const nextProviderIds = {
    ...(current.provider_ids || {}),
    ...(proposal?.provider_ids || {}),
  }
  return {
    ...current,
    tmdb_id: current.tmdb_id || proposal?.tmdb_id,
    imdb_id: current.imdb_id || proposal?.imdb_id,
    provider_ids: nextProviderIds,
    external_urls: nextExternalUrls,
    birthday: current.birthday || proposal?.birthday,
    deathday: current.deathday || proposal?.deathday,
    place_of_birth: current.place_of_birth || proposal?.place_of_birth,
    gender: current.gender || proposal?.gender,
    known_for_department: current.known_for_department || proposal?.known_for_department,
    popularity: current.popularity ?? proposal?.popularity,
    homepage: current.homepage || proposal?.homepage || nextExternalUrls.homepage,
    overview: current.overview || proposal?.overview,
  }
}

async function enrichActorFromTmdb(seq: number) {
  if (!actorId.value || !actor.value || editMode.value) return
  if (!actor.value.tmdb_id && !actor.value.imdb_id) return
  try {
    const resp = await api.post(`/media-library/actor/${encodeURIComponent(actorId.value)}/metadata/tmdb-preview`, null, {
      params: { lang: currentLang.value },
    })
    if (seq !== actorLoadSeq || !actor.value || editMode.value) return
    actor.value = mergeMissingActorMetadata(actor.value, resp.data?.proposal || {})
    syncForm(actor.value)
  } catch {
    // TMDB enrichment is best-effort; the saved Emby/NOOR profile remains usable.
  }
}

async function loadMovies() {
  if (!actorId.value) return
  moviesLoading.value = true
  try {
    const resp = await api.get(`/media-library/actor/${encodeURIComponent(actorId.value)}/movies`, {
      params: { limit: pageSize, offset: (page.value - 1) * pageSize },
    })
    movies.value = resp.data.items || []
    total.value = resp.data.total || 0
  } catch (error: any) {
    movies.value = []
    total.value = 0
    toast.error(error?.response?.data?.detail || error?.message || t('files.actors.moviesLoadFailed'))
  } finally {
    moviesLoading.value = false
  }
}

async function saveActor() {
  if (!actorId.value) return
  if (!editMode.value) {
    editMode.value = true
    return
  }
  saving.value = true
  try {
    const providerIds: Record<string, string> = {
      Tmdb: form.value.tmdb.trim(),
      Imdb: form.value.imdb.trim(),
    }
    const resp = await api.post(`/media-library/actor/${encodeURIComponent(actorId.value)}`, {
      name: form.value.name.trim(),
      sort_name: form.value.sort_name.trim(),
      jp_name: form.value.jp_name.trim(),
      zh_cn_name: form.value.zh_cn_name.trim(),
      zh_tw_name: form.value.zh_tw_name.trim(),
      aliases: form.value.aliases.split(/\n|,/).map(item => item.trim()).filter(Boolean),
      overview: form.value.overview,
      provider_ids: providerIds,
      birthday: form.value.birthday,
      deathday: form.value.deathday,
      place_of_birth: form.value.place_of_birth,
      gender: form.value.gender,
      known_for_department: form.value.known_for_department,
      popularity: form.value.popularity ? Number(form.value.popularity) : null,
      homepage: form.value.homepage,
      external_urls: {
        ...(actor.value?.external_urls || {}),
        ...(form.value.homepage ? { homepage: form.value.homepage } : {}),
      },
    }, {
      params: { lang: actorNameLang.value },
    })
    actor.value = resp.data.actor || actor.value
    syncForm(actor.value)
    editMode.value = false
    toast.success(resp.data.synced ? t('files.actors.detailSaveSuccess') : t('files.actors.detailSaveLocalOnly'))
  } catch (error: any) {
    toast.error(error?.response?.data?.detail || error?.message || t('files.actors.detailSaveFailed'))
  } finally {
    saving.value = false
  }
}

async function removeProviderId(providerKey: string) {
  const key = String(providerKey || '').trim()
  if (!actorId.value || !key || providerRemoving.value[key]) return
  const ok = await confirm({
    title: t('files.actors.providerRemoveTitle'),
    message: t('files.actors.providerRemoveConfirm', { provider: key }),
    confirmText: t('files.actors.providerRemove'),
    danger: true,
  })
  if (!ok) return
  providerRemoving.value = { ...providerRemoving.value, [key]: true }
  try {
    const resp = await api.post(`/media-library/actor/${encodeURIComponent(actorId.value)}`, {
      provider_ids: { [key]: '' },
    }, {
      params: { lang: actorNameLang.value },
    })
    actor.value = resp.data.actor || actor.value
    syncForm(actor.value)
    toast.success(resp.data.synced ? t('files.actors.providerRemoveSuccess') : t('files.actors.detailSaveLocalOnly'))
    if (deleteDiagnostics.value) void diagnoseDelete()
  } catch (error: any) {
    toast.error(error?.response?.data?.detail || error?.message || t('files.actors.providerRemoveFailed'))
  } finally {
    const next = { ...providerRemoving.value }
    delete next[key]
    providerRemoving.value = next
  }
}

function cancelEdit() {
  syncForm(actor.value)
  editMode.value = false
}

function openMovie(item: MediaItem) {
  router.push({ path: '/library', query: { q: item.name } })
}

function openDiagnosticItem(item: any) {
  router.push({ path: '/library', query: { q: item?.name || item?.id || '' } })
}

function openExternal(url?: string) {
  if (!url) return
  window.open(url, '_blank', 'noopener,noreferrer')
}

async function deleteActor() {
  if (!actorId.value || deleting.value) return
  const ok = await confirm({
    title: t('files.actors.deleteTitle'),
    message: t('files.actors.deleteConfirm', { name: displayName.value || actorId.value }),
    confirmText: t('common.delete'),
    danger: true,
  })
  if (!ok) return
  deleting.value = true
  try {
    await api.delete(`/media-library/actor/${encodeURIComponent(actorId.value)}`)
    toast.success(t('files.actors.deleteSuccess'))
    goBack()
  } catch (error: any) {
    toast.error(error?.response?.data?.detail || error?.message || t('files.actors.deleteFailed'))
  } finally {
    deleting.value = false
  }
}

function deleteBlockerLabel(reason: string) {
  if (reason === 'person_can_delete_false') return t('files.actors.deleteDiagnosticBlockerCanDelete')
  if (reason === 'person_still_has_related_items') return t('files.actors.deleteDiagnosticBlockerRelated')
  return reason || '-'
}

async function diagnoseDelete() {
  if (!actorId.value || deleteDiagnosticsLoading.value) return
  deleteDiagnosticsLoading.value = true
  try {
    const resp = await api.get(`/media-library/actor/${encodeURIComponent(actorId.value)}/delete-diagnostics`)
    deleteDiagnostics.value = resp.data || null
  } catch (error: any) {
    toast.error(error?.response?.data?.detail || error?.message || t('files.actors.deleteDiagnosticFailed'))
  } finally {
    deleteDiagnosticsLoading.value = false
  }
}

function chooseAvatarFile() {
  fileInput.value?.click()
}

async function uploadAvatar(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file || !actorId.value) return
  uploadingAvatar.value = true
  try {
    const data = new FormData()
    data.append('file', file)
    const resp = await api.post(`/media-library/actor/${encodeURIComponent(actorId.value)}/avatar`, data, {
      params: { lang: currentLang.value },
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    actor.value = resp.data.actor || actor.value
    toast.success(t('files.actors.avatarUpdated'))
  } catch (error: any) {
    toast.error(error?.response?.data?.detail || error?.message || t('files.actors.avatarUpdateFailed'))
  } finally {
    uploadingAvatar.value = false
    input.value = ''
  }
}

async function openAvatarPicker() {
  avatarModalOpen.value = true
  avatarCandidates.value = []
  avatarCandidatesLoading.value = true
  try {
    const resp = await api.post('/plugins/gfriends/actions/candidates', {
      payload: {
        name: gfriendsSearchName.value,
        aliases: actorAliases.value,
        limit: 36,
      },
    })
    avatarCandidates.value = resp.data.items || []
  } catch (error: any) {
    toast.error(error?.response?.data?.detail || error?.message || t('files.actors.avatarCandidatesFailed'))
  } finally {
    avatarCandidatesLoading.value = false
  }
}

async function selectAvatar(candidate: any) {
  const url = candidate?.remote_url || candidate?.url
  if (!url || !actorId.value) return
  uploadingAvatar.value = true
  try {
    const resp = await api.post(`/media-library/actor/${encodeURIComponent(actorId.value)}/avatar-url`, {
      url,
    }, {
      params: { lang: currentLang.value },
    })
    actor.value = resp.data.actor || actor.value
    avatarModalOpen.value = false
    toast.success(t('files.actors.avatarUpdated'))
  } catch (error: any) {
    toast.error(error?.response?.data?.detail || error?.message || t('files.actors.avatarUpdateFailed'))
  } finally {
    uploadingAvatar.value = false
  }
}

async function previewTmdbMetadata() {
  if (!actorId.value || tmdbLoading.value) return
  tmdbLoading.value = true
  tmdbPreview.value = null
  try {
    const resp = await api.post(`/media-library/actor/${encodeURIComponent(actorId.value)}/metadata/tmdb-preview`, null, {
      params: { lang: currentLang.value },
    })
    tmdbPreview.value = resp.data
    tmdbApplyName.value = false
    tmdbApplyAvatar.value = !!resp.data?.proposal?.image_url
    tmdbModalOpen.value = true
  } catch (error: any) {
    toast.error(error?.response?.data?.detail || error?.message || t('files.actors.tmdbPreviewFailed'))
  } finally {
    tmdbLoading.value = false
  }
}

async function applyTmdbMetadata() {
  if (!actorId.value || tmdbApplying.value) return
  tmdbApplying.value = true
  try {
    const resp = await api.post(`/media-library/actor/${encodeURIComponent(actorId.value)}/metadata/tmdb-apply`, {
      apply_name: tmdbApplyName.value,
      apply_overview: true,
      apply_provider_ids: true,
      apply_avatar: tmdbApplyAvatar.value,
    }, {
      params: { lang: currentLang.value },
    })
    actor.value = resp.data.actor || actor.value
    syncForm(actor.value)
    tmdbModalOpen.value = false
    if (resp.data.avatar_sync_error) {
      toast.warning(t('files.actors.tmdbApplyAvatarLocalOnly'))
    } else {
      toast.success(resp.data.synced ? t('files.actors.tmdbApplySuccess') : t('files.actors.detailSaveLocalOnly'))
    }
  } catch (error: any) {
    toast.error(error?.response?.data?.detail || error?.message || t('files.actors.tmdbApplyFailed'))
  } finally {
    tmdbApplying.value = false
  }
}

watch(page, loadMovies)
watch(currentLang, loadActor)
watch(actorNameLang, loadActor)
watch(actorId, () => {
  page.value = 1
  overviewExpanded.value = false
  loadActor()
  loadMovies()
})

onMounted(() => {
  loadActor()
  loadMovies()
})
</script>

<template>
  <div class="actor-detail">
    <div class="actor-detail__topbar">
      <button type="button" class="actor-icon-button actor-icon-button--back" :title="t('common.back')" :aria-label="t('common.back')" @click="goBack">
        <BaseIcon name="chevronLeft" class="w-4 h-4" />
      </button>
    </div>

    <section class="actor-profile ui-card">
      <div class="actor-profile__side">
        <div class="actor-profile__avatar">
          <img v-if="actor?.image_url" :src="actor.image_url" :alt="displayName" />
          <span v-else>{{ actorInitial(displayName) }}</span>
          <div v-if="editMode" class="actor-profile__avatar-actions">
            <VuiButton variant="gradient" color="primary" size="small" :disabled="uploadingAvatar" customClass="actor-action-button" @click="chooseAvatarFile">
              {{ t('files.actors.uploadAvatar') }}
            </VuiButton>
            <VuiButton variant="outlined" color="secondary" size="small" :disabled="uploadingAvatar" customClass="actor-action-button" @click="openAvatarPicker">
              Gfriends
            </VuiButton>
            <input ref="fileInput" class="actor-profile__file" type="file" accept="image/*" @change="uploadAvatar" />
          </div>
        </div>
        <div v-if="socialLinks.length" class="actor-profile__links">
          <button v-for="link in socialLinks" :key="link.key" :title="`${link.label}: ${link.url}`" :aria-label="link.label" @click="openExternal(link.url)">
            <BaseIcon :name="link.icon" class="actor-profile__link-icon" />
          </button>
        </div>
      </div>

      <div v-if="loading" class="actor-profile__loading">
        <BaseIcon name="loading" class="w-5 h-5" />
      </div>

      <div v-else class="actor-profile__content">
        <div class="actor-profile__head">
          <div>
            <h1>{{ displayName || t('files.actors.detailTitle') }}</h1>
            <p v-if="actor?.name && actor.display_name && actor.name !== actor.display_name">{{ actor.name }}</p>
          </div>
          <div class="actor-profile__actions">
            <VuiButton v-if="editMode && canFetchTmdb" variant="outlined" color="secondary" size="small" :disabled="tmdbLoading" customClass="actor-action-button" @click="previewTmdbMetadata">
              {{ t('files.actors.tmdbFill') }}
            </VuiButton>
            <VuiButton v-if="editMode" variant="outlined" color="secondary" size="small" customClass="actor-action-button" @click="cancelEdit">
              {{ t('common.cancel') }}
            </VuiButton>
            <VuiButton variant="outlined" color="secondary" size="small" :disabled="deleteDiagnosticsLoading" customClass="actor-action-button" @click="diagnoseDelete">
              {{ t('files.actors.deleteDiagnostic') }}
            </VuiButton>
            <VuiButton v-if="editMode" variant="gradient" color="primary" size="small" :disabled="saving" customClass="actor-action-button" @click="saveActor">
              {{ t('common.save') }}
            </VuiButton>
            <button v-else type="button" class="actor-icon-button" :title="t('common.edit')" :aria-label="t('common.edit')" @click="saveActor">
              <BaseIcon name="edit" class="w-4 h-4" />
            </button>
            <VuiButton v-if="editMode" variant="outlined" color="secondary" size="small" :disabled="deleting" customClass="actor-action-button actor-action-button--danger" @click="deleteActor">
              {{ t('common.delete') }}
            </VuiButton>
          </div>
        </div>

        <div v-if="!editMode" class="actor-readonly">
          <div class="actor-readonly__item">
            <span class="actor-field-label actor-field-label--icon"><BaseIcon name="brandEmby" class="actor-field-label__icon" />{{ t('files.actors.detailEmbyName') }}</span>
            <strong>{{ form.name || '-' }}</strong>
          </div>
          <div class="actor-readonly__item">
            <span class="actor-field-label actor-field-label--icon"><BaseIcon name="brandEmby" class="actor-field-label__icon" />{{ t('files.actors.detailEmbySortName') }}</span>
            <strong>{{ form.sort_name || '-' }}</strong>
          </div>
          <div class="actor-readonly__item">
            <span>{{ t('files.actors.detailJapaneseName') }}</span>
            <strong>{{ form.jp_name || '-' }}</strong>
          </div>
          <div class="actor-readonly__item">
            <span>{{ t('files.actors.detailZhCnName') }}</span>
            <strong>{{ form.zh_cn_name || '-' }}</strong>
          </div>
          <div class="actor-readonly__item">
            <span>{{ t('files.actors.detailZhTwName') }}</span>
            <strong>{{ form.zh_tw_name || '-' }}</strong>
          </div>
          <div class="actor-readonly__item actor-readonly__item--overview">
            <span>{{ t('files.actors.detailAliases') }}</span>
            <div v-if="aliasTags.length" class="actor-alias-tags">
              <span v-for="alias in aliasTags" :key="alias">{{ alias }}</span>
            </div>
            <p v-else>-</p>
          </div>
          <div class="actor-readonly__item">
            <span>{{ t('files.actors.detailBirthday') }}</span>
            <strong>{{ birthdayLabel() }}</strong>
          </div>
          <div class="actor-readonly__item">
            <span>{{ t('files.actors.detailBirthPlace') }}</span>
            <strong>{{ form.place_of_birth || '-' }}</strong>
          </div>
          <div class="actor-readonly__item">
            <span>{{ t('files.actors.detailGender') }}</span>
            <strong>{{ form.gender || '-' }}</strong>
          </div>
          <div class="actor-readonly__item">
            <span>{{ t('files.actors.detailKnownFor') }}</span>
            <strong>{{ form.known_for_department || '-' }}</strong>
          </div>
          <div class="actor-readonly__item">
            <span>{{ t('files.actors.detailPopularity') }}</span>
            <strong>{{ form.popularity || '-' }}</strong>
          </div>
          <div class="actor-readonly__item">
            <span>{{ t('files.actors.detailHomepage') }}</span>
            <strong>
              <button v-if="form.homepage" class="actor-link" @click="openExternal(form.homepage)">{{ form.homepage }}</button>
              <template v-else>-</template>
            </strong>
          </div>
          <div class="actor-readonly__item actor-readonly__item--overview">
            <span>{{ t('files.actors.providerIds') }}</span>
            <div v-if="providerIdEntries.length" class="actor-provider-ids">
              <span v-for="[key, value] in providerIdEntries" :key="key">
                <strong>{{ key }}</strong>
                <em>{{ value }}</em>
              </span>
            </div>
            <p v-else>-</p>
          </div>
          <div class="actor-readonly__item actor-readonly__item--overview">
            <span>{{ t('files.actors.detailOverview') }}</span>
            <p :class="{ 'is-collapsed': overviewTooLong && !overviewExpanded }">{{ form.overview || '-' }}</p>
            <button v-if="overviewTooLong" type="button" class="actor-overview-toggle" @click="overviewExpanded = !overviewExpanded">
              {{ overviewExpanded ? t('files.actors.overviewCollapse') : t('files.actors.overviewExpand') }}
            </button>
          </div>
        </div>

        <div v-else class="actor-form">
          <label>
            <span class="actor-field-label actor-field-label--icon"><BaseIcon name="brandEmby" class="actor-field-label__icon" />{{ t('files.actors.detailEmbyName') }}</span>
            <input v-model="form.name" type="text" />
          </label>
          <label>
            <span class="actor-field-label actor-field-label--icon"><BaseIcon name="brandEmby" class="actor-field-label__icon" />{{ t('files.actors.detailEmbySortName') }}</span>
            <input v-model="form.sort_name" type="text" />
          </label>
          <label>
            <span>{{ t('files.actors.detailJapaneseName') }}</span>
            <input v-model="form.jp_name" type="text" />
          </label>
          <label>
            <span>{{ t('files.actors.detailZhCnName') }}</span>
            <input v-model="form.zh_cn_name" type="text" />
          </label>
          <label>
            <span>{{ t('files.actors.detailZhTwName') }}</span>
            <input v-model="form.zh_tw_name" type="text" />
          </label>
          <label class="actor-form__overview">
            <span>{{ t('files.actors.detailAliases') }}</span>
            <textarea v-model="form.aliases" rows="4" />
          </label>
          <label>
            <span>TMDB</span>
            <input v-model="form.tmdb" type="text" />
          </label>
          <label>
            <span>IMDB</span>
            <input v-model="form.imdb" type="text" />
          </label>
          <label>
            <span>{{ t('files.actors.detailBirthday') }}</span>
            <input v-model="form.birthday" type="date" />
          </label>
          <label>
            <span>{{ t('files.actors.detailDeathday') }}</span>
            <input v-model="form.deathday" type="date" />
          </label>
          <label class="actor-form__overview">
            <span>{{ t('files.actors.detailBirthPlace') }}</span>
            <input v-model="form.place_of_birth" type="text" />
          </label>
          <label>
            <span>{{ t('files.actors.detailGender') }}</span>
            <input v-model="form.gender" type="text" />
          </label>
          <label>
            <span>{{ t('files.actors.detailKnownFor') }}</span>
            <input v-model="form.known_for_department" type="text" />
          </label>
          <label>
            <span>{{ t('files.actors.detailPopularity') }}</span>
            <input v-model="form.popularity" type="number" step="0.001" />
          </label>
          <label>
            <span>{{ t('files.actors.detailHomepage') }}</span>
            <input v-model="form.homepage" type="url" />
          </label>
          <div class="actor-form__overview actor-provider-editor">
            <span>{{ t('files.actors.providerIds') }}</span>
            <div v-if="providerIdEntries.length" class="actor-provider-ids actor-provider-ids--editable">
              <span v-for="[key, value] in providerIdEntries" :key="key">
                <strong>{{ key }}</strong>
                <em>{{ value }}</em>
                <button type="button" :disabled="providerRemoving[key]" @click="removeProviderId(key)">
                  {{ t('files.actors.providerRemove') }}
                </button>
              </span>
            </div>
            <p v-else>-</p>
          </div>
          <label class="actor-form__overview">
            <span>{{ t('files.actors.detailOverview') }}</span>
            <textarea v-model="form.overview" rows="7" />
          </label>
        </div>
      </div>
    </section>

    <section v-if="deleteDiagnostics" class="actor-diagnostics ui-card">
      <div class="actor-section-head">
        <h2>{{ t('files.actors.deleteDiagnosticTitle') }}</h2>
        <span>
          {{ t('files.actors.deleteDiagnosticSummary', {
            total: deleteDiagnostics.related_total || 0,
            canDelete: deleteDiagnostics.can_delete_cleanly ? t('common.yes') : t('common.no'),
          }) }}
        </span>
      </div>
      <div class="actor-diagnostics__status">
        <span :class="{ 'is-ok': deleteDiagnostics.person_exists, 'is-warn': !deleteDiagnostics.person_exists }">
          {{ deleteDiagnostics.person_exists ? t('files.actors.deleteDiagnosticPersonExists') : t('files.actors.deleteDiagnosticPersonMissing') }}
        </span>
        <span>
          CanDelete:
          <strong>{{ deleteDiagnostics.person?.can_delete === false ? 'false' : deleteDiagnostics.person?.can_delete === true ? 'true' : '-' }}</strong>
        </span>
        <span v-if="deleteDiagnostics.is_ignored_by_noor">{{ t('files.actors.deleteDiagnosticIgnored') }}</span>
      </div>
      <div v-if="deleteDiagnostics.delete_blockers?.length" class="actor-diagnostics__blockers">
        <strong>{{ t('files.actors.deleteDiagnosticBlockers') }}</strong>
        <span v-for="reason in deleteDiagnostics.delete_blockers" :key="reason">{{ deleteBlockerLabel(reason) }}</span>
      </div>
      <div class="actor-diagnostics__groups">
        <article v-for="(group, type) in deleteDiagnostics.by_type" :key="type" class="actor-diagnostics__group" :class="{ 'is-empty': !(group.total || 0) }">
          <div class="actor-diagnostics__group-head">
            <strong>{{ diagnosticTypeLabels[String(type)] || type }}</strong>
            <span>{{ group.total || 0 }}</span>
          </div>
          <div v-if="group.items?.length" class="actor-diagnostics__items">
            <button v-for="item in group.items" :key="item.id" type="button" @click="openDiagnosticItem(item)">
              <strong>{{ item.name || item.id }}</strong>
              <span>{{ item.path || item.type || '-' }}</span>
            </button>
          </div>
        </article>
      </div>
    </section>

    <section class="actor-movies">
      <div class="actor-section-head">
        <h2>{{ t('files.actors.detailMovies') }}</h2>
        <span>{{ t('files.actors.detailMovieCount', { count: total }) }}</span>
      </div>
      <div v-if="moviesLoading" class="actor-empty ui-card">
        <BaseIcon name="loading" class="w-5 h-5" />
      </div>
      <div v-else-if="!movies.length" class="actor-empty ui-card">{{ t('files.actors.detailNoMovies') }}</div>
      <div v-else class="actor-movie-grid">
        <MediaCard
          v-for="item in movies"
          :key="item.id"
          :item="item"
          @click="openMovie"
          @quick-action="openMovie"
          @subtitle-action="openMovie"
          @delete-action="openMovie"
        />
      </div>
      <NoorPagination v-if="totalPages > 1" v-model:page="page" :total-pages="totalPages" />
    </section>

    <BaseModal v-if="avatarModalOpen" :title="t('files.actors.avatarPickerTitle')" size="lg" @close="avatarModalOpen = false">
      <div v-if="avatarCandidatesLoading" class="actor-empty">
        <BaseIcon name="loading" class="w-5 h-5" />
      </div>
      <div v-else-if="!avatarCandidates.length" class="actor-empty">{{ t('files.actors.avatarNoCandidates') }}</div>
      <div v-else class="avatar-candidates">
        <button
          v-for="candidate in avatarCandidates"
          :key="candidate.remote_url || candidate.url"
          class="avatar-candidate"
          :disabled="uploadingAvatar"
          @click="selectAvatar(candidate)"
        >
          <img :src="candidate.url" :alt="candidate.name || displayName" loading="lazy" />
          <span>{{ candidate.name || displayName }}</span>
          <em>{{ candidate.folder }}</em>
        </button>
      </div>
    </BaseModal>

    <BaseModal v-if="tmdbModalOpen" :title="t('files.actors.tmdbPreviewTitle')" size="lg" @close="tmdbModalOpen = false">
      <div v-if="!tmdbPreview" class="actor-empty">
        <BaseIcon name="loading" class="w-5 h-5" />
      </div>
      <div v-else class="tmdb-preview">
        <div v-if="tmdbPreview.proposal?.image_url" class="tmdb-preview__hero">
          <img :src="tmdbPreview.proposal.image_url" :alt="tmdbPreview.proposal.name || displayName" />
          <div>
            <strong>{{ tmdbPreview.proposal.name || displayName }}</strong>
            <span v-if="tmdbPreview.proposal.birthday">{{ tmdbPreview.proposal.birthday }}</span>
            <span v-if="tmdbPreview.proposal.place_of_birth">{{ tmdbPreview.proposal.place_of_birth }}</span>
          </div>
        </div>

        <div class="tmdb-preview__options">
          <label>
            <input v-model="tmdbApplyName" type="checkbox" />
            <span>{{ t('files.actors.tmdbApplyName') }}</span>
          </label>
          <label>
            <input v-model="tmdbApplyAvatar" type="checkbox" :disabled="!tmdbPreview.proposal?.image_url" />
            <span>{{ t('files.actors.tmdbApplyAvatar') }}</span>
          </label>
        </div>

        <div v-if="tmdbPreview.diffs?.length" class="tmdb-diffs">
          <article v-for="diff in tmdbPreview.diffs" :key="diff.field" class="tmdb-diff">
            <span>{{ diff.label }}</span>
            <div>
              <p>{{ diff.current || '-' }}</p>
              <strong>{{ diff.proposed || '-' }}</strong>
            </div>
          </article>
        </div>
        <div v-else class="actor-empty">{{ t('files.actors.tmdbNoDiff') }}</div>
      </div>

      <template #footer>
        <div class="actor-modal-actions">
          <VuiButton variant="outlined" color="secondary" size="small" customClass="actor-action-button" @click="tmdbModalOpen = false">
            {{ t('common.cancel') }}
          </VuiButton>
          <VuiButton variant="gradient" color="primary" size="small" :disabled="tmdbApplying" customClass="actor-action-button" @click="applyTmdbMetadata">
            {{ t('files.actors.tmdbApply') }}
          </VuiButton>
        </div>
      </template>
    </BaseModal>
  </div>
</template>

<style scoped>
.actor-detail {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.actor-detail__topbar {
  display: flex;
  justify-content: flex-start;
}

.actor-profile {
  display: grid;
  grid-template-columns: 300px minmax(0, 1fr);
  gap: 1rem;
  padding: 1rem;
}

.actor-profile__side {
  display: grid;
  align-content: start;
  gap: 0.85rem;
  width: 300px;
}

.actor-profile__avatar {
  overflow: hidden;
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 300px;
  height: 450px;
  border-radius: var(--radius-md);
  background: linear-gradient(135deg, rgba(0, 117, 255, 0.25), rgba(255, 255, 255, 0.06));
  color: var(--color-text-primary);
  font-size: 2.2rem;
  font-weight: 900;
}

.actor-profile__avatar-actions {
  position: absolute;
  inset-inline: 0.5rem;
  bottom: 0.5rem;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.45rem;
}

.actor-profile__links {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 0.45rem;
  padding-top: 0.25rem;
}

.actor-profile__links button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  border: 1px solid var(--color-border-subtle);
  border-radius: 999px;
  padding: 0;
  background: rgba(255, 255, 255, 0.045);
  color: var(--color-text-muted);
  cursor: pointer;
}

.actor-profile__link-icon {
  width: 15px;
  height: 15px;
  color: var(--color-text-secondary);
}

.actor-profile__links button:hover {
  border-color: color-mix(in srgb, var(--color-primary) 55%, transparent);
  color: var(--color-text-primary);
}

.actor-profile__file {
  display: none;
}

.actor-profile__avatar img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.actor-profile__content {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.actor-profile__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
}

.actor-icon-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 2rem;
  height: 2rem;
  border: 1px solid var(--color-border-subtle);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.045);
  color: var(--color-text-secondary);
  cursor: pointer;
}

.actor-icon-button:hover {
  border-color: color-mix(in srgb, var(--color-primary) 55%, transparent);
  color: var(--color-text-primary);
  background: rgba(255, 255, 255, 0.075);
}

.actor-icon-button--back {
  width: 2.15rem;
  height: 2.15rem;
}

.actor-profile__actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 0.5rem;
  max-width: min(100%, 34rem);
}

:deep(.actor-action-button) {
  min-width: 4.5rem;
  justify-content: center;
  text-align: center;
  letter-spacing: 0;
  text-transform: none;
}

:deep(.actor-action-button--danger) {
  border-color: color-mix(in srgb, var(--color-danger, #ff4d6d) 60%, transparent);
  color: var(--color-danger, #ff6b81);
}

.actor-profile__head h1 {
  margin: 0;
  color: var(--color-text-primary);
  font-size: 1.45rem;
  font-weight: 900;
}

.actor-profile__head p {
  margin: 0.25rem 0 0;
  color: var(--color-text-muted);
  font-size: 0.82rem;
}

.actor-form {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.75rem;
}

.actor-readonly {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.75rem;
}

.actor-readonly__item {
  min-width: 0;
  display: grid;
  gap: 0.35rem;
  padding: 0.7rem 0.75rem;
  border: 1px solid var(--color-border-subtle);
  border-radius: var(--radius-md);
  background: rgba(255, 255, 255, 0.035);
}

.actor-readonly__item--overview {
  grid-column: 1 / -1;
}

.actor-readonly__item span {
  color: var(--color-text-muted);
  font-size: 0.76rem;
  font-weight: 800;
}

.actor-field-label {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
}

.actor-field-label__icon {
  width: 0.95rem;
  height: 0.95rem;
  color: var(--color-text-secondary);
}

.actor-alias-tags {
  display: flex;
  flex-wrap: nowrap;
  gap: 0.4rem;
  overflow-x: auto;
  padding-bottom: 0.1rem;
}

.actor-alias-tags span {
  flex: 0 0 auto;
  max-width: 14rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  padding: 0.2rem 0.55rem;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.06);
  color: var(--color-text-secondary);
  font-size: 0.74rem;
  font-weight: 800;
}

.actor-provider-ids {
  display: grid;
  gap: 0.45rem;
}

.actor-provider-ids > span {
  min-width: 0;
  display: grid;
  grid-template-columns: minmax(5.5rem, max-content) minmax(0, 1fr);
  gap: 0.45rem;
  align-items: center;
  padding: 0.45rem 0.55rem;
  border-radius: calc(var(--radius-md) - 2px);
  background: rgba(255, 255, 255, 0.045);
}

.actor-provider-ids strong,
.actor-provider-ids em {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.actor-provider-ids strong {
  color: var(--color-text-primary);
  font-size: 0.78rem;
  font-weight: 850;
}

.actor-provider-ids em {
  color: var(--color-text-muted);
  font-size: 0.74rem;
  font-style: normal;
}

.actor-provider-ids--editable > span {
  grid-template-columns: minmax(5.5rem, max-content) minmax(0, 1fr) max-content;
}

.actor-provider-ids button {
  border: 1px solid color-mix(in srgb, var(--color-danger, #ff4d6d) 48%, transparent);
  border-radius: 999px;
  padding: 0.18rem 0.55rem;
  background: rgba(255, 77, 109, 0.08);
  color: var(--color-danger, #ff6b81);
  font-size: 0.7rem;
  font-weight: 850;
  cursor: pointer;
}

.actor-provider-ids button:disabled {
  cursor: progress;
  opacity: 0.62;
}

.actor-provider-editor {
  display: grid;
  gap: 0.35rem;
}

.actor-readonly__item strong,
.actor-readonly__item p {
  min-width: 0;
  margin: 0;
  color: var(--color-text-primary);
  font-size: 0.88rem;
  line-height: 1.6;
  white-space: pre-wrap;
}

.actor-readonly__item p.is-collapsed {
  display: -webkit-box;
  overflow: hidden;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 5;
}

.actor-overview-toggle {
  justify-self: start;
  border: 0;
  padding: 0;
  background: transparent;
  color: var(--color-primary);
  font-size: 0.78rem;
  font-weight: 800;
  cursor: pointer;
}

.actor-link {
  border: 0;
  padding: 0;
  background: transparent;
  color: var(--color-primary);
  font: inherit;
  cursor: pointer;
}

.actor-form label {
  display: grid;
  gap: 0.35rem;
}

.actor-form span,
.actor-section-head span {
  color: var(--color-text-muted);
  font-size: 0.76rem;
  font-weight: 800;
}

.actor-form input,
.actor-form textarea {
  width: 100%;
  border: 1px solid var(--color-border-subtle);
  border-radius: var(--radius-md);
  background: rgba(255, 255, 255, 0.05);
  color: var(--color-text-primary);
  font-size: 0.86rem;
  outline: none;
}

.actor-form input {
  min-height: 2.25rem;
  padding: 0 0.7rem;
}

.actor-form textarea {
  min-height: 8rem;
  padding: 0.65rem 0.7rem;
  resize: vertical;
}

.actor-form__overview {
  grid-column: 1 / -1;
}

.actor-section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 0.75rem;
}

.actor-section-head h2 {
  margin: 0;
  color: var(--color-text-primary);
  font-size: 1rem;
  font-weight: 850;
}

.actor-movie-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(10rem, 1fr));
  gap: 0.8rem;
}

.actor-diagnostics {
  display: grid;
  gap: 0.75rem;
  padding: 1rem;
}

.actor-diagnostics__status,
.actor-diagnostics__blockers {
  display: flex;
  flex-wrap: wrap;
  gap: 0.45rem;
}

.actor-diagnostics__status span,
.actor-diagnostics__blockers span {
  padding: 0.22rem 0.6rem;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.055);
  color: var(--color-text-secondary);
  font-size: 0.74rem;
  font-weight: 800;
}

.actor-diagnostics__status span.is-ok {
  color: rgb(155, 225, 175);
  background: rgba(45, 212, 120, 0.12);
}

.actor-diagnostics__status span.is-warn,
.actor-diagnostics__blockers span {
  color: rgb(255, 216, 154);
  background: rgba(255, 181, 71, 0.13);
}

.actor-diagnostics__blockers strong {
  display: inline-flex;
  align-items: center;
  color: var(--color-text-muted);
  font-size: 0.76rem;
  font-weight: 850;
}

.actor-diagnostics__groups {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(15rem, 1fr));
  gap: 0.65rem;
}

.actor-diagnostics__group {
  min-width: 0;
  display: grid;
  gap: 0.5rem;
  padding: 0.7rem;
  border: 1px solid var(--color-border-subtle);
  border-radius: var(--radius-md);
  background: rgba(255, 255, 255, 0.035);
}

.actor-diagnostics__group.is-empty {
  opacity: 0.62;
}

.actor-diagnostics__group-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
}

.actor-diagnostics__group-head strong {
  color: var(--color-text-primary);
  font-size: 0.82rem;
  font-weight: 850;
}

.actor-diagnostics__group-head span {
  color: var(--color-text-muted);
  font-size: 0.78rem;
  font-weight: 850;
}

.actor-diagnostics__items {
  display: grid;
  gap: 0.4rem;
}

.actor-diagnostics__items button {
  min-width: 0;
  display: grid;
  gap: 0.15rem;
  border: 0;
  border-radius: calc(var(--radius-md) - 2px);
  padding: 0.45rem 0.5rem;
  background: rgba(255, 255, 255, 0.045);
  color: inherit;
  text-align: left;
  cursor: pointer;
}

.actor-diagnostics__items button:hover {
  background: rgba(255, 255, 255, 0.075);
}

.actor-diagnostics__items strong,
.actor-diagnostics__items span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.actor-diagnostics__items strong {
  color: var(--color-text-primary);
  font-size: 0.78rem;
  font-weight: 800;
}

.actor-diagnostics__items span {
  color: var(--color-text-muted);
  font-size: 0.7rem;
}

.actor-empty,
.actor-profile__loading {
  min-height: 8rem;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--color-text-muted);
}

.avatar-candidates {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(8rem, 1fr));
  gap: 0.75rem;
}

.avatar-candidate {
  display: grid;
  gap: 0.45rem;
  padding: 0.55rem;
  border: 1px solid var(--color-border-subtle);
  border-radius: var(--radius-md);
  background: rgba(255, 255, 255, 0.04);
  color: var(--color-text-primary);
  text-align: left;
  cursor: pointer;
}

.avatar-candidate:hover:not(:disabled) {
  border-color: color-mix(in srgb, var(--color-primary) 55%, transparent);
  background: rgba(255, 255, 255, 0.07);
}

.avatar-candidate img {
  width: 100%;
  aspect-ratio: 3 / 4;
  object-fit: cover;
  border-radius: calc(var(--radius-md) - 2px);
  background: rgba(0, 0, 0, 0.18);
}

.avatar-candidate span,
.avatar-candidate em {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.avatar-candidate span {
  font-size: 0.82rem;
  font-weight: 800;
}

.avatar-candidate em {
  color: var(--color-text-muted);
  font-size: 0.72rem;
  font-style: normal;
}

.tmdb-preview {
  display: grid;
  gap: 1rem;
}

.tmdb-preview__hero {
  display: grid;
  grid-template-columns: 5rem minmax(0, 1fr);
  gap: 0.85rem;
  align-items: center;
}

.tmdb-preview__hero img {
  width: 5rem;
  aspect-ratio: 3 / 4;
  object-fit: cover;
  border-radius: var(--radius-md);
}

.tmdb-preview__hero div,
.tmdb-preview__options,
.tmdb-diffs,
.tmdb-diff,
.tmdb-diff div {
  min-width: 0;
}

.tmdb-preview__hero div {
  display: grid;
  gap: 0.25rem;
}

.tmdb-preview__hero strong {
  color: var(--color-text-primary);
  font-size: 1rem;
}

.tmdb-preview__hero span {
  color: var(--color-text-muted);
  font-size: 0.8rem;
}

.tmdb-preview__options {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
}

.tmdb-preview__options label {
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
  color: var(--color-text-secondary);
  font-size: 0.82rem;
  font-weight: 800;
}

.tmdb-diffs {
  display: grid;
  gap: 0.65rem;
}

.tmdb-diff {
  display: grid;
  gap: 0.45rem;
  padding: 0.75rem;
  border: 1px solid var(--color-border-subtle);
  border-radius: var(--radius-md);
  background: rgba(255, 255, 255, 0.035);
}

.tmdb-diff > span {
  color: var(--color-text-muted);
  font-size: 0.75rem;
  font-weight: 900;
}

.tmdb-diff div {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: 0.65rem;
}

.tmdb-diff p,
.tmdb-diff strong {
  overflow: hidden;
  max-height: 10rem;
  margin: 0;
  color: var(--color-text-secondary);
  font-size: 0.8rem;
  line-height: 1.55;
  white-space: pre-wrap;
}

.tmdb-diff strong {
  color: var(--color-text-primary);
}

.actor-modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.6rem;
}

@media (max-width: 760px) {
  .actor-profile {
    grid-template-columns: 1fr;
  }

  .actor-profile__avatar {
    width: min(300px, 100%);
    height: auto;
    aspect-ratio: 2 / 3;
  }

  .actor-profile__side {
    width: min(300px, 100%);
  }

  .actor-form {
    grid-template-columns: 1fr;
  }

  .actor-profile__head {
    flex-direction: column;
  }

  .actor-profile__actions,
  .actor-readonly {
    width: 100%;
    grid-template-columns: 1fr;
  }

  .actor-profile__actions {
    justify-content: flex-start;
  }

  .tmdb-diff div {
    grid-template-columns: 1fr;
  }
}
</style>
