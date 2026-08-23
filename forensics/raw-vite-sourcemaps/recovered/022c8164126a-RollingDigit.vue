<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'

const props = defineProps<{
  target: string
  delay: number
  rolling: boolean
}>()

const display = ref('0')
let intervalId: ReturnType<typeof setInterval> | null = null

function spinRandom() {
  display.value = String(Math.floor(Math.random() * 10))
}

// Computed: show rolling random OR final target
const currentDisplay = computed(() => {
  if (props.rolling) {
    return display.value
  }
  return props.target
})

onMounted(() => {
  if (props.rolling) {
    spinRandom()
    intervalId = setInterval(spinRandom, 60)
  } else {
    display.value = props.target
  }
})

onUnmounted(() => {
  if (intervalId) clearInterval(intervalId)
})
</script>

<template>
  <span class="rolling-digit" :class="{ 'is-rolling': props.rolling }">
    {{ currentDisplay }}
  </span>
</template>

<style scoped>
.rolling-digit {
  display: inline-block;
  min-width: 0.55em;
  text-align: center;
  font-variant-numeric: tabular-nums;
}

.is-rolling {
  opacity: 0.6;
}
</style>
