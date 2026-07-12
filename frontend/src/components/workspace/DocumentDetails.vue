<script setup lang="ts">
import { computed, toRef } from 'vue'
import { useI18n } from 'vue-i18n'
import { ExternalLink, FileX, LoaderCircle } from '@lucide/vue'
import { Progress } from '@/components/ui/progress'
import { useDocumentsStore } from '@/stores/documents'
import { documentFileUrl } from '@/lib/api'
import { formatDate, formatDocumentType, formatFileSize } from '@/lib/format'
import { useAnimatedProgress } from '@/lib/useAnimatedProgress'
import type { SupportedLocale } from '@/i18n'

const store = useDocumentsStore()
const { t, locale } = useI18n()

const doc = computed(() => store.selectedDetail)
const isActive = computed(() => doc.value?.status === 'pending' || doc.value?.status === 'processing')
const displayedProgress = useAnimatedProgress(
  toRef(() => doc.value?.progress_percent ?? 0),
  toRef(() => isActive.value),
)

const fields = computed(() => {
  if (!doc.value) return []
  const base: Array<[string, string | null]> = [
    [t('workspace.details.fields.documentNumber'), doc.value.document_number],
    [t('workspace.details.fields.issuingAuthority'), doc.value.issuing_authority],
    [t('workspace.details.fields.issueDate'), doc.value.issue_date],
    [t('workspace.details.fields.expiryDate'), doc.value.expiry_date],
    [t('workspace.details.fields.detectedLanguage'), doc.value.detected_language],
  ]
  const extra = Object.entries(doc.value.key_fields ?? {}).map(
    ([key, value]) => [key.replace(/_/g, ' '), value] as [string, string],
  )
  return [...base, ...extra].filter(([, value]) => value)
})
</script>

<template>
  <div class="p-5">
    <div v-if="!doc" class="flex h-full items-center justify-center py-10 text-sm text-muted-foreground">
      {{ t('workspace.details.emptyState') }}
    </div>

    <div v-else-if="isActive" class="flex flex-col items-center gap-3 py-10 text-center">
      <LoaderCircle class="h-5 w-5 animate-spin text-accent" />
      <p class="text-sm text-foreground">{{ t('workspace.details.analyzing') }}</p>
      <p class="text-xs text-muted-foreground">{{ t('workspace.details.analyzingHint') }}</p>
      <div class="mt-1 w-full max-w-[220px]">
        <div class="h-1.5 w-full overflow-hidden rounded-full bg-accent/15">
          <div
            class="h-full rounded-full bg-accent transition-[width] duration-300 ease-out"
            :style="{ width: `${displayedProgress}%` }"
          />
        </div>
        <p class="mt-1.5 text-xs font-medium tabular-nums text-accent">{{ Math.round(displayedProgress) }}%</p>
      </div>
    </div>

    <div v-else-if="doc.status === 'error'" class="flex flex-col items-center gap-3 py-10 text-center">
      <FileX class="h-5 w-5 text-destructive" />
      <p class="text-sm text-foreground">{{ t('workspace.details.errorTitle') }}</p>
      <p class="max-w-sm text-xs text-muted-foreground">{{ doc.error_message }}</p>
    </div>

    <div v-else class="space-y-4">
      <div class="flex items-start justify-between gap-3">
        <div>
          <h2 class="font-display text-xl text-foreground">
            {{ formatDocumentType(doc.document_type, t('workspace.details.unclassified')) }}
          </h2>
          <p class="text-xs text-muted-foreground">
            {{ doc.original_filename }} · {{ formatFileSize(doc.file_size) }} · {{ formatDate(doc.created_at, locale as SupportedLocale) }}
          </p>
        </div>
        <a
          :href="documentFileUrl(doc.id)"
          target="_blank"
          rel="noopener"
          class="flex shrink-0 items-center gap-1 text-xs font-medium text-primary hover:underline"
        >
          {{ t('workspace.details.viewOriginal') }}
          <ExternalLink class="h-3 w-3" />
        </a>
      </div>

      <dl class="grid grid-cols-2 gap-x-6 gap-y-3">
        <div v-for="[label, value] in fields" :key="label" class="min-w-0">
          <dt class="text-xs capitalize text-muted-foreground">{{ label }}</dt>
          <dd class="truncate text-sm text-foreground">{{ value }}</dd>
        </div>
      </dl>

      <div v-if="doc.ocr_confidence !== null" class="pt-1">
        <div class="mb-1.5 flex items-center justify-between text-xs text-muted-foreground">
          <span>{{ t('workspace.details.ocrConfidence') }}</span>
          <span>{{ Math.round(doc.ocr_confidence * 100) }}%</span>
        </div>
        <Progress :model-value="doc.ocr_confidence * 100" class="h-1.5" />
      </div>
    </div>
  </div>
</template>
