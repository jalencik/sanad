<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { ShieldCheck } from '@lucide/vue'
import TopBar from '@/components/layout/TopBar.vue'
import { Badge } from '@/components/ui/badge'
import { adminApi } from '@/lib/api'
import { formatDate } from '@/lib/format'
import type { AdminUserSummary } from '@/lib/types'
import type { SupportedLocale } from '@/i18n'

const { t, locale } = useI18n()
const users = ref<AdminUserSummary[]>([])
const isLoading = ref(true)
const errorMessage = ref('')

onMounted(async () => {
  try {
    users.value = await adminApi.listUsers()
  } catch {
    errorMessage.value = t('admin.loadError')
  } finally {
    isLoading.value = false
  }
})
</script>

<template>
  <div class="flex h-dvh flex-col">
    <TopBar />

    <div class="px-safe pb-safe mx-auto w-full max-w-[1600px] flex-1 overflow-y-auto px-4 py-6 md:px-6 md:py-8">
      <div class="mb-6 flex items-center gap-2.5">
        <span class="flex h-9 w-9 items-center justify-center rounded-md bg-primary text-primary-foreground">
          <ShieldCheck class="h-4.5 w-4.5" />
        </span>
        <div>
          <h1 class="font-display text-xl leading-tight text-foreground">{{ t('admin.title') }}</h1>
          <p class="text-sm text-muted-foreground">{{ t('admin.subtitle', { count: users.length }) }}</p>
        </div>
      </div>

      <div v-if="isLoading" class="py-10 text-center text-sm text-muted-foreground">
        {{ t('admin.loading') }}
      </div>
      <div v-else-if="errorMessage" class="py-10 text-center text-sm text-destructive">
        {{ errorMessage }}
      </div>
      <!--
        Below md the table becomes cards. A 6-column table can only survive a
        375px screen by scrolling sideways, and a horizontally scrolling table
        inside a vertically scrolling page is a genuinely bad thing to hand
        someone on a phone - you lose the header labels the moment you scroll.
        Each card repeats its own labels, so no column needs remembering.
      -->
      <ul v-else class="flex flex-col gap-3 md:hidden">
        <li v-for="user in users" :key="user.id" class="rounded-lg border border-border p-4">
          <div class="flex items-start justify-between gap-3">
            <div class="min-w-0">
              <p class="break-words font-medium text-foreground">{{ user.full_name }}</p>
              <p class="break-words text-xs text-muted-foreground">{{ user.email }}</p>
            </div>
            <Badge v-if="user.is_admin" variant="secondary" class="shrink-0">
              {{ t('admin.columns.admin') }}
            </Badge>
          </div>

          <dl class="mt-3 grid grid-cols-3 gap-2 border-t border-border pt-3 text-sm">
            <div>
              <dt class="text-xs text-muted-foreground">{{ t('admin.columns.documents') }}</dt>
              <dd class="tabular-nums text-foreground">{{ user.document_count }}</dd>
            </div>
            <div>
              <dt class="text-xs text-muted-foreground">{{ t('admin.columns.done') }}</dt>
              <dd class="tabular-nums text-success">{{ user.done_count }}</dd>
            </div>
            <div>
              <dt class="text-xs text-muted-foreground">{{ t('admin.columns.errors') }}</dt>
              <dd class="tabular-nums text-destructive">{{ user.error_count }}</dd>
            </div>
          </dl>

          <p class="mt-3 text-xs text-muted-foreground">
            {{ t('admin.columns.joined') }} · {{ formatDate(user.created_at, locale as SupportedLocale) }}
          </p>
        </li>
      </ul>

      <div v-if="!isLoading && !errorMessage" class="hidden overflow-x-auto rounded-lg border border-border md:block">
        <table class="w-full min-w-[720px] text-left text-sm">
          <thead>
            <tr class="border-b border-border bg-muted/50 text-xs uppercase tracking-wide text-muted-foreground">
              <th class="px-4 py-3 font-medium">{{ t('admin.columns.user') }}</th>
              <th class="px-4 py-3 font-medium">{{ t('admin.columns.joined') }}</th>
              <th class="px-4 py-3 font-medium">{{ t('admin.columns.documents') }}</th>
              <th class="px-4 py-3 font-medium">{{ t('admin.columns.done') }}</th>
              <th class="px-4 py-3 font-medium">{{ t('admin.columns.errors') }}</th>
              <th class="px-4 py-3 font-medium">{{ t('admin.columns.role') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="user in users" :key="user.id" class="border-b border-border last:border-0 hover:bg-muted/40">
              <td class="px-4 py-3">
                <p class="font-medium text-foreground">{{ user.full_name }}</p>
                <p class="text-xs text-muted-foreground">{{ user.email }}</p>
              </td>
              <td class="px-4 py-3 text-muted-foreground">{{ formatDate(user.created_at, locale as SupportedLocale) }}</td>
              <td class="px-4 py-3 text-foreground">{{ user.document_count }}</td>
              <td class="px-4 py-3 text-success">{{ user.done_count }}</td>
              <td class="px-4 py-3 text-destructive">{{ user.error_count }}</td>
              <td class="px-4 py-3">
                <Badge v-if="user.is_admin" variant="secondary">{{ t('admin.columns.admin') }}</Badge>
                <span v-else class="text-xs text-muted-foreground">{{ t('admin.columns.member') }}</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>
