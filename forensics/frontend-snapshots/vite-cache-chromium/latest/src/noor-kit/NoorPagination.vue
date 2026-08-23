<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(defineProps<{
  page: number
  total: number
  pageSize?: number
}>(), {
  pageSize: 10,
})

const emit = defineEmits<{ 'update:page': [value: number] }>()
const pageCount = computed(() => Math.max(1, Math.ceil(props.total / props.pageSize)))
const pages = computed<(number | string)[]>(() => {
  const total = pageCount.value
  if (total <= 7) return Array.from({ length: total }, (_, index) => index + 1)

  const current = props.page
  const list: (number | string)[] = [1]
  const left = Math.max(2, current - 1)
  const right = Math.min(total - 1, current + 1)

  if (left > 2) list.push('...')
  for (let item = left; item <= right; item += 1) list.push(item)
  if (right < total - 1) list.push('...')
  list.push(total)
  return list
})

function go(page: number) {
  const next = Math.max(1, Math.min(page, pageCount.value))
  if (next !== props.page) emit('update:page', next)
}
</script>

<template>
  <nav class="noor-pagination" aria-label="分页">
    <UButton type="button" color="neutral" variant="soft" size="sm" :disabled="page <= 1" @click="go(page - 1)">上一页</UButton>
    <template v-for="item in pages" :key="item">
      <span v-if="typeof item === 'string'" class="pagination-ellipsis">...</span>
      <UButton
        v-else
        type="button"
        :color="item === page ? 'primary' : 'neutral'"
        :variant="item === page ? 'solid' : 'soft'"
        size="sm"
        :class="{ 'is-active': item === page }"
        @click="go(item)"
      >
        {{ item }}
      </UButton>
    </template>
    <UButton type="button" color="neutral" variant="soft" size="sm" :disabled="page >= pageCount" @click="go(page + 1)">下一页</UButton>
  </nav>
</template>
