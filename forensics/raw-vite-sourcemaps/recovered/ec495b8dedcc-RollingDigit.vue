<script setup lang="ts">
import { ref, watch, onMounted, onUnmounted } from 'vue'

const props = defineProps<{
  target: string
  delay: number
}>()

const display = ref('0')
let intervalId: ReturnType<typeof setInterval> | null = null
let pendingTarget: string | null = null

function spinRandom() {
  display.value = String(Math.floor(Math.random() * 10))
}

function startRolling() {
  if (intervalId) return
  spinRandom()
  intervalId = setInterval(spinRandom, 60)
}

function stopRolling() {
  if (intervalId) {
    clearInterval(intervalId)
    intervalId = null
  }
  display.value = props.target
}

onMounted(() => {
  // Start rolling immediately on mount (visible before data loads)
  if (props.target === '' || props.target === '0') {
    startRolling()
  } else {
    // Data already loaded, do one roll animation then stop
    rollToTarget()
  }
})

function rollToTarget() {
  const chars = '0123456789'
  const duration = 600
  const start = performance.now()

  function frame(now: number) {
    const elapsed = now - start
    const progress = Math.min(elapsed / duration, 1)
    const eased = 1 - Math.pow(1 - progress, 3)

    if (progress < 1) {
      const idx = Math.floor(eased * chars.length) % chars.length
      display.value = chars[idx]
      requestAnimationFrame(frame)
    } else {
      display.value = props.target
    }
  }

  requestAnimationFrame(frame)
}

watch(() => props.target, (newTarget) => {
  // Data changed → stop rolling and roll to new target
  stopRolling()
  pendingTarget = newTarget
  // Small delay to show the "stop" state, then animate to target
  setTimeout(() => {
    if (pendingTarget === newTarget) {
      rollToTarget()
    }
  }, 100)
})
</script>

<template>
  <span class="rolling-digit">{{ display }}</span>
</template>

<style scoped>
.rolling-digit {
  display: inline-block;
  min-width: 0.55em;
  text-align: center;
  font-variant-numeric: tabular-nums;
}
</style>
