<script setup lang="ts">
import BaseIcon from './BaseIcon.vue'
import VuiBadge from '../ui/Badge/VuiBadge.vue'
import VuiButton from '../ui/Button/VuiButton.vue'
import VuiProgress from '../ui/Progress/VuiProgress.vue'
import type { Job } from '../../api/types'

export type JobCardViewModel = {
  selected?: boolean
  flashing?: boolean
  showTypeChip?: boolean
  showProgressPanel?: boolean
  showSummaryLine?: boolean
  showMetaLine?: boolean
  showCompletedAt?: boolean
  typeChipLabel: string
  typeChipClass: string
  strategyChipLabel?: string
  strategyChipClass?: string
  badgeLabel: string
  badgeTone: string
  iconName: string
  iconClass: string
  phaseLabel?: string
  chainLine?: string
  showChainLine?: boolean
  summaryLine?: string
  metaLine?: string
  completedAt?: string
  canCancel?: boolean
  overallLabel?: string
  phaseLabelText?: string
  cancelLabel?: string
  overallProgressValue?: number
  overallProgressText?: string
  showPhaseProgress?: boolean
  phaseProgressValue?: number
  phaseProgressText?: string
  chainStepLabel?: string
  chainRoleLabel?: string
  chainWaitingLabel?: string
  chainHint?: string
  isPrimaryChainJob?: boolean
  isFollowupChainJob?: boolean
  diagnosticSummary?: string[]
}

defineProps<{
  job: Job
  view: JobCardViewModel
}>()

defineEmits<{
  click: [job: Job]
  cancel: [jobId: string]
}>()
</script>

<template>
  <div
    class="job-card ui-card p-4 cursor-pointer"
    :class="{
      'job-card--selected': view.selected,
      'job-card--flash': view.flashing,
      'job-card--chain-primary': view.isPrimaryChainJob,
      'job-card--chain-followup': view.isFollowupChainJob,
    }"
    @click="$emit('click', job)"
  >
    <div class="flex items-start gap-3">
      <div class="job-card__icon" :class="view.iconClass">
        <BaseIcon :name="view.iconName" class="w-4 h-4" :class="job.status === 'running' ? 'animate-spin' : ''" />
      </div>
      <div class="flex-1 min-w-0">
        <div class="flex items-center justify-between mb-2">
          <div class="flex items-center gap-2 min-w-0 flex-1">
            <span
              v-if="view.showTypeChip"
              class="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-bold border shrink-0"
              :class="view.typeChipClass"
            >{{ view.typeChipLabel }}</span>
            <span
              v-if="view.strategyChipLabel"
              class="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-bold border shrink-0"
              :class="view.strategyChipClass"
            >{{ view.strategyChipLabel }}</span>
            <p class="text-sm font-medium truncate text-white font-display">
              {{ job.emby_item_name || job.input_path?.split('/').pop() }}
            </p>
          </div>
          <VuiBadge variant="gradient" :color="view.badgeTone" size="xs">{{ view.badgeLabel }}</VuiBadge>
        </div>

        <div class="flex flex-wrap items-center gap-2" :class="view.showProgressPanel ? 'mb-2' : 'mt-1'">
          <p v-if="view.showProgressPanel && view.phaseLabel" class="text-xs text-white/55">{{ view.phaseLabel }}</p>
          <span v-if="view.chainStepLabel" class="text-[11px] text-white/34 border border-white/10 rounded-full px-2 py-0.5">{{ view.chainStepLabel }}</span>
          <span v-if="view.chainRoleLabel" class="text-[11px] text-accent-cyan/80 border border-accent-cyan/20 rounded-full px-2 py-0.5">{{ view.chainRoleLabel }}</span>
          <span v-if="view.chainWaitingLabel" class="text-[11px] text-white/40 border border-white/10 rounded-full px-2 py-0.5">{{ view.chainWaitingLabel }}</span>
          <span v-else-if="view.chainHint" class="text-[11px] text-white/30 border border-white/10 rounded-full px-2 py-0.5">{{ view.chainHint }}</span>
          <p v-if="view.showCompletedAt && view.completedAt" class="text-xs text-white/40">{{ view.completedAt }}</p>
        </div>

        <p v-if="view.showChainLine && view.chainLine" class="job-card__chain-line" :class="{ 'job-card__chain-line--compact': !view.showProgressPanel }">{{ view.chainLine }}</p>
        <p v-if="view.showSummaryLine && view.summaryLine" class="text-xs text-white/35 mb-2 truncate">{{ view.summaryLine }}</p>
        <p v-if="view.showMetaLine && view.metaLine" class="text-xs text-white/40 truncate">{{ view.metaLine }}</p>
        <div v-if="view.diagnosticSummary?.length" class="job-card__diagnostics">
          <span v-for="item in view.diagnosticSummary" :key="item" class="job-card__diagnostic-chip">{{ item }}</span>
        </div>

        <template v-if="view.showProgressPanel">
          <div v-if="view.overallProgressText" class="space-y-2">
            <div class="flex items-center gap-2">
              <span class="text-[11px] text-white/32 shrink-0">{{ view.overallLabel }}</span>
              <VuiProgress :value="view.overallProgressValue || 0" color="primary" variant="gradient" class="flex-1" />
              <span class="text-xs text-white/40 min-w-[2.5rem]">{{ view.overallProgressText }}</span>
              <VuiButton v-if="view.canCancel" variant="outlined" color="error" size="small" @click.stop="$emit('cancel', job.id)">
                {{ view.cancelLabel }}
              </VuiButton>
            </div>
            <div v-if="view.showPhaseProgress" class="flex items-center gap-2">
              <span class="text-[11px] text-white/26 shrink-0">{{ view.phaseLabelText }}</span>
              <VuiProgress :value="view.phaseProgressValue || 0" color="info" class="flex-1 opacity-80" />
              <span class="text-[11px] text-white/28 min-w-[2.5rem]">{{ view.phaseProgressText }}</span>
            </div>
          </div>
        </template>
      </div>
    </div>
  </div>
