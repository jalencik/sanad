<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { Sparkles } from '@lucide/vue'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { useDocumentsStore } from '@/stores/documents'

const store = useDocumentsStore()
const { t } = useI18n()
const doc = computed(() => store.selectedDetail)
</script>

<template>
  <div class="p-4 md:p-5">
    <div class="mb-3 flex items-center gap-2">
      <Sparkles class="h-4 w-4 text-accent" />
      <h3 class="text-sm font-medium text-foreground">{{ t('workspace.summary.title') }}</h3>
    </div>

    <div v-if="!doc" class="py-6 text-sm text-muted-foreground">
      {{ t('workspace.summary.emptyState') }}
    </div>

    <div v-else-if="doc.status === 'pending' || doc.status === 'processing'" class="py-6 text-sm text-muted-foreground">
      {{ t('workspace.summary.waiting') }}
    </div>

    <div v-else-if="doc.status === 'error'" class="py-6 text-sm text-muted-foreground">
      {{ t('workspace.summary.errorState') }}
    </div>

    <Tabs v-else default-value="original" class="w-full">
      <!-- Switching between the original-language and English summary is the
           main thing anyone does on this panel, so the triggers get a real
           touch target on phones and revert to the compact default from md. -->
      <!-- The list's height ships as `group-data-horizontal/tabs:h-8`, and a
           plain `h-auto` can't override a variant-prefixed class - it has to
           be countered at the same prefix, or the 32px container clips its own
           44px triggers. -->
      <TabsList class="group-data-horizontal/tabs:h-auto md:group-data-horizontal/tabs:h-8">
        <TabsTrigger value="original" class="h-11 md:h-auto">
          {{ t('workspace.summary.originalTab') }}
        </TabsTrigger>
        <TabsTrigger value="english" class="h-11 md:h-auto">
          {{ t('workspace.summary.englishTab') }}
        </TabsTrigger>
      </TabsList>
      <TabsContent value="original" class="mt-3 text-sm leading-relaxed text-foreground">
        {{ doc.summary_original || t('workspace.summary.noOriginal') }}
      </TabsContent>
      <TabsContent value="english" class="mt-3 text-sm leading-relaxed text-foreground">
        {{ doc.summary_english || t('workspace.summary.noEnglish') }}
      </TabsContent>
    </Tabs>
  </div>
</template>
