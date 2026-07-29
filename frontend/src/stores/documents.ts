import { defineStore } from 'pinia'
import * as api from '@/lib/api'
import type { DocumentDetail, DocumentSummary } from '@/lib/types'

const ACTIVE_POLL_MS = 2000

function isActive(doc: { status: string } | null | undefined): boolean {
  return doc?.status === 'pending' || doc?.status === 'processing'
}

export const useDocumentsStore = defineStore('documents', {
  state: () => ({
    documents: [] as DocumentSummary[],
    selectedId: null as string | null,
    selectedDetail: null as DocumentDetail | null,
    isLoadingList: false,
    isUploading: false,
    pollHandle: null as ReturnType<typeof setInterval> | null,
  }),

  actions: {
    async fetchDocuments() {
      this.isLoadingList = true
      try {
        this.documents = await api.listDocuments()
        this.maybeStartPolling()
      } catch (error) {
        console.error('Failed to load documents', error)
      } finally {
        this.isLoadingList = false
      }
    },

    async selectDocument(id: string) {
      this.selectedId = id
      try {
        const detail = await api.getDocument(id)
        this.selectedDetail = detail
        this.syncListEntry(detail)
      } catch (error) {
        console.error('Failed to load document', error)
        this.selectedDetail = null
      }
    },

    clearSelection() {
      this.selectedId = null
      this.selectedDetail = null
    },

    async uploadFile(file: File) {
      this.isUploading = true
      try {
        const created = await api.uploadDocument(file)
        this.documents.unshift(created)
        this.maybeStartPolling()
        await this.selectDocument(created.id)
      } finally {
        this.isUploading = false
      }
    },

    async cancelDocument(id: string) {
      const updated = await api.cancelDocument(id)
      const idx = this.documents.findIndex((doc) => doc.id === id)
      if (idx !== -1) this.documents[idx] = updated
      if (this.selectedId === id) this.selectedDetail = updated
    },

    async removeDocument(id: string) {
      await api.deleteDocument(id)
      this.documents = this.documents.filter((doc) => doc.id !== id)
      if (this.selectedId === id) {
        this.clearSelection()
      }
    },

    syncListEntry(detail: DocumentDetail) {
      const idx = this.documents.findIndex((doc) => doc.id === detail.id)
      if (idx !== -1) this.documents[idx] = detail
    },

    // Polls the WHOLE list, not just whichever document happens to be
    // selected - otherwise a document that isn't currently open keeps
    // showing its stale "Queued"/"Analyzing" row forever once it actually
    // finishes, since nothing was ever re-fetching it.
    maybeStartPolling() {
      if (this.pollHandle) return
      if (!this.documents.some(isActive)) return

      this.pollHandle = setInterval(async () => {
        try {
          const fresh = await api.listDocuments()
          this.documents = fresh

          if (this.selectedId) {
            const current = fresh.find((doc) => doc.id === this.selectedId)
            if (current) {
              if (current.status !== this.selectedDetail?.status || !isActive(current)) {
                this.selectedDetail = await api.getDocument(this.selectedId)
              } else if (this.selectedDetail) {
                // Same status, still processing - the list poll we just did
                // already carries the fields that change during processing
                // (progress, ETA), so sync those in instead of firing a
                // second request every 2s just to keep them fresh.
                this.selectedDetail = {
                  ...this.selectedDetail,
                  progress_percent: current.progress_percent,
                  processing_started_at: current.processing_started_at,
                  estimated_completion_at: current.estimated_completion_at,
                }
              }
            }
          }

          if (!fresh.some(isActive)) this.stopPolling()
        } catch (error) {
          console.error('Failed to poll document list', error)
          this.stopPolling()
        }
      }, ACTIVE_POLL_MS)
    },

    stopPolling() {
      if (this.pollHandle) {
        clearInterval(this.pollHandle)
        this.pollHandle = null
      }
    },
  },
})
