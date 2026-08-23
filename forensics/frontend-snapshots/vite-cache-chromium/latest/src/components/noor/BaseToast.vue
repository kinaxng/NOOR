<script setup lang="ts">
import { useToast } from '../../composables/useToast'

const { toasts, remove } = useToast()

const icons = {
  success: `<svg xmlns="http://www.w3.org/2000/svg" class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" /></svg>`,
  error: `<svg xmlns="http://www.w3.org/2000/svg" class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" /></svg>`,
  warning: `<svg xmlns="http://www.w3.org/2000/svg" class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" /></svg>`,
  info: `<svg xmlns="http://www.w3.org/2000/svg" class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>`,
}
</script>

<template>
  <Teleport to="body">
    <div class="fixed top-16 right-4 z-[9999] flex flex-col gap-3 pointer-events-none" style="max-width: 360px;">
      <TransitionGroup name="toast">
        <div
          v-for="toast in toasts"
          :key="toast.id"
          class="toast pointer-events-auto flex items-start gap-3 px-4 py-3 rounded-lg shadow-xl border"
          :class="{
            'toast-success border-status-success/50': toast.type === 'success',
            'toast-error border-status-error/50': toast.type === 'error',
            'toast-warning border-status-warning/50': toast.type === 'warning',
            'toast border-border-default': toast.type === 'info',
          }"
        >
          <span
            class="flex-shrink-0 mt-0.5"
            :class="{
              'text-status-success': toast.type === 'success',
              'text-status-error': toast.type === 'error',
              'text-status-warning': toast.type === 'warning',
              'text-accent-cyan': toast.type === 'info',
            }"
            v-html="icons[toast.type]"
          ></span>
          <p class="flex-1 text-sm text-text-primary">{{ toast.message }}</p>
          <button
            @click="remove(toast.id)"
            class="flex-shrink-0 text-text-muted hover:text-text-secondary transition-colors"
          >
            <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      </TransitionGroup>
    </div>
  </Teleport>
</template>

<style scoped>
.toast-enter-active {
  animation: toast-in 0.3s ease-out;
}
.toast-leave-active {
  animation: toast-out 0.3s ease-in;
}
@keyframes toast-in {
  from { opacity: 0; transform: translateX(100%); }
  to { opacity: 1; transform: translateX(0); }
}
@keyframes toast-out {
  from { opacity: 1; transform: translateX(0); }
  to { opacity: 0; transform: translateX(100%); }
}
</style>
