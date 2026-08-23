<script setup lang="ts">
defineProps<{
  tabs: Array<{ key: string; label: string }>
  modelValue: string
}>()

const emit = defineEmits<{ 'update:modelValue': [value: string] }>()
</script>

<template>
  <div class="noor-tabs" role="tablist">
    <UButton
      v-for="tab in tabs"
      :key="tab.key"
      type="button"
      :color="tab.key === modelValue ? 'primary' : 'neutral'"
      :variant="tab.key === modelValue ? 'solid' : 'ghost'"
      size="sm"
      class="noor-tab"
      :class="{ 'is-active': tab.key === modelValue }"
      role="tab"
      @click="emit('update:modelValue', tab.key)"
    >
      {{ tab.label }}
    </UButton>
  </div>
</template>
