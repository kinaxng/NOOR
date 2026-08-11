<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import BaseIcon from './BaseIcon.vue'

const props = defineProps<{
  pluginId: string
  icon?: string
  class?: string
}>()

const failed = ref(false)
const svgMarkup = ref('')
const loadKey = computed(() => `${props.pluginId}:${props.icon || ''}`)

const assetUrl = computed(() => {
  const raw = (props.icon || '').trim()
  if (!raw || failed.value) return ''
  if (/^https?:\/\//i.test(raw)) return raw
  if (raw.startsWith('/api/plugins/')) return raw
  if (raw.includes('/') || raw.endsWith('.svg') || raw.endsWith('.png') || raw.endsWith('.webp') || raw.endsWith('.ico')) {
    return `/api/plugins/${encodeURIComponent(props.pluginId)}/assets/${raw.replace(/^\/+/, '')}`
  }
  return ''
})

const baseIconName = computed(() => {
  const raw = (props.icon || '').trim()
  if (!raw || assetUrl.value) return 'plugin'
  return raw
})

watch(loadKey, async () => {
  failed.value = false
  svgMarkup.value = ''
  const url = assetUrl.value
  if (!url || !/\.svg(?:$|\?)/i.test(url)) return
  try {
    const res = await fetch(url)
    if (!res.ok) throw new Error(`icon ${res.status}`)
    const text = await res.text()
    const start = text.search(/<svg[\s>]/i)
    if (start < 0) throw new Error('not svg')
    svgMarkup.value = text.slice(start)
  } catch {
    failed.value = true
    svgMarkup.value = ''
  }
}, { immediate: true })
</script>

<template>
  <span :class="['plugin-icon', $props.class]">
    <span v-if="svgMarkup" class="plugin-icon__svg" v-html="svgMarkup"></span>
    <img v-else-if="assetUrl" :src="assetUrl" alt="" class="plugin-icon__img" @error="failed = true" />
    <BaseIcon v-else :name="baseIconName" class="plugin-icon__fallback" />
  </span>
</template>

<style scoped>
.plugin-icon {
  display: inline-grid;
  place-items: center;
  width: 1.75rem;
  height: 1.75rem;
  color: currentColor;
}

.plugin-icon__img,
.plugin-icon__fallback,
.plugin-icon__svg,
.plugin-icon__svg :deep(svg) {
  width: 100%;
  height: 100%;
  display: block;
}

.plugin-icon__img {
  object-fit: contain;
}
</style>
