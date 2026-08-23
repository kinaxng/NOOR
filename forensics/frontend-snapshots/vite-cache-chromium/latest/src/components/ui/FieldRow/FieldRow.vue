<script setup lang="ts">
defineProps<{
  label: string
  description?: string
  hint?: string
}>()
</script>

<template>
  <div class="field-row">
    <div class="field-row__label-col">
      <span class="field-row__label">{{ label }}</span>
      <span v-if="description" class="field-row__desc">{{ description }}</span>
    </div>
    <div class="field-row__input-col">
      <slot />
      <p v-if="hint" class="field-row__hint">{{ hint }}</p>
    </div>
  </div>
</template>

<style scoped>
.field-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1.5rem;
  align-items: start;
  padding: 0.75rem 0;
  border-bottom: 1px solid rgba(255, 255, 255, 0.04);
}

.field-row:last-child {
  border-bottom: none;
  padding-bottom: 0;
}

/* Mobile: stack to single column */
@media (max-width: 640px) {
  .field-row {
    grid-template-columns: 1fr;
    gap: 0.5rem;
  }
}

.field-row__label-col {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
  padding-top: 0.55rem;
}

.field-row__label {
  font-family: var(--font-display);
  font-size: 0.8125rem;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.75);
}

.field-row__desc {
  font-family: var(--font-display);
  font-size: 0.6875rem;
  color: rgba(255, 255, 255, 0.28);
  line-height: 1.55;
}

.field-row__input-col {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.field-row__hint {
  font-family: var(--font-display);
  font-size: 0.625rem;
  color: rgba(255, 255, 255, 0.22);
  margin: 0;
  line-height: 1.5;
}
</style>
