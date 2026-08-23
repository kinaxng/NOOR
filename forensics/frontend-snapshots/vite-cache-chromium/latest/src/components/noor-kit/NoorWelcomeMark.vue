<script setup lang="ts">
defineProps<{
  username?: string
  message?: string
  greeting?: string
}>()
</script>

<template>
  <UCard variant="subtle" class="ui-card overflow-hidden h-full">
    <div class="relative h-full min-h-[220px] rounded-xl border border-white/10 bg-[radial-gradient(circle_at_20%_10%,rgba(33,212,253,.24),transparent_45%),radial-gradient(circle_at_85%_70%,rgba(255,45,149,.18),transparent_48%),linear-gradient(130deg,rgba(255,255,255,.06),rgba(255,255,255,.01))] p-5">
      <p class="text-xs uppercase tracking-[0.08em] text-white/55">{{ greeting || '欢迎回来' }}</p>
      <h2 class="mt-2 text-3xl font-bold text-white">{{ username || 'NOOR' }}</h2>
      <p class="mt-3 text-sm text-white/70 max-w-[30rem]">{{ message || '管理媒体、字幕与任务流程。' }}</p>
    </div>
  </UCard>
</template>
