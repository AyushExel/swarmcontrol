import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

// The dashboard. `npm run dev` serves it with hot reload against `swctl serve` on :8787;
// `npm run build` writes it into the Python package, which serves it in production.

export default defineConfig({
  root: 'web',
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: { '/api': { target: 'http://localhost:8787', changeOrigin: true } },
    fs: { allow: ['..'] },
  },
  build: { outDir: '../src/swarmcontrol/web', emptyOutDir: true },
});
