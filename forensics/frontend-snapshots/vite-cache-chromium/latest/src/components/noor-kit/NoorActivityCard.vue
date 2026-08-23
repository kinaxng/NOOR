<script setup lang="ts">
defineProps<{
  title?: string
}>()
</script>

<template>
  <UCard variant="subtle" class="ui-card">
    <div class="flex items-center justify-between mb-3">
      <h3 class="text-sm font-semibold text-white">{{ title }}</h3>
      <slot name="action" />
    </div>
    <div class="space-y-2">
      <slot />
    </div>
  </UCard>
</template>
