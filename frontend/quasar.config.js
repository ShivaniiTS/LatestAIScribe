import { configure } from 'quasar/wrappers'

export default configure(() => {
  return {
    boot: ['axios'],

    css: ['app.scss'],

    extras: ['roboto-font', 'material-icons'],

    build: {
      target: { browser: ['es2022'] },
      vueRouterMode: 'history',
      env: {
        API_BASE_URL: process.env.VITE_API_BASE_URL || 'http://localhost:8000',
      },
      // vite-plugin-checker (ESLint) removed — not needed for production builds
    },

    devServer: {
      port: 9000,
      open: true,
    },

    framework: {
      plugins: ['Notify', 'Dialog', 'Loading'],
      config: {
        notify: { position: 'top-right', timeout: 3000 },
      },
    },

    animations: [],
    ssr: { pwa: false },
    pwa: false,
    capacitor: {},
    electron: {},
  }
})
