<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'

const props = withDefaults(defineProps<{
  title?: string
  summary?: string
  className?: string
  collapsible?: boolean
  collapseKey?: string
  defaultCollapsed?: boolean
}>(), {
  title: '',
  summary: '',
  className: '',
  collapsible: false,
  collapseKey: '',
  defaultCollapsed: true,
})

const collapsed = ref(false)
const storageKey = computed(() => props.collapseKey ? `noor:filter-panel:${props.collapseKey}` : '')
const legacyStorageKey = computed(() => props.collapseKey ? `noor:control-panel:${props.collapseKey}` : '')

function readCollapsed() {
  if (!props.collapsible) return false
  if (typeof window === 'undefined') return !!props.defaultCollapsed
  if (!storageKey.value) return !!props.defaultCollapsed
  const saved = window.localStorage.getItem(storageKey.value)
  if (saved == null && legacyStorageKey.value) {
    const legacySaved = window.localStorage.getItem(legacyStorageKey.value)
    if (legacySaved != null) return legacySaved === '1'
  }
  if (saved == null) return !!props.defaultCollapsed
  return saved === '1'
}

function writeCollapsed(value: boolean) {
  if (!props.collapsible || typeof window === 'undefined' || !storageKey.value) return
  window.localStorage.setItem(storageKey.value, value ? '1' : '0')
}

function toggleCollapse() {
  collapsed.value = !collapsed.value
}

onMounted(() => {
  collapsed.value = readCollapsed()
})

watch(() => [props.collapsible, props.collapseKey, props.defaultCollapsed], () => {
  collapsed.value = readCollapsed()
})

watch(collapsed, value => {
  writeCollapsed(value)
})
</script>

<template>
  <section :class="['noor-control-panel', className, { 'is-collapsed': collapsible && collapsed, 'is-collapsible': collapsible }]">
    <button
      v-if="collapsible"
      type="button"
      class="noor-control-panel__collapse-btn"
      :title="collapsed ? '展开筛选面板' : '收起筛选面板'"
      @click="toggleCollapse"
    >
      <span class="noor-control-panel__collapse-icon">⌃</span>
    </button>
    <div v-if="title || summary || $slots.actions" class="noor-control-panel__header">
      <div class="noor-control-panel__header-main">
        <strong v-if="title" class="noor-control-panel__title">{{ title }}</strong>
        <span v-if="summary" class="noor-control-panel__summary">{{ summary }}</span>
      </div>
      <div v-if="$slots.actions" class="noor-control-panel__header-actions">
        <slot name="actions" />
      </div>
    </div>
    <div v-if="$slots.primary" class="noor-control-panel__row noor-control-panel__row--primary">
      <slot name="primary" />
    </div>
    <div v-if="$slots.secondary" class="noor-control-panel__row noor-control-panel__row--secondary">
      <slot name="secondary" />
    </div>
    <div v-if="$slots.tertiary" class="noor-control-panel__row noor-control-panel__row--tertiary">
      <slot name="tertiary" />
    </div>
    <div class="noor-control-panel__body">
      <div v-if="$slots.left" class="noor-control-panel__left">
        <slot name="left" />
      </div>
      <div v-if="$slots.right" class="noor-control-panel__right">
        <slot name="right" />
      </div>
    </div>
    <div v-if="$slots.default" class="noor-control-panel__footer">
      <slot />
    </div>
  </section>
</template>
