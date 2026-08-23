<script setup lang="ts">
withDefaults(defineProps<{
  title: string
  metrics: { label: string; value: string; unit?: string }[]
  progressValue?: number
  progressLabel?: string
  progressColor?: string
}>(), {
  progressValue: 0,
  progressColor: '#0075FF',
})
</script>

<template>
  <UCard variant="subtle" class="ui-card">
    <div class="flex items-center justify-between mb-3">
      <h3 class="text-sm font-semibold text-white">{{ title }}</h3>
      <span v-if="progressLabel" class="text-xs text-white/55">{{ progressLabel }}</span>
    </div>

    <div class="space-y-2 mb-3">
      <div v-for="m in metrics" :key="m.label" class="flex items-center justify-between text-xs">
        <span class="text-white/55">{{ m.label }}</span>
        <span class="text-white/85">{{ m.value }}<span v-if="m.unit" class="text-white/55"> {{ m.unit }}</span></span>
      </div>
    </div>

    <div class="h-1.5 rounded-full bg-white/10 overflow-hidden">
      <div class="h-full rounded-full transition-all duration-300" :style="{ width: `${Math.max(0, Math.min(100, progressValue || 0))}%`, background: progressColor }" />
    </div>
  </UCard>
</template>
