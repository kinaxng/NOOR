import { ref, watch, provide, inject, type Ref } from 'vue'

export type Lang = 'zh' | 'en'

const STORAGE_KEY = 'lada-lang'

// Module-level state — single source of truth
const _currentLang = ref<Lang>((localStorage.getItem(STORAGE_KEY) as Lang) || 'zh')

const dictionaries: Record<Lang, Record<string, string>> = { zh: {}, en: {} }
let zhLoaded = false
let enLoaded = false

async function loadDict(lang: Lang) {
  if (lang === 'zh' && !zhLoaded) {
    const m = await import('../i18n/zh')
    Object.assign(dictionaries.zh, m.zh)
    zhLoaded = true
  }
  if (lang === 'en' && !enLoaded) {
    const m = await import('../i18n/en')
    Object.assign(dictionaries.en, m.en)
    enLoaded = true
  }
}
loadDict(_currentLang.value)

// Provide/inject key
const I18N_KEY = Symbol('i18n') as any

export function useI18n() {
  const ctx = inject<{
    currentLang: Ref<Lang>
    switchLang: (lang: Lang) => void
    t: (key: string, params?: Record<string, string | number>) => string
  }>(I18N_KEY)

  if (ctx) {
    // Also set up a watcher so that templates using t() will re-render when lang changes
    // This is needed because Vue can't track reactive deps inside function calls in templates
    watch(_currentLang, () => {}, { flush: 'post' })
    return ctx
  }

  function switchLang(lang: Lang) {
    _currentLang.value = lang
    localStorage.setItem(STORAGE_KEY, lang)
    loadDict(lang)
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
    currentLang: _currentLang,
    switchLang,
    t,
  }
}

export function provideI18n() {
  function switchLang(lang: Lang) {
    _currentLang.value = lang
    localStorage.setItem(STORAGE_KEY, lang)
    loadDict(lang)
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

  const provided = {
    currentLang: _currentLang,
    switchLang,
    t,
  }
  provide(I18N_KEY, provided)
  return provided
}
