import { defineConfig } from 'vitest/config';
import { sveltekit } from '@sveltejs/kit/vite';

export default defineConfig({
  plugins: [sveltekit()],
  test: {
    include: ['tests/**/*.{test,spec}.ts'],
    environment: 'node',
    globals: true,
    coverage: {
      provider: 'v8',
      reporter: ['text', 'html', 'lcov'],
      include: ['src/lib/**/*.ts'],
      exclude: [
        'src/lib/**/*.svelte',
        'src/lib/db/index.ts', // SQLite binary dependency
        'src/lib/worker/**', // Background worker
        'src/lib/stores/**' // Svelte runes
      ]
    }
  }
});
