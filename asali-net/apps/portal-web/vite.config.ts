import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

// In development the portal talks to one running node: NODE_URL=http://127.0.0.1:8402 npm run dev
const node = process.env.NODE_URL ?? 'http://127.0.0.1:8402'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: { proxy: { '/api': node, '/share': node } },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test-setup.ts'],
    css: false,
    exclude: ['e2e/**', 'node_modules/**', 'dist/**'],
  },
})
