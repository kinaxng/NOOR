<script setup lang="ts">
import NoorSkeletonCard from './NoorSkeletonCard.vue'

withDefaults(defineProps<{
  count?: number
  minWidth?: string
  action?: boolean
}>(), {
  count: 12,
  minWidth: '300px',
  action: false,
})
</script>

<template>
  <div class="noor-skeleton-grid" :style="{ gridTemplateColumns: `repeat(auto-fill,minmax(${minWidth},1fr))` }">
    <NoorSkeletonCard v-for="i in count" :key="i" :action="action" />
  </div>
</template>

<style scoped>
.noor-skeleton-grid{display:grid;gap:12px}
@media(max-width:760px){.noor-skeleton-grid{grid-template-columns:1fr!important}}
</style>
