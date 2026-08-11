<script setup lang="ts">
const props = withDefaults(defineProps<{
  status?: 'idle' | 'running' | 'success' | 'error'
  progress?: number
  disabled?: boolean
  idleLabel?: string
  runningLabel?: string
  successLabel?: string
  errorLabel?: string
  label?: string
  full?: boolean
  size?: 'md' | 'lg'
}>(), {
  status: 'idle',
  progress: 0,
  disabled: false,
  idleLabel: '提交',
  runningLabel: '',
  successLabel: '已完成',
  errorLabel: '失败',
  label: '',
  full: false,
  size: 'md',
})

const emit = defineEmits<{ click: [event: MouseEvent] }>()

function onClick(event: MouseEvent) {
  if (props.disabled || props.status === 'running' || props.status === 'success') return
  emit('click', event)
}
</script>

<template>
  <button
    type="button"
    class="vui-submit-button"
    :class="[`vui-submit-button--${status}`, `vui-submit-button--${size}`, { 'vui-submit-button--full': full }]"
    :disabled="disabled || status === 'running' || status === 'success'"
    @click="onClick"
  >
    <i class="vui-submit-button__bar" :style="{ width: `${Math.max(0, Math.min(100, progress || 0))}%` }"></i>
    <span class="vui-submit-button__label">
      <slot>
        {{ label || (status === 'success' ? successLabel : status === 'error' ? errorLabel : status === 'running' ? (runningLabel || `${Math.round(progress || 0)}%`) : idleLabel) }}
      </slot>
    </span>
  </button>
</template>

<style scoped>
.vui-submit-button {
  position: relative;
  overflow: hidden;
  isolation: isolate;
  min-width: 108px;
  min-height: 2.25rem;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0.55rem 1rem;
  border-radius: var(--radius-button);
  border: 1px solid rgba(0, 117, 255, 0.34);
  background: rgba(0, 117, 255, 0.16);
  color: #fff;
  font-family: var(--font-display);
  font-size: 0.75rem;
  font-weight: var(--font-weight-bold);
  line-height: 1;
  letter-spacing: 0.02em;
  transition: all var(--transition-fast);
  cursor: pointer;
}
.vui-submit-button--full { width: 100%; }
.vui-submit-button--lg { min-height: 2.5rem; }
.vui-submit-button:hover:not(:disabled) {
  border-color: rgba(57, 147, 254, 0.5);
  background: rgba(0, 117, 255, 0.22);
  transform: translateY(-1px);
}
.vui-submit-button:disabled { cursor: default; }
.vui-submit-button__bar {
  position: absolute;
  inset: 0 auto 0 0;
  width: 0;
  background: linear-gradient(90deg, rgba(0, 117, 255, 0.52), rgba(33, 212, 253, 0.34));
  transition: width 0.2s ease-out, background var(--transition-fast);
  z-index: -1;
}
.vui-submit-button__label {
  position: relative;
  z-index: 1;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.vui-submit-button--running {
  border-color: rgba(33, 212, 253, 0.45);
  background: rgba(33, 212, 253, 0.1);
}
.vui-submit-button--success {
  border-color: rgba(1, 181, 116, 0.46);
  background: rgba(1, 181, 116, 0.22);
}
.vui-submit-button--success .vui-submit-button__bar {
  width: 100% !important;
  background: rgba(1, 181, 116, 0.36);
}
.vui-submit-button--error {
  border-color: rgba(227, 26, 26, 0.38);
  background: rgba(227, 26, 26, 0.14);
}
.vui-submit-button--error .vui-submit-button__bar {
  width: 100% !important;
  background: rgba(227, 26, 26, 0.22);
}
</style>
