<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { RouterLink, useRouter } from 'vue-router'
import { Check, FileText, Globe, LogOut, Moon, ShieldCheck, Sun } from '@lucide/vue'
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
  <!-- pt-safe/px-safe: the bar paints under the notch, its contents don't. -->
  <header class="px-safe pt-safe border-b border-border">
    <div class="mx-auto flex h-14 max-w-[1600px] items-center justify-between px-3 md:h-16 md:px-6">
      <RouterLink to="/" class="flex h-11 items-center gap-2.5 md:h-auto">
        <span class="flex h-8 w-8 items-center justify-center rounded-md bg-primary text-primary-foreground">
          <FileText class="h-4 w-4" />
        </span>
        <span class="font-display text-lg leading-none text-foreground">Sanad</span>
      </RouterLink>

      <nav class="flex items-center gap-1 md:gap-2">
        <DropdownMenu>
          <DropdownMenuTrigger as-child>
            <!-- size-11 = 44px, the minimum comfortable touch target; desktop
                 keeps the original compact 32px icon button. -->
            <Button variant="ghost" size="icon" class="size-11 md:size-8" :aria-label="t('nav.language')">
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
          class="size-11 md:size-8"
          :aria-label="theme === 'light' ? t('nav.switchToDark') : t('nav.switchToLight')"
          @click="toggle"
        >
          <Sun v-if="theme === 'dark'" class="h-4 w-4" />
          <Moon v-else class="h-4 w-4" />
        </Button>

        <template v-if="authStore.isAuthenticated">
          <!-- Hidden below md purely to keep the bar from overflowing a 360px
               screen. Nothing is lost: this only ever renders on the landing
               page, which carries the same call to action twice in its body. -->
          <Button v-if="showWorkspaceLink" as-child class="hidden md:inline-flex">
            <RouterLink to="/app">{{ t('nav.openWorkspace') }}</RouterLink>
          </Button>
          <!-- Same reasoning; on mobile Admin moves into the account menu
               below, which is where people look for account-scoped links. -->
          <Button v-if="authStore.user?.is_admin" variant="ghost" as-child class="hidden md:inline-flex">
            <RouterLink to="/admin">{{ t('nav.admin') }}</RouterLink>
          </Button>
          <DropdownMenu>
            <DropdownMenuTrigger as-child>
              <Button variant="outline" size="icon" class="size-11 rounded-full md:size-8">
                <span class="text-xs font-medium">{{ initials }}</span>
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuLabel class="font-normal">
                <p class="truncate text-sm font-medium text-foreground">{{ authStore.user?.full_name }}</p>
                <p class="truncate text-xs text-muted-foreground">{{ authStore.user?.email }}</p>
              </DropdownMenuLabel>
              <DropdownMenuSeparator />
              <DropdownMenuItem
                v-if="authStore.user?.is_admin"
                class="md:hidden"
                @click="router.push('/admin')"
              >
                <ShieldCheck class="h-3.5 w-3.5" />
                {{ t('nav.admin') }}
              </DropdownMenuItem>
              <DropdownMenuItem @click="onSignOut">
                <LogOut class="h-3.5 w-3.5" />
                {{ t('nav.signOut') }}
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </template>
        <template v-else>
          <Button variant="ghost" as-child class="h-11 px-3 md:h-8 md:px-2.5">
            <RouterLink to="/sign-in">{{ t('nav.signIn') }}</RouterLink>
          </Button>
          <Button as-child class="h-11 px-3 md:h-8 md:px-2.5">
            <RouterLink to="/sign-up">{{ t('nav.signUp') }}</RouterLink>
          </Button>
        </template>
      </nav>
    </div>
  </header>
</template>
