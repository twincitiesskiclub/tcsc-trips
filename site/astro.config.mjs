import { defineConfig } from 'astro/config';
import react from '@astrojs/react';
import keystatic from '@keystatic/astro';
import markdoc from '@astrojs/markdoc';
import sitemap from '@astrojs/sitemap';
import tailwindcss from '@tailwindcss/vite';

// Keystatic injects server routes (prerender: false), which require a server
// adapter. We use local-mode Keystatic as a dev-time editing UI only, so the
// integration is enabled outside production builds and `astro build` stays
// fully static (no adapter).
// react() exists solely for the Keystatic admin UI, so it is gated with it.
const isProductionBuild = process.env.NODE_ENV === 'production';
// The existing Render service is dashboard-managed. Until it is linked to
// the Blueprint, retain static resources for slash-form legacy URLs and page
// directories so a code deploy cannot turn valid links into 404s. The stale
// no-slash dashboard rules land on compatibility routes in the registration
// app. The Blueprint sets this flag and then real edge 301s can take over.
const hasManagedEdgeConfig = process.env.TCSC_EDGE_CONFIG === 'true';

export default defineConfig({
  site: 'https://twincitiesskiclub.org',
  output: 'static',
  trailingSlash: hasManagedEdgeConfig ? 'never' : 'ignore',
  build: {
    // Flat files let Blueprint-managed edge rules see slash URLs. Directory
    // output is the safe fallback while the existing service has only its
    // older dashboard rules, because Render serves resources before rules.
    format: hasManagedEdgeConfig ? 'file' : 'directory',
  },
  // Static fallback pages keep retired signup URLs useful before host-level
  // rules are synchronized. They are omitted once managed edge 301s exist,
  // because Render gives generated resources precedence over redirect rules.
  redirects: hasManagedEdgeConfig
    ? {}
    : {
        '/register': 'https://tcsc.ski/',
        '/copy-of-register': 'https://tcsc.ski/',
        '/sisu-signup': '/trips',
        '/trip-sign-up': '/trips',
      },
  // Astro 7 defaults to JSX-style whitespace trimming. Keep the previous
  // HTML-aware behavior so the framework upgrade cannot join inline text.
  compressHTML: true,
  vite: {
    plugins: [tailwindcss()],
  },
  integrations: [
    // markdoc() is required in ALL builds: content collections read the
    // .mdoc files Keystatic writes, and render() needs the integration.
    markdoc(),
    sitemap({
      // Directory output is the compatibility fallback, not the public URL
      // convention. Keep sitemap entries aligned with extensionless canonicals.
      serialize(item) {
        const url = new URL(item.url);
        if (url.pathname !== '/' && url.pathname.endsWith('/')) {
          url.pathname = url.pathname.slice(0, -1);
        }
        return { ...item, url: url.href };
      },
    }),
    ...(isProductionBuild ? [] : [react(), keystatic()]),
  ],
  image: {
    service: { entrypoint: 'astro/assets/services/sharp' },
  },
});
