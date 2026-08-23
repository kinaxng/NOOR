<script setup lang="ts">
withDefaults(defineProps<{
  modelValue?: boolean
  label?: string
}>(), {
  modelValue: false,
  label: '',
})

const emit = defineEmits<{ 'update:modelValue': [value: boolean] }>()
</script>

<template>
  <label class="noor-toggle">
    <input
      type="checkbox"
      :checked="modelValue"
      @change="emit('update:modelValue', ($event.target as HTMLInputElement).checked)"
    />
    <span>{{ label }}</span>
  </label>
</template>
