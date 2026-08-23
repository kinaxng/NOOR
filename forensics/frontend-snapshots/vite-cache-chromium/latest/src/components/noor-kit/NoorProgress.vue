<script setup lang="ts">
withDefaults(defineProps<{
  value?: number
  tone?: 'primary' | 'info' | 'success' | 'warning' | 'danger' | 'secondary'
  variant?: 'solid' | 'soft'
  shimmer?: boolean
}>(), {
  value: 0,
  tone: 'info',
  variant: 'solid',
  shimmer: false,
})
</script>

<template>
  <div class="noor-progress">
    <div
      class="noor-progress__bar"
      :class="[`noor-progress__bar--${tone}`, `noor-progress__bar--${variant}`]"
      :style="{ width: `${Math.min(100, Math.max(0, value))}%` }"
    >
      <div v-if="shimmer" class="noor-progress__shimmer" />
    </div>
  </div>
</template>

<style scoped>
.noor-progress {
  width: 100%;
  height: 6px;
  background: rgba(255, 255, 255, 0.08);
  border-radius: 999px;
  overflow: hidden;
}

.noor-progress__bar {
  height: 100%;
  border-radius: 999px;
  position: relative;
  overflow: hidden;
  transition: width 0.35s cubic-bezier(0.22, 1, 0.36, 1);
}

.noor-progress__shimmer {
  position: absolute;
  inset: 0;
  background: linear-gradient(90deg, transparent 0%, rgba(255, 255, 255, 0.35) 50%, transparent 100%);
  background-size: 200% 100%;
  animation: noor-progress-shimmer 1.3s ease-in-out infinite;
}

@keyframes noor-progress-shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

.noor-progress__bar--solid.noor-progress__bar--primary,
.noor-progress__bar--solid.noor-progress__bar--info { background: #0075FF; }
.noor-progress__bar--solid.noor-progress__bar--success { background: #01B574; }
.noor-progress__bar--solid.noor-progress__bar--warning { background: #FFB547; }
.noor-progress__bar--solid.noor-progress__bar--danger { background: #E31A1A; }
.noor-progress__bar--solid.noor-progress__bar--secondary { background: #627594; }

.noor-progress__bar--soft.noor-progress__bar--primary,
.noor-progress__bar--soft.noor-progress__bar--info { background: rgba(0, 117, 255, 0.72); }
.noor-progress__bar--soft.noor-progress__bar--success { background: rgba(1, 181, 116, 0.72); }
.noor-progress__bar--soft.noor-progress__bar--warning { background: rgba(255, 181, 71, 0.72); }
.noor-progress__bar--soft.noor-progress__bar--danger { background: rgba(227, 26, 26, 0.72); }
.noor-progress__bar--soft.noor-progress__bar--secondary { background: rgba(98, 117, 148, 0.72); }
</style>
