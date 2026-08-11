<script setup lang="ts">
import { computed, ref } from 'vue'
import type { MediaItem } from '../../api/types'
import { useI18n } from '../../composables/useI18n'

const { t, i18nVersion } = useI18n()

const props = defineProps<{
  item: MediaItem
  selected?: boolean
  imageMode?: 'cover' | 'backdrop'
  facefusionBadgeAlwaysVisible?: boolean
}>()

const emit = defineEmits<{
  click: [item: MediaItem]
  quickAction: [item: MediaItem]
  facefusionAction: [item: MediaItem]
  subtitleAction: [item: MediaItem]
  deleteAction: [item: MediaItem]
}>()

const showDeleteAction = ref(false)

const displayName = computed(() => {
  return props.item.nfo?.title || props.item.nfo?.originaltitle || props.item.name
})

const hasChinese = computed(() => {
  return props.item.tags?.has_chinese || (props.item.subtitle_count ?? 0) > 0
})

const isCracked = computed(() => {
  return props.item.tags?.is_cracked
})

const chineseLabel = computed(() => {
  void i18nVersion.value
  return t('mediacard.chinese')
})
const crackedLabel = computed(() => {
  void i18nVersion.value
  return isCracked.value ? t('mediacard.cracked') : t('mediacard.crack')
})
const releaseTypeLabel = computed(() => {
  void i18nVersion.value
  if (props.item.tags?.release_type_key === 'leaked') return t('library.filter.leaked')
  if (props.item.tags?.release_type_key === 'uncensored') return t('library.filter.uncensored')
  return props.item.tags?.release_type || ''
})

const isFaceFusionOutput = computed(() => {
  if (props.item.tags?.has_facefusion) return true
  const values = [
    props.item.name,
    props.item.path,
    props.item.nfo?.title,
    props.item.nfo?.originaltitle,
    props.item.nfo?.sorttitle,
    props.item.nfo?.num,
  ]
  return values.some(value => /(^|[^a-z0-9])(facefusion|ff)(?=[^a-z0-9]|$)/i.test(String(value || '')))
})

const facefusionLabel = computed(() => {
  void i18nVersion.value
  return t('mediacard.facefusion')
})

const imageUrl = computed(() => {
  if (props.imageMode === 'backdrop') return props.item.fanart_path || props.item.poster_path
  return props.item.poster_path || props.item.fanart_path
})

const imageAlt = computed(() => props.item.name)

function handleCoverContextMenu() {
  showDeleteAction.value = true
}

function handleCoverClick() {
  if (showDeleteAction.value) {
    showDeleteAction.value = false
    return
  }
  emit('click', props.item)
}

function handleDeleteClick() {
  showDeleteAction.value = false
  emit('deleteAction', props.item)
}

function handleCrackBadgeClick() {
  emit('quickAction', props.item)
}

function handleFaceFusionBadgeClick() {
  emit('facefusionAction', props.item)
}

</script>

<template>
  <div
    class="media-card bg-surface overflow-hidden transition-all duration-300"
    :class="[
      imageMode === 'backdrop' ? 'media-card--backdrop' : 'media-card--cover',
      { 'media-card--pin-facefusion': facefusionBadgeAlwaysVisible },
    ]"
  >
    <!-- Poster -->
    <div
      class="media-card__image bg-bg-elevated relative overflow-hidden cursor-pointer"
      @click="handleCoverClick"
      @contextmenu.prevent="handleCoverContextMenu"
      @mouseleave="showDeleteAction = false"
    >
      <img
        v-if="imageUrl"
        :src="imageUrl"
        :alt="imageAlt"
        class="w-full h-full object-cover transition-transform duration-300 hover:scale-105"
        loading="lazy"
      />
      <div v-else class="w-full h-full flex items-center justify-center text-text-muted text-xs">
        {{ t('mediacard.noCover') }}
      </div>

      <button
        v-if="showDeleteAction"
        type="button"
        class="media-card__delete-action"
        @click.stop="handleDeleteClick"
      >
        删除作品
      </button>

    </div>

    <!-- Info -->
    <div class="p-3">
      <p
        class="text-xs line-clamp-2 h-8 text-text-body mb-1.5 cursor-pointer hover:text-white transition-colors"
        @click="$emit('click', item)"
      >
        {{ displayName }}
      </p>


      <!-- Tags -->
      <div class="flex flex-wrap gap-1">
        <!-- Chinese/Subtitle tag -->
        <button
          class="text-xs px-1.5 py-0.5 rounded transition-colors cursor-pointer border"
          :class="hasChinese ? 'tag-subtitle' : 'tag-subtitle--none'"
          @click.stop="$emit('subtitleAction', item)"
        >
          {{ chineseLabel }}
        </button>

        <!-- Cracked tag -->
        <button
          v-if="!item.tags?.release_type"
          class="text-xs px-1.5 py-0.5 rounded transition-colors cursor-pointer border"
          :class="isCracked ? 'tag-cracked' : 'tag-cracked--none'"
          @click.stop="handleCrackBadgeClick"
        >
          {{ crackedLabel }}
        </button>

        <button
          v-if="!item.tags?.release_type"
          class="media-card__facefusion-tag text-xs px-1.5 py-0.5 rounded transition-colors cursor-pointer border"
          :class="isFaceFusionOutput ? 'tag-facefusion--active' : 'tag-facefusion--idle'"
          @click.stop="handleFaceFusionBadgeClick"
        >
          {{ facefusionLabel }}
        </button>

        <!-- Release type badge -->
        <span
          v-if="item.tags?.release_type"
          class="text-xs px-1.5 py-0.5 rounded border"
          :class="item.tags.release_type_key === 'leaked' ? 'tag-leaked' : 'tag-uncensored'"
        >
          {{ releaseTypeLabel }}
        </span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.media-card__image {
  aspect-ratio: 2 / 3;
}

.media-card--backdrop .media-card__image {
  aspect-ratio: 2184 / 1468;
}

.media-card--backdrop .p-3 {
  padding: 0.65rem 0.75rem 0.75rem;
}

.media-card__delete-action {
  position: absolute;
  left: 50%;
  top: 50%;
  transform: translate(-50%, -50%);
  z-index: 2;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 6.25rem;
  min-height: 2.35rem;
  padding: 0.55rem 0.85rem;
  border: 1px solid rgba(248, 113, 113, 0.55);
  border-radius: 0.55rem;
  background: rgba(127, 29, 29, 0.9);
  color: #fff;
  font-size: 0.78rem;
  font-weight: 800;
  box-shadow: 0 12px 32px rgba(0, 0, 0, 0.42);
}

.media-card__delete-action:hover {
  background: rgba(185, 28, 28, 0.94);
}

.media-card__facefusion-tag {
  display: none;
}

.media-card:hover .media-card__facefusion-tag,
.media-card--pin-facefusion .media-card__facefusion-tag {
  display: inline-flex;
  align-items: center;
}

.tag-facefusion--idle {
  border-color: rgba(255, 255, 255, 0.12);
  background: rgba(255, 255, 255, 0.045);
  color: rgba(255, 255, 255, 0.58);
}

.tag-facefusion--idle:hover {
  border-color: rgba(0, 117, 255, 0.36);
  background: rgba(0, 117, 255, 0.12);
  color: #fff;
}

.tag-facefusion--active {
  border-color: rgba(0, 117, 255, 0.28);
  background: rgba(0, 117, 255, 0.1);
  color: #9cc9ff;
}

.tag-facefusion--active:hover {
  border-color: rgba(0, 117, 255, 0.52);
  background: rgba(0, 117, 255, 0.18);
  color: #fff;
}
</style>

