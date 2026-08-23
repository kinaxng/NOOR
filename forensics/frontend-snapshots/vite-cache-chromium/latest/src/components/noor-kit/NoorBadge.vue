<script setup lang="ts">
withDefaults(defineProps<{
  tone?: 'muted' | 'info' | 'success' | 'warning' | 'danger'
  size?: 'sm' | 'md'
}>(), {
  tone: 'muted',
  size: 'sm',
})

const toneMap = {
  muted: { color: 'neutral', variant: 'soft' },
  info: { color: 'info', variant: 'soft' },
  success: { color: 'success', variant: 'soft' },
  warning: { color: 'warning', variant: 'soft' },
  danger: { color: 'error', variant: 'soft' },
} as const
</script>

<template>
  <UBadge
    :color="toneMap[tone].color"
    :variant="toneMap[tone].variant"
    :size="size"
    class="noor-badge"
  >
    <slot />
  </UBadge>
</template>
