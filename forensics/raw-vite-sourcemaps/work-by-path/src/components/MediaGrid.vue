<script setup lang="ts">
import { useEmbyStore } from '../stores/emby'
import { useJobsStore } from '../stores/jobs'
import { useI18n } from '../composables/useI18n'
import MediaCard from './MediaCard.vue'
import BaseButton from './BaseButton.vue'
import type { EmbyItem } from '../api/types'

const { t } = useI18n()
const embyStore = useEmbyStore()

const emit = defineEmits<{
  selectVideo: [item: EmbyItem]
  quickAction: [item: EmbyItem]
  subtitleAction: [item: EmbyItem]
}>()

function goNextPage() {
  embyStore.nextPage()
}

function goPrevPage() {
  embyStore.prevPage()
}
</script>

<template>
  <div>
    <!-- Loading -->
    <div v-if="embyStore.loading" class="text-text-muted text-center py-12">
      Loading...
    </div>

    <!-- Empty State -->
    <div v-else-if="embyStore.filteredItems.length === 0" class="text-text-muted text-center py-12">
      {{ t('library.noResults') }}
    </div>

    <!-- Grid -->
    <div v-else class="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
      <MediaCard
        v-for="item in embyStore.items"
        :key="item.id"
        :item="item"
        @click="emit('selectVideo', item)"
        @quickAction="emit('quickAction', item)"
        @subtitleAction="emit('subtitleAction', item)"
      />
    </div>

    <!-- Pagination -->
    <div v-if="embyStore.totalPages > 1" class="flex justify-center items-center gap-4 mt-6">
      <BaseButton
        variant="secondary"
        size="sm"
        @click="goPrevPage"
        :disabled="embyStore.currentPage <= 1"
      >
        Previous
      </BaseButton>
      <span class="text-text-secondary text-sm">
        Page {{ embyStore.currentPage }} / {{ embyStore.totalPages }}
      </span>
      <BaseButton
        variant="secondary"
        size="sm"
        @click="goNextPage"
        :disabled="embyStore.currentPage >= embyStore.totalPages"
      >
        Next
      </BaseButton>
    </div>
  </div>
</template>
