const routes = [
  {
    path: '/',
    component: () => import('layouts/MainLayout.vue'),
    children: [
      {
        path: '',
        component: () => import('pages/IndexPage.vue'),
      },
      {
        path: 'md-checkout-main',
        component: () => import('pages/MDCheckoutMain.vue'),
      },
      {
        path: 'forms/ai-scribe',
        component: () => import('src/ai_scribe_frontend/pages/AIScribePage.vue'),
      },
      {
        path: 'soap-history',
        component: () => import('src/ai_scribe_frontend/pages/SoapHistoryPage.vue'),
      },
      {
        path: 'help',
        component: () => import('pages/HelpPage.vue'),
      },
    ],
  },
  {
    path: '/:catchAll(.*)*',
    component: () => import('pages/ErrorNotFound.vue'),
  },
]

export default routes
