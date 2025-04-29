import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { fileURLToPath } from 'url';
import { dirname, resolve } from 'path';
import dotenv from 'dotenv';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

// Load env from parent directory
dotenv.config({ path: resolve(__dirname, '../.env') });

// Parse allowed hosts from environment variable or use defaults
const allowedHostsFromEnv = process.env.VITE_ALLOWED_HOSTS 
  ? process.env.VITE_ALLOWED_HOSTS.split(',') 
  : ["sync.voxcon.ai"];

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 9743,
    host: '0.0.0.0',
    strictPort: true,
    hmr: {
      clientPort: 9743
    },
    watch: {
      usePolling: true
    },
    proxy: {
      '/api.v1': {
        target: 'http://localhost:9742',
        changeOrigin: true
      }
    },
    cors: true,
    headers: {
      'Access-Control-Allow-Origin': '*'
    }
  },
  preview: {
    port: 9743,
    host: '0.0.0.0',
    strictPort: true,
    allowedHosts: [...allowedHostsFromEnv, "localhost", "127.0.0.1"],
    headers: {
      'Access-Control-Allow-Origin': '*'
    }
  },
  resolve: {
    alias: {
      '@': resolve(__dirname, './src'),
    },
  },
  assetsInclude: ['**/*.png', '**/*.jpg', '**/*.svg', '**/*.gif'],
  build: {
    assetsDir: 'assets',
    copyPublicDir: true,
    rollupOptions: {
      output: {
        assetFileNames: 'assets/[name]-[hash][extname]'
      }
    }
  }
}); 