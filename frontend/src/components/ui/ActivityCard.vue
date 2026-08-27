<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from '../../composables/useI18n'

const props = defineProps<{
  title?: string
}>()

const { t, i18nVersion } = useI18n()
const resolvedTitle = computed(() => {
  void i18nVersion.value
  return props.title || t('common.recentActivity')
})
</script>

<template>
  <div class="activity-card ui-card">
    <div class="activity-card__header">
      <h3 class="activity-card__title">{{ resolvedTitle }}</h3>
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
  margin-bottom: 1rem;
  padding-bottom: 0.9rem;
  border-bottom: 1px solid var(--color-border-subtle);
}

.activity-card__title {
  font-family: var(--font-display);
  font-size: var(--font-size-sm);
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
