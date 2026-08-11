
<script setup lang="ts">
import VuiBadge from '../ui/Badge/VuiBadge.vue'

export type JobChainMemberViewModel = {
  id: string
  active?: boolean
  positionLabel?: string
  stepLabel?: string
  roleLabel?: string
  name: string
  phaseLine?: string
  progressText?: string
  statusLabel: string
  statusTone: string
}

defineProps<{
  title: string
  flow?: string
  summary?: string
  members: JobChainMemberViewModel[]
}>()

defineEmits<{
  select: [jobId: string]
}>()
</script>

<template>
  <div class="job-chain-panel">
    <div class="job-chain-panel__head">
      <div class="job-chain-panel__meta">
        <span class="job-chain-panel__title">{{ title }}</span>
        <span v-if="flow" class="job-chain-panel__flow">{{ flow }}</span>
      </div>
      <span v-if="summary" class="job-chain-panel__summary">{{ summary }}</span>
    </div>
    <div class="job-chain-panel__list">
      <button
        v-for="member in members"
        :key="member.id"
        type="button"
        class="job-chain-panel__item"
        :class="{ 'job-chain-panel__item--active': member.active }"
        @click="$emit('select', member.id)"
      >
        <div class="job-chain-panel__step">
          <span class="job-chain-panel__index">{{ member.positionLabel }}</span>
          <span class="job-chain-panel__step-name">{{ member.stepLabel }}</span>
          <span v-if="member.roleLabel" class="job-chain-panel__role">{{ member.roleLabel }}</span>
        </div>
        <div class="job-chain-panel__content">
          <p class="job-chain-panel__name">{{ member.name }}</p>
          <p v-if="member.phaseLine" class="job-chain-panel__phase">{{ member.phaseLine }}</p>
          <p v-if="member.progressText" class="job-chain-panel__progress">{{ member.progressText }}</p>
        </div>
        <VuiBadge :color="member.statusTone" variant="gradient" size="xs">
          {{ member.statusLabel }}
        </VuiBadge>
      </button>
    </div>
  </div>
</template>

<style scoped>
.job-chain-panel {
  border-bottom: 1px solid rgba(255,255,255,0.06);
  background: linear-gradient(180deg, rgba(255,255,255,0.025), rgba(255,255,255,0.01));
}

.job-chain-panel__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  padding: 0.9rem 1rem 0.75rem;
  border-bottom: 1px solid rgba(255,255,255,0.05);
}

.job-chain-panel__meta {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
}

.job-chain-panel__title {
  font-size: 11px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: rgba(255,255,255,0.34);
}

.job-chain-panel__flow {
  font-size: 12px;
  color: rgba(255,255,255,0.56);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.job-chain-panel__summary {
  font-size: 11px;
  color: rgba(255,255,255,0.38);
}

.job-chain-panel__list {
  display: flex;
  flex-direction: column;
  gap: 0.45rem;
  padding: 0.8rem 1rem 1rem;
}

.job-chain-panel__item {
  width: 100%;
  border: 1px solid rgba(255,255,255,0.06);
  background: rgba(255,255,255,0.02);
  border-radius: 12px;
  padding: 0.75rem;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  text-align: left;
  transition: all var(--transition-normal);
}

.job-chain-panel__item:hover {
  border-color: rgba(0,117,255,0.22);
  background: rgba(255,255,255,0.035);
}

.job-chain-panel__item--active {
  border-color: rgba(0,117,255,0.34);
  background: rgba(0,117,255,0.08);
}

.job-chain-panel__step {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  min-width: 0;
}

.job-chain-panel__index,
.job-chain-panel__step-name {
  font-size: 11px;
  color: rgba(255,255,255,0.42);
}

.job-chain-panel__content {
  flex: 1;
  min-width: 0;
}

.job-chain-panel__name {
  font-size: 12px;
  color: rgba(255,255,255,0.82);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.job-chain-panel__phase {
  margin-top: 0.2rem;
  font-size: 11px;
  color: rgba(255,255,255,0.46);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.job-chain-panel__progress {
  margin-top: 0.2rem;
  font-size: 11px;
  color: rgba(255,255,255,0.3);
}

.job-chain-panel__role {
  font-size: 10px;
  color: rgba(86, 204, 242, 0.76);
}
</style>


