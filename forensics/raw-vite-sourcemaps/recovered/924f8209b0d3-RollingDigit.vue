<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'

const props = defineProps<{
  digit: string  // single character: '0'-'9'
  delay: number   // animation delay in ms
}>()

const displayDigit = ref('0')
const spinning = ref(false)

function rollTo(target: string, duration: number) {
  spinning.value = true
  const start = Date.now()
  const steps = 20
  const chars = '0123456789'

  const interval = setInterval(() => {
    const elapsed = Date.now() - start
    const progress = Math.min(elapsed / duration, 1)
    const eased = 1 - Math.pow(1 - progress, 3) // ease-out cubic

    if (progress < 1) {
      const idx = Math.floor(eased * chars.length * 0.99) % chars.length
      displayDigit.value = chars[idx]
    } else {
      clearInterval(interval)
      displayDigit.value = target
      spinning.value = false
    }
  }, duration / steps)
}

watch(() => props.digit, (newVal) => {
  rollTo(newVal, 800 + props.delay * 50)
})

onMounted(() => {
  rollTo(props.digit, 600 + props.delay * 50)
})
</script>

<template>
  <span
    class="rolling-digit"
    :style="{ animationDelay: delay + 'ms', opacity: spinning ? 0.4 : 1 }"
  >{{ displayDigit }}</span>
</template>

<style scoped>
.rolling-digit {
  display: inline-block;
  min-width: 0.6em;
  text-align: center;
  transition: color 0.1s;
}

.rolling-digit--spin {
  color: rgba(255, 255, 255, 0.4);
}
</style>
