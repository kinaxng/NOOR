<script setup lang="ts">
defineProps<{
  open: boolean
  title?: string
  description?: string
  size?: 'sm' | 'md' | 'lg' | 'xl'
}>()

const emit = defineEmits<{ 'update:open': [value: boolean] }>()
</script>

<template>
  <UModal
    :open="open"
    :title="title"
    :description="description"
    :ui="{
      content: `noor-dialog noor-dialog--${size || 'md'}`,
      header: 'noor-dialog__header',
      body: 'noor-dialog__body',
      footer: 'noor-dialog__footer'
    }"
    @update:open="emit('update:open', $event)"
  >
    <template #body>
      <slot />
    </template>
    <template v-if="$slots.footer" #footer>
      <slot name="footer" />
    </template>
  </UModal>
</template>
