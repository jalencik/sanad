<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { RouterLink, useRouter } from 'vue-router'
import { FileText } from '@lucide/vue'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import GoogleIcon from '@/components/GoogleIcon.vue'
import { useAuthStore } from '@/stores/auth'

const { t } = useI18n()
const router = useRouter()
const authStore = useAuthStore()

const fullName = ref('')
const email = ref('')
const password = ref('')
const isSubmitting = ref(false)
const errorMessage = ref('')

async function onSubmit() {
  errorMessage.value = ''
  isSubmitting.value = true
  try {
    await authStore.signup(email.value, password.value, fullName.value)
    router.replace('/app')
  } catch (error: unknown) {
    const status = (error as { response?: { status?: number } })?.response?.status
    errorMessage.value = status === 409 ? t('auth.signUp.duplicateError') : t('auth.signUp.genericError')
  } finally {
    isSubmitting.value = false
  }
}

function onGoogleSignIn() {
  window.location.href = '/api/auth/google/login'
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
      <h1 class="font-display text-xl text-foreground">{{ t('auth.signUp.title') }}</h1>
      <p class="mt-1 text-sm text-muted-foreground">{{ t('auth.signUp.subtitle') }}</p>

      <form class="mt-6 space-y-4" @submit.prevent="onSubmit">
        <div class="space-y-1.5">
          <Label for="full-name">{{ t('auth.fullNameLabel') }}</Label>
          <Input
            id="full-name"
            v-model="fullName"
            type="text"
            autocomplete="name"
            required
            :placeholder="t('auth.fullNamePlaceholder')"
          />
        </div>
        <div class="space-y-1.5">
          <Label for="email">{{ t('auth.emailLabel') }}</Label>
          <Input id="email" v-model="email" type="email" autocomplete="email" required placeholder="you@example.com" />
        </div>
        <div class="space-y-1.5">
          <Label for="password">{{ t('auth.passwordLabel') }}</Label>
          <Input id="password" v-model="password" type="password" autocomplete="new-password" required minlength="8" />
          <p class="text-xs text-muted-foreground">{{ t('auth.signUp.passwordHint') }}</p>
        </div>

        <p v-if="errorMessage" class="text-sm text-destructive">{{ errorMessage }}</p>

        <Button type="submit" class="w-full" :disabled="isSubmitting">
          {{ isSubmitting ? t('auth.signUp.submitting') : t('auth.signUp.submit') }}
        </Button>
      </form>

      <div class="my-4 flex items-center gap-3">
        <div class="h-px flex-1 bg-border" />
        <span class="text-xs text-muted-foreground">{{ t('auth.orDivider') }}</span>
        <div class="h-px flex-1 bg-border" />
      </div>

      <Button type="button" variant="outline" class="w-full" @click="onGoogleSignIn">
        <GoogleIcon />
        {{ t('auth.continueWithGoogle') }}
      </Button>

      <p class="mt-5 text-center text-sm text-muted-foreground">
        {{ t('auth.signUp.haveAccount') }}
        <RouterLink to="/sign-in" class="font-medium text-primary hover:underline">
          {{ t('auth.signUp.switchToSignIn') }}
        </RouterLink>
      </p>
    </div>
  </div>
</template>
