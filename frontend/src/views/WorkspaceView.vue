<script setup lang="ts">
import { computed, onMounted, onUnmounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import { ChevronLeft } from '@lucide/vue'
import TopBar from '@/components/layout/TopBar.vue'
import UploadDropzone from '@/components/workspace/UploadDropzone.vue'
import DocumentList from '@/components/workspace/DocumentList.vue'
import DocumentDetails from '@/components/workspace/DocumentDetails.vue'
import SummaryPanel from '@/components/workspace/SummaryPanel.vue'
import { Separator } from '@/components/ui/separator'
import { useDocumentsStore } from '@/stores/documents'

const store = useDocumentsStore()
const route = useRoute()
const router = useRouter()
const { t } = useI18n()

const routeId = computed(() => (route.params.id as string | undefined) || null)
const hasSelection = computed(() => routeId.value !== null)

// The URL is the single source of truth for what's open; the store follows it.
// Driving it the other way round is what forces apps into intercepting the
// hardware back button, and that's the thing mobile users complain about most.
// The equality guard matters: uploadFile() selects the new document itself
// before we navigate, so without it every upload would refetch immediately.
watch(
  routeId,
  (id) => {
    if (id === null) {
      store.clearSelection()
    } else if (store.selectedId !== id) {
      store.selectDocument(id)
    }
  },
  { immediate: true },
)

function backToList() {
  // Reuse the existing history entry when the list is genuinely the previous
  // page, so back-then-forward behaves. On a deep link (shared URL, reload on
  // a document) there's nothing to go back to, so push instead of stranding
  // the user or bouncing them out of the app entirely.
  if (router.options.history.state.back === '/app') {
    router.back()
  } else {
    router.push({ name: 'workspace' })
  }
}

onMounted(() => {
  store.fetchDocuments()
})

onUnmounted(() => {
  store.stopPolling()
})
</script>

<template>
  <!-- dvh, not vh: mobile browsers report 100vh as the height *without* the
       address bar, so a vh-sized app column always hides its last rows behind
       the browser chrome. -->
  <div class="flex h-dvh flex-col">
    <TopBar />

    <div class="flex min-h-0 flex-1 flex-col md:flex-row">
      <!-- Upload + browse. Below md this is the entire screen until a document
           is opened; from md up it's the permanent left pane. -->
      <section
        class="min-h-0 flex-1 flex-col border-border md:w-[42%] md:max-w-md md:border-r"
        :class="hasSelection ? 'hidden md:flex' : 'flex'"
      >
        <UploadDropzone />
        <Separator />
        <DocumentList />
      </section>

      <!-- Details + summary. Below md the section itself scrolls and the two
           children are plain stacked blocks, so a document reads as one
           continuous page. From md up the section stops scrolling and hands
           each child its own sized, independently scrolling pane - the
           original desktop behaviour, unchanged. -->
      <section
        class="min-h-0 flex-1 overflow-y-auto md:flex-col md:overflow-hidden"
        :class="hasSelection ? 'block md:flex' : 'hidden md:flex'"
      >
        <div
          v-if="hasSelection"
          class="sticky top-0 z-10 border-b border-border bg-background/95 px-2 py-1.5 backdrop-blur md:hidden"
        >
          <button
            type="button"
            class="inline-flex h-11 items-center gap-1 rounded-lg px-3 text-sm font-medium text-foreground transition-colors hover:bg-muted"
            @click="backToList"
          >
            <ChevronLeft class="h-4 w-4" />
            {{ t('workspace.details.backToList') }}
          </button>
        </div>

        <div class="md:min-h-0 md:flex-[1.1] md:overflow-y-auto md:border-b md:border-border">
          <DocumentDetails />
        </div>
        <div class="pb-safe md:min-h-0 md:flex-1 md:overflow-y-auto md:pb-0">
          <SummaryPanel />
        </div>
      </section>
    </div>
  </div>
</template>
