import { config, fields, singleton } from '@keystatic/core';

export default config({
  storage: { kind: 'local' },
  collections: {},
  singletons: {
    site_meta: singleton({
      label: 'Site metadata',
      path: 'src/content/site_meta',
      schema: {
        title: fields.text({ label: 'Site title' }),
        description: fields.text({ label: 'Default description' }),
      },
    }),
  },
});
