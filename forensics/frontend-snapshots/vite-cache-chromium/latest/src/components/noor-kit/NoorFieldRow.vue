<script setup lang="ts">
defineProps<{
  label: string
  description?: string
  hint?: string
}>()
</script>

<template>
  <div class="noor-field-row">
    <div class="noor-field-row__label-col">
      <span class="noor-field-row__label">{{ label }}</span>
      <span v-if="description" class="noor-field-row__desc">{{ description }}</span>
    </div>
    <div class="noor-field-row__input-col">
      <slot />
      <p v-if="hint" class="noor-field-row__hint">{{ hint }}</p>
    </div>
  </div>
</template>

<style scoped>
.noor-field-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1.5rem;
  align-items: start;
  padding: 0.75rem 0;
  border-bottom: 1px solid rgba(255, 255, 255, 0.04);
}

.noor-field-row:last-child {
  border-bottom: none;
  padding-bottom: 0;
}

@media (max-width: 640px) {
  .noor-field-row {
    grid-template-columns: 1fr;
    gap: 0.5rem;
  }
}

.noor-field-row__label-col {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
  padding-top: 0.55rem;
}

.noor-field-row__label {
  font-family: var(--font-display);
  font-size: 0.8125rem;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.75);
}

.noor-field-row__desc {
  font-family: var(--font-display);
  font-size: 0.6875rem;
  color: rgba(255, 255, 255, 0.28);
  line-height: 1.55;
}

.noor-field-row__input-col {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.noor-field-row__hint {
  font-family: var(--font-display);
  font-size: 0.625rem;
  color: rgba(255, 255, 255, 0.22);
  margin: 0;
  line-height: 1.5;
}
</style>
