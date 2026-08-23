<script setup lang="ts">
import { computed } from 'vue'
import type { MediaItem } from '../../api/types'
import { useI18n } from '../../composables/useI18n'

const { t, i18nVersion } = useI18n()

const props = defineProps<{
  item: MediaItem
  selected?: boolean
  imageMode?: 'cover' | 'backdrop'
}>()

defineEmits<{
  click: [item: MediaItem]
  quickAction: [item: MediaItem]
  subtitleAction: [item: MediaItem]
}>()

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

const imageUrl = computed(() => {
  if (props.imageMode === 'backdrop') return props.item.fanart_path || props.item.poster_path
  return props.item.poster_path || props.item.fanart_path
})

const imageAlt = computed(() => props.item.name)

</script>

<template>
  <div
    class="media-card bg-surface overflow-hidden transition-all duration-300"
    :class="imageMode === 'backdrop' ? 'media-card--backdrop' : 'media-card--cover'"
  >
    <!-- Poster -->
    <div
      class="media-card__image bg-bg-elevated relative overflow-hidden cursor-pointer"
      @click="$emit('click', item)"
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
          class="text-xs px-1.5 py-0.5 rounded transition-colors border"
          :class="isCracked ? 'tag-cracked' : 'tag-cracked--none'"
          @click.stop="!isCracked && $emit('quickAction', item)"
        >
          {{ crackedLabel }}
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
</style>
