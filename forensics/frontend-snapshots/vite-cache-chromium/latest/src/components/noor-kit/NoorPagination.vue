<script setup lang="ts">
defineProps<{
  page: number
  total: number
  pageSize?: number
  siblingCount?: number
}>()

const emit = defineEmits<{ 'update:page': [page: number] }>()
</script>

<template>
  <UPagination
    :page="page"
    :total="total"
    :items-per-page="pageSize || 10"
    :sibling-count="siblingCount ?? 1"
    color="neutral"
    variant="soft"
    active-color="primary"
    active-variant="solid"
    size="sm"
    class="noor-pagination"
    @update:page="emit('update:page', $event)"
  />
</template>
