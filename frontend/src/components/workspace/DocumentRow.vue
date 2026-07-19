<script setup lang="ts">
import { computed, toRef } from 'vue'
import { useI18n } from 'vue-i18n'
import { FileText } from '@lucide/vue'
import StatusBadge from './StatusBadge.vue'
import { useProcessingEta } from '@/lib/useProcessingEta'
import { formatDate, formatDocumentType } from '@/lib/format'
import type { DocumentSummary } from '@/lib/types'
import type { SupportedLocale } from '@/i18n'

const props = defineProps<{ doc: DocumentSummary; selected: boolean }>()
defineEmits<{ select: [] }>()

const { t, locale } = useI18n()

const isActive = computed(() => props.doc.status === 'pending' || props.doc.status === 'processing')
const { displayedProgress } = useProcessingEta({
  progressPercent: toRef(() => props.doc.progress_percent),
  active: toRef(() => isActive.value),
  processingStartedAt: toRef(() => props.doc.processing_started_at),
  estimatedCompletionAt: toRef(() => props.doc.estimated_completion_at),
})
</script>

<template>
  <button
    type="button"
    class="relative flex w-full items-start gap-3 overflow-hidden border-b border-border px-4 py-3 text-left transition-colors hover:bg-muted"
    :class="{ 'bg-muted': selected }"
    @click="$emit('select')"
  >
    <span class="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-secondary text-secondary-foreground">
      <FileText class="h-4 w-4" />
    </span>
    <span class="min-w-0 flex-1">
      <span class="flex items-center justify-between gap-2">
        <span class="truncate text-sm font-medium text-foreground">{{ doc.original_filename }}</span>
      </span>
      <span class="mt-0.5 flex items-center justify-between gap-2">
        <span class="truncate text-xs text-muted-foreground">
          {{ formatDocumentType(doc.document_type, t('workspace.details.unclassified')) }}
        </span>
        <StatusBadge :status="doc.status" :progress-percent="Math.round(displayedProgress)" />
      </span>
      <span class="mt-0.5 block text-xs text-muted-foreground">
        {{ formatDate(doc.created_at, locale as SupportedLocale) }}
      </span>
    </span>

    <span v-if="isActive" class="absolute inset-x-0 bottom-0 h-0.5 bg-accent/15" aria-hidden="true">
      <span class="block h-full bg-accent" :style="{ width: `${displayedProgress}%` }" />
    </span>
  </button>
</template>
