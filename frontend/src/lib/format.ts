import type { SupportedLocale } from '@/i18n'

const INTL_LOCALES: Record<SupportedLocale, string> = {
  en: 'en-US',
  uz: 'uz-Latn-UZ',
  ru: 'ru-RU',
}

export function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  const units = ['KB', 'MB', 'GB']
  let value = bytes / 1024
  let unitIndex = 0
  while (value >= 1024 && unitIndex < units.length - 1) {
    value /= 1024
    unitIndex += 1
  }
  return `${value.toFixed(1)} ${units[unitIndex]}`
}

export function formatDate(iso: string, locale: SupportedLocale): string {
  return new Date(iso).toLocaleString(INTL_LOCALES[locale], {
    dateStyle: 'medium',
    timeStyle: 'short',
  })
}

export function formatDocumentType(type: string | null, unclassifiedLabel: string): string {
  if (!type) return unclassifiedLabel
  return type
    .split('_')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ')
}
