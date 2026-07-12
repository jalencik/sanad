<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { Search } from '@lucide/vue'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Input } from '@/components/ui/input'
import DocumentRow from './DocumentRow.vue'
import { useDocumentsStore } from '@/stores/documents'

const store = useDocumentsStore()
const { t } = useI18n()
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
      <!-- Skeleton rows while the first fetch is in flight, so the list never
           flashes "No documents yet" at someone who actually has documents. -->
      <div v-if="store.isLoadingList && store.documents.length === 0" aria-hidden="true">
        <div v-for="n in 3" :key="n" class="flex w-full animate-pulse items-start gap-3 border-b border-border px-4 py-3">
          <span class="mt-0.5 h-8 w-8 shrink-0 rounded-md bg-muted" />
          <span class="min-w-0 flex-1 space-y-2 py-0.5">
            <span class="block h-3.5 w-3/5 rounded bg-muted" />
            <span class="block h-3 w-2/5 rounded bg-muted" />
          </span>
        </div>
      </div>

      <div v-else-if="filtered.length === 0" class="px-4 py-10 text-center text-sm text-muted-foreground">
        {{ store.documents.length === 0 ? t('workspace.list.empty') : t('workspace.list.noMatches') }}
      </div>

      <DocumentRow
        v-for="doc in filtered"
        :key="doc.id"
        :doc="doc"
        :selected="doc.id === store.selectedId"
        @select="select(doc.id)"
      />
    </ScrollArea>
  </div>
</template>
