import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const port = parseInt(process.env.VITE_PORT || process.env.PORT || '5174', 10)

export default defineConfig({
  plugins: [react()],
  server: {
    port,
    host: true
  }
})
