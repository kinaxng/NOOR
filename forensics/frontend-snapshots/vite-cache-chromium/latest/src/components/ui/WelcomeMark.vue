<script setup lang="ts">
import { computed } from 'vue'
import AnimatedGradientCanvas from './AnimatedGradientCanvas.vue'

const props = defineProps<{
  username?: string
  message?: string
  greeting?: string
}>()

const gradientConfig = computed(() => ({
  preset: 'Prism' as const,
  speed: 14,
}))
</script>

<template>
  <div class="welcome-mark">
    <AnimatedGradientCanvas :config="gradientConfig" radius="var(--radius-xl)" />
    <div class="welcome-mark__overlay" />
    <div class="welcome-mark__grain" />

    <div class="welcome-mark__content">
      <div class="welcome-mark__eyebrow">{{ props.greeting }}</div>
      <h2 class="welcome-mark__name">{{ props.username }}</h2>
      <p class="welcome-mark__message">{{ props.message }}</p>
    </div>
  </div>
</template>

<style scoped>
.welcome-mark {
  position: relative;
  min-height: 21.25rem;
  overflow: hidden;
  border-radius: var(--radius-xl);
  border: 1px solid var(--color-border-default);
  background: var(--color-bg-surface);
  box-shadow: var(--shadow-md);
  isolation: isolate;
}

.welcome-mark__overlay {
  position: absolute;
  inset: 0;
  z-index: 1;
  pointer-events: none;
  background:
    radial-gradient(circle at 18% 28%, rgba(255, 255, 255, 0.035), transparent 20%),
    linear-gradient(180deg, rgba(26, 31, 58, 0.48) 0%, rgba(26, 31, 58, 0.58) 100%),
    linear-gradient(90deg, rgba(3, 12, 29, 0.18) 0%, rgba(3, 12, 29, 0.04) 40%, rgba(3, 12, 29, 0.28) 100%),
    linear-gradient(140deg, rgba(26, 31, 58, 0.78) 0%, rgba(30, 37, 68, 0.44) 52%, rgba(3, 12, 29, 0.26) 100%);
}

.welcome-mark__grain {
  position: absolute;
  inset: 0;
  z-index: 2;
  pointer-events: none;
  opacity: 0.05;
  background-image:
    linear-gradient(rgba(255, 255, 255, 0.08) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255, 255, 255, 0.08) 1px, transparent 1px);
  background-size: 18px 18px;
  mask-image: linear-gradient(180deg, rgba(0, 0, 0, 0.72), transparent 100%);
}

.welcome-mark__content {
  position: relative;
  z-index: 3;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  justify-content: flex-start;
  gap: 0.75rem;
  height: 100%;
  padding: 1.5rem;
}

.welcome-mark__eyebrow {
  font-family: var(--font-display);
  font-size: var(--font-size-xs);
  font-weight: var(--font-weight-medium);
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: rgba(255, 255, 255, 0.62);
}

.welcome-mark__name {
  margin: 0;
  max-width: 16rem;
  font-family: var(--font-display);
  font-size: clamp(1.75rem, 2.3vw, 2.15rem);
  font-weight: var(--font-weight-bold);
  line-height: 1.1;
  color: var(--color-text-primary);
}

.welcome-mark__message {
  margin: 0;
  max-width: 28rem;
  padding-top: 0.15rem;
  font-family: var(--font-display);
  font-size: var(--font-size-base);
  line-height: 1.65;
  color: rgba(255, 255, 255, 0.78);
  white-space: pre-line;
}

@media (max-width: 1024px) {
  .welcome-mark {
    min-height: 18rem;
  }

  .welcome-mark__content {
    padding: 1.5rem;
  }

  .welcome-mark__message {
    max-width: 24rem;
    font-size: var(--font-size-sm);
  }
}
</style>
