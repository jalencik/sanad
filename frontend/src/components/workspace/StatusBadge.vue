<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { CircleCheck, CircleX, Clock, LoaderCircle } from '@lucide/vue'
import type { DocumentStatus } from '@/lib/types'

const props = defineProps<{ status: DocumentStatus; progressPercent?: number }>()
const { t } = useI18n()

const config = computed(() => {
  switch (props.status) {
    case 'pending':
      return { label: t('workspace.status.pending'), icon: Clock, class: 'text-muted-foreground', spin: false }
    case 'processing':
      return { label: t('workspace.status.processing'), icon: LoaderCircle, class: 'text-warning', spin: true }
    case 'done':
      return { label: t('workspace.status.done'), icon: CircleCheck, class: 'text-success', spin: false }
    case 'error':
      return { label: t('workspace.status.error'), icon: CircleX, class: 'text-destructive', spin: false }
  }
})
</script>

<template>
  <span class="inline-flex items-center gap-1 text-xs font-medium tabular-nums" :class="config.class">
    <component :is="config.icon" class="h-3 w-3" :class="{ 'animate-spin': config.spin }" />
    {{ config.label }}
    <span v-if="status === 'processing' && progressPercent !== undefined" class="text-[11px] opacity-80">
      {{ progressPercent }}%
    </span>
  </span>
</template>
