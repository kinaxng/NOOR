<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'

const props = defineProps<{
  target: string
  delay: number
  rolling: boolean
  groupIdx: number  // 0-4: which stat group
  digitIdx: number // 0=ones, 1=tens, 2=hundreds
}>()

const DIGITS = ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9']
const DIGIT_H = 1.2 // em per digit

function getDigitIndex(d: string): number {
  const idx = DIGITS.indexOf(d)
  return idx >= 0 ? idx : 0
}

function easeOut(t: number): number {
  return 1 - Math.pow(1 - t, 3)
}

// Per-group shared rolling state - reset on each module load (HMR-safe)
function createGroupState() {
  return {
    isRolling: false,
    counter: 0,
    intervalId: null as ReturnType<typeof setInterval> | null,
    rafId: null as number | null,
    stopTimeoutId: null as ReturnType<typeof setTimeout> | null,
    easeOutStarted: false,
  }
}
const groupState: Record<number, ReturnType<typeof createGroupState>> = {
  0: createGroupState(),
  1: createGroupState(),
  2: createGroupState(),
  3: createGroupState(),
  4: createGroupState(),
}

// Per-group shared offset ref
const groupOffsets = [
  ref(0),
  ref(0),
  ref(0),
  ref(0),
  ref(0),
]

const myOffset = groupOffsets[props.groupIdx]
const state = groupState[props.groupIdx]

onMounted(() => {
  myOffset.value = -getDigitIndex(props.target) * DIGIT_H
  state.counter = getDigitIndex(props.target)
})

watch(() => props.rolling, (isRolling) => {
  if (isRolling) {
    // Cancel any pending ease-out
    if (state.stopTimeoutId) { clearTimeout(state.stopTimeoutId); state.stopTimeoutId = null }
    if (state.rafId) { cancelAnimationFrame(state.rafId); state.rafId = null }
    state.easeOutStarted = false

    state.isRolling = true
    if (state.intervalId) clearInterval(state.intervalId)
    let idx = 0
    state.counter = idx
    myOffset.value = -idx * DIGIT_H
    state.intervalId = setInterval(() => {
      idx = (idx + 1) % 10
      state.counter = idx
      myOffset.value = -idx * DIGIT_H
    }, 60)
  } else {
    if (state.intervalId) { clearInterval(state.intervalId); state.intervalId = null }
    state.isRolling = false

    // Only one instance per group should start the ease-out
    if (state.easeOutStarted) return
    state.easeOutStarted = true

    // Don't overwrite an existing pending timeout
    if (state.stopTimeoutId) return
    state.stopTimeoutId = setTimeout(() => {
      const start = performance.now()
      const duration = 1000
      const targetIdx = getDigitIndex(props.target)
      const startIdx = state.counter

      function frame(now: number) {
        const elapsed = now - start
        const progress = Math.min(elapsed / duration, 1)
        const eased = easeOut(progress)
        const diff = (targetIdx - startIdx + 10) % 10
        const currentIdx = (startIdx + Math.round(diff * eased)) % 10
        myOffset.value = -(currentIdx * DIGIT_H)
        if (progress < 1) {
          state.rafId = requestAnimationFrame(frame)
        } else {
          myOffset.value = -(targetIdx * DIGIT_H)
          state.rafId = null
        }
      }
      state.rafId = requestAnimationFrame(frame)
    }, 1000)
  }
}, { immediate: true })

watch(() => props.target, (newTarget) => {
  if (!state.isRolling) {
    myOffset.value = -getDigitIndex(newTarget) * DIGIT_H
    state.counter = getDigitIndex(newTarget)
  }
})
</script>

<template>
  <span class="rolling-digit">
    <span class="rolling-digit__clipper">
      <span class="rolling-digit__track" :style="{ transform: `translateY(${myOffset}em)` }">
        <span v-for="d in DIGITS" :key="d" class="rolling-digit__cell">{{ d }}</span>
      </span>
    </span>
  </span>
</template>

<style scoped>
.rolling-digit {
  display: inline-block;
  position: relative;
  width: 0.65em;
  height: 1.2em;
  overflow: visible;
  vertical-align: top;
}

.rolling-digit__clipper {
  position: relative;
  width: 0.65em;
  height: 1.2em;
  overflow: hidden;
}

.rolling-digit__track {
  display: flex;
  flex-direction: column;
  position: absolute;
  top: 0;
  left: 0;
  width: 0.65em;
}

.rolling-digit__cell {
  display: block;
  width: 0.65em;
  height: 1.2em;
  line-height: 1.2em;
  text-align: center;
}
</style>
