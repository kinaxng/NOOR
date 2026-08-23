<script setup lang="ts">
withDefaults(defineProps<{
  modelValue?: string | number
  placeholder?: string
  type?: string
  disabled?: boolean
  readonly?: boolean
  size?: 'sm' | 'md'
}>(), {
  modelValue: '',
  placeholder: '',
  type: 'text',
  disabled: false,
  readonly: false,
  size: 'sm',
})

const emit = defineEmits<{ 'update:modelValue': [value: string] }>()
</script>

<template>
  <UInput
    :model-value="modelValue"
    :placeholder="placeholder"
    :type="type"
    :disabled="disabled"
    :readonly="readonly"
    :size="size"
    color="primary"
    variant="soft"
    class="noor-input"
    @update:model-value="emit('update:modelValue', String($event ?? ''))"
  />
</template>
