import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

export default defineConfig({
	plugins: [sveltekit()],
	server: {
		host: '0.0.0.0',  // Accessible from local network (phone, other devices)
		port: 5173
	},
	preview: {
		host: '0.0.0.0',
		port: 5173
	}
});
