<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(defineProps<{
  tone?: 'primary' | 'secondary' | 'danger' | 'ghost'
  disabled?: boolean
  type?: 'button' | 'submit' | 'reset'
}>(), {
  tone: 'secondary',
  disabled: false,
  type: 'button',
})

const color = computed(() => (props.tone === 'danger' ? 'error' : props.tone === 'primary' ? 'primary' : 'neutral'))
const variant = computed(() => (props.tone === 'ghost' ? 'ghost' : props.tone === 'primary' ? 'solid' : 'soft'))
</script>

<template>
  <UButton
    :type="type"
    :color="color"
    :variant="variant"
    size="sm"
    class="noor-button"
    :class="`noor-button--${tone}`"
    :disabled="disabled"
  >
    <slot />
  </UButton>
</template>
