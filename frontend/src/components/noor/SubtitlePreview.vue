<script setup lang="ts">
defineProps<{
  filename: string
  content: string
  loading: boolean
}>()

const emit = defineEmits<{
  close: []
}>()
</script>

<template>
  <Teleport to="body">
    <Transition name="fade">
      <div
        v-if="content || loading"
        class="fixed inset-0 bg-bg-void/80 backdrop-blur-sm flex items-center justify-center z-[200] p-4"
        @click.self="emit('close')"
      >
        <div class="bg-bg-surface rounded-xl max-w-4xl w-full max-h-[90vh] flex flex-col overflow-hidden border border-border-subtle shadow-2xl">
          <!-- Header -->
          <div class="flex items-center justify-between px-4 py-3 border-b border-border-subtle">
            <h3 class="text-lg font-medium text-text-primary">{{ filename }}</h3>
            <button
              @click="emit('close')"
              class="text-text-muted hover:text-text-primary transition-colors p-1"
            >
              <svg xmlns="http://www.w3.org/2000/svg" class="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          <!-- Content -->
          <div class="flex-1 overflow-auto p-4">
            <!-- Loading -->
            <div v-if="loading" class="flex items-center justify-center h-32">
              <div class="animate-spin w-8 h-8 border-2 border-accent-cyan border-t-transparent rounded-full"></div>
            </div>

            <!-- Content -->
            <pre v-else class="whitespace-pre-wrap text-text-secondary text-sm font-mono leading-relaxed">{{ content }}</pre>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
