<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { Camera, CloudUpload, FolderOpen } from '@lucide/vue'
import { useRouter } from 'vue-router'
import { toast } from 'vue-sonner'
import { useDocumentsStore } from '@/stores/documents'

const store = useDocumentsStore()
const router = useRouter()
const { t } = useI18n()
const isDragging = ref(false)
const fileInput = ref<HTMLInputElement | null>(null)
const cameraInput = ref<HTMLInputElement | null>(null)

const ACCEPTED_TYPES = ['application/pdf', 'image/png', 'image/jpeg', 'image/tiff', 'image/webp']
const ACCEPT_ATTR = 'application/pdf,image/png,image/jpeg,image/tiff,image/webp'

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
    const created = await store.uploadFile(file)
    toast.success(t('workspace.upload.successTitle'), {
      description: t('workspace.upload.successBody', { name: file.name }),
    })
    // Take the user straight to the document they just uploaded. On mobile
    // that's the difference between landing on the processing view and being
    // left on the list wondering whether anything happened.
    if (created) router.push({ name: 'workspace', params: { id: created.id } })
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

function onCameraClick() {
  cameraInput.value?.click()
}

function onFileInputChange(event: Event) {
  const target = event.target as HTMLInputElement
  handleFiles(target.files)
  target.value = ''
}
</script>

<template>
  <div class="p-4">
    <!--
      Below md: two explicit actions. Drag-and-drop is a gesture phones don't
      have, so the desktop zone reduces to a small tap target on the exact
      devices where targets need to be biggest. The camera path matters most
      here - on a phone the camera *is* the scanner, so shooting a document
      beats transferring one onto the phone first.
    -->
    <div class="flex flex-col gap-2 md:hidden">
      <button
        type="button"
        class="inline-flex h-12 w-full items-center justify-center gap-2 rounded-lg bg-primary px-4 text-sm font-medium text-primary-foreground transition-colors active:bg-primary/90"
        @click="onCameraClick"
      >
        <Camera class="h-4 w-4" />
        {{ t('workspace.upload.takePhoto') }}
      </button>
      <button
        type="button"
        class="inline-flex h-12 w-full items-center justify-center gap-2 rounded-lg border border-border bg-background px-4 text-sm font-medium text-foreground transition-colors active:bg-muted"
        @click="onBrowseClick"
      >
        <FolderOpen class="h-4 w-4" />
        {{ t('workspace.upload.chooseFile') }}
      </button>
      <p class="text-center text-xs text-muted-foreground">{{ t('workspace.upload.fileHint') }}</p>
    </div>

    <!-- md and up: the original drag-and-drop zone, unchanged. -->
    <div
      class="hidden flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed px-4 py-8 text-center transition-colors md:flex"
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
      :accept="ACCEPT_ATTR"
      @change="onFileInputChange"
    />
    <!--
      A second, separate input purely because `capture` is an attribute of the
      element, not of the click: putting it on the shared input would force the
      camera for "choose file" too, cutting off Files/Drive/Photos. Narrowed to
      image/* since capture only ever yields a photo.
    -->
    <input
      ref="cameraInput"
      type="file"
      class="hidden"
      accept="image/*"
      capture="environment"
      @change="onFileInputChange"
    />
  </div>
</template>
