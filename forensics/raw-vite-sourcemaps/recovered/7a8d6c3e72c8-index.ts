import { createRouter, createWebHistory } from 'vue-router'
import Home from '../views/Home.vue'
import Jobs from '../views/Jobs.vue'
import History from '../views/History.vue'
import Settings from '../views/Settings.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'home', component: Home },
    { path: '/jobs', name: 'jobs', component: Jobs },
    { path: '/history', name: 'history', component: History },
    { path: '/settings', name: 'settings', component: Settings },
  ],
})

export default router
