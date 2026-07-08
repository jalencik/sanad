import { defineStore } from 'pinia'
import { authApi } from '@/lib/api'
import type { AuthUser } from '@/lib/types'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    user: null as AuthUser | null,
    isInitializing: true,
  }),

  getters: {
    isAuthenticated: (state) => state.user !== null,
  },

  actions: {
    async initialize() {
      try {
        this.user = await authApi.me()
      } catch {
        this.user = null
      } finally {
        this.isInitializing = false
      }
    },

    async login(email: string, password: string) {
      this.user = await authApi.login(email, password)
    },

    async signup(email: string, password: string, fullName: string) {
      this.user = await authApi.signup(email, password, fullName)
    },

    async logout() {
      try {
        await authApi.logout()
      } finally {
        this.user = null
      }
    },
  },
})
