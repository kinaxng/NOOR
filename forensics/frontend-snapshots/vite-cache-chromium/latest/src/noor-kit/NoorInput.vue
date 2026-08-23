<script setup lang="ts">
withDefaults(defineProps<{
  modelValue?: string | number
  placeholder?: string
  type?: string
}>(), {
  modelValue: '',
  placeholder: '',
  type: 'text',
})

const emit = defineEmits<{ 'update:modelValue': [value: string] }>()
</script>

<template>
  <UInput
    :model-value="String(modelValue ?? '')"
    :type="type"
    :placeholder="placeholder"
    size="sm"
    class="noor-input"
    @update:model-value="emit('update:modelValue', String($event ?? ''))"
  />
</template>
