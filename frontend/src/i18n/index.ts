import { en } from './en'
import { zh } from './zh'

export const dictionaries = {
  zh,
  en,
}

export type DictionaryLanguage = keyof typeof dictionaries
