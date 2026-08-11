<script setup lang="ts">
const model = defineModel<boolean>({ default: false })

defineProps<{
  disabled?: boolean
}>()

function toggle() {
  model.value = !model.value
}
</script>

<template>
  <button
    type="button"
    class="settings-switch"
    :class="{ 'settings-switch--on': model, 'settings-switch--disabled': disabled }"
    :disabled="disabled"
    role="switch"
    :aria-checked="model"
    @click="toggle"
  >
    <span class="settings-switch__thumb" />
  </button>
</template>

<style scoped>
.settings-switch {
  position: relative;
  display: inline-flex;
  align-items: center;
  width: 2.5rem;
  height: 1.4rem;
  padding: 0;
  border: 0;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.1);
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.08);
  cursor: pointer;
  transition: background var(--transition-fast), box-shadow var(--transition-fast), opacity var(--transition-fast);
  flex-shrink: 0;
}

.settings-switch:hover:not(:disabled) {
  background: rgba(255, 255, 255, 0.14);
}

.settings-switch:focus-visible {
  outline: none;
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.08), 0 0 0 3px rgba(0, 117, 255, 0.18);
}

.settings-switch--on {
  background: rgba(0, 117, 255, 0.82);
  box-shadow: inset 0 0 0 1px rgba(0, 117, 255, 0.16);
}

.settings-switch--on:hover:not(:disabled) {
  background: rgba(0, 117, 255, 0.9);
}

.settings-switch--disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.settings-switch__thumb {
  width: 1rem;
  height: 1rem;
  margin-left: 0.2rem;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.78);
  transition: transform var(--transition-fast), background var(--transition-fast);
}

.settings-switch--on .settings-switch__thumb {
  transform: translateX(1.1rem);
  background: #fff;
}
</style>
