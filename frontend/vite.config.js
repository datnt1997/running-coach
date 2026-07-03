import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  base: '/app',
  server: {
    proxy: {
      '/goal': 'http://localhost:8000',
      '/fitness-chat': 'http://localhost:8000',
      '/goals': 'http://localhost:8000',
      '/plan': 'http://localhost:8000',
      '/strava': 'http://localhost:8000',
      '/health': 'http://localhost:8000',
    },
  },
})
