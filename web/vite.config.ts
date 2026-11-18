import react from '@vitejs/plugin-react';
import { defineConfig } from 'vitest/config';

// API chạy ở 127.0.0.1:8000; dev server proxy cả REST và WebSocket qua /api.
const API_TARGET = process.env.VITE_API_TARGET ?? 'http://127.0.0.1:8000';

export default defineConfig({
  plugins: [react()],
  build: { chunkSizeWarningLimit: 1000 },
  server: {
    host: '0.0.0.0', // mở được từ máy khác trong LAN
    port: 5173,
    proxy: {
      '/api': { target: API_TARGET, changeOrigin: true, ws: true },
    },
  },
  preview: {
    host: '0.0.0.0',
    port: 4173,
    proxy: {
      '/api': { target: API_TARGET, changeOrigin: true, ws: true },
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
    css: false,
    // Máy dev 16 GB chạy nhiều tiến trình song song: giới hạn worker để tránh Node hết heap.
    maxWorkers: 2,
  },
});
