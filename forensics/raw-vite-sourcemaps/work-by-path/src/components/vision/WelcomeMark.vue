<script setup lang="ts">
defineProps<{
  username?: string
  message?: string
}>()
</script>

<template>
  <div class="welcome-mark">
    <!-- Decorative gradient blobs -->
    <div class="welcome-mark__blob welcome-mark__blob--1" />
    <div class="welcome-mark__blob welcome-mark__blob--2" />
    <div class="welcome-mark__blob welcome-mark__blob--3" />

    <div class="welcome-mark__content">
      <div class="welcome-mark__top">
        <div>
          <p class="welcome-mark__greeting">欢迎回来,</p>
          <h2 class="welcome-mark__name">{{ username || '用户' }}</h2>
        </div>
      </div>

      <div class="welcome-mark__body">
        <p class="welcome-mark__message">
          {{ message || '很高兴再次见到你！\n有什么需要帮助的请随时告诉我。' }}
        </p>
      </div>

      <div class="welcome-mark__footer">
        <button class="welcome-mark__cta">
          <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
          </svg>
          <span>语音助手</span>
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.welcome-mark {
  position: relative;
  height: 340px;
  border-radius: var(--radius-xl);
  overflow: hidden;
  background: linear-gradient(159.02deg, #0f123b 14.25%, #090d2e 56.45%, #020515 86.14%);
  border: 1px solid rgba(255, 255, 255, 0.06);
  padding: 2rem;
  display: flex;
  flex-direction: column;
}

/* Decorative blobs */
.welcome-mark__blob {
  position: absolute;
  border-radius: 50%;
  filter: blur(60px);
  pointer-events: none;
}

.welcome-mark__blob--1 {
  width: 200px;
  height: 200px;
  top: -40px;
  right: -20px;
  background: radial-gradient(circle, #0075FF 0%, transparent 70%);
  opacity: 0.4;
}

.welcome-mark__blob--2 {
  width: 150px;
  height: 150px;
  bottom: 20px;
  right: 80px;
  background: radial-gradient(circle, #0075FF 0%, transparent 70%);
  opacity: 0.3;
}

.welcome-mark__blob--3 {
  width: 100px;
  height: 100px;
  bottom: -20px;
  left: 40px;
  background: radial-gradient(circle, #21D4FD 0%, transparent 70%);
  opacity: 0.2;
}

/* Content */
.welcome-mark__content {
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
  height: 100%;
}

.welcome-mark__top {
  flex-shrink: 0;
}

.welcome-mark__greeting {
  font-family: var(--font-display);
  font-size: 0.75rem;
  font-weight: 400;
  color: rgba(255, 255, 255, 0.6);
  margin-bottom: 0.25rem;
  line-height: 1;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.welcome-mark__name {
  font-family: var(--font-display);
  font-size: 1.875rem;
  font-weight: 700;
  color: #FFFFFF;
  line-height: 1.2;
  margin-bottom: 0;
}

.welcome-mark__body {
  flex: 1;
  display: flex;
  align-items: center;
}

.welcome-mark__message {
  font-family: var(--font-display);
  font-size: 0.875rem;
  font-weight: 400;
  color: rgba(255, 255, 255, 0.6);
  line-height: 1.6;
  white-space: pre-line;
}

.welcome-mark__footer {
  flex-shrink: 0;
  margin-top: auto;
}

.welcome-mark__cta {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.625rem 1.25rem;
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.15);
  border-radius: var(--radius-button);
  font-family: var(--font-display);
  font-size: 0.875rem;
  font-weight: 500;
  color: #FFFFFF;
  cursor: pointer;
  transition: all var(--transition-fast);
}

.welcome-mark__cta:hover {
  background: rgba(255, 255, 255, 0.15);
  border-color: rgba(255, 255, 255, 0.25);
}
</style>
