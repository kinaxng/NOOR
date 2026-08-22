<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import api from '../api'
import BaseIcon from '../components/noor/BaseIcon.vue'
import VuiButton from '../components/ui/Button/VuiButton.vue'
import NoorPagination from '../components/ui/Pagination.vue'
import { useI18n } from '../composables/useI18n'
import { useToast } from '../composables/useToast'
import type { MediaActor, MediaActorDuplicateGroup } from '../api/types'

type SortKey = 'SortName' | 'DateCreated'
type SortOrder = 'Ascending' | 'Descending'

const { t, i18nVersion } = useI18n()
const toast = useToast()

const actors = ref<MediaActor[]>([])
const duplicateGroups = ref<MediaActorDuplicateGroup[]>([])
const loading = ref(false)
const duplicateLoading = ref(false)
const query = ref('')
const page = ref(1)
const pageSize = 60
const total = ref(0)
const sortBy = ref<SortKey>('SortName')
const sortOrder = ref<SortOrder>('Ascending')
const showDuplicates = ref(false)

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize)))
const resultLabel = computed(() => {
  void i18nVersion.value
  return t('files.actors.resultCount', { count: total.value })
})

let searchTimer: number | null = null

function actorInitial(name: string) {
  return (name || '?').trim().slice(0, 1).toUpperCase()
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
  try {
    const resp = await api.get('/media-library/actors/duplicates')
    duplicateGroups.value = resp.data.groups || []
    showDuplicates.value = true
  } catch (error: any) {
    duplicateGroups.value = []
    toast.error(error?.response?.data?.detail || error?.message || t('files.actors.duplicatesFailed'))
  } finally {
    duplicateLoading.value = false
  }
}

function setSort(key: SortKey, order: SortOrder) {
  sortBy.value = key
  sortOrder.value = order
  page.value = 1
  loadActors()
}

function openEmby(actor: MediaActor) {
  if (!actor.emby_url) return
  window.open(actor.emby_url, '_blank', 'noopener,noreferrer')
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

onMounted(() => {
  loadActors()
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
        <div class="actor-search">
          <BaseIcon name="search" class="actor-search__icon" />
          <input v-model="query" type="search" :placeholder="t('files.actors.searchPlaceholder')" class="actor-search__input" />
        </div>
        <VuiButton variant="secondary" color="secondary" size="small" :loading="duplicateLoading" @click="loadDuplicates">
          <BaseIcon name="user" class="w-4 h-4" />
          {{ t('files.actors.detectDuplicates') }}
        </VuiButton>
      </div>
    </div>

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

    <section v-if="showDuplicates" class="duplicate-panel ui-card">
      <div class="duplicate-panel__head">
        <div>
          <h2>{{ t('files.actors.duplicatesTitle') }}</h2>
          <span>{{ t('files.actors.duplicatesCount', { count: duplicateGroups.length }) }}</span>
        </div>
        <button type="button" class="duplicate-panel__close" @click="showDuplicates = false">
          <BaseIcon name="close" />
        </button>
      </div>

      <div v-if="duplicateGroups.length" class="duplicate-groups">
        <article v-for="group in duplicateGroups" :key="group.key" class="duplicate-group">
          <div class="duplicate-group__title">
            <strong>{{ group.name }}</strong>
            <span>{{ group.count }}</span>
          </div>
          <div class="duplicate-members">
            <button
              v-for="actor in group.actors"
              :key="actor.id"
              type="button"
              class="duplicate-member"
              @click="openEmby(actor)"
            >
              <span class="duplicate-member__avatar">
                <img v-if="actor.image_url" :src="actor.image_url" :alt="actor.name" loading="lazy" />
                <span v-else>{{ actorInitial(actor.name) }}</span>
              </span>
              <span class="duplicate-member__body">
                <span>{{ actor.name }}</span>
                <em v-if="actor.tmdb_id">TMDB {{ actor.tmdb_id }}</em>
              </span>
            </button>
          </div>
        </article>
      </div>
      <div v-else class="actor-empty actor-empty--compact">{{ t('files.actors.noDuplicates') }}</div>
    </section>

    <div v-if="loading" class="actor-loading">
      <BaseIcon name="loading" class="actor-loading__icon" />
    </div>

    <div v-else-if="!actors.length" class="actor-empty ui-card">
      <BaseIcon name="user" class="actor-empty__icon" />
      <span>{{ t('files.actors.empty') }}</span>
    </div>

    <div v-else class="actor-grid">
      <article v-for="actor in actors" :key="actor.id" class="actor-card ui-card" @click="openEmby(actor)">
        <div class="actor-card__avatar">
          <img v-if="actor.image_url" :src="actor.image_url" :alt="actor.name" loading="lazy" />
          <span v-else>{{ actorInitial(actor.name) }}</span>
        </div>
        <div class="actor-card__body">
          <h3>{{ actor.name }}</h3>
          <p v-if="actor.overview">{{ actor.overview }}</p>
          <div class="actor-card__meta">
            <span v-if="actor.movie_count !== null && actor.movie_count !== undefined">{{ t('files.actors.movieCount', { count: actor.movie_count }) }}</span>
            <span v-if="actor.tmdb_id">TMDB {{ actor.tmdb_id }}</span>
          </div>
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

.duplicate-group {
  padding: 0.75rem;
  border: 1px solid var(--color-border-subtle);
  border-radius: var(--radius-md);
  background: rgba(255, 255, 255, 0.035);
}

.duplicate-group__title {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.6rem;
}

.duplicate-group__title strong {
  color: var(--color-text-primary);
  font-size: 0.88rem;
}

.duplicate-group__title span {
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
  border-radius: var(--radius-md);
  background: rgba(255, 255, 255, 0.04);
  text-align: left;
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
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
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

.actor-card__body p {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  margin: 0;
  color: var(--color-text-muted);
  font-size: 0.76rem;
  line-height: 1.45;
}

.actor-card__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
  margin-top: auto;
}

.actor-card__meta span {
  min-height: 1.35rem;
  display: inline-flex;
  align-items: center;
  padding: 0 0.45rem;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.06);
  color: var(--color-text-secondary);
  font-size: 0.68rem;
  font-weight: 800;
}

@media (max-width: 720px) {
  .page-header,
  .actor-actions {
    align-items: stretch;
    flex-direction: column;
  }

  .actor-search {
    width: 100%;
  }

  .actor-grid {
    grid-template-columns: 1fr;
  }
}
</style>
