<script setup lang="ts">
import BaseModal from '../ui/BaseModal.vue'
import VuiButton from '../ui/Button/VuiButton.vue'
import { useI18n } from '../../composables/useI18n'
import { useConfirm } from '../../composables/useConfirm'

const { t } = useI18n()
const { confirmState, resolveConfirm } = useConfirm()
</script>

<template>
  <BaseModal
    v-if="confirmState.open"
    :title="confirmState.title || t('common.confirm')"
    :size="confirmState.size"
    @close="resolveConfirm(false)"
  >
    <p class="confirm-dialog__message">{{ confirmState.message }}</p>
    <p v-if="confirmState.note" class="confirm-dialog__note">{{ confirmState.note }}</p>

    <div v-if="confirmState.details.length" class="confirm-dialog__details">
      <section
        v-for="section in confirmState.details"
        :key="section.label"
        class="confirm-dialog__section"
      >
        <div class="confirm-dialog__section-label">{{ section.label }}</div>
        <div class="confirm-dialog__section-list">
          <div
            v-for="item in section.items"
            :key="item"
            class="confirm-dialog__path"
            :title="item"
          >
            {{ item }}
          </div>
        </div>
      </section>
    </div>

    <template #footer>
      <div class="confirm-dialog__actions">
        <VuiButton v-if="!confirmState.hideCancel" variant="outlined" color="secondary" size="small" @click="resolveConfirm(false)">
          {{ confirmState.cancelText || t('common.cancel') }}
        </VuiButton>
        <VuiButton
          variant="gradient"
          :color="confirmState.danger ? 'error' : 'info'"
          size="small"
          @click="resolveConfirm(true)"
        >
          {{ confirmState.confirmText || t('common.confirm') }}
        </VuiButton>
      </div>
    </template>
  </BaseModal>
</template>

<style scoped>
.confirm-dialog__message {
  font-family: var(--font-display);
  font-size: 0.875rem;
  line-height: 1.6;
  color: var(--color-text-secondary);
  margin: 0;
  white-space: pre-wrap;
}


.confirm-dialog__note {
  margin: 0.75rem 0 0;
  padding: 0.75rem 0.875rem;
  border-radius: var(--radius-md);
  border: 1px solid color-mix(in srgb, var(--color-warning) 30%, transparent);
  background: color-mix(in srgb, var(--color-warning) 10%, transparent);
  font-size: 0.75rem;
  line-height: 1.55;
  color: var(--color-text-secondary);
}

.confirm-dialog__details {
  margin-top: 1rem;
  display: grid;
  gap: 0.875rem;
}

.confirm-dialog__section {
  display: flex;
  flex-direction: column;
  gap: 0.45rem;
}

.confirm-dialog__section-label {
  font-size: 0.75rem;
  color: var(--color-text-muted);
}

.confirm-dialog__section-list {
  display: flex;
  flex-direction: column;
  gap: 0.375rem;
  max-height: min(48vh, 30rem);
  overflow: auto;
  padding: 0.75rem;
  border-radius: var(--radius-md);
  border: 1px solid var(--color-border-default);
  background: rgba(255, 255, 255, 0.03);
}

.confirm-dialog__path {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 0.75rem;
  line-height: 1.5;
  color: var(--color-text-primary);
  word-break: break-all;
}

@media (min-width: 960px) {
  .confirm-dialog__details:has(.confirm-dialog__section + .confirm-dialog__section) {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    align-items: start;
  }
}

.confirm-dialog__actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.75rem;
}

@media (max-width: 640px) {
  .confirm-dialog__details {
    gap: 0.75rem;
  }

  .confirm-dialog__section-list {
    max-height: min(36vh, 20rem);
    padding: 0.625rem;
  }

  .confirm-dialog__actions {
    width: 100%;
    justify-content: stretch;
  }

  .confirm-dialog__actions :deep(button) {
    flex: 1 1 0;
  }
}
</style>
