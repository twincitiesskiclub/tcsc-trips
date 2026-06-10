import { defineConfig } from 'astro/config';

export default defineConfig({
  site: 'https://twincitiesskiclub.org',
  output: 'static',
  image: {
    service: { entrypoint: 'astro/assets/services/sharp' },
  },
});
