<script setup lang="ts">
withDefaults(defineProps<{
  active?: boolean
  disabled?: boolean
  size?: 'xs' | 'sm'
  tone?: 'secondary' | 'primary' | 'danger'
}>(), {
  active: false,
  disabled: false,
  size: 'sm',
  tone: 'secondary',
})

const toneMap = {
  secondary: { color: 'neutral', variant: 'soft' },
  primary: { color: 'primary', variant: 'soft' },
  danger: { color: 'error', variant: 'soft' },
} as const
</script>

<template>
  <UButton
    :disabled="disabled"
    :color="toneMap[tone].color"
    :variant="active ? 'solid' : toneMap[tone].variant"
    :size="size"
    class="noor-chip-button"
    :class="{ 'noor-chip-button--active': active }"
  >
    <slot />
  </UButton>
</template>

