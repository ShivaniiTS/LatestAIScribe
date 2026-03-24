import { defineBoot } from '#q-app/wrappers'
import axios from 'axios'

// Use relative base URL so the same origin serves API + static files.
// In dev, set VITE_API_BASE_URL to e.g. http://localhost:8080
export const baseURL = import.meta.env.VITE_API_BASE_URL || ''

const api = axios.create({
  baseURL,
  timeout: 60000,
})

api.interceptors.response.use(
  response => response,
  error => {
    if (error.code === 'ECONNABORTED') {
      console.error('Request timeout - server may be processing a large file')
    }
    return Promise.reject(error)
  }
)

export default defineBoot(({ app }) => {
  app.config.globalProperties.$api = api
})

export { api }
