var _a;
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
var apiTarget = (_a = process.env.GVA_API_TARGET) !== null && _a !== void 0 ? _a : 'http://127.0.0.1:7860';
export default defineConfig({
    plugins: [react()],
    server: {
        proxy: {
            '/api': apiTarget,
        },
    },
});
