import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

const backendProxyTarget = process.env.BACKEND_PROXY_URL || 'http://localhost:8000';

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 5173,
    host: '0.0.0.0',
    proxy: {
      '/api': {
        target: backendProxyTarget,
        changeOrigin: true,
      },
      '/health': {
        target: backendProxyTarget,
        changeOrigin: true,
      },
    },
  },
});
