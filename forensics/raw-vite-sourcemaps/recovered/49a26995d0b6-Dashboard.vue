<script setup lang="ts">
import { onMounted, computed } from 'vue'
import { useEmbyStore } from '../stores/emby'
import { useJobsStore } from '../stores/jobs'
import { RouterLink } from 'vue-router'
import BaseIcon from '../components/BaseIcon.vue'
import VuiProgress from '../components/vision/VuiProgress/VuiProgress.vue'
import VuiBadge from '../components/vision/VuiBadge/VuiBadge.vue'
import MiniStatisticsCard from '../components/vision/MiniStatisticsCard.vue'
import WelcomeMark from '../components/vision/WelcomeMark.vue'
import ActivityCard from '../components/vision/ActivityCard.vue'

const embyStore = useEmbyStore()
const jobsStore = useJobsStore()

onMounted(async () => {
  await embyStore.fetchLibraries()
  await jobsStore.fetchJobs()
})

// Stats
const stats = computed(() => {
  const total = embyStore.total || 0
  const running = jobsStore.jobs.filter(j => j.status === 'running').length
  const queued = jobsStore.jobs.filter(j => j.status === 'queued').length
  const completedToday = jobsStore.jobs.filter(j => {
    if (j.status !== 'completed' || !j.completed_at) return false
    return new Date(j.completed_at).toDateString() === new Date().toDateString()
  }).length
  const totalCompleted = jobsStore.jobs.filter(j => j.status === 'completed').length
  const totalFailed = jobsStore.jobs.filter(j => j.status === 'failed').length
  return { total, running, queued, completedToday, totalCompleted, totalFailed }
})

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
  <div class="max-w-[1400px] mx-auto space-y-6 animate-fade-in">

    <!-- Welcome + Stats Row -->
    <div class="grid grid-cols-1 lg:grid-cols-4 gap-6">
      <!-- Welcome Card (spans 2 cols on large) -->
      <div class="lg:col-span-2">
        <WelcomeMark username="用户" message="很高兴再次见到你！\n系统运行一切正常。" />
      </div>

      <!-- Right Stats -->
      <div class="lg:col-span-2 grid grid-cols-1 sm:grid-cols-2 gap-4">
        <MiniStatisticsCard
          :title="'媒体总数'"
          :count="stats.total.toLocaleString()"
          percentage=""
          icon="library"
          direction="right"
        >
          <template #icon>
            <BaseIcon name="library" class="w-5 h-5 text-white" />
          </template>
        </MiniStatisticsCard>

        <MiniStatisticsCard
          :title="'运行中任务'"
          :count="stats.running"
          :percentage="stats.queued > 0 ? `+${stats.queued} 排队` : undefined"
          percentage-color="info"
          icon="loading"
          direction="right"
        >
          <template #icon>
            <BaseIcon name="jobs" class="w-5 h-5 text-white" />
          </template>
        </MiniStatisticsCard>

        <MiniStatisticsCard
          :title="'今日完成'"
          :count="stats.completedToday"
          percentage-color="success"
          icon="check"
          direction="right"
        >
          <template #icon>
            <BaseIcon name="check" class="w-5 h-5 text-white" />
          </template>
        </MiniStatisticsCard>

        <MiniStatisticsCard
          :title="'总完成任务'"
          :count="stats.totalCompleted"
          :percentage="stats.totalFailed > 0 ? `${stats.totalFailed} 失败` : undefined"
          :percentage-color="stats.totalFailed > 0 ? 'error' : 'success'"
          icon="sparkles"
          direction="right"
        >
          <template #icon>
            <BaseIcon name="sparkles" class="w-5 h-5 text-white" />
          </template>
        </MiniStatisticsCard>
      </div>
    </div>

    <!-- Charts Row (placeholder + Activity) -->
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <!-- Chart placeholder card -->
      <div
        class="lg:col-span-2 vision-card"
        style="min-height: 300px;"
      >
        <div class="flex items-center justify-between mb-6">
          <div>
            <h3 class="text-sm font-semibold font-display text-white">任务统计</h3>
            <p class="text-xs mt-0.5 text-white/50">本周任务完成趋势</p>
          </div>
          <VuiBadge variant="gradient" color="info" size="sm">周</VuiBadge>
        </div>

        <!-- Simple bar visualization -->
        <div class="flex items-end gap-2 h-40 mb-4">
          <div
            v-for="(val, i) in [40, 65, 45, 80, 55, 90, 70]"
            :key="i"
            class="flex-1 rounded-t-sm transition-all duration-500"
            :style="{
              height: `${val}%`,
              background: i === 5
                ? '#0075FF'
                : 'rgba(0, 117, 255, 0.3)',
              animationDelay: `${i * 80}ms`,
              opacity: i === 5 ? 1 : 0.5 + i * 0.07
            }"
          />
        </div>

        <div class="flex items-center justify-between text-xs text-white/40">
          <span>周一</span><span>周二</span><span>周三</span><span>周四</span><span>周五</span><span>周六</span><span>周日</span>
        </div>

        <!-- Stats footer -->
        <div class="flex items-center gap-6 mt-6 pt-4 border-t border-white/5">
          <div>
            <p class="text-xs text-white/40">本周完成</p>
            <p class="text-lg font-bold font-display text-white">
              {{ stats.completedToday + stats.totalCompleted }}
            </p>
          </div>
          <div>
            <p class="text-xs text-white/40">本周失败</p>
            <p class="text-lg font-bold font-display text-[#E31A1A]">
              {{ stats.totalFailed }}
            </p>
          </div>
          <div>
            <p class="text-xs text-white/40">成功率</p>
            <p class="text-lg font-bold font-display text-[#01B574]">
              {{ stats.totalCompleted + stats.totalFailed > 0
                ? Math.round((stats.totalCompleted / (stats.totalCompleted + stats.totalFailed)) * 100)
                : 100 }}%
            </p>
          </div>
        </div>
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

    <!-- Quick Actions Row -->
    <div class="grid grid-cols-2 lg:grid-cols-4 gap-4">
      <RouterLink
        v-for="action in [
          { icon: 'library', label: '浏览媒体库', desc: '查看所有媒体', color: 'primary' },
          { icon: 'jobs', label: '任务管理', desc: '查看运行中任务', color: 'info' },
          { icon: 'history', label: '历史记录', desc: '查看完成记录', color: 'success' },
          { icon: 'settings', label: '系统设置', desc: '配置参数', color: 'secondary' },
        ]"
        :key="action.label"
        :to="action.icon === 'library' ? '/library' : action.icon === 'jobs' ? '/jobs' : action.icon === 'history' ? '/history' : '/settings'"
        class="quick-action-card"
      >
        <div
          class="quick-action-card__icon"
          :class="`quick-action-card__icon--${action.color}`"
        >
          <BaseIcon :name="action.icon" class="w-5 h-5" />
        </div>
        <div>
          <p class="quick-action-card__label">{{ action.label }}</p>
          <p class="quick-action-card__desc">{{ action.desc }}</p>
        </div>
        <BaseIcon name="chevronRight" class="w-4 h-4 ml-auto opacity-40 quick-action-card__arrow" />
      </RouterLink>
    </div>

    <!-- System Info Row -->
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <!-- System Status -->
      <div
        class="vision-card"
      >
        <h3 class="text-sm font-semibold mb-4 font-display text-white">系统状态</h3>
        <div class="space-y-3">
          <div v-for="item in [
            { label: '媒体库', value: `${embyStore.libraries.length} 个`, status: embyStore.libraries.length > 0 ? 'success' : 'error' },
            { label: 'Emby 连接', value: embyStore.libraries.length > 0 ? '已连接' : '未连接', status: embyStore.libraries.length > 0 ? 'success' : 'error' },
            { label: '任务总数', value: `${jobsStore.jobs.length}`, status: 'info' },
            { label: '队列状态', value: `${stats.running + stats.queued} / ${jobsStore.jobs.length}`, status: 'info' },
          ]" :key="item.label" class="flex items-center justify-between">
            <span class="text-sm text-white/50">{{ item.label }}</span>
            <div class="flex items-center gap-2">
              <span
                class="w-1.5 h-1.5 rounded-full"
                :style="{ background: item.status === 'success' ? '#01B574' : item.status === 'error' ? '#E31A1A' : '#0075FF' }"
              />
              <span class="text-sm font-medium text-sm font-semibold font-display text-white">{{ item.value }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- LADA System -->
      <div
        class="vision-card"
      >
        <h3 class="text-sm font-semibold mb-4 font-display text-white">LADA 版本信息</h3>
        <div class="space-y-4">
          <div>
            <p class="text-xs mb-1 text-white/40">Frontend</p>
            <VuiBadge variant="gradient" color="info" size="xs">v1.0.0</VuiBadge>
          </div>
          <div>
            <VuiProgress :value="stats.totalCompleted > 0 ? (stats.totalCompleted / (stats.totalCompleted + stats.totalFailed || 1)) * 100 : 0" color="success" variant="gradient" />
            <div class="flex justify-between mt-1">
              <span class="text-xs text-white/40">任务成功率</span>
              <span class="text-xs font-semibold text-[#01B574]">
                {{ stats.totalCompleted + stats.totalFailed > 0
                  ? Math.round((stats.totalCompleted / (stats.totalCompleted + stats.totalFailed)) * 100)
                  : 100 }}%
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.activity-item {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.625rem;
  border-radius: var(--radius-md);
  transition: background var(--transition-fast);
}

.activity-item:hover {
  background: rgba(255, 255, 255, 0.03);
}

.activity-item__icon {
  width: 1.75rem;
  height: 1.75rem;
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.activity-item__icon--success { background: rgba(1, 181, 116, 0.15); color: #01B574; }
.activity-item__icon--error { background: rgba(227, 26, 26, 0.15); color: #E31A1A; }
.activity-item__icon--primary { background: rgba(0, 117, 255, 0.15); color: #0075FF; }
.activity-item__icon--warning { background: rgba(255, 181, 71, 0.15); color: #FFB547; }
.activity-item__icon--info { background: rgba(0, 117, 255, 0.15); color: #0075FF; }
.activity-item__icon--secondary { background: rgba(168, 184, 216, 0.15); color: #A8B8D8; }

.activity-item__content {
  flex: 1;
  min-width: 0;
}

.activity-item__name {
  font-family: var(--font-display);
  font-size: 0.8125rem;
  font-weight: 500;
  color: #FFFFFF;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.activity-item__meta {
  font-family: var(--font-display);
  font-size: 0.6875rem;
  color: rgba(255, 255, 255, 0.4);
  margin-top: 0.125rem;
}

.quick-action-card {
  display: flex;
  align-items: center;
  gap: 0.875rem;
  padding: 1rem 1.25rem;
  border-radius: var(--radius-xl);
  background: linear-gradient(127.09deg, rgba(6, 11, 40, 0.94) 19.41%, rgba(10, 14, 35, 0.49) 76.65%);
  border: 1px solid rgba(255, 255, 255, 0.06);
  text-decoration: none;
  transition: all var(--transition-normal);
}

.quick-action-card:hover {
  border-color: rgba(0, 117, 255, 0.3);
  box-shadow: 0 8px 26px -4px rgba(0, 117, 255, 0.2);
  transform: translateY(-2px);
}

.quick-action-card__icon {
  width: 2.5rem;
  height: 2.5rem;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.quick-action-card__icon--primary { background: rgba(0, 117, 255, 0.15); color: #0075FF; }
.quick-action-card__icon--info { background: rgba(0, 117, 255, 0.15); color: #0075FF; }
.quick-action-card__icon--success { background: rgba(1, 181, 116, 0.15); color: #01B574; }
.quick-action-card__icon--secondary { background: rgba(168, 184, 216, 0.15); color: #A8B8D8; }

.quick-action-card__label {
  font-family: var(--font-display);
  font-size: 0.875rem;
  font-weight: 600;
  color: #FFFFFF;
  line-height: 1;
}

.quick-action-card__desc {
  font-family: var(--font-display);
  font-size: 0.6875rem;
  color: rgba(255, 255, 255, 0.4);
  margin-top: 0.25rem;
  line-height: 1;
}

.quick-action-card__arrow {
  flex-shrink: 0;
  transition: transform var(--transition-fast);
}

.quick-action-card:hover .quick-action-card__arrow {
  transform: translateX(3px);
  opacity: 0.7;
}
</style>
