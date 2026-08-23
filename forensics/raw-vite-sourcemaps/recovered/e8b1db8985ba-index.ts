import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'dashboard',
      component: () => import('../views/Dashboard.vue'),
    },
    {
      path: '/library',
      name: 'home',
      component: () => import('../views/Home.vue'),
    },
    {
      path: '/jobs',
      name: 'jobs',
      component: () => import('../views/Jobs.vue'),
    },
    {
      path: '/history',
      name: 'history',
      component: () => import('../views/History.vue'),
    },
    {
      path: '/settings',
      name: 'settings',
      component: () => import('../views/settings/SettingsIndex.vue'),
    },
  ],
})

export default router
