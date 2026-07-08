<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { FileText } from '@lucide/vue'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { useAuthStore } from '@/stores/auth'

const { t } = useI18n()
const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()

const email = ref('')
const password = ref('')
const isSubmitting = ref(false)
const errorMessage = ref('')

async function onSubmit() {
  errorMessage.value = ''
  isSubmitting.value = true
  try {
    await authStore.login(email.value, password.value)
    const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : '/app'
    router.replace(redirect)
  } catch (error: unknown) {
    const status = (error as { response?: { status?: number } })?.response?.status
    errorMessage.value = status === 429 ? t('auth.signIn.rateLimitError') : t('auth.signIn.genericError')
  } finally {
    isSubmitting.value = false
  }
}
</script>

<template>
  <div class="flex min-h-screen flex-col items-center justify-center px-4">
    <RouterLink to="/" class="mb-8 flex items-center gap-2.5">
      <span class="flex h-8 w-8 items-center justify-center rounded-md bg-primary text-primary-foreground">
        <FileText class="h-4 w-4" />
      </span>
      <span class="font-display text-lg leading-none text-foreground">Sanad</span>
    </RouterLink>

    <div class="w-full max-w-sm rounded-xl border border-border bg-card p-6 shadow-sm">
      <h1 class="font-display text-xl text-foreground">{{ t('auth.signIn.title') }}</h1>
      <p class="mt-1 text-sm text-muted-foreground">{{ t('auth.signIn.subtitle') }}</p>

      <form class="mt-6 space-y-4" @submit.prevent="onSubmit">
        <div class="space-y-1.5">
          <Label for="email">{{ t('auth.emailLabel') }}</Label>
          <Input id="email" v-model="email" type="email" autocomplete="email" required placeholder="you@example.com" />
        </div>
        <div class="space-y-1.5">
          <Label for="password">{{ t('auth.passwordLabel') }}</Label>
          <Input id="password" v-model="password" type="password" autocomplete="current-password" required />
        </div>

        <p v-if="errorMessage" class="text-sm text-destructive">{{ errorMessage }}</p>

        <Button type="submit" class="w-full" :disabled="isSubmitting">
          {{ isSubmitting ? t('auth.signIn.submitting') : t('auth.signIn.submit') }}
        </Button>
      </form>

      <p class="mt-5 text-center text-sm text-muted-foreground">
        {{ t('auth.signIn.noAccount') }}
        <RouterLink to="/sign-up" class="font-medium text-primary hover:underline">
          {{ t('auth.signIn.switchToSignUp') }}
        </RouterLink>
      </p>
    </div>
  </div>
</template>
