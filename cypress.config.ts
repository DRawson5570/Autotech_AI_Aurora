import { defineConfig } from 'cypress';

export default defineConfig({
	e2e: {
		baseUrl: 'http://localhost:8080',
		setupNodeEvents(on, config) {
			on('task', {
				log(message) {
					console.log('CYPRESS TASK LOG:', message);
					return null;
				},
			});
			return config;
		}
	},
	video: true
});
