<script setup lang="ts">
defineProps<{ align?: 'between' | 'start' }>()
</script>

<template>
  <div class="noor-top-action-bar" :class="align === 'start' ? 'noor-top-action-bar--start' : ''">
    <div v-if="$slots.tabs" class="noor-top-action-bar__tabs"><slot name="tabs" /></div>
    <div class="noor-top-action-bar__actions"><slot /></div>
  </div>
</template>
