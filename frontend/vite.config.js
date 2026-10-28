import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Запросы к /api и /media Vite перенаправляет на Django (порт 8000).
// Поэтому во фронтенде адреса относительные, а CORS при разработке не мешает.
const backend = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': { target: backend, changeOrigin: true },
      '/media': { target: backend, changeOrigin: true },
    },
  },
})
