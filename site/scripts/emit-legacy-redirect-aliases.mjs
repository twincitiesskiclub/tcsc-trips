import { copyFile } from 'node:fs/promises';

const legacyRoutes = ['register', 'copy-of-register', 'sisu-signup', 'trip-sign-up'];

// A Blueprint-managed deploy has real edge 301s and intentionally omits the
// Astro fallback routes. The existing dashboard-managed service still has
// stale redirect rules, so publish both directory and flat-file forms there.
// Render recognizes `route.html` as the exact extensionless resource and
// serves it before the stale dashboard rule.
if (process.env.TCSC_EDGE_CONFIG !== 'true') {
  const dist = new URL('../dist/', import.meta.url);

  await Promise.all(
    legacyRoutes.map((route) =>
      copyFile(new URL(`${route}/index.html`, dist), new URL(`${route}.html`, dist)),
    ),
  );

  console.log(`Emitted ${legacyRoutes.length} flat legacy-redirect aliases.`);
}
