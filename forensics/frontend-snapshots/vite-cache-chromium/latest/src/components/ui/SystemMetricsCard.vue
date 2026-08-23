<script setup lang="ts">
import BaseIcon from '../noor/BaseIcon.vue'

withDefaults(defineProps<{
  title: string
  metrics: { label: string; value: string; unit?: string }[]
  progressValue?: number  // 0-100
  progressLabel?: string
  progressColor?: string  // default '#0075FF'
}>(), {
  progressValue: 0,
  progressColor: '#0075FF',
})
</script>

<template>
  <div class="system-metrics-card ui-card flex flex-col">
    <!-- Header -->
    <div class="system-metrics-card__header flex items-center justify-between">
      <h3 class="system-metrics-card__title">{{ title }}</h3>
      <BaseIcon name="activity" class="system-metrics-card__icon w-[18px] h-[18px]" />
    </div>

    <div class="system-metrics-card__body flex items-center flex-1 gap-6">
      <div class="system-metrics-card__metrics flex-1">
        <div
          v-for="metric in metrics"
          :key="metric.label"
          class="system-metrics-card__metric-row"
        >
          <span class="system-metrics-card__metric-label">{{ metric.label }}</span>
          <span class="system-metrics-card__metric-value">
            {{ metric.value }}<span v-if="metric.unit" class="system-metrics-card__metric-unit">{{ metric.unit }}</span>
          </span>
        </div>
      </div>

      <div v-if="progressValue !== undefined" class="system-metrics-card__ring flex-shrink-0 relative">
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
        <div class="system-metrics-card__ring-center absolute inset-0 flex flex-col items-center justify-center">
          <span class="system-metrics-card__ring-value">{{ progressValue }}%</span>
          <span v-if="progressLabel" class="system-metrics-card__ring-label">{{ progressLabel }}</span>
        </div>
      </div>
    </div>
  </div>
</template>


<style scoped>
.system-metrics-card {
  padding: 1.5rem;
  border: 1px solid var(--color-border-default);
  background: linear-gradient(180deg, rgba(255,255,255,0.015) 0%, rgba(255,255,255,0) 100%), var(--color-bg-surface);
}

.system-metrics-card__header {
  margin-bottom: 1.25rem;
  padding-bottom: 0.95rem;
  border-bottom: 1px solid var(--color-border-subtle);
}

.system-metrics-card__title {
  font-family: var(--font-display);
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-semibold);
  color: var(--color-text-primary);
}

.system-metrics-card__icon {
  color: var(--color-brand);
  opacity: 0.95;
}

.system-metrics-card__body {
  justify-content: space-between;
}

.system-metrics-card__metrics {
  display: flex;
  flex-direction: column;
  gap: 0.8rem;
}

.system-metrics-card__metric-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.9rem;
}

.system-metrics-card__metric-label {
  font-family: var(--font-display);
  font-size: 11px;
  color: rgba(255,255,255,0.46);
}

.system-metrics-card__metric-value {
  font-family: var(--font-display);
  font-size: 0.95rem;
  font-weight: var(--font-weight-semibold);
  color: var(--color-text-primary);
}

.system-metrics-card__metric-unit {
  margin-left: 0.3rem;
  font-size: 11px;
  color: rgba(255,255,255,0.38);
}

.system-metrics-card__ring {
  width: 108px;
  height: 108px;
}

.system-metrics-card__ring-center {
  gap: 0.05rem;
}

.system-metrics-card__ring-value {
  font-family: var(--font-display);
  font-size: 1.85rem;
  font-weight: var(--font-weight-bold);
  color: var(--color-text-primary);
}

.system-metrics-card__ring-label {
  font-family: var(--font-display);
  font-size: 11px;
  color: rgba(255,255,255,0.4);
}

@media (max-width: 768px) {
  .system-metrics-card {
    padding: 1rem;
  }

  .system-metrics-card__body {
    gap: 0.9rem;
  }

  .system-metrics-card__metrics {
    gap: 0.65rem;
  }

  .system-metrics-card__ring {
    width: 92px;
    height: 92px;
  }

  .system-metrics-card__ring-value {
    font-size: 1.55rem;
  }
}
</style>
