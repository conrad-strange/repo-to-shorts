import {defineConfig} from 'vite';
import react from '@vitejs/plugin-react';

declare const process: {env?: Record<string, string | undefined>};

const apiTarget = process.env.GVA_API_TARGET ?? 'http://127.0.0.1:7860';

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': apiTarget,
    },
  },
});
