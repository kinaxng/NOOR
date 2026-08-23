<script setup lang="ts">
import NoorSkeleton from './NoorSkeleton.vue'

withDefaults(defineProps<{
  mediaRatio?: string
  lines?: number
  action?: boolean
}>(), {
  mediaRatio: '16 / 9',
  lines: 2,
  action: false,
})
</script>

<template>
  <div class="noor-skeleton-card">
    <NoorSkeleton width="100%" height="auto" radius="0" class="noor-skeleton-card__media" :style="{ aspectRatio: mediaRatio }" />
    <div class="noor-skeleton-card__body">
      <NoorSkeleton height="34px" radius="8px" />
      <NoorSkeleton v-for="i in Math.max(0, lines - 1)" :key="i" height="12px" :width="i % 2 ? '62%' : '78%'" />
      <div v-if="action" class="noor-skeleton-card__actions">
        <NoorSkeleton width="92px" height="26px" radius="9px" />
      </div>
    </div>
  </div>
</template>

<style scoped>
.noor-skeleton-card{display:flex;flex-direction:column;overflow:hidden;border:1px solid rgba(255,255,255,.06);background:var(--color-bg-surface,rgb(26,31,55));min-width:0}
.noor-skeleton-card__media{flex:0 0 auto}
.noor-skeleton-card__body{display:flex;flex-direction:column;gap:8px;padding:9px 10px 10px;min-height:90px}
.noor-skeleton-card__actions{display:flex;justify-content:flex-end;margin-top:auto}
</style>
