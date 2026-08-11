import { ref, computed } from 'vue'

const STORAGE_KEY = 'lada-blur-cover'

// Persisted master setting
const masterEnabled = ref<boolean>(
  localStorage.getItem(STORAGE_KEY) === null
    ? true
    : localStorage.getItem(STORAGE_KEY) === 'true'
)

// Runtime override from toolbar (not persisted)
const toolbarOverride = ref<boolean | null>(null)

export function useBlurCover() {
  // Effective value: toolbar override > master setting
  const blurEnabled = computed(() =>
    toolbarOverride.value !== null ? toolbarOverride.value : masterEnabled.value
  )

  // Toolbar: temporary toggle, does NOT persist
  function toggleBlur() {
    if (toolbarOverride.value === null) {
      toolbarOverride.value = !masterEnabled.value
    } else {
      toolbarOverride.value = !toolbarOverride.value
    }
  }

  // Settings: persist to localStorage
  function setBlur(value: boolean) {
    masterEnabled.value = value
    toolbarOverride.value = null
    localStorage.setItem(STORAGE_KEY, String(value))
  }

  return {
    blurEnabled,
    toggleBlur,
    setBlur,
  }
}
