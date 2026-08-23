<script setup lang="ts">
import { ref, computed, useSlots } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '../../../api'
import type { MediaItemDetail } from '../../../api/types'
import { useI18n } from '../../../composables/useI18n'

const { t } = useI18n()
const slots = useSlots()
const route = useRoute()
const router = useRouter()

const emit = defineEmits<{
  play: []
}>()

const props = defineProps<{
  detail: MediaItemDetail | null
  selectedVariantName?: string
  showPlay?: boolean
}>()

const actorsExpanded = ref(false)
const MAX_ACTOR_LINES = 4

const actorList = computed(() => {
  const fromNfo = props.detail?.nfo?.actors || []
  if (fromNfo.length) return fromNfo
  return props.detail?.actors || []
})

const hasOverflowActors = computed(() => {
  return actorList.value.length > MAX_ACTOR_LINES
})

const visibleActors = computed(() => {
  if (!actorList.value.length) return []
  if (actorsExpanded.value || !hasOverflowActors.value) {
    return actorList.value
  }
  return actorList.value.slice(0, MAX_ACTOR_LINES)
})

const displayTitle = computed(() => {
  if (!props.detail) return ''
  return props.detail.nfo?.title || props.detail.nfo?.originaltitle || props.detail.name
})

const actorToggleLabel = computed(() => {
  if (!actorsExpanded.value) {
    return `+${actorList.value.length - MAX_ACTOR_LINES}`
  }
  return t('detail.collapseActors')
})

const playTitle = computed(() => props.selectedVariantName ? `${t('detail.playPreview')} · ${props.selectedVariantName}` : t('detail.playPreview'))

function libraryReturnTo() {
  const query = new URLSearchParams()
  for (const [key, value] of Object.entries(route.query)) {
    if (key === 'detail') continue
    if (Array.isArray(value)) {
      for (const item of value) {
        if (item != null) query.append(key, String(item))
      }
    } else if (value != null) {
      query.set(key, String(value))
    }
  }
  if (props.detail?.id) query.set('detail', props.detail.id)
  return `${route.path}${query.toString() ? `?${query.toString()}` : ''}`
}

async function openActor(actor: { name?: string }) {
  const name = String(actor?.name || '').trim()
  if (!name) return
  try {
    const resp = await api.get('/media-library/actors', {
      params: { q: name, limit: 1 },
    })
    const actorId = resp.data?.actors?.[0]?.id
    if (!actorId) return
    router.push({
      path: `/actors/${encodeURIComponent(actorId)}`,
      query: { returnTo: libraryReturnTo() },
    })
  } catch {
    // The actor badge still works as static metadata if lookup fails.
  }
}
</script>

<template>
  <!-- Header Row 1: Backdrop thumbnail (full bleed, auto height) -->
  <div class="header-media w-full bg-bg-elevated overflow-hidden ring-1 ring-border-default">
    <slot v-if="slots.media" name="media" />
    <template v-else>
      <img
        v-if="detail?.backdrop_path"
        :src="detail.backdrop_path"
        class="w-full object-cover"
      />
      <div v-else-if="detail?.poster_path" class="w-full flex items-center justify-center">
        <img :src="detail.poster_path" class="max-h-48 object-contain" />
      </div>
      <div v-else class="w-full h-32 flex items-center justify-center">
        <svg xmlns="http://www.w3.org/2000/svg" class="w-8 h-8 text-white/20" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M7 4v16M17 4v16M3 8h4m10 0h4M3 12h18M3 16h4m10 0h4M4 20h16a1 1 0 001-1V5a1 1 0 00-1-1H4a1 1 0 00-1 1v14a1 1 0 001 1z" />
        </svg>
      </div>
    </template>
    <button
      v-if="!slots.media && showPlay !== false && detail?.file_path"
      type="button"
      class="header-media__play"
      :title="playTitle"
      @click="emit('play')"
    >
      <svg xmlns="http://www.w3.org/2000/svg" class="w-6 h-6" viewBox="0 0 24 24" fill="currentColor">
        <path d="M8 5.14v13.72c0 .74.8 1.21 1.46.85l10.08-5.86a.98.98 0 000-1.7L9.46 4.29A.98.98 0 008 5.14z" />
      </svg>
    </button>
  </div>

  <!-- Header Row 2: Title + tagline + actors -->
  <div class="p-4 border border-border-subtle rounded-lg">
    <p v-if="detail?.nfo?.tagline" class="text-accent-cyan text-xs mb-1 italic">"{{ detail.nfo.tagline }}"</p>
    <h2 class="text-xl font-bold text-text-primary leading-tight">{{ displayTitle }}</h2>

    <!-- Actors -->
    <div v-if="visibleActors.length" class="mt-2 flex flex-wrap gap-1 items-center">
      <button
        v-for="actor in visibleActors"
        :key="actor.name"
        type="button"
        class="px-2 py-0.5 bg-bg-elevated rounded text-xs text-text-secondary hover:text-text-primary hover:bg-bg-default"
        @click="openActor(actor)"
      >
        {{ actor.name }}
      </button>
      <button
        v-if="hasOverflowActors"
        @click="actorsExpanded = !actorsExpanded"
        class="px-2 py-0.5 bg-bg-elevated rounded text-xs text-accent-cyan hover:bg-bg-default"
      >
        {{ actorToggleLabel }}
      </button>
    </div>
  </div>
</template>

<style scoped>
.header-media {
  position: relative;
}

.header-media__play {
  position: absolute;
  right: 0.9rem;
  bottom: 0.9rem;
  width: 3rem;
  height: 3rem;
  border-radius: 999px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid rgba(255, 255, 255, 0.18);
  background: rgba(7, 14, 22, 0.78);
  color: rgba(255, 255, 255, 0.96);
  box-shadow: 0 12px 30px rgba(0, 0, 0, 0.32);
  transition: transform 0.16s ease, background 0.16s ease, border-color 0.16s ease;
}

.header-media__play:hover {
  transform: scale(1.04);
  background: rgba(0, 117, 255, 0.88);
  border-color: rgba(0, 117, 255, 0.55);
}
</style>
