import { computed, ref } from 'vue'

const GLOBAL_STORAGE_KEY = 'noor-cover-blur-global'
const BROWSER_STORAGE_KEY = 'noor-cover-blur-browser'
const LEGACY_STORAGE_KEY = 'lada-blur-cover'

function readBooleanStorage(key: string, fallback: boolean) {
  const value = localStorage.getItem(key)
  return value === null ? fallback : value === 'true'
}

const legacyValue = localStorage.getItem(LEGACY_STORAGE_KEY)
const initialGlobalEnabled = localStorage.getItem(GLOBAL_STORAGE_KEY) === null && legacyValue !== null
  ? legacyValue === 'true'
  : readBooleanStorage(GLOBAL_STORAGE_KEY, true)

const globalBlurEnabled = ref<boolean>(initialGlobalEnabled)
const browserBlurEnabled = ref<boolean>(readBooleanStorage(BROWSER_STORAGE_KEY, true))

export function useBlurCover() {
  const blurEnabled = computed(() => globalBlurEnabled.value && browserBlurEnabled.value)

  function setGlobalBlur(value: boolean) {
    globalBlurEnabled.value = value
    localStorage.setItem(GLOBAL_STORAGE_KEY, String(value))
  }

  function syncGlobalBlur(value: boolean) {
    globalBlurEnabled.value = value
    localStorage.setItem(GLOBAL_STORAGE_KEY, String(value))
  }

  function setBrowserBlur(value: boolean) {
    browserBlurEnabled.value = value
    localStorage.setItem(BROWSER_STORAGE_KEY, String(value))
  }

  function toggleBrowserBlur() {
    setBrowserBlur(!browserBlurEnabled.value)
  }

  return {
    blurEnabled,
    globalBlurEnabled,
    browserBlurEnabled,
    setGlobalBlur,
    syncGlobalBlur,
    setBrowserBlur,
    toggleBrowserBlur,
  }
}
