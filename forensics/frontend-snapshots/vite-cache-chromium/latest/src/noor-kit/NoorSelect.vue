<script setup lang="ts">
type Option = { label: string; value: string | number | boolean }

withDefaults(defineProps<{
  modelValue?: string | number | boolean
  options?: Option[]
  placeholder?: string
  disabled?: boolean
}>(), {
  modelValue: '',
  options: () => [],
  placeholder: '请选择',
  disabled: false,
})

const emit = defineEmits<{ 'update:modelValue': [value: string | number | boolean] }>()

function decodeValue(value: string, options: Option[]) {
  const matched = options.find(option => String(option.value) === value)
  return matched ? matched.value : value
}
</script>

<template>
  <select
    class="noor-select"
    :value="String(modelValue ?? '')"
    :disabled="disabled"
    @change="emit('update:modelValue', decodeValue(($event.target as HTMLSelectElement).value, options))"
  >
    <option v-if="!options.length" value="">{{ placeholder }}</option>
    <option v-for="option in options" :key="String(option.value)" :value="String(option.value)">
      {{ option.label }}
    </option>
  </select>
</template>
