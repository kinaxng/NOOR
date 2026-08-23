<script setup lang="ts">
import { onMounted, computed } from 'vue'
import { useEmbyStore } from '../stores/emby'
import { useJobsStore } from '../stores/jobs'
import BaseIcon from '../components/BaseIcon.vue'
import VuiBadge from '../components/vision/VuiBadge/VuiBadge.vue'
import SystemMetricsCard from '../components/vision/SystemMetricsCard.vue'
import WelcomeMark from '../components/vision/WelcomeMark.vue'
import ActivityCard from '../components/vision/ActivityCard.vue'

const embyStore = useEmbyStore()
const jobsStore = useJobsStore()

onMounted(async () => {
  await embyStore.fetchLibraries()
  await jobsStore.fetchJobs()
  if (embyStore.enabledLibraryIds.length === 0) {
    await embyStore.fetchAllItems(1)
  } else if (embyStore.libraries.length > 0) {
    // fetch items for first enabled library to populate tag counts
    const lib = embyStore.libraries[0]
    embyStore.selectLibrary(lib)
    await embyStore.fetchItems(lib.id)
  }
})

// Stats (media tag counts from emby store)
const stats = computed(() => embyStore.tagCounts)

// Recent jobs
const recentJobs = computed(() =>
  [...jobsStore.jobs]
    .sort((a, b) => new Date(b.created_at || 0).getTime() - new Date(a.created_at || 0).getTime())
    .slice(0, 6)
)

function formatTime(dateStr?: string) {
  if (!dateStr) return '-'
  const d = new Date(dateStr)
  const now = new Date()
  const diff = now.getTime() - d.getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return '刚刚'
  if (mins < 60) return `${mins} 分钟前`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours} 小时前`
  return d.toLocaleDateString('zh-CN')
}

function getStatusColor(status: string) {
  const map: Record<string, string> = {
    completed: 'success',
    running: 'primary',
    failed: 'error',
    queued: 'warning',
  }
  return map[status] || 'secondary'
}

function getStatusLabel(status: string) {
  const map: Record<string, string> = {
    completed: '完成',
    running: '运行中',
    failed: '失败',
    queued: '排队',
  }
  return map[status] || status
}
</script>

<template>
  <div class="w-full space-y-6 animate-fade-in">

    <!-- Welcome + Stats (single card) -->
    <div class="vision-card">
      <!-- Welcome header -->
      <WelcomeMark username="用户" message="很高兴再次见到你！\n系统运行一切正常。" />

      <!-- Stats row at bottom -->
      <div class="grid grid-cols-2 sm:grid-cols-5 gap-3 mt-6">
        <div class="flex flex-col items-center justify-center py-4 text-center rounded-xl" style="background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.06);">
          <span class="text-2xl font-bold text-white/70 font-display">{{ stats.total }}</span>
          <span class="text-xs text-white/40 font-display mt-1">全部</span>
        </div>
        <div class="flex flex-col items-center justify-center py-4 text-center rounded-xl" style="background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.06);">
          <span class="text-2xl font-bold text-[#0075FF] font-display">{{ stats.cracked }}</span>
          <span class="text-xs text-white/40 font-display mt-1">已破</span>
        </div>
        <div class="flex flex-col items-center justify-center py-4 text-center rounded-xl" style="background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.06);">
          <span class="text-2xl font-bold text-[#01B574] font-display">{{ stats.chinese }}</span>
          <span class="text-xs text-white/40 font-display mt-1">中字</span>
        </div>
        <div class="flex flex-col items-center justify-center py-4 text-center rounded-xl" style="background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.06);">
          <span class="text-2xl font-bold text-[#FFB547] font-display">{{ stats.leaked }}</span>
          <span class="text-xs text-white/40 font-display mt-1">流出</span>
        </div>
        <div class="flex flex-col items-center justify-center py-4 text-center rounded-xl" style="background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.06);">
          <span class="text-2xl font-bold text-white font-display">{{ stats.uncensored }}</span>
          <span class="text-xs text-white/40 font-display mt-1">无码</span>
        </div>
      </div>
    </div>

    <!-- Activity Card -->
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <div class="lg:col-span-2">
        <!-- GPU Metrics -->
        <SystemMetricsCard
          title="GPU 状态"
          :metrics="[
            { label: 'GPU 利用率', value: '67', unit: '%' },
            { label: '显存使用', value: '8.2', unit: 'GB / 16 GB' },
            { label: 'GPU 温度', value: '62', unit: '°C' },
            { label: '功耗', value: '187', unit: 'W' },
          ]"
          :progress-value="67"
          progress-label="GPU"
          class="mb-6"
        />

        <!-- CPU / Memory Metrics -->
        <SystemMetricsCard
          title="CPU & 内存"
          :metrics="[
            { label: 'CPU 利用率', value: '23', unit: '%' },
            { label: '内存使用', value: '16.3', unit: 'GB / 32 GB' },
            { label: 'CPU 温度', value: '48', unit: '°C' },
            { label: '磁盘读取', value: '127', unit: 'MB/s' },
          ]"
          :progress-value="51"
          progress-label="内存"
          progress-color="#01B574"
        />
      </div>

      <!-- Recent Activity -->
      <div>
        <ActivityCard title="最近任务">
          <template #action>
            <RouterLink to="/jobs" class="text-xs font-medium text-[#0075FF]">
              查看全部 →
            </RouterLink>
          </template>

          <div v-if="recentJobs.length === 0" class="py-8 text-center">
            <p class="text-sm text-white/30">暂无任务记录</p>
          </div>

          <div
            v-for="job in recentJobs"
            :key="job.id"
            class="activity-item"
          >
            <div class="activity-item__icon" :class="`activity-item__icon--${getStatusColor(job.status)}`">
              <BaseIcon
                :name="job.status === 'completed' ? 'check' : job.status === 'failed' ? 'x' : job.status === 'running' ? 'loading' : 'clock'"
                class="w-3.5 h-3.5"
              />
            </div>
            <div class="activity-item__content">
              <p class="activity-item__name">{{ job.emby_item_name || job.input_path?.split('/').pop() || 'Unknown' }}</p>
              <p class="activity-item__meta">{{ job.job_type || 'nfo' }} · {{ formatTime(job.created_at) }}</p>
            </div>
            <VuiBadge
              color="info"
              variant="gradient"
              size="xs"
            >
              {{ getStatusLabel(job.status) }}
            </VuiBadge>
          </div>
        </ActivityCard>
      </div>
    </div>
  </div>
</template>
