<script setup lang="ts">
import { computed } from 'vue'
import { useToast, type ToastType } from '../../composables/useToast'

const { toasts, remove } = useToast()

const meta: Record<ToastType, { title: string; icon: string }> = {
  success: {
    title: '操作完成',
    icon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg>`,
  },
  error: {
    title: '操作失败',
    icon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 8v5"/><path d="M12 17h.01"/><path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z"/></svg>`,
  },
  warning: {
    title: '需要注意',
    icon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 9v4"/><path d="M12 17h.01"/><path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z"/></svg>`,
  },
  info: {
    title: '系统提示',
    icon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 16v-4"/><path d="M12 8h.01"/><circle cx="12" cy="12" r="9"/></svg>`,
  },
}

const orderedToasts = computed(() => toasts.value.slice(-5))

function toastTitle(type: ToastType) {
  return meta[type]?.title || meta.info.title
}

function toastIcon(type: ToastType) {
  return meta[type]?.icon || meta.info.icon
}
</script>

<template>
  <Teleport to="body">
    <div class="noor-toast-region" aria-live="polite" aria-atomic="false">
      <TransitionGroup name="noor-toast" tag="div" class="noor-toast-stack">
        <article
          v-for="toast in orderedToasts"
          :key="toast.id"
          class="noor-toast"
          :class="`noor-toast--${toast.type}`"
          role="status"
        >
          <div class="noor-toast-glow" aria-hidden="true"></div>
          <div class="noor-toast-accent" aria-hidden="true"></div>
          <div class="noor-toast-icon" v-html="toastIcon(toast.type)"></div>
          <div class="noor-toast-content">
            <div class="noor-toast-title">{{ toastTitle(toast.type) }}</div>
            <div class="noor-toast-message">{{ toast.message }}</div>
          </div>
          <button type="button" class="noor-toast-close" aria-label="关闭通知" @click="remove(toast.id)">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round">
              <path d="M6 6l12 12M18 6 6 18" />
            </svg>
          </button>
          <div
            v-if="toast.duration && toast.duration > 0"
            class="noor-toast-timer"
            :style="{ animationDuration: `${toast.duration}ms` }"
            aria-hidden="true"
          ></div>
        </article>
      </TransitionGroup>
    </div>
  </Teleport>
</template>

<style>
.noor-toast-region {
  position: fixed;
  top: calc(var(--safe-area-inset-top, 0px) + 4.25rem);
  right: 1.25rem;
  z-index: 9999;
  width: min(25rem, calc(100vw - 2rem));
  pointer-events: none;
}

.noor-toast-stack {
  display: flex;
  flex-direction: column;
  gap: .75rem;
}

.noor-toast {
  --toast-color: var(--color-info);
  --toast-color-soft: rgba(0, 117, 255, .18);
  position: relative;
  display: grid;
  grid-template-columns: 2.25rem minmax(0, 1fr) 1.8rem;
  gap: .78rem;
  align-items: start;
  overflow: hidden;
  padding: .88rem .82rem .82rem .95rem;
  border: 1px solid rgba(255, 255, 255, .08);
  border-radius: 1rem;
  background:
    linear-gradient(135deg, rgba(255, 255, 255, .08), rgba(255, 255, 255, .035)),
    rgba(12, 18, 38, .92);
  box-shadow: 0 18px 55px rgba(0, 0, 0, .38), inset 0 1px 0 rgba(255, 255, 255, .08);
  backdrop-filter: blur(18px) saturate(1.25);
  pointer-events: auto;
}

.noor-toast--success {
  --toast-color: var(--color-success);
  --toast-color-soft: rgba(1, 181, 116, .18);
}

.noor-toast--error {
  --toast-color: var(--color-error-hover);
  --toast-color-soft: rgba(227, 26, 26, .18);
}

.noor-toast--warning {
  --toast-color: var(--color-warning);
  --toast-color-soft: rgba(255, 181, 71, .18);
}

.noor-toast--info {
  --toast-color: var(--color-info);
  --toast-color-soft: rgba(0, 117, 255, .18);
}

.noor-toast-glow {
  position: absolute;
  inset: -45% auto auto -20%;
  width: 9rem;
  height: 9rem;
  border-radius: 999px;
  background: radial-gradient(circle, var(--toast-color-soft), transparent 68%);
  opacity: .95;
  pointer-events: none;
}

.noor-toast-accent {
  position: absolute;
  inset: .7rem auto .7rem 0;
  width: 3px;
  border-radius: 999px;
  background: var(--toast-color);
  box-shadow: 0 0 16px var(--toast-color);
}

.noor-toast-icon {
  position: relative;
  display: grid;
  place-items: center;
  width: 2.25rem;
  height: 2.25rem;
  border: 1px solid color-mix(in srgb, var(--toast-color), transparent 55%);
  border-radius: .78rem;
  background: var(--toast-color-soft);
  color: var(--toast-color);
}

.noor-toast-icon :deep(svg) {
  width: 1.1rem;
  height: 1.1rem;
}

.noor-toast-content {
  position: relative;
  min-width: 0;
  display: grid;
  gap: .14rem;
}

.noor-toast-title {
  color: rgba(255, 255, 255, .9);
  font-family: var(--font-display);
  font-size: .78rem;
  font-weight: 700;
  letter-spacing: .01em;
  line-height: 1.25;
}

.noor-toast-message {
  color: rgba(255, 255, 255, .62);
  font-size: .78rem;
  line-height: 1.45;
  overflow-wrap: anywhere;
}

.noor-toast-close {
  position: relative;
  display: grid;
  place-items: center;
  width: 1.8rem;
  height: 1.8rem;
  border: 0;
  border-radius: 999px;
  background: transparent;
  color: rgba(255, 255, 255, .34);
  transition: background var(--transition-fast), color var(--transition-fast);
}

.noor-toast-close:hover {
  background: rgba(255, 255, 255, .075);
  color: rgba(255, 255, 255, .78);
}

.noor-toast-close svg {
  width: .95rem;
  height: .95rem;
}

.noor-toast-timer {
  position: absolute;
  left: 0;
  bottom: 0;
  height: 2px;
  width: 100%;
  transform-origin: left center;
  background: linear-gradient(90deg, var(--toast-color), color-mix(in srgb, var(--toast-color), white 30%));
  opacity: .9;
  animation: noor-toast-timer linear forwards;
}

.noor-toast-enter-active {
  transition: opacity 220ms ease-out, transform 260ms cubic-bezier(.16, 1, .3, 1);
}

.noor-toast-leave-active {
  position: absolute;
  width: 100%;
  transition: opacity 180ms ease-in, transform 220ms ease-in;
}

.noor-toast-move {
  transition: transform 220ms cubic-bezier(.16, 1, .3, 1);
}

.noor-toast-enter-from {
  opacity: 0;
  transform: translate3d(1.25rem, -.25rem, 0) scale(.98);
}

.noor-toast-leave-to {
  opacity: 0;
  transform: translate3d(1.25rem, 0, 0) scale(.98);
}

@keyframes noor-toast-timer {
  from { transform: scaleX(1); }
  to { transform: scaleX(0); }
}

@media (max-width: 680px) {
  .noor-toast-region {
    top: calc(var(--safe-area-inset-top, 0px) + .85rem);
    right: 1rem;
    bottom: auto;
    width: calc(100vw - 2rem);
  }

  .noor-toast {
    grid-template-columns: 2rem minmax(0, 1fr) 1.65rem;
    padding: .78rem .72rem .72rem .85rem;
  }

  .noor-toast-icon {
    width: 2rem;
    height: 2rem;
    border-radius: .68rem;
  }
}
</style>
