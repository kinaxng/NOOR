<script setup lang="ts">
import { computed } from 'vue'

type SelectValue = string | number | boolean

const props = defineProps<{
  modelValue?: SelectValue
  options: Array<Record<string, any> & { label: string; disabled?: boolean }>
  placeholder?: string
  disabled?: boolean
  valueKey?: string
  labelKey?: string
}>()

const emit = defineEmits<{ 'update:modelValue': [value: SelectValue] }>()

const stringItems = computed(() => props.options.map((option) => ({
  ...option,
  __value: String(option[props.valueKey || 'value'] ?? '__NOOR_EMPTY__'),
  value: String(option[props.valueKey || 'value'] ?? '__NOOR_EMPTY__'),
})))

const stringModelValue = computed(() => props.modelValue === undefined || props.modelValue === null ? undefined : String(props.modelValue || '__NOOR_EMPTY__'))

function emitValue(value: SelectValue) {
  const valueKey = props.valueKey || 'value'
  const matched = props.options.find(option => String(option[valueKey] ?? '__NOOR_EMPTY__') === String(value))
  emit('update:modelValue', (matched ? matched[valueKey] : value) as SelectValue)
}
</script>

<template>
  <USelect
    :model-value="stringModelValue"
    :items="stringItems"
    :placeholder="placeholder"
    :disabled="disabled"
    value-key="__value"
    :label-key="labelKey || 'label'"
    color="primary"
    variant="soft"
    size="sm"
    class="noor-select"
    @update:model-value="emitValue($event as SelectValue)"
  />
</template>
