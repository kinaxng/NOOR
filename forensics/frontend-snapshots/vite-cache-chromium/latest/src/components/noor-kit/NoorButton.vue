<script setup lang="ts">
withDefaults(defineProps<{
  tone?: 'primary' | 'secondary' | 'danger' | 'ghost' | 'link'
  size?: 'xs' | 'sm' | 'md'
  disabled?: boolean
  loading?: boolean
  icon?: string
  type?: 'button' | 'submit' | 'reset'
}>(), {
  tone: 'secondary',
  size: 'sm',
  disabled: false,
  loading: false,
  type: 'button',
})

const toneMap = {
  primary: { color: 'primary', variant: 'solid' },
  secondary: { color: 'neutral', variant: 'soft' },
  danger: { color: 'error', variant: 'soft' },
  ghost: { color: 'neutral', variant: 'ghost' },
  link: { color: 'primary', variant: 'link' },
} as const
</script>

<template>
  <UButton
    :type="type"
    :disabled="disabled"
    :loading="loading"
    :icon="icon"
    :color="toneMap[tone].color"
    :variant="toneMap[tone].variant"
    :size="size"
    class="noor-button"
  >
    <slot />
  </UButton>
</template>
