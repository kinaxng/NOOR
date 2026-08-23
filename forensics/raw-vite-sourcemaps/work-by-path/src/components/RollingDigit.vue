<script setup lang="ts">
import { ref, watch, onMounted, shallowRef } from 'vue'

const props = defineProps<{
  target: string
  delay: number
  rolling: boolean
  groupIdx: number  // 0-4: which stat group
  digitIdx: number // 0=ones, 1=tens, 2=hundreds
}>()

const DIGITS = ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9']
const DIGIT_H = 1.2 // em per digit

const offset = ref(0)
let stopTimeoutId: ReturnType<typeof setTimeout> | null = null
let scrollRafId: number | null = null

function getDigitIndex(d: string): number {
  const idx = DIGITS.indexOf(d)
  return idx >= 0 ? idx : 0
}

function easeOut(t: number): number {
  return 1 - Math.pow(1 - t, 3)
}

// Shared rolling state per group - all digits in same group share these
const groupState: Record<number, {
  isRolling: boolean
  counter: number
  intervalId: ReturnType<typeof setInterval> | null
}> = {
  0: { isRolling: false, counter: 0, intervalId: null },
  1: { isRolling: false, counter: 0, intervalId: null },
  2: { isRolling: false, counter: 0, intervalId: null },
  3: { isRolling: false, counter: 0, intervalId: null },
  4: { isRolling: false, counter: 0, intervalId: null },
}

// Shared offset refs per group - all digits in same group share the SAME ref
const groupOffsetRefs = {
  0: ref(0),
  1: ref(0),
  2: ref(0),
  3: ref(0),
  4: ref(0),
}

onMounted(() => {
  if (!groupState[props.groupIdx].isRolling) {
    offset.value = -getDigitIndex(props.target) * DIGIT_H
    groupOffsetRefs[props.groupIdx].value = offset.value
  }
})

watch(() => props.rolling, (isRolling) => {
  const state = groupState[props.groupIdx]

  if (isRolling) {
    if (scrollRafId) { cancelAnimationFrame(scrollRafId); scrollRafId = null }
    if (stopTimeoutId) { clearTimeout(stopTimeoutId); stopTimeoutId = null }

    state.isRolling = true
    if (state.intervalId) clearInterval(state.intervalId)
    let idx = 0
    state.counter = idx
    offset.value = -idx * DIGIT_H
    groupOffsetRefs[props.groupIdx].value = offset.value
    state.intervalId = setInterval(() => {
      idx = (idx + 1) % 10
      state.counter = idx
      offset.value = -idx * DIGIT_H
      groupOffsetRefs[props.groupIdx].value = offset.value
    }, 60)
  } else {
    if (state.intervalId) { clearInterval(state.intervalId); state.intervalId = null }
    state.isRolling = false
    stopTimeoutId = setTimeout(() => {
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
        offset.value = -(currentIdx * DIGIT_H)
        groupOffsetRefs[props.groupIdx].value = offset.value
        if (progress < 1) {
          scrollRafId = requestAnimationFrame(frame)
        } else {
          offset.value = -(targetIdx * DIGIT_H)
          groupOffsetRefs[props.groupIdx].value = offset.value
          scrollRafId = null
        }
      }
      scrollRafId = requestAnimationFrame(frame)
    }, 1000)
  }
}, { immediate: true })

watch(() => props.target, (newTarget) => {
  if (!groupState[props.groupIdx].isRolling) {
    offset.value = -getDigitIndex(newTarget) * DIGIT_H
    groupOffsetRefs[props.groupIdx].value = offset.value
  }
})
</script>

<template>
  <span class="rolling-digit">
    <span class="rolling-digit__clipper">
      <span class="rolling-digit__track" :style="{ transform: `translateY(${offset}em)` }">
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
