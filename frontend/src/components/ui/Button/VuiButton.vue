<script setup lang="ts">
withDefaults(defineProps<{
  variant?: 'text' | 'contained' | 'outlined' | 'gradient'
  size?: 'small' | 'medium' | 'large'
  color?: string
  circular?: boolean
  iconOnly?: boolean
  disabled?: boolean
  customClass?: string
}>(), {
  variant: 'contained',
  size: 'medium',
  color: 'white',
  circular: false,
  iconOnly: false,
  disabled: false,
})
</script>

<template>
  <button
    class="vui-button"
    :class="[
      `vui-button--${variant}`,
      `vui-button--${size}`,
      { 'vui-button--circular': circular },
      { 'vui-button--icon-only': iconOnly },
      customClass,
    ]"
    :disabled="disabled"
  >
    <slot />
  </button>
</template>

<style scoped>
.vui-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.375rem;
  font-family: var(--font-display);
  font-weight: var(--font-weight-bold);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  border: none;
  cursor: pointer;
  transition: all var(--transition-fast);
  position: relative;
  white-space: nowrap;
  line-height: 1;
}

.vui-button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* Sizes */
.vui-button--small {
  padding: 0.5rem 1rem;
  font-size: 0.75rem;
  border-radius: var(--radius-button);
}

.vui-button--medium {
  padding: 0.6875rem 1.25rem;
  font-size: 0.875rem;
  border-radius: var(--radius-button);
}

.vui-button--large {
  padding: 0.875rem 1.5rem;
  font-size: 1rem;
  border-radius: var(--radius-button);
}

/* Circular */
.vui-button--circular {
  border-radius: 50%;
  padding: 0.6875rem;
}

/* Icon Only */
.vui-button--icon-only.vui-button--small {
  width: 1.5875rem;
  height: 1.5875rem;
  min-width: 1.5875rem;
  padding: 0;
}

.vui-button--icon-only.vui-button--medium {
  width: 2.375rem;
  height: 2.375rem;
  min-width: 2.375rem;
  padding: 0;
}

.vui-button--icon-only.vui-button--large {
  width: 3.25rem;
  height: 3.25rem;
  min-width: 3.25rem;
  padding: 0;
}

/* Contained */
.vui-button--contained {
  background: #FFFFFF;
  color: #344767;
  box-shadow: 0 4px 6px -1px rgba(0,0,0,0.12), 0 2px 4px -1px rgba(0,0,0,0.07);
}

.vui-button--contained:hover:not(:disabled) {
  background: #FFFFFF;
  box-shadow: 0 4px 6px -1px rgba(0,0,0,0.15), 0 2px 4px -1px rgba(0,0,0,0.1);
}

.vui-button--contained:focus:not(:hover) {
  box-shadow: 0 0 0 3px rgba(0, 117, 255, 0.5);
}

/* Outlined */
.vui-button--outlined {
  background: transparent;
  border: 1px solid rgba(255, 255, 255, 0.75);
  color: #FFFFFF;
}

.vui-button--outlined:hover:not(:disabled) {
  background: transparent;
  border-color: #FFFFFF;
}

.vui-button--outlined:focus:not(:hover) {
  box-shadow: 0 0 0 3px rgba(0, 117, 255, 0.4);
}

/* Gradient - Blue like Vision UI */
.vui-button--gradient {
  background: #0075FF;
  color: #FFFFFF;
  box-shadow: 0 4px 6px -1px rgba(0, 117, 255, 0.35), 0 2px 4px -1px rgba(0, 117, 255, 0.2);
}

.vui-button--gradient:hover:not(:disabled) {
  background: #3993FE;
  box-shadow: 0 6px 12px -2px rgba(0, 117, 255, 0.45);
  transform: translateY(-1px);
}

.vui-button--gradient:focus:not(:hover) {
  box-shadow: none;
}

/* Text */
.vui-button--text {
  background: transparent;
  color: #FFFFFF;
  box-shadow: none;
  text-transform: none;
  font-weight: var(--font-weight-regular);
  letter-spacing: 0;
}

.vui-button--text:hover:not(:disabled) {
  color: rgba(255, 255, 255, 0.7);
}

/* Color variants for contained/gradient */
/* All gradient buttons are now blue */
.vui-button--contained.vui-button--info,
.vui-button--gradient.vui-button--info,
.vui-button--contained.vui-button--success,
.vui-button--gradient.vui-button--success,
.vui-button--contained.vui-button--warning,
.vui-button--gradient.vui-button--warning,
.vui-button--contained.vui-button--error,
.vui-button--gradient.vui-button--error {
  background: #0075FF;
  color: #FFFFFF;
  box-shadow: 0 4px 6px -1px rgba(0, 117, 255, 0.35);
}

.vui-button--contained.vui-button--info:hover:not(:disabled),
.vui-button--gradient.vui-button--info:hover:not(:disabled),
.vui-button--contained.vui-button--success:hover:not(:disabled),
.vui-button--gradient.vui-button--success:hover:not(:disabled),
.vui-button--contained.vui-button--warning:hover:not(:disabled),
.vui-button--gradient.vui-button--warning:hover:not(:disabled),
.vui-button--contained.vui-button--error:hover:not(:disabled),
.vui-button--gradient.vui-button--error:hover:not(:disabled) {
  background: #3993FE;
  transform: translateY(-1px);
  box-shadow: 0 6px 12px -2px rgba(0, 117, 255, 0.45);
}
</style>
