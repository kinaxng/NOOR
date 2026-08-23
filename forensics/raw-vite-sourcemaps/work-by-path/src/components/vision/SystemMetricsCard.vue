<script setup lang="ts">
import { computed } from 'vue'
import BaseIcon from '../BaseIcon.vue'
import RollingDigit from '../RollingDigit.vue'

const props = withDefaults(defineProps<{
  title: string
  metrics: { label: string; value: string; unit?: string }[]
  progressValue?: number  // 0-100
  progressLabel?: string
  progressColor?: string  // default '#0075FF'
  rolling?: boolean      // whether numbers should roll
}>(), {
  progressValue: 0,
  progressColor: '#0075FF',
  rolling: false,
})

// Split a value into digit segments for RollingDigit
// e.g. "8.2" -> [{ type: 'digit', value: '8' }, { type: 'text', value: '.' }, { type: 'digit', value: '2' }]
type Segment = { type: 'digit'; value: string } | { type: 'text'; value: string }
function splitValue(value: string): Segment[] {
  const result: Segment[] = []
  let current = ''
  for (const ch of value) {
    if (/[0-9]/.test(ch)) {
      if (current && result.length > 0) {
        result.push({ type: 'text', value: current })
        current = ''
      }
      result.push({ type: 'digit', value: ch })
    } else {
      if (result.length > 0 && result[result.length - 1].type === 'text') {
        current += ch
      } else {
        current += ch
      }
    }
  }
  if (current) result.push({ type: 'text', value: current })
  return result
}

const progressDigits = computed(() => splitValue(String(props.progressValue)))

</script>

<template>
  <div class="vision-card flex flex-col">
    <!-- Header -->
    <div class="flex items-center justify-between mb-6">
      <h3 class="text-sm font-semibold font-display text-white">{{ title }}</h3>
      <BaseIcon name="activity" class="w-[18px] h-[18px] text-[#0075FF]" />
    </div>

    <div class="flex items-center flex-1 gap-6">
      <!-- Metrics list -->
      <div class="flex-1 space-y-4">
        <div
          v-for="metric in metrics"
          :key="metric.label"
          class="flex items-center justify-between"
        >
          <span class="text-xs text-white/50 font-display">{{ metric.label }}</span>
          <span class="text-sm font-semibold font-display text-white">
            {{ metric.value }}<span v-if="metric.unit" class="text-xs text-white/40 ml-1">{{ metric.unit }}</span>
          </span>
        </div>
      </div>

      <!-- Circular progress -->
      <div v-if="progressValue !== undefined" class="flex-shrink-0 relative" style="width: 120px; height: 120px;">
        <svg
          viewBox="0 0 120 120"
          class="w-full h-full"
          style="transform: rotate(-90deg); overflow: visible;"
        >
          <!-- Track -->
          <circle
            cx="60"
            cy="60"
            r="50"
            fill="none"
            stroke="rgba(255,255,255,0.06)"
            stroke-width="10"
          />
          <!-- Progress -->
          <circle
            cx="60"
            cy="60"
            r="50"
            fill="none"
            :stroke="progressColor"
            stroke-width="10"
            stroke-linecap="round"
            :stroke-dasharray="314.159"
            :stroke-dashoffset="314.159 * (1 - progressValue / 100)"
            style="transition: stroke-dashoffset 400ms ease;"
          />
        </svg>
        <!-- Center text -->
        <div class="absolute inset-0 flex flex-col items-center justify-center">
          <span class="text-xl font-bold font-display text-white">{{ progressValue }}%</span>
          <span v-if="progressLabel" class="text-xs text-white/40 font-display">{{ progressLabel }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