</template>

<style scoped>
.job-card {
  transition: all var(--transition-normal);
}

.job-card:hover {
  border-color: rgba(0, 117, 255, 0.3);
  box-shadow: 0 8px 26px -4px rgba(0, 117, 255, 0.2);
  transform: translateY(-1px);
}

.job-card--selected {
  border-color: rgba(0, 117, 255, 0.4);
  box-shadow: 0 0 0 1px rgba(0, 117, 255, 0.2), 0 8px 26px -4px rgba(0, 117, 255, 0.25);
}

.job-card--chain-primary {
  border-left: 1px solid rgba(0, 117, 255, 0.34);
}

.job-card--chain-followup {
  border-left: 1px solid rgba(86, 204, 242, 0.26);
}

.job-card--flash {
  animation: job-card-flash 2s ease-out 1;
}

@keyframes job-card-flash {
  0% {
    box-shadow: 0 0 0 0 rgba(0,117,255,0.45), 0 10px 30px -6px rgba(0,117,255,0.35);
    border-color: rgba(0,117,255,0.55);
  }
  100% {
    box-shadow: 0 0 0 1px rgba(0,117,255,0.12), 0 8px 26px -4px rgba(0,117,255,0.08);
    border-color: rgba(255,255,255,0.08);
  }
}

.job-card__icon {
  width: 2.25rem;
  height: 2.25rem;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.job-card__icon--running {
  background: rgba(0, 117, 255, 0.15);
  color: #0075FF;
}

.job-card__icon--queued {
  background: rgba(255, 181, 71, 0.15);
  color: #FFB547;
}

.job-card__icon--completed {
  background: rgba(1, 181, 116, 0.15);
  color: #01B574;
}

.job-card__icon--failed {
  background: rgba(227, 26, 26, 0.15);
  color: #E31A1A;
}

.job-card__icon--cancelled,
.job-card__icon--skipped {
  background: rgba(255, 181, 71, 0.14);
  color: #FFB547;
}

.job-card__chain-line {
  margin-bottom: 0.45rem;
  font-size: 11px;
  color: rgba(255,255,255,0.32);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.job-card__chain-line--compact {
  margin-top: 0.35rem;
  margin-bottom: 0;
}

.job-card__diagnostics {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
  margin-top: 0.55rem;
}

.job-card__diagnostic-chip {
  display: inline-flex;
  align-items: center;
  padding: 0.18rem 0.45rem;
  border-radius: 999px;
  border: 1px solid rgba(255,255,255,0.08);
  background: rgba(255,255,255,0.025);
  font-size: 10px;
  color: rgba(255,255,255,0.46);
  line-height: 1.2;
}
</style>
