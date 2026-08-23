import { zh } from './zh'
import { en } from './en'

export type Lang = 'zh' | 'en'

const dictionaries: Record<Lang, Record<string, string>> = { zh, en }

const STORAGE_KEY = 'lada-lang'

let _currentLang: Lang = (localStorage.getItem(STORAGE_KEY) as Lang) || 'zh'

export function getCurrentLang(): Lang {
  return _currentLang
}

export function setLang(lang: Lang): void {
  _currentLang = lang
  localStorage.setItem(STORAGE_KEY, lang)
}

export function t(key: string, params?: Record<string, string | number>): string {
  const dict = dictionaries[_currentLang] || dictionaries.zh
  let text = dict[key] ?? key
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      text = text.replace(`{${k}}`, String(v))
    }
  }
  return text
}
