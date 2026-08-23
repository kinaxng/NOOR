<script setup lang="ts">
const model = defineModel<boolean>({ default: false })

defineProps<{
  disabled?: boolean
}>()

function toggle() {
  if (model.value === undefined) model.value = false
  model.value = !model.value
}
</script>

<template>
  <button
    type="button"
    class="noor-switch"
    :class="{ 'is-on': model, 'is-disabled': disabled }"
    :disabled="disabled"
    role="switch"
    :aria-checked="model"
    @click="toggle"
  >
    <span class="noor-switch__thumb" />
  </button>
</template>

<style scoped>
.noor-switch {
  position: relative;
  width: 2.5rem;
  height: 1.4rem;
  border: 0;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.1);
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.08);
  cursor: pointer;
  transition: background var(--transition-fast), box-shadow var(--transition-fast), opacity var(--transition-fast);
  flex-shrink: 0;
}

.noor-switch:hover:not(:disabled) {
  background: rgba(255, 255, 255, 0.14);
}

.noor-switch:focus-visible {
  outline: none;
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.08), 0 0 0 3px rgba(0, 117, 255, 0.18);
}

.noor-switch.is-on {
  background: rgba(0, 117, 255, 0.82);
  box-shadow: inset 0 0 0 1px rgba(0, 117, 255, 0.16);
}

.noor-switch.is-on:hover:not(:disabled) {
  background: rgba(0, 117, 255, 0.9);
}

.noor-switch.is-disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.noor-switch__thumb {
  position: absolute;
  left: 0.2rem;
  top: 0.2rem;
  width: 1rem;
  height: 1rem;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.78);
  transition: transform var(--transition-fast), background var(--transition-fast);
}

.noor-switch.is-on .noor-switch__thumb {
  transform: translateX(1.1rem);
  background: #fff;
}
</style>
