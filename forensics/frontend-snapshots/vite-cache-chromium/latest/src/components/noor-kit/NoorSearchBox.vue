<script setup lang="ts">
withDefaults(defineProps<{
  modelValue?: string
  placeholder?: string
  compact?: boolean
}>(), {
  modelValue: '',
  placeholder: '搜索',
  compact: false,
})

const emit = defineEmits<{ 'update:modelValue': [value: string]; clear: [] }>()

function clear() {
  emit('update:modelValue', '')
  emit('clear')
}
</script>

<template>
  <div class="noor-search-box" :class="{ 'noor-search-box--compact': compact, 'is-active': !!modelValue }">
    <UInput
      :model-value="modelValue"
      :placeholder="placeholder"
      size="sm"
      color="primary"
      variant="soft"
      class="noor-search-box__input"
      @update:model-value="emit('update:modelValue', String($event ?? ''))"
    />
    <button v-if="modelValue" type="button" class="noor-search-box__clear" aria-label="清除搜索" @click="clear">×</button>
  </div>
</template>
