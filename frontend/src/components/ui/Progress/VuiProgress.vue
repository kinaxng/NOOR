<script setup lang="ts">
withDefaults(defineProps<{
  value?: number
  color?: string
  variant?: 'contained' | 'gradient'
  shimmer?: boolean
  customClass?: string
}>(), {
  value: 0,
  color: 'info',
  variant: 'gradient',
  shimmer: false,
})
</script>

<template>
  <div class="vui-progress" :class="customClass">
    <div
      class="vui-progress__bar"
      :class="[`vui-progress__bar--${variant}`, `vui-progress__bar--${color}`]"
      :style="{ width: `${Math.min(100, Math.max(0, value))}%` }"
    >
      <div v-if="shimmer" class="vui-progress__shimmer" />
    </div>
  </div>
</template>

<style scoped>
.vui-progress {
  width: 100%;
  height: 0.375rem;
  background: rgba(255, 255, 255, 0.06);
  border-radius: 160px;
  overflow: hidden;
}

.vui-progress__bar {
  height: 100%;
  border-radius: 160px;
  transition: width 0.4s cubic-bezier(0.16, 1, 0.3, 1);
  position: relative;
  overflow: hidden;
}

.vui-progress__shimmer {
  position: absolute;
  inset: 0;
  background: linear-gradient(
    90deg,
    transparent 0%,
    rgba(255, 255, 255, 0.3) 50%,
    transparent 100%
  );
  background-size: 200% 100%;
  animation: shimmer-slide 1.5s ease-in-out infinite;
}

@keyframes shimmer-slide {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

/* Gradient variants */
.vui-progress__bar--gradient.vui-progress__bar--primary { background: #0075FF; }
.vui-progress__bar--gradient.vui-progress__bar--info { background: #0075FF; }
.vui-progress__bar--gradient.vui-progress__bar--success { background: #01B574; }
.vui-progress__bar--gradient.vui-progress__bar--warning { background: #FFB547; }
.vui-progress__bar--gradient.vui-progress__bar--error { background: #E31A1A; }
.vui-progress__bar--gradient.vui-progress__bar--secondary { background: #627594; }
.vui-progress__bar--gradient.vui-progress__bar--dark { background: #141727; }
.vui-progress__bar--gradient.vui-progress__bar--white { background: #FFFFFF; }
.vui-progress__bar--gradient.vui-progress__bar--cyan { background: #21D4FD; }
.vui-progress__bar--gradient.vui-progress__bar--magenta { background: #FF2D95; }
.vui-progress__bar--gradient.vui-progress__bar--amber { background: #FFB547; }

/* Contained variants */
.vui-progress__bar--contained.vui-progress__bar--primary {
  background: rgba(0, 117, 255, 0.2);
  color: #0075FF;
}
.vui-progress__bar--contained.vui-progress__bar--info {
  background: rgba(0, 117, 255, 0.2);
  color: #0075FF;
}
.vui-progress__bar--contained.vui-progress__bar--success {
  background: rgba(1, 181, 116, 0.2);
  color: #01B574;
}
.vui-progress__bar--contained.vui-progress__bar--warning {
  background: rgba(255, 181, 71, 0.2);
  color: #FFB547;
}
.vui-progress__bar--contained.vui-progress__bar--error {
  background: rgba(227, 26, 26, 0.2);
  color: #E31A1A;
}
.vui-progress__bar--contained.vui-progress__bar--white {
  background: rgba(255, 255, 255, 0.15);
  color: #FFFFFF;
}
.vui-progress__bar--contained.vui-progress__bar--cyan {
  background: rgba(33, 212, 253, 0.2);
  color: #21D4FD;
}
.vui-progress__bar--contained.vui-progress__bar--magenta {
  background: rgba(255, 45, 149, 0.2);
  color: #FF2D95;
}
.vui-progress__bar--contained.vui-progress__bar--amber {
  background: rgba(255, 181, 71, 0.2);
  color: #FFB547;
}
</style>
