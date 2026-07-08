import { createI18n } from 'vue-i18n'
import en from './locales/en'
import uz from './locales/uz'
import ru from './locales/ru'

export type MessageSchema = typeof en

const STORAGE_KEY = 'sanad-locale'
export const SUPPORTED_LOCALES = ['en', 'uz', 'ru'] as const
export type SupportedLocale = (typeof SUPPORTED_LOCALES)[number]

export const LOCALE_LABELS: Record<SupportedLocale, string> = {
  en: 'English',
  uz: "O'zbekcha",
  ru: 'Русский',
}

function isSupportedLocale(value: string): value is SupportedLocale {
  return (SUPPORTED_LOCALES as readonly string[]).includes(value)
}

function detectInitialLocale(): SupportedLocale {
  const stored = localStorage.getItem(STORAGE_KEY)
  if (stored && isSupportedLocale(stored)) return stored

  const browserLang = navigator.language.slice(0, 2)
  if (isSupportedLocale(browserLang)) return browserLang

  return 'en'
}

export const i18n = createI18n<[MessageSchema], SupportedLocale, false>({
  legacy: false,
  locale: detectInitialLocale(),
  fallbackLocale: 'en',
  messages: { en, uz, ru },
})

export function setLocale(locale: SupportedLocale): void {
  i18n.global.locale.value = locale
  localStorage.setItem(STORAGE_KEY, locale)
  document.documentElement.lang = locale
}

document.documentElement.lang = i18n.global.locale.value
