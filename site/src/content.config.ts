// Astro content collections — mirrors the Keystatic schema (keystatic.config.ts).
//
// VERIFIED FILE-SHAPE CONVENTIONS (round-tripped through the Keystatic UI,
// 2026-06-09; @keystatic/core 0.5.50, Astro 5.18, @astrojs/markdoc 0.15):
//
// - Data collections (photos, practice_seasons, sponsors):
//     src/content/<collection>/<slug>.yaml — bare YAML, no frontmatter fences.
// - Markdoc collections (coaches, trips, wax_entries):
//     src/content/<collection>/<slug>.mdoc — YAML frontmatter + markdoc body
//     (the body is the Keystatic `format.contentField`; it is NOT in `data`,
//     access it via `render(entry)`).
// - Keystatic's `fields.slug` stores the *display name* under the `slug` key
//     in the data/frontmatter (e.g. `slug: Throwaway Test Season`), while the
//     generated url-slug becomes the file name. So `data.slug` here is a
//     human-readable display name, NOT a url slug.
// - Singletons serialize as single files:
//     pure data    -> src/content/pages/home.yaml, src/content/pages/contact.yaml,
//                     src/content/pages/sponsors_page.yaml, src/content/nav.yaml,
//                     src/content/site_meta.yaml
//     markdoc body -> src/content/pages/about.mdoc, community.mdoc, racing.mdoc
// - Empty optional scalar fields (text/url/integer/date/image) are OMITTED
//     from the file entirely -> model as .optional() in zod.
// - Empty optional object fields serialize as an EMPTY MAP (e.g.
//     `conditions_snapshot: {}`) -> inner fields must all be optional.
// - Select/checkbox/integer defaults ARE written explicitly by the UI
//     (e.g. `author_role: coach`), but zod `.default()` keeps hand-written
//     files lenient.
// - Unquoted YAML dates (`date: 2026-06-09`) parse as JS Date -> z.coerce.date().
// - Images store public-path strings (e.g. `/images/uploads/foo.jpg`).
//
// ID CONVENTION (Astro 5 content layer): entries expose `entry.id` (there is
// no `entry.slug` in the content-layer API). Because Astro's glob loader
// would otherwise hijack the entry id with the frontmatter `slug` field
// (which Keystatic uses for the DISPLAY NAME, see above), every collection
// passes `generateId` so that `entry.id` === the file name without
// extension, i.e. the Keystatic url-slug. Singleton collections contain
// exactly one entry whose id is the singleton name, e.g.
// `getEntry('home', 'home')`, `getEntry('nav', 'nav')`.
import { defineCollection, z } from 'astro:content';
import { glob } from 'astro/loaders';

/** entry.id = file name without extension (ignore frontmatter `slug`). */
const idFromFileName = ({ entry }: { entry: string }) =>
  entry.replace(/\.[^/.]+$/, '');

const dataLoader = (name: string) =>
  glob({ pattern: '*.yaml', base: `./src/content/${name}`, generateId: idFromFileName });

const mdocLoader = (name: string) =>
  glob({ pattern: '*.mdoc', base: `./src/content/${name}`, generateId: idFromFileName });

/** Loader for a Keystatic singleton serialized as a single file. */
const singletonLoader = (file: string, base = './src/content/pages') =>
  glob({ pattern: file, base, generateId: idFromFileName });

// --- Collections -----------------------------------------------------------

const photos = defineCollection({
  loader: dataLoader('photos'),
  schema: z.object({
    slug: z.string(), // display name ("Photo identifier")
    image: z.string(),
    alt_text: z.string().min(1),
    caption: z.string().optional(),
    event_tag: z
      .enum(['practice', 'birkie', 'sisu', 'travel', 'social', 'race'])
      .default('practice'),
    member_names: z.array(z.string()).optional(),
    order: z.number().int().default(0),
    show_on_home: z.boolean().default(false),
    photo_consent_recorded: z.boolean().default(false),
  }),
});

const coaches = defineCollection({
  loader: mdocLoader('coaches'),
  schema: z.object({
    slug: z.string(), // display name ("Name (display)")
    role: z.string(),
    photo: z.string(),
    photo_alt: z.string().min(1),
    credentials: z.array(z.string()).optional(),
    order: z.number().int().default(0),
  }),
});

