import { ref, provide, inject, type Ref } from 'vue'

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

// t as a plain function that reads the module-level _currentLang ref
// Components call this via useI18n() which injects or falls back to module-level
function makeT() {
  return (key: string, params?: Record<string, string | number>): string => {
    const dict = dictionaries[_currentLang.value] || dictionaries.zh
    let text = dict[key] ?? key
    if (params) {
      for (const [k, v] of Object.entries(params)) {
        text = text.replace(`{${k}}`, String(v))
      }
    }
    return text
  }
}

// Provide/inject key
const I18N_KEY = Symbol('i18n') as any

export function useI18n() {
  const ctx = inject<{
    currentLang: Ref<Lang>
    switchLang: (lang: Lang) => void
    t: (key: string, params?: Record<string, string | number>) => string
  }>(I18N_KEY)

  if (ctx) {
    return ctx
  }

  function switchLang(lang: Lang) {
    _currentLang.value = lang
    localStorage.setItem(STORAGE_KEY, lang)
    loadDict(lang)
  }

  return {
    currentLang: _currentLang,
    switchLang,
    t: makeT(),
  }
}

export function provideI18n() {
  function switchLang(lang: Lang) {
    _currentLang.value = lang
    localStorage.setItem(STORAGE_KEY, lang)
    loadDict(lang)
  }

  const provided = {
    currentLang: _currentLang,
    switchLang,
    t: makeT(),
  }
  provide(I18N_KEY, provided)
  return provided
}
