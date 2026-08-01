<script setup lang="ts">
import { computed, ref, toRef } from 'vue'
import { useI18n } from 'vue-i18n'
import { ExternalLink, FileX, LoaderCircle, X } from '@lucide/vue'
import { Progress } from '@/components/ui/progress'
import { useDocumentsStore } from '@/stores/documents'
import { documentFileUrl } from '@/lib/api'
import { CANCELLED_MESSAGE } from '@/lib/types'
import { formatCountdown, formatDate, formatDocumentType, formatFileSize } from '@/lib/format'
import { useProcessingEta } from '@/lib/useProcessingEta'
import type { SupportedLocale } from '@/i18n'

const store = useDocumentsStore()
const { t, locale } = useI18n()

const doc = computed(() => store.selectedDetail)
const isActive = computed(() => doc.value?.status === 'pending' || doc.value?.status === 'processing')
const isCancelled = computed(() => doc.value?.status === 'error' && doc.value.error_message === CANCELLED_MESSAGE)
const { displayedProgress, secondsRemaining } = useProcessingEta({
  progressPercent: toRef(() => doc.value?.progress_percent ?? 0),
  active: toRef(() => isActive.value),
  processingStartedAt: toRef(() => doc.value?.processing_started_at),
  estimatedCompletionAt: toRef(() => doc.value?.estimated_completion_at),
})

const isCancelling = ref(false)

async function handleCancel() {
  const id = doc.value?.id
  if (!id || isCancelling.value) return
  isCancelling.value = true
  try {
    await store.cancelDocument(id)
  } catch (error) {
    console.error('Failed to cancel document', error)
  } finally {
    isCancelling.value = false
  }
}

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
  <div class="p-4 md:p-5">
    <div v-if="!doc" class="flex h-full items-center justify-center py-10 text-sm text-muted-foreground">
      {{ t('workspace.details.emptyState') }}
    </div>

    <div v-else-if="isActive" class="flex flex-col gap-1 py-6 text-center">
      <div class="flex justify-start">
        <button
          type="button"
          class="inline-flex h-11 items-center gap-1.5 rounded-lg px-3 text-sm font-medium text-muted-foreground transition-colors hover:bg-destructive/10 hover:text-destructive disabled:pointer-events-none disabled:opacity-50 md:h-auto md:gap-1 md:rounded md:px-1.5 md:py-1 md:text-xs"
          :disabled="isCancelling"
          @click="handleCancel"
        >
          <X class="h-3.5 w-3.5" />
          {{ isCancelling ? t('workspace.details.cancelling') : t('workspace.details.cancelButton') }}
        </button>
      </div>
      <div class="flex flex-col items-center gap-3 py-4">
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
          <p v-if="secondsRemaining !== null" class="mt-0.5 text-xs tabular-nums text-muted-foreground">
            {{
              secondsRemaining > 0
                ? t('workspace.details.timeRemaining', { time: formatCountdown(secondsRemaining) })
                : t('workspace.details.almostDone')
            }}
          </p>
        </div>
      </div>
    </div>

    <div v-else-if="doc.status === 'error'" class="flex flex-col items-center gap-3 py-10 text-center">
      <FileX class="h-5 w-5 text-destructive" />
      <p class="text-sm text-foreground">{{ isCancelled ? t('workspace.details.cancelledTitle') : t('workspace.details.errorTitle') }}</p>
      <p v-if="!isCancelled" class="max-w-sm text-xs text-muted-foreground">{{ doc.error_message }}</p>
    </div>

    <div v-else class="space-y-4">
      <!-- Stacks below md so a long filename doesn't squeeze the action into a
           sliver; side by side from md up, exactly as before. -->
      <div class="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
        <div class="min-w-0">
          <h2 class="font-display text-xl text-foreground">
            {{ formatDocumentType(doc.document_type, t('workspace.details.unclassified')) }}
          </h2>
          <p class="break-words text-xs text-muted-foreground">
            {{ doc.original_filename }} · {{ formatFileSize(doc.file_size) }} · {{ formatDate(doc.created_at, locale as SupportedLocale) }}
          </p>
        </div>
        <!-- A real 44px button on touch; reverts to the original bare text
             link from md up so desktop is untouched. -->
        <a
          :href="documentFileUrl(doc.id)"
          target="_blank"
          rel="noopener"
          class="inline-flex h-11 shrink-0 items-center justify-center gap-1.5 rounded-lg border border-border px-4 text-sm font-medium text-primary transition-colors active:bg-muted md:h-auto md:gap-1 md:rounded-none md:border-0 md:px-0 md:text-xs md:hover:underline"
        >
          {{ t('workspace.details.viewOriginal') }}
          <ExternalLink class="h-3.5 w-3.5 md:h-3 md:w-3" />
        </a>
      </div>

      <!-- One column on phones: two columns of extracted values at 375px left
           every field truncated to the point of uselessness. break-words also
           replaces truncate, because a document number you can't finish
           reading is the one thing this screen exists to show you. -->
      <dl class="grid grid-cols-1 gap-x-6 gap-y-3 md:grid-cols-2">
        <div v-for="[label, value] in fields" :key="label" class="min-w-0">
          <dt class="text-xs capitalize text-muted-foreground">{{ label }}</dt>
          <dd class="break-words text-sm text-foreground">{{ value }}</dd>
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
