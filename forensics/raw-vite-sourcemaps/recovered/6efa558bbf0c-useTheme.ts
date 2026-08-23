import { ref, watch } from 'vue'

export type Theme = 'classic' | 'neon'

const STORAGE_KEY = 'lada-theme'

const currentTheme = ref<Theme>((localStorage.getItem(STORAGE_KEY) as Theme) || 'classic')

function applyTheme(theme: Theme) {
  const html = document.documentElement
  html.classList.remove('theme-classic', 'theme-neon')
  html.classList.add(`theme-${theme}`)
}

export function useTheme() {
  function switchTheme(theme: Theme) {
    currentTheme.value = theme
    localStorage.setItem(STORAGE_KEY, theme)
    applyTheme(theme)
  }

  function toggleTheme() {
    const next: Theme = currentTheme.value === 'classic' ? 'neon' : 'classic'
    switchTheme(next)
  }

  // Apply on init
  applyTheme(currentTheme.value)

  return {
    currentTheme,
    switchTheme,
    toggleTheme,
  }
}
