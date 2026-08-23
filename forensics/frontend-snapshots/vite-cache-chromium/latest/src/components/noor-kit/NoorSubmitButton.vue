<script setup lang="ts">
const props = withDefaults(defineProps<{
  status?: 'idle' | 'submitting' | 'success' | 'error'
  progress?: number
  idleLabel?: string
  submittingLabel?: string
  successLabel?: string
  errorLabel?: string
  disabled?: boolean
}>(), {
  status: 'idle',
  progress: 0,
  idleLabel: '提交',
  submittingLabel: '提交中',
  successLabel: '已提交',
  errorLabel: '提交失败',
  disabled: false,
})

const emit = defineEmits<{ click: [MouseEvent] }>()

function label() {
  if (props.status === 'submitting') return props.progress ? `${Math.round(props.progress)}%` : props.submittingLabel
  if (props.status === 'success') return props.successLabel
  if (props.status === 'error') return props.errorLabel
  return props.idleLabel
}
</script>

<template>
  <button
    type="button"
    class="noor-submit-button"
    :class="`noor-submit-button--${status}`"
    :disabled="disabled || status === 'submitting' || status === 'success'"
    @click="emit('click', $event)"
  >
    <span v-if="status === 'submitting' || status === 'success'" class="noor-submit-button__bar" :style="{ width: `${status === 'success' ? 100 : Math.max(0, Math.min(100, progress || 0))}%` }" />
    <span class="noor-submit-button__label">{{ label() }}</span>
  </button>
</template>
