<script setup lang="ts">
withDefaults(defineProps<{
  width?: string
  height?: string
  radius?: string
  inline?: boolean
}>(), {
  width: '100%',
  height: '1rem',
  radius: '8px',
  inline: false,
})
</script>

<template>
  <span
    class="noor-skeleton"
    :class="{ 'noor-skeleton--inline': inline }"
    :style="{ width, height, borderRadius: radius }"
    aria-hidden="true"
  />
</template>

<style scoped>
.noor-skeleton{position:relative;display:block;overflow:hidden;background:rgba(255,255,255,.045)}
.noor-skeleton--inline{display:inline-block;vertical-align:middle}
.noor-skeleton::after{content:"";position:absolute;inset:0;transform:translateX(-100%);background:linear-gradient(90deg,transparent,rgba(255,255,255,.08),transparent);animation:noor-skeleton-shimmer 1.2s infinite}
@keyframes noor-skeleton-shimmer{100%{transform:translateX(100%)}}
@media (prefers-reduced-motion: reduce){.noor-skeleton::after{animation:none}}
</style>
