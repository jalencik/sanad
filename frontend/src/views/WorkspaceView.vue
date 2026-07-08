<script setup lang="ts">
import { onMounted, onUnmounted } from 'vue'
import TopBar from '@/components/layout/TopBar.vue'
import UploadDropzone from '@/components/workspace/UploadDropzone.vue'
import DocumentList from '@/components/workspace/DocumentList.vue'
import DocumentDetails from '@/components/workspace/DocumentDetails.vue'
import SummaryPanel from '@/components/workspace/SummaryPanel.vue'
import { Separator } from '@/components/ui/separator'
import { useDocumentsStore } from '@/stores/documents'

const store = useDocumentsStore()

onMounted(() => {
  store.fetchDocuments()
})

onUnmounted(() => {
  store.stopPolling()
})
</script>

<template>
  <div class="flex h-screen flex-col">
    <TopBar />

    <div class="flex min-h-0 flex-1 flex-col md:flex-row">
      <!-- Left: upload + browse -->
      <section class="flex min-h-0 flex-1 flex-col border-border md:w-[42%] md:max-w-md md:border-r">
        <UploadDropzone />
        <Separator />
        <DocumentList />
      </section>

      <!-- Right: details (upper) + AI summary (lower) -->
      <section class="flex min-h-0 flex-1 flex-col">
        <div class="min-h-0 flex-[1.1] overflow-y-auto border-b border-border">
          <DocumentDetails />
        </div>
        <div class="min-h-0 flex-1 overflow-y-auto">
          <SummaryPanel />
        </div>
      </section>
    </div>
  </div>
</template>
