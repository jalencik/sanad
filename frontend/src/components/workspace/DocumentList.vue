<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { FileText, Search } from '@lucide/vue'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Input } from '@/components/ui/input'
import StatusBadge from './StatusBadge.vue'
import { useDocumentsStore } from '@/stores/documents'
import { formatDate, formatDocumentType } from '@/lib/format'
import type { SupportedLocale } from '@/i18n'

const store = useDocumentsStore()
const { t, locale } = useI18n()
const query = ref('')

const filtered = computed(() => {
  const q = query.value.trim().toLowerCase()
  if (!q) return store.documents
  return store.documents.filter((doc) => doc.original_filename.toLowerCase().includes(q))
})

function select(id: string) {
  store.selectDocument(id)
}
</script>

<template>
  <div class="flex min-h-0 flex-1 flex-col">
    <div class="px-4 pb-3">
      <div class="relative">
        <Search class="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
        <Input v-model="query" :placeholder="t('workspace.list.searchPlaceholder')" class="pl-8" />
      </div>
    </div>

    <ScrollArea class="flex-1 border-t border-border">
      <div v-if="filtered.length === 0" class="px-4 py-10 text-center text-sm text-muted-foreground">
        {{ store.documents.length === 0 ? t('workspace.list.empty') : t('workspace.list.noMatches') }}
      </div>

      <button
        v-for="doc in filtered"
        :key="doc.id"
        type="button"
        class="relative flex w-full items-start gap-3 overflow-hidden border-b border-border px-4 py-3 text-left transition-colors hover:bg-muted"
        :class="{ 'bg-muted': doc.id === store.selectedId }"
        @click="select(doc.id)"
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
            <StatusBadge :status="doc.status" :progress-percent="doc.progress_percent" />
          </span>
          <span class="mt-0.5 block text-xs text-muted-foreground">
            {{ formatDate(doc.created_at, locale as SupportedLocale) }}
          </span>
        </span>

        <span
          v-if="doc.status === 'processing'"
          class="absolute inset-x-0 bottom-0 h-0.5 bg-warning/15"
          aria-hidden="true"
        >
          <span
            class="block h-full bg-warning transition-[width] duration-500 ease-out"
            :style="{ width: `${doc.progress_percent}%` }"
          />
        </span>
      </button>
    </ScrollArea>
  </div>
</template>
