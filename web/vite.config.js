import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// The built app is served by the Flask backend at /app/, so every address starts with /app/.
// While developing, API calls (/api/...) are forwarded to the Flask backend on port 5000,
// so the login cookie works exactly like it will when hosted.
export default defineConfig({
  base: '/app/',
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://127.0.0.1:5000',
    },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
})
