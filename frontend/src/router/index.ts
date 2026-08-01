import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import LandingPage from '@/views/LandingPage.vue'
import SignInView from '@/views/SignInView.vue'
import SignUpView from '@/views/SignUpView.vue'
import WorkspaceView from '@/views/WorkspaceView.vue'
import AdminView from '@/views/AdminView.vue'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'landing', component: LandingPage },
    { path: '/sign-in', name: 'sign-in', component: SignInView },
    { path: '/sign-up', name: 'sign-up', component: SignUpView },
    // The open document lives in the URL rather than in component state so
    // that Android's back button and iOS's swipe-back gesture navigate out of
    // a document for free, and so a reload keeps you on the one you opened.
    // On desktop the param only drives which row is highlighted - both panes
    // render either way.
    { path: '/app/:id?', name: 'workspace', component: WorkspaceView, meta: { requiresAuth: true } },
    { path: '/admin', name: 'admin', component: AdminView, meta: { requiresAuth: true, requiresAdmin: true } },
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

  if (to.meta.requiresAdmin && !authStore.user?.is_admin) {
    return { name: 'workspace' }
  }

  if ((to.name === 'sign-in' || to.name === 'sign-up') && authStore.isAuthenticated) {
    return { name: 'workspace' }
  }

  return true
})
