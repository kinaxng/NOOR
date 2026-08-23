<script setup lang="ts">
defineProps<{
  tabs: Array<{ key: string; label: string; disabled?: boolean }>
  modelValue: string
}>()

const emit = defineEmits<{ 'update:modelValue': [value: string] }>()
</script>

<template>
  <UTabs
    :model-value="modelValue"
    :items="tabs.map(tab => ({ label: tab.label, value: tab.key, disabled: tab.disabled }))"
    color="primary"
    variant="pill"
    size="sm"
    class="noor-tabs"
    @update:model-value="emit('update:modelValue', String($event))"
  />
</template>
