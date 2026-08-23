<script setup lang="ts">
withDefaults(defineProps<{
  variant?: 'default' | 'soft'
}>(), {
  variant: 'default',
})
</script>

<template>
  <UCard
    :variant="variant === 'soft' ? 'soft' : 'subtle'"
    class="noor-card ui-card"
  >
    <slot />
  </UCard>
</template>

