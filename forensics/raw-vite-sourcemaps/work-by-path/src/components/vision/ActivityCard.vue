<script setup lang="ts">
defineProps<{
  title?: string
}>()
</script>

<template>
  <div class="activity-card vision-card">
    <div class="activity-card__header">
      <h3 class="activity-card__title">{{ title || '最近活动' }}</h3>
      <slot name="action" />
    </div>
    <div class="activity-card__body">
      <slot />
    </div>
  </div>
</template>

<style scoped>
.activity-card {
  height: 100%;
}

.activity-card__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 1.25rem;
}

.activity-card__title {
  font-family: var(--font-display);
  font-size: 0.875rem;
  font-weight: 600;
  color: #FFFFFF;
  line-height: 1;
}

.activity-card__body {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}
</style>
