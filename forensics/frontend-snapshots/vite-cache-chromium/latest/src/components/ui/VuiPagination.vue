<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted } from 'vue'
import { useI18n } from '../../composables/useI18n'

const props = withDefaults(defineProps<{
  page: number
  pageSize?: number
  total: number
  pageSizeOptions?: number[]
  showTotal?: boolean
  showPageSize?: boolean
  siblingCount?: number
}>(), {
  pageSize: 20,
  pageSizeOptions: () => [20, 50, 100],
  showTotal: false,
  showPageSize: false,
  siblingCount: 1,
})

const emit = defineEmits<{
  'update:page': [number]
  'update:pageSize': [number]
}>()

const { t, i18nVersion } = useI18n()

const totalPages = computed(() => Math.max(1, Math.ceil(Math.max(0, props.total) / Math.max(1, props.pageSize))))
const safePage = computed(() => Math.max(1, Math.min(props.page || 1, totalPages.value)))
const startItem = computed(() => props.total === 0 ? 0 : (safePage.value - 1) * props.pageSize + 1)
const endItem = computed(() => Math.min(props.total, safePage.value * props.pageSize))

const pageItems = computed<(number | 'ellipsis')[]>(() => {
  const total = totalPages.value
  const current = safePage.value
  const siblings = Math.max(0, props.siblingCount)
  const maxItems = 5 + siblings * 2
  if (total <= maxItems) return Array.from({ length: total }, (_, idx) => idx + 1)

  const left = Math.max(2, current - siblings)
  const right = Math.min(total - 1, current + siblings)
  const items: (number | 'ellipsis')[] = [1]
  if (left > 2) items.push('ellipsis')
  for (let p = left; p <= right; p += 1) items.push(p)
  if (right < total - 1) items.push('ellipsis')
  items.push(total)
  return items
})

const totalLabel = computed(() => {
  void i18nVersion.value
  return t('pagination.total', { total: props.total, start: startItem.value, end: endItem.value })
})
const pageLabel = computed(() => {
  void i18nVersion.value
  return t('common.pageCounter', { current: safePage.value, total: totalPages.value })
})

function go(page: number) {
  const next = Math.max(1, Math.min(page, totalPages.value))
  if (next !== safePage.value) emit('update:page', next)
}

function updatePageSize(event: Event) {
  const value = Number((event.target as HTMLSelectElement).value || props.pageSize)
  emit('update:pageSize', value)
  emit('update:page', 1)
}

function handleKeydown(event: KeyboardEvent) {
  const target = event.target as HTMLElement | null
  const tagName = target?.tagName?.toLowerCase() || ''
  if (tagName === 'input' || tagName === 'textarea' || tagName === 'select' || target?.isContentEditable) return
  if (event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) return
  if (event.key === 'Home') {
    event.preventDefault()
    go(1)
  } else if (event.key === 'End') {
    event.preventDefault()
    go(totalPages.value)
  } else if (event.key === 'PageUp') {
    event.preventDefault()
    go(safePage.value - 1)
  } else if (event.key === 'PageDown') {
    event.preventDefault()
    go(safePage.value + 1)
  }
}

onMounted(() => {
  window.addEventListener('keydown', handleKeydown)
})

onBeforeUnmount(() => {
  window.removeEventListener('keydown', handleKeydown)
})
</script>

<template>
  <nav v-if="totalPages > 1 || showTotal || showPageSize" class="vui-pagination" aria-label="Pagination">
    <div v-if="showTotal" class="vui-pagination__total">{{ totalLabel }}</div>

    <div class="vui-pagination__controls">
      <button class="vui-pagination__btn" :disabled="safePage <= 1" @click="go(safePage - 1)">
        {{ t('common.prevPage') }}
      </button>

      <div class="vui-pagination__pages">
        <template v-for="(item, idx) in pageItems" :key="`${item}-${idx}`">
          <span v-if="item === 'ellipsis'" class="vui-pagination__ellipsis">…</span>
          <button
            v-else
            class="vui-pagination__page"
            :class="{ 'vui-pagination__page--active': item === safePage }"
            @click="go(item)"
          >
            {{ item }}
          </button>
        </template>
      </div>

      <span class="vui-pagination__compact">{{ pageLabel }}</span>

      <button class="vui-pagination__btn" :disabled="safePage >= totalPages" @click="go(safePage + 1)">
        {{ t('common.nextPage') }}
      </button>
    </div>

    <label v-if="showPageSize" class="vui-pagination__size">
      <span>{{ t('pagination.pageSize') }}</span>
      <select :value="pageSize" @change="updatePageSize">
        <option v-for="option in pageSizeOptions" :key="option" :value="option">{{ option }}</option>
      </select>
    </label>
  </nav>
</template>

<style scoped>
.vui-pagination {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.75rem;
  flex-wrap: wrap;
  padding: 0.35rem 0;
  color: var(--color-text-secondary);
}

.vui-pagination:focus {
  outline: none;
}

.vui-pagination:focus-visible {
  outline: none;
}

.vui-pagination__total,
.vui-pagination__size {
  font-size: 0.75rem;
  color: var(--color-text-muted);
}

.vui-pagination__controls {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.35rem;
}

.vui-pagination__pages {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
}

.vui-pagination__btn,
.vui-pagination__page {
  height: 2rem;
  min-width: 2rem;
  padding: 0 0.65rem;
  border-radius: 0.7rem;
  border: 1px solid rgba(255, 255, 255, 0.1);
  background: rgba(255, 255, 255, 0.045);
  color: var(--color-text-secondary);
  font-size: 0.75rem;
  font-weight: 650;
  transition: all 0.15s ease;
}

.vui-pagination__btn:hover:not(:disabled),
.vui-pagination__page:hover:not(:disabled) {
  background: rgba(255, 255, 255, 0.075);
  color: var(--color-text-primary);
}

.vui-pagination__page--active {
  border-color: rgba(0, 117, 255, 0.36);
  background: rgba(0, 117, 255, 0.18);
  color: #fff;
}

.vui-pagination__btn:disabled,
.vui-pagination__page:disabled {
  opacity: 0.42;
  cursor: not-allowed;
}

.vui-pagination__ellipsis {
  min-width: 1.4rem;
  text-align: center;
  color: rgba(255, 255, 255, 0.28);
}

.vui-pagination__compact {
  display: none;
  min-width: 5.5rem;
  text-align: center;
  font-size: 0.75rem;
  color: var(--color-text-secondary);
}

.vui-pagination__size {
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
}

.vui-pagination__size select {
  height: 2rem;
  border-radius: 0.65rem;
  border: 1px solid rgba(255, 255, 255, 0.1);
  background: rgba(255, 255, 255, 0.055);
  color: var(--color-text-primary);
  padding: 0 0.55rem;
}

@media (max-width: 640px) {
  .vui-pagination {
    gap: 0.55rem;
  }

  .vui-pagination__total {
    width: 100%;
    text-align: center;
  }

  .vui-pagination__pages {
    display: none;
  }

  .vui-pagination__compact {
    display: inline-block;
  }

  .vui-pagination__btn {
    min-width: 4.5rem;
  }
}
</style>
