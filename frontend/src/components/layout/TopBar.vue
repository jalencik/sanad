<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { RouterLink, useRouter } from 'vue-router'
import { Check, FileText, Globe, LogOut, Moon, Sun } from '@lucide/vue'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { useTheme } from '@/lib/theme'
import { LOCALE_LABELS, SUPPORTED_LOCALES, setLocale, type SupportedLocale } from '@/i18n'
import { useAuthStore } from '@/stores/auth'

defineProps<{
  showWorkspaceLink?: boolean
}>()

const { t, locale } = useI18n()
const { theme, toggle } = useTheme()
const authStore = useAuthStore()
const router = useRouter()

const initials = computed(() => {
  const name = authStore.user?.full_name ?? ''
  return name
    .split(' ')
    .map((part) => part.charAt(0))
    .slice(0, 2)
    .join('')
    .toUpperCase()
})

async function onSignOut() {
  await authStore.logout()
  router.push('/')
}
</script>

<template>
  <header class="border-b border-border">
    <div class="mx-auto flex h-16 max-w-[1600px] items-center justify-between px-6">
      <RouterLink to="/" class="flex items-center gap-2.5">
        <span class="flex h-8 w-8 items-center justify-center rounded-md bg-primary text-primary-foreground">
          <FileText class="h-4 w-4" />
        </span>
        <span class="font-display text-lg leading-none text-foreground">Sanad</span>
      </RouterLink>

      <nav class="flex items-center gap-2">
        <DropdownMenu>
          <DropdownMenuTrigger as-child>
            <Button variant="ghost" size="icon" :aria-label="t('nav.language')">
              <Globe class="h-4 w-4" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuLabel>{{ t('nav.language') }}</DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem
              v-for="code in SUPPORTED_LOCALES"
              :key="code"
              @click="setLocale(code as SupportedLocale)"
            >
              <Check v-if="locale === code" class="h-3.5 w-3.5" />
              <span v-else class="w-3.5" />
              {{ LOCALE_LABELS[code] }}
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>

        <Button
          variant="ghost"
          size="icon"
          :aria-label="theme === 'light' ? t('nav.switchToDark') : t('nav.switchToLight')"
          @click="toggle"
        >
          <Sun v-if="theme === 'dark'" class="h-4 w-4" />
          <Moon v-else class="h-4 w-4" />
        </Button>

        <template v-if="authStore.isAuthenticated">
          <Button v-if="showWorkspaceLink" as-child>
            <RouterLink to="/app">{{ t('nav.openWorkspace') }}</RouterLink>
          </Button>
          <DropdownMenu>
            <DropdownMenuTrigger as-child>
              <Button variant="outline" size="icon" class="rounded-full">
                <span class="text-xs font-medium">{{ initials }}</span>
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuLabel class="font-normal">
                <p class="truncate text-sm font-medium text-foreground">{{ authStore.user?.full_name }}</p>
                <p class="truncate text-xs text-muted-foreground">{{ authStore.user?.email }}</p>
              </DropdownMenuLabel>
              <DropdownMenuSeparator />
              <DropdownMenuItem @click="onSignOut">
                <LogOut class="h-3.5 w-3.5" />
                {{ t('nav.signOut') }}
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </template>
        <template v-else>
          <Button variant="ghost" as-child>
            <RouterLink to="/sign-in">{{ t('nav.signIn') }}</RouterLink>
          </Button>
          <Button as-child>
            <RouterLink to="/sign-up">{{ t('nav.signUp') }}</RouterLink>
          </Button>
        </template>
      </nav>
    </div>
  </header>
</template>
