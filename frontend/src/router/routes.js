const routes = [
  {
    path: '/',
    component: () => import('layouts/MainLayout.vue'),
    children: [
      { path: '', name: 'dashboard', component: () => import('pages/DashboardPage.vue') },
      { path: 'scribe', name: 'scribe', component: () => import('pages/ScribePage.vue') },
      { path: 'encounters/:id', name: 'encounter-detail', component: () => import('pages/EncounterDetailPage.vue'), props: true },
      { path: 'history', name: 'history', component: () => import('pages/HistoryPage.vue') },
      { path: 'mt-review', name: 'mt-review', component: () => import('pages/MTReviewPage.vue') },
      { path: 'providers', name: 'providers', component: () => import('pages/ProvidersPage.vue') },
    ],
  },
  {
    path: '/:catchAll(.*)*',
    component: () => import('pages/ErrorNotFound.vue'),
  },
]

export default routes
