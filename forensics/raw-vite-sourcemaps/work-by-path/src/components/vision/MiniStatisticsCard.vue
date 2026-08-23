<script setup lang="ts">
import BaseIcon from '../BaseIcon.vue'

withDefaults(defineProps<{
  title?: string
  count?: string | number
  percentage?: string
  percentageColor?: 'success' | 'error' | 'warning' | 'info' | 'primary' | 'secondary'
  icon?: any
  direction?: 'left' | 'right'
  bgColor?: string
}>(), {
  title: '',
  count: 0,
  percentage: '',
  percentageColor: 'success',
  direction: 'right',
  bgColor: 'white',
})
</script>

<template>
  <div class="mini-stat-card vision-card">
    <div class="mini-stat-card__inner">
      <div class="mini-stat-card__content" :class="`mini-stat-card__content--${direction}`">
        <!-- Left icon slot -->
        <template v-if="direction === 'left'">
          <div class="mini-stat-card__icon-box mini-stat-card__icon-box--left">
            <slot name="icon">
              <BaseIcon v-if="icon" :name="icon" class="w-5 h-5 text-white" />
            </slot>
          </div>
        </template>

        <!-- Text content -->
        <div class="mini-stat-card__text" :style="direction === 'left' ? '' : ''">
          <p class="mini-stat-card__title">{{ title }}</p>
          <p class="mini-stat-card__count">
            {{ count }}
            <span
              v-if="percentage"
              class="mini-stat-card__percentage"
              :class="`mini-stat-card__percentage--${percentageColor}`"
            >
              {{ percentage }}
            </span>
          </p>
        </div>

        <!-- Right icon slot -->
        <template v-if="direction === 'right'">
          <div class="mini-stat-card__icon-box mini-stat-card__icon-box--right">
            <slot name="icon">
              <BaseIcon v-if="icon" :name="icon" class="w-5 h-5 text-white" />
            </slot>
          </div>
        </template>
      </div>
    </div>
  </div>
</template>
<style scoped>
</style>

<style scoped>
.mini-stat-card {
  transition: all var(--transition-normal);
  position: relative;
  overflow: hidden;
}

.mini-stat-card:hover {
  border-color: rgba(0, 117, 255, 0.3);
  box-shadow: 0 8px 26px -4px rgba(0, 117, 255, 0.2);
  transform: translateY(-2px);
}

.mini-stat-card__inner {
  display: flex;
  align-items: center;
}

.mini-stat-card__content {
  display: flex;
  align-items: center;
  width: 100%;
  gap: 0.5rem;
}

.mini-stat-card__content--right {
  flex-direction: row;
}

.mini-stat-card__content--left {
  flex-direction: row;
}

.mini-stat-card__text {
  flex: 1;
  min-width: 0;
}

.mini-stat-card__title {
  font-family: var(--font-display);
  font-size: 0.75rem;
  font-weight: 500;
  color: rgba(255, 255, 255, 0.6);
  text-transform: capitalize;
  margin-bottom: 0.25rem;
  line-height: 1;
}

.mini-stat-card__count {
  font-family: var(--font-display);
  font-size: 1.5rem;
  font-weight: 700;
  color: #FFFFFF;
  line-height: 1.2;
  display: flex;
  align-items: baseline;
  gap: 0.375rem;
  flex-wrap: wrap;
}

.mini-stat-card__percentage {
  font-size: 0.875rem;
  font-weight: 700;
}

.mini-stat-card__percentage--success { color: #01B574; }
.mini-stat-card__percentage--error { color: #E31A1A; }
.mini-stat-card__percentage--warning { color: #FFB547; }
.mini-stat-card__percentage--info { color: #0075FF; }
.mini-stat-card__percentage--primary { color: #0075FF; }
.mini-stat-card__percentage--secondary { color: #A8B8D8; }

.mini-stat-card__icon-box {
  width: 3rem;
  height: 3rem;
  border-radius: var(--radius-lg);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  background: #0075FF;
  box-shadow: 0 4px 6px -1px rgba(0, 117, 255, 0.35);
}

.mini-stat-card__icon-box--right {
  margin-left: auto;
}

.mini-stat-card__icon-box--left {
  margin-right: 0.5rem;
}
</style>
