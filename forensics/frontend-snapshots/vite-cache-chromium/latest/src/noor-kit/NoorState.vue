<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(defineProps<{
  type?: 'loading' | 'empty' | 'error'
  title?: string
  description?: string
}>(), {
  type: 'empty',
  title: '',
  description: '',
})

const resolvedTitle = computed(() => props.title || (props.type === 'loading' ? '加载中' : props.type === 'error' ? '加载失败' : '暂无内容'))
const color = computed(() => props.type === 'error' ? 'error' : props.type === 'loading' ? 'info' : 'neutral')
</script>

<template>
  <UAlert :color="color" variant="soft" class="noor-state" :class="`noor-state--${type}`">
    <template #title>
      <span v-if="type === 'loading'" class="spinner" />
      <strong>{{ resolvedTitle }}</strong>
    </template>
    <template v-if="description" #description>
      {{ description }}
    </template>
  </UAlert>
</template>
