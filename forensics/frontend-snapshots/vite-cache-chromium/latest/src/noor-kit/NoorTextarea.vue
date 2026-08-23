<script setup lang="ts">
withDefaults(defineProps<{
  modelValue?: string
  placeholder?: string
  rows?: number
}>(), {
  modelValue: '',
  placeholder: '',
  rows: 4,
})

const emit = defineEmits<{ 'update:modelValue': [value: string] }>()
</script>

<template>
  <UTextarea
    :model-value="modelValue"
    :placeholder="placeholder"
    :rows="rows"
    color="primary"
    variant="soft"
    size="sm"
    class="noor-textarea"
    @update:model-value="emit('update:modelValue', String($event ?? ''))"
  />
</template>