const practice_seasons = defineCollection({
  loader: dataLoader('practice_seasons'),
  schema: z.object({
    slug: z.string(), // display name ("Season name")
    date_range: z.string(),
    fee_cents: z.number().int(),
    summary: z.string(),
    what_included: z.array(z.string()).default([]),
  }),
});

const trips = defineCollection({
  loader: mdocLoader('trips'),
  schema: z.object({
    slug: z.string(), // display name ("Trip name")
    location: z.string(),
    dates: z.string(),
    cost_summary: z.string(),
    signup_deadline: z.string().optional(),
    capacity: z.string().optional(),
    refund_policy: z.string().optional(),
    signup_url: z.string().url().optional(),
    hero_photo: z.string().optional(),
  }),
});

const wax_entries = defineCollection({
  loader: mdocLoader('wax_entries'),
  schema: z.object({
    slug: z.string(), // display name ("Title")
    date: z.coerce.date(),
    author_name: z.string().optional(),
    author_role: z.enum(['coach', 'member', 'board']).default('coach'),
    lede: z.string().optional(),
    photo: z.string().optional(),
    conditions_snapshot: z
      .object({
        location: z.string().optional(),
        temp_f: z.number().int().nullish(),
        wax_used: z.string().optional(),
      })
      .optional(),
  }),
});

const sponsors = defineCollection({
  loader: dataLoader('sponsors'),
  schema: z.object({
    slug: z.string(), // display name ("Sponsor name")
    logo: z.string(),
    tier: z.enum(['trailblazer', 'supporter', 'friend']).default('supporter'),
    url: z.string().url().optional(),
  }),
});

// --- Singleton pages (one entry each; id === singleton name) ---------------

const home = defineCollection({
  loader: singletonLoader('home.yaml'),
  schema: z.object({
    hero_headline: z.string(),
    hero_image: z.string(),
    hero_image_alt: z.string(),
    registration_state: z.enum(['open', 'coming_soon', 'closed']).default('closed'),
    cta_open_label: z.string().default('Register for the season →'),
    cta_open_url: z.string().url().optional(),
    cta_coming_soon_label: z.string().default('Get on the list'),
    cta_coming_soon_url: z.string().url().optional(),
    cta_closed_label: z.string().default('Member area'),
    cta_closed_url: z.string().url().optional(),
    mission_paragraph: z.string().optional(),
  }),
});

const about = defineCollection({
  loader: singletonLoader('about.mdoc'),
  schema: z.object({
    headline: z.string().optional(),
    intro: z.string().optional(),
  }),
});

const community = defineCollection({
  loader: singletonLoader('community.mdoc'),
  schema: z.object({
    headline: z.string().optional(),
    intro: z.string().optional(),
    team_bonding_activities: z.array(z.string()).default([]),
  }),
});

const racing = defineCollection({
  loader: singletonLoader('racing.mdoc'),
  schema: z.object({
    headline: z.string().optional(),
    intro: z.string().optional(),
    races: z
      .array(
        z.object({
          name: z.string().optional(),
          location: z.string().optional(),
          date: z.string().optional(),
          notes: z.string().optional(),
        }),
      )
      .default([]),
  }),
});

const sponsors_page = defineCollection({
  loader: singletonLoader('sponsors_page.yaml'),
  schema: z.object({
    headline: z.string().optional(),
    intro: z.string().optional(),
  }),
});

const contact = defineCollection({
  loader: singletonLoader('contact.yaml'),
  schema: z.object({
    email: z.string().optional(),
    mailing_address: z.string().optional(),
    instagram_url: z.string().url().optional(),
    slack_invite_url: z.string().url().optional(),
  }),
});

const nav = defineCollection({
  loader: singletonLoader('nav.yaml', './src/content'),
  schema: z.object({
    top_links: z
      .array(z.object({ label: z.string(), href: z.string() }))
      .default([]),
  }),
});

const site_meta = defineCollection({
  loader: singletonLoader('site_meta.yaml', './src/content'),
  schema: z.object({
    title: z.string().default('Twin Cities Ski Club'),
    description: z.string().optional(),
    og_image: z.string().optional(),
  }),
});

export const collections = {
  photos,
  coaches,
  practice_seasons,
  trips,
  wax_entries,
  sponsors,
  home,
  about,
  community,
  racing,
  sponsors_page,
  contact,
  nav,
  site_meta,
};
