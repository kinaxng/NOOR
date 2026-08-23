<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(defineProps<{
  tone?: 'muted' | 'info' | 'success' | 'warning' | 'danger'
}>(), {
  tone: 'muted',
})

const color = computed(() => ({
  muted: 'neutral',
  info: 'info',
  success: 'success',
  warning: 'warning',
  danger: 'error',
}[props.tone]))
</script>

<template>
  <UBadge :color="color" variant="soft" size="sm" class="noor-badge" :class="`noor-badge--${tone}`">
    <slot />
  </UBadge>
</template>
