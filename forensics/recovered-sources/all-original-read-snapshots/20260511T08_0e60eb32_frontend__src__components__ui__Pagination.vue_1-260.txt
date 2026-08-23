<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted } from 'vue'
import { useI18n } from '../../composables/useI18n'

const props = withDefaults(defineProps<{
  page: number
  totalPages: number
  siblingCount?: number
  keyboard?: boolean
}>(), {
  siblingCount: 2,
  keyboard: true,
})

const emit = defineEmits<{
  'update:page': [value: number]
  page: [value: number]
}>()

const { t, i18nVersion } = useI18n()
const total = computed(() => Math.max(1, props.totalPages || 1))
const current = computed(() => Math.min(Math.max(1, props.page || 1), total.value))

const pages = computed(() => {
  const out: number[] = []
  const start = Math.max(1, current.value - props.siblingCount)
  const end = Math.min(total.value, current.value + props.siblingCount)
  for (let i = start; i <= end; i += 1) out.push(i)
  return out
})

const prevLabel = computed(() => { void i18nVersion.value; return t('common.prevPage') })
const nextLabel = computed(() => { void i18nVersion.value; return t('common.nextPage') })

function go(page: number) {
  const next = Math.min(Math.max(1, page), total.value)
  if (next === current.value) return
  emit('update:page', next)
  emit('page', next)
}

function onKeydown(event: KeyboardEvent) {
  if (!props.keyboard) return
  const target = event.target as HTMLElement | null
  if (target && ['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName)) return
  if (event.key === 'PageUp') { event.preventDefault(); go(current.value - 1) }
  else if (event.key === 'PageDown') { event.preventDefault(); go(current.value + 1) }
  else if (event.key === 'Home') { event.preventDefault(); go(1) }
  else if (event.key === 'End') { event.preventDefault(); go(total.value) }
}

onMounted(() => window.addEventListener('keydown', onKeydown))
onBeforeUnmount(() => window.removeEventListener('keydown', onKeydown))
</script>

<template>
  <nav v-if="total > 1" class="noor-pagination" aria-label="Pagination">
    <button class="noor-pagination__btn" :disabled="current <= 1" @click="go(current - 1)">{{ prevLabel }}</button>
    <button
      v-for="p in pages"
      :key="p"
      class="noor-pagination__btn noor-pagination__page"
      :class="{ 'is-active': p === current }"
      :aria-current="p === current ? 'page' : undefined"
      @click="go(p)"
    >{{ p }}</button>
    <button class="noor-pagination__btn" :disabled="current >= total" @click="go(current + 1)">{{ nextLabel }}</button>
  </nav>
</template>

<style scoped>
.noor-pagination {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 0.4rem;
  margin-top: 1rem;
  flex-wrap: wrap;
}
.noor-pagination__btn {
  min-height: 30px;
  min-width: 30px;
  padding: 0.35rem 0.75rem;
  border-radius: var(--radius-md);
  font-family: var(--font-display);
  font-size: 0.75rem;
  font-weight: 700;
  transition: all var(--transition-fast);
  background: rgba(255,255,255,0.04);
  border: 1px solid rgba(255,255,255,0.08);
  color: rgba(255,255,255,0.78);
}
.noor-pagination__btn:hover:not(:disabled) {
  background: rgba(255,255,255,0.08);
  color: #fff;
  transform: translateY(-1px);
}
.noor-pagination__btn:disabled {
  opacity: 0.38;
  cursor: not-allowed;
}
.noor-pagination__page.is-active {
  background: var(--color-brand);
  color: white;
  border-color: transparent;
  box-shadow: 0 4px 12px rgba(0, 117, 255, 0.25);
}
</style>
