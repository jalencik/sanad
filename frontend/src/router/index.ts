import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import LandingPage from '@/views/LandingPage.vue'
import SignInView from '@/views/SignInView.vue'
import SignUpView from '@/views/SignUpView.vue'
import WorkspaceView from '@/views/WorkspaceView.vue'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'landing', component: LandingPage },
    { path: '/sign-in', name: 'sign-in', component: SignInView },
    { path: '/sign-up', name: 'sign-up', component: SignUpView },
    { path: '/app', name: 'workspace', component: WorkspaceView, meta: { requiresAuth: true } },
  ],
  scrollBehavior() {
    return { top: 0 }
  },
})

router.beforeEach((to) => {
  const authStore = useAuthStore()

  if (to.meta.requiresAuth && !authStore.isAuthenticated) {
    return { name: 'sign-in', query: { redirect: to.fullPath } }
  }

  if ((to.name === 'sign-in' || to.name === 'sign-up') && authStore.isAuthenticated) {
    return { name: 'workspace' }
  }

  return true
})
