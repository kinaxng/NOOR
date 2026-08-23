<script setup lang="ts">
withDefaults(defineProps<{
  icon?: string
  tone?: 'primary' | 'secondary' | 'danger' | 'ghost'
  size?: 'xs' | 'sm' | 'md'
  disabled?: boolean
  loading?: boolean
  title?: string
  ariaLabel?: string
}>(), {
  icon: '',
  tone: 'secondary',
  size: 'sm',
  disabled: false,
  loading: false,
  title: '',
  ariaLabel: '',
})

const toneMap = {
  primary: { color: 'primary', variant: 'solid' },
  secondary: { color: 'neutral', variant: 'soft' },
  danger: { color: 'error', variant: 'soft' },
  ghost: { color: 'neutral', variant: 'ghost' },
} as const
</script>

<template>
  <UButton
    :icon="icon || undefined"
    :disabled="disabled"
    :loading="loading"
    :title="title || undefined"
    :aria-label="ariaLabel || title || undefined"
    :color="toneMap[tone].color"
    :variant="toneMap[tone].variant"
    :size="size"
    square
    class="noor-icon-button"
  >
    <slot />
  </UButton>
</template>

