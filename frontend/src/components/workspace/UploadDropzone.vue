<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { CloudUpload } from '@lucide/vue'
import { toast } from 'vue-sonner'
import { useDocumentsStore } from '@/stores/documents'

const store = useDocumentsStore()
const { t } = useI18n()
const isDragging = ref(false)
const fileInput = ref<HTMLInputElement | null>(null)

const ACCEPTED_TYPES = ['application/pdf', 'image/png', 'image/jpeg', 'image/tiff', 'image/webp']

async function handleFiles(files: FileList | null) {
  if (!files || files.length === 0) return
  const file = files[0]

  if (!ACCEPTED_TYPES.includes(file.type)) {
    toast.error(t('workspace.upload.unsupportedTitle'), {
      description: t('workspace.upload.unsupportedBody'),
    })
    return
  }

  try {
    await store.uploadFile(file)
    toast.success(t('workspace.upload.successTitle'), {
      description: t('workspace.upload.successBody', { name: file.name }),
    })
  } catch {
    toast.error(t('workspace.upload.failureTitle'), {
      description: t('workspace.upload.failureBody'),
    })
  }
}

function onDrop(event: DragEvent) {
  isDragging.value = false
  handleFiles(event.dataTransfer?.files ?? null)
}

function onBrowseClick() {
  fileInput.value?.click()
}

function onFileInputChange(event: Event) {
  const target = event.target as HTMLInputElement
  handleFiles(target.files)
  target.value = ''
}
</script>

<template>
  <div class="p-4">
    <div
      class="flex flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed px-4 py-8 text-center transition-colors"
      :class="isDragging ? 'border-accent bg-accent/10' : 'border-border'"
      @dragover.prevent="isDragging = true"
      @dragleave.prevent="isDragging = false"
      @drop.prevent="onDrop"
    >
      <CloudUpload class="h-6 w-6 text-muted-foreground" />
      <p class="text-sm text-foreground">
        {{ t('workspace.upload.dragHint') }}
        <button
          type="button"
          class="font-medium text-primary underline underline-offset-2"
          @click="onBrowseClick"
        >
          {{ t('workspace.upload.browseLink') }}
        </button>
      </p>
      <p class="text-xs text-muted-foreground">{{ t('workspace.upload.fileHint') }}</p>
    </div>
    <input
      ref="fileInput"
      type="file"
      class="hidden"
      accept="application/pdf,image/png,image/jpeg,image/tiff,image/webp"
      @change="onFileInputChange"
    />
  </div>
</template>
