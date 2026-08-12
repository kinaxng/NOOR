import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'dashboard', component: () => import('../views/Dashboard.vue') },
    // Keep the former workbench URLs usable after the routed/componentized migration.
    { path: '/recommendations', redirect: (to) => ({ path: '/plugins/av-recommend', query: to.query, hash: to.hash }) },
    { path: '/subscriptions', redirect: (to) => ({ path: '/plugins/subscription-core', query: to.query, hash: to.hash }) },
    { path: '/tasks', redirect: (to) => ({ path: '/jobs', query: to.query, hash: to.hash }) },
    { path: '/actors', redirect: (to) => ({ path: '/files/actors', query: to.query, hash: to.hash }) },
    { path: '/javdb/:code', redirect: (to) => ({ path: '/plugins/javdb', query: { ...to.query, code: to.params.code }, hash: to.hash }) },
    { path: '/actor/emby/:actorId', redirect: (to) => ({ path: `/actors/${encodeURIComponent(String(to.params.actorId || ''))}`, query: { ...to.query, returnTo: to.query.returnTo || '/files/actors' }, hash: to.hash }) },
    { path: '/library/:libraryFilter?', name: 'home', component: () => import('../views/Home.vue') },
    { path: '/jobs/:jobTab?', name: 'jobs', component: () => import('../views/Jobs.vue') },
    { path: '/history/:historyFilter?', name: 'history', component: () => import('../views/History.vue') },
    { path: '/files/:fileTab?', name: 'files', component: () => import('../views/FilesView.vue') },
    { path: '/actors/:actorId', name: 'actor-detail', component: () => import('../views/ActorDetailView.vue') },
    { path: '/hardlinks', redirect: '/files/hardlinks' },
    { path: '/search/resources', name: 'resource-search', component: () => import('../views/ResourceSearch.vue') },
    { path: '/plugins', name: 'plugins', component: () => import('../views/PluginManager.vue') },
    { path: '/plugins/:pluginId/:pluginPath(.*)*', name: 'plugin-host', component: () => import('../views/PluginHost.vue') },
    { path: '/settings/:settingsTab?', name: 'settings', component: () => import('../views/settings/SettingsIndex.vue') },
  ],
})

export default router
