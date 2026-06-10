import { defineConfig } from 'astro/config';
import tailwind from '@astrojs/tailwind';
import react from '@astrojs/react';
import keystatic from '@keystatic/astro';

// Keystatic injects server routes (prerender: false), which Astro 5 only
// allows when a server adapter is installed. We use local-mode Keystatic as
// a dev-time editing UI only, so the integration is enabled outside of
// production builds and `astro build` stays fully static (no adapter).
// react() exists solely for the Keystatic admin UI, so it is gated with it.
const isProductionBuild = process.env.NODE_ENV === 'production';

export default defineConfig({
  site: 'https://twincitiesskiclub.org',
  output: 'static',
  integrations: [
    tailwind({ applyBaseStyles: false }),
    ...(isProductionBuild ? [] : [react(), keystatic()]),
  ],
  image: {
    service: { entrypoint: 'astro/assets/services/sharp' },
  },
});
