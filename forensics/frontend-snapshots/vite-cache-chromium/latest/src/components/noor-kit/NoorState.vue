<script setup lang="ts">
withDefaults(defineProps<{
  type?: 'empty' | 'loading' | 'error'
  title?: string
  description?: string
}>(), {
  type: 'empty',
  title: '',
  description: '',
})
</script>

<template>
  <div class="noor-state" :class="`noor-state--${type}`">
    <span v-if="type === 'loading'" class="noor-state__spinner" />
    <div class="noor-state__title">{{ title || (type === 'loading' ? '加载中' : type === 'error' ? '加载失败' : '暂无内容') }}</div>
    <div v-if="description" class="noor-state__description">{{ description }}</div>
  </div>
</template>
