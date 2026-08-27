import { ref, watch, type Ref } from 'vue'

export type Lang = 'zh' | 'en'

const STORAGE_KEY = 'lada-lang'

// Module-level state — single source of truth
const _currentLang = ref<Lang>((localStorage.getItem(STORAGE_KEY) as Lang) || 'zh')

// Version increments when language changes, forcing reactive re-renders
const _version = ref(0)

const dictionaries: Record<Lang, Record<string, string>> = { zh: {}, en: {} }

// Tracks when dictionaries have been loaded
const _initialized = ref(false)

// Load both dictionaries upfront (both are small ~5KB each)
// This ensures t() always returns synchronously without async timing issues
async function preloadDictionaries() {
  const [zhModule, enModule] = await Promise.all([
    import('../i18n/zh'),
    import('../i18n/en'),
  ])
  Object.assign(dictionaries.zh, zhModule.zh)
  Object.assign(dictionaries.en, enModule.en)
  _initialized.value = true
}
preloadDictionaries()

export function useI18n() {
  // Watch the module-level lang and increment version when it changes
  watch(_currentLang, () => {
    _version.value++
  })

  function switchLang(lang: Lang) {
    _currentLang.value = lang
    localStorage.setItem(STORAGE_KEY, lang)
    _version.value++ // Increment immediately so reactive updates happen synchronously
  }

  function t(key: string, params?: Record<string, string | number>): string {
    const dict = dictionaries[_currentLang.value] || dictionaries.zh
    let text = dict[key] ?? key
    if (params) {
      for (const [k, v] of Object.entries(params)) {
        text = text.replace(`{${k}}`, String(v))
      }
    }
    return text
  }

  return {
    currentLang: _currentLang as Ref<Lang>,
    i18nVersion: _version,
    switchLang,
    t,
    // Expose raw ref for use in computed() - ensures Vue tracks dependency correctly
    // when t() reads _currentLang.value directly
    _currentLang,
    // Tracks when dictionaries have been loaded - use this to force recomputation
    // after dictionaries are ready
    _initialized,
  }
}
