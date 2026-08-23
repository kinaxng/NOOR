<script setup lang="ts">
import { RouterView, RouterLink, useRoute } from 'vue-router'
import { useTheme } from './composables/useTheme'
import { useI18n } from './composables/useI18n'

const route = useRoute()
const { currentTheme, toggleTheme } = useTheme()
const { t, currentLang, switchLang } = useI18n()
</script>

<template>
  <div class="min-h-screen bg-gray-900 text-gray-100">
    <!-- Top Navigation Bar -->
    <nav class="bg-gray-800 border-b border-gray-700">
      <div class="max-w-7xl mx-auto px-4">
        <div class="flex items-center h-14 space-x-8">
          <!-- Brand -->
          <span class="text-xl font-bold text-blue-400 tracking-wide">Lada WebUI</span>

          <!-- Nav Links -->
          <div class="flex space-x-4">
            <RouterLink
              to="/"
              :class="[
                'px-3 py-2 rounded-md text-sm font-medium transition-colors',
                route.path === '/' ? 'bg-gray-700 text-white' : 'text-gray-300 hover:bg-gray-700'
              ]"
            >
              {{ t('nav.library') }}
            </RouterLink>
            <RouterLink
              to="/jobs"
              :class="[
                'px-3 py-2 rounded-md text-sm font-medium transition-colors',
                route.path === '/jobs' ? 'bg-gray-700 text-white' : 'text-gray-300 hover:bg-gray-700'
              ]"
            >
              {{ t('nav.jobs') }}
            </RouterLink>
            <RouterLink
              to="/history"
              :class="[
                'px-3 py-2 rounded-md text-sm font-medium transition-colors',
                route.path === '/history' ? 'bg-gray-700 text-white' : 'text-gray-300 hover:bg-gray-700'
              ]"
            >
              {{ t('nav.history') }}
            </RouterLink>
            <RouterLink
              to="/settings"
              :class="[
                'px-3 py-2 rounded-md text-sm font-medium transition-colors',
                route.path === '/settings' ? 'bg-gray-700 text-white' : 'text-gray-300 hover:bg-gray-700'
              ]"
            >
              {{ t('nav.settings') }}
            </RouterLink>
          </div>

          <!-- Spacer -->
          <div class="flex-1"></div>

          <!-- Theme Toggle -->
          <button
            @click="toggleTheme"
            :title="currentTheme === 'classic' ? 'Switch to Neon Terminal' : 'Switch to Classic'"
            class="flex items-center gap-1.5 px-3 py-1.5 rounded border text-xs font-medium transition-colors"
            :class="currentTheme === 'neon'
              ? 'border-cyan-400/50 text-cyan-400 hover:bg-cyan-400/10'
              : 'border-gray-600 text-gray-400 hover:text-gray-200 hover:border-gray-400'"
          >
            <!-- Sun icon for classic, terminal icon for neon -->
            <svg v-if="currentTheme === 'classic'" xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <circle cx="12" cy="12" r="4" />
              <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41" />
            </svg>
            <svg v-else xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <polyline points="4 17 10 11 4 5" />
              <line x1="12" y1="19" x2="20" y2="19" />
            </svg>
            <span>{{ currentTheme === 'classic' ? 'Neon' : 'Classic' }}</span>
          </button>

          <!-- Language Toggle -->
          <button
            @click="switchLang(currentLang === 'zh' ? 'en' : 'zh')"
            :title="currentLang === 'zh' ? 'Switch to English' : '切换到中文'"
            class="px-3 py-1.5 rounded border border-gray-600 text-xs font-medium text-gray-400 hover:text-gray-200 hover:border-gray-400 transition-colors"
          >
            {{ currentLang === 'zh' ? 'EN' : '中' }}
          </button>
        </div>
      </div>
    </nav>

    <main>
      <RouterView />
    </main>
  </div>
</template>
