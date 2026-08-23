<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useHardlinksStore } from '../stores/hardlinks'

const store = useHardlinksStore()

const stats = computed(() => [
  { label: '作品组', value: store.groups.length, filter: 'all' },
  { label: '异常组', value: store.issueGroups.length, filter: 'issue' },
  { label: '仅主文件', value: store.sourceOnlyGroups.length, filter: 'source-only' },
  { label: '仅硬链接', value: store.hardlinkOnlyGroups.length, filter: 'hardlink-only' },
])

function sizeText(value?: number | null) {
  if (!value) return '-'
  if (value > 1024 ** 3) return `${(value / 1024 ** 3).toFixed(2)} GB`
  return `${(value / 1024 ** 2).toFixed(1)} MB`
}

const showDeletePreviewModal = computed({
  get: () => !!store.deletePreview,
  set: (val) => {
    if (!val) store.closeDeletePreview()
  }
})

onMounted(() => store.fetchGroups())
</script>

<template>
  <UDashboardPage>
    <UDashboardPanel grow>
      <UDashboardNavbar title="硬链接">
        <template #right>
          <div class="flex items-center gap-2">
            <UInput v-model="store.query" icon="i-heroicons-magnifying-glass-20-solid" placeholder="搜索作品或路径" clearable />
            <UButton color="primary" @click="store.fetchGroups()">重新扫描</UButton>
          </div>
        </template>
      </UDashboardNavbar>

      <UDashboardToolbar>
        <template #left>
          <div class="flex items-center gap-2">
            <UButton
              v-for="item in stats"
              :key="item.label"
              :color="store.filter === item.filter ? 'primary' : 'gray'"
              variant="soft"
              @click="store.setFilter((item.filter as any) || 'all')"
            >
              {{ item.label }}
              <UBadge color="white" class="ml-2">{{ item.value }}</UBadge>
            </UButton>
          </div>
        </template>
      </UDashboardToolbar>

      <UDashboardPanelContent>
        <div v-if="store.loading" class="flex flex-col items-center justify-center py-12 text-gray-500">
          <UIcon name="i-heroicons-arrow-path-20-solid" class="w-8 h-8 animate-spin mb-4" />
          <p>加载硬链接中...</p>
        </div>
        
        <div v-else-if="store.error" class="flex flex-col items-center justify-center py-12">
          <UIcon name="i-heroicons-exclamation-triangle-20-solid" class="w-12 h-12 text-red-500 mb-4" />
          <p class="text-red-500 font-medium">{{ store.error }}</p>
        </div>
        
        <div v-else-if="!store.filteredGroups.length" class="flex flex-col items-center justify-center py-12 text-gray-500">
          <UIcon name="i-heroicons-link-slash-20-solid" class="w-12 h-12 mb-4 text-gray-400" />
          <p>暂无匹配作品</p>
        </div>

        <div v-else class="space-y-4">
          <UCard v-for="group in store.pagedGroups" :key="group.code" class="overflow-hidden">
            <template #header>
              <div class="flex items-center justify-between">
                <h3 class="text-base font-semibold leading-6 text-gray-900 dark:text-white">{{ group.code }}</h3>
                <div class="flex items-center gap-2">
                  <UBadge :color="group.status === 'issue' ? 'orange' : 'green'" variant="subtle">
                    {{ group.status === 'issue' ? '异常' : '正常' }}
                  </UBadge>
                  <UButton color="red" variant="soft" size="xs" @click="store.previewDeleteGroup(group)">删整组</UButton>
                </div>
              </div>
            </template>
            <div class="space-y-2">
              <div v-for="entry in group.entries" :key="`${group.code}:${entry.source_path || entry.hardlink_paths.join('|')}`" class="space-y-2">
                <div class="flex items-center gap-2 p-2 bg-gray-50 dark:bg-gray-800/50 rounded-md">
                  <UBadge color="gray" variant="solid" size="xs">主文件</UBadge>
                  <span class="flex-1 text-sm font-medium truncate" :class="{ 'text-gray-400': !entry.source_path }">{{ entry.source_path || '未找到对应主文件' }}</span>
                  <span class="text-xs text-gray-500 whitespace-nowrap">{{ sizeText(entry.source_size) }}</span>
                  <UButton v-if="entry.source_path" color="red" variant="ghost" size="xs" icon="i-heroicons-trash-20-solid" @click="store.previewDeleteSourceChain(group, entry)" />
                </div>
                <div v-for="path in entry.hardlink_paths" :key="path" class="flex items-center gap-2 p-2 pl-6 bg-gray-50/50 dark:bg-gray-800/30 rounded-md">
                  <UBadge color="gray" variant="soft" size="xs">硬链接</UBadge>
                  <span class="flex-1 text-sm truncate text-gray-600 dark:text-gray-400">{{ path }}</span>
                  <UButton color="red" variant="ghost" size="xs" icon="i-heroicons-trash-20-solid" @click="store.previewDeleteHardlink(path)" />
                </div>
              </div>
            </div>
          </UCard>
        </div>

        <div v-if="!store.loading && store.filteredGroups.length > store.pageSize" class="mt-4 flex justify-center">
          <UPagination v-model="store.page" :total="store.filteredGroups.length" :page-count="store.pageSize" />
        </div>
      </UDashboardPanelContent>

      <UModal v-model="showDeletePreviewModal" prevent-close>
        <UCard>
          <template #header>
            <div class="flex items-center justify-between">
              <h3 class="text-base font-semibold leading-6 text-gray-900 dark:text-white">删除预览: {{ store.deletePreview?.title }}</h3>
              <UButton color="gray" variant="ghost" icon="i-heroicons-x-mark-20-solid" class="-my-1" @click="store.closeDeletePreview()" />
            </div>
            <p class="text-sm text-gray-500 mt-1">预计删除目录 {{ store.deletePreview?.planned_dirs.length || 0 }} 个，文件 {{ store.deletePreview?.planned_files.length || 0 }} 个</p>
          </template>
          
          <div v-if="store.previewLoading" class="flex justify-center p-4">
            <UIcon name="i-heroicons-arrow-path-20-solid" class="w-8 h-8 animate-spin text-gray-400" />
          </div>
          <div v-else-if="store.deletePreview" class="space-y-4 max-h-[60vh] overflow-y-auto">
            <UAlert title="注意" description="仅当目录内全部视频文件都属于本次删除目标时才会整目录删除，否则只删除明确列出的文件。" color="yellow" variant="soft" />
            
            <div v-if="store.deletePreview.planned_dirs.length" class="space-y-2">
              <h4 class="text-sm font-medium text-gray-900 dark:text-white">将删除的目录</h4>
              <div class="bg-gray-50 dark:bg-gray-800 rounded-md p-3 space-y-1">
                <div v-for="path in store.deletePreview.planned_dirs" :key="path" class="text-xs font-mono text-gray-600 dark:text-gray-300 break-all">{{ path }}</div>
              </div>
            </div>
            
            <div v-if="store.deletePreview.planned_files.length" class="space-y-2">
              <h4 class="text-sm font-medium text-gray-900 dark:text-white">将删除的文件</h4>
              <div class="bg-gray-50 dark:bg-gray-800 rounded-md p-3 space-y-1">
                <div v-for="path in store.deletePreview.planned_files" :key="path" class="text-xs font-mono text-gray-600 dark:text-gray-300 break-all">{{ path }}</div>
              </div>
            </div>
          </div>

          <template #footer>
            <div class="flex justify-end gap-3">
              <UButton color="gray" variant="ghost" @click="store.closeDeletePreview()">取消</UButton>
              <UButton color="red" :loading="store.deleteLoading" @click="store.confirmDeletePreview()">确认删除</UButton>
            </div>
          </template>
        </UCard>
      </UModal>
    </UDashboardPanel>
  </UDashboardPage>
</template>
