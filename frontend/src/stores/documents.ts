import { defineStore } from 'pinia'
import * as api from '@/lib/api'
import type { DocumentDetail, DocumentSummary } from '@/lib/types'

const ACTIVE_POLL_MS = 2000

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
      } catch (error) {
        console.error('Failed to load documents', error)
      } finally {
        this.isLoadingList = false
      }
    },

    async selectDocument(id: string) {
      this.selectedId = id
      try {
        this.selectedDetail = await api.getDocument(id)
        this.maybeStartPolling()
      } catch (error) {
        console.error('Failed to load document', error)
        this.selectedDetail = null
      }
    },

    clearSelection() {
      this.stopPolling()
      this.selectedId = null
      this.selectedDetail = null
    },

    async uploadFile(file: File) {
      this.isUploading = true
      try {
        const created = await api.uploadDocument(file)
        this.documents.unshift(created)
        await this.selectDocument(created.id)
      } finally {
        this.isUploading = false
      }
    },

    async removeDocument(id: string) {
      await api.deleteDocument(id)
      this.documents = this.documents.filter((doc) => doc.id !== id)
      if (this.selectedId === id) {
        this.clearSelection()
      }
    },

    maybeStartPolling() {
      this.stopPolling()
      if (!this.selectedId) return
      if (this.selectedDetail?.status !== 'pending' && this.selectedDetail?.status !== 'processing') {
        return
      }
      this.pollHandle = setInterval(async () => {
        if (!this.selectedId) return
        try {
          const detail = await api.getDocument(this.selectedId)
          this.selectedDetail = detail
          const idx = this.documents.findIndex((doc) => doc.id === detail.id)
          if (idx !== -1) this.documents[idx] = detail
          if (detail.status === 'done' || detail.status === 'error') {
            this.stopPolling()
          }
        } catch (error) {
          console.error('Failed to poll document status', error)
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
