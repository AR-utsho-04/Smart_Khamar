import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// In development, API calls to /api are forwarded to the FastAPI backend.
// 127.0.0.1 (not "localhost") avoids an IPv6 problem on Windows with Node 17+.
export default defineConfig({
  plugins: [react()],
  server: { host: '127.0.0.1', port: 5173, proxy: { '/api': { target: 'http://127.0.0.1:8000', changeOrigin: true } } },
});
