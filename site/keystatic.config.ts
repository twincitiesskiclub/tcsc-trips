// Keystatic schema — the content contract for the TCSC marketing site.
//
// Field names/types here are load-bearing: the Astro content-collections
// config (src/content.config.ts), the content port, and the future Slack
// editing agent all depend on them. Do not rename fields casually.
//
// Amendments vs the original plan text (documented per plan instructions):
// 1. Collections with a markdoc body declare `format: { contentField: ... }`
//    so entries serialize as `.mdoc` files (YAML frontmatter + markdoc body),
//    which is what Astro's markdoc-aware glob loader reads.
// 2. The about/community/racing singletons also declare
//    `format: { contentField: 'body' }` for the same reason — without it,
//    Keystatic would store the markdoc body in a separate sibling file
//    (e.g. `about/body.mdoc` next to `about.yaml`), which Astro could not
//    associate with the entry.
// 3. The community singleton gained a `body` markdoc field (the source
//    community page has body prose).
//
// Serialization (local storage, no trailing slash on singleton paths):
// - Pure-data singletons -> `<path>.yaml` (e.g. src/content/pages/home.yaml)
// - Markdoc singletons   -> `<path>.mdoc` (frontmatter + body)
// - Data collections     -> `src/content/<name>/<slug>.yaml`
// - Markdoc collections  -> `src/content/<name>/<slug>.mdoc`
// - `fields.slug` stores the *display name* under the field key (`slug:`)
//   in frontmatter; the generated slug becomes the file name.
//
// Images: all content-rendered images live under `src/assets/images/<kind>/`
// and are stored in frontmatter as RELATIVE paths (e.g.
// `../../assets/images/coaches/anna/photo.jpg`) so Astro's content-layer
// `image()` schema helper routes them through the astro:assets/sharp pipeline
// (responsive srcset, intrinsic dimensions). Every content file sits at depth
// `src/content/<dir>/<file>`, so the relative prefix is always `../../`.
// Keystatic's `directory` is relative to this config file (the `site/` root);
// `publicPath` is the literal prefix written into frontmatter.
// VERIFIED upload shapes (via the UI, 2026-06-09):
// - collection entry: file lands at `<directory>/<entry-slug>/<field>.<ext>`,
//   frontmatter gets `<publicPath><entry-slug>/<field>.<ext>`
// - singleton: file lands at `<directory>/<field>.<ext>`,
//   frontmatter gets `<publicPath><field>.<ext>`
// - replacing an image DELETES the previously referenced asset file.
// EXCEPTION: site_meta.og_image stays in `public/og/` — og:image needs a
// stable absolute URL and no transformation.
import { config, fields, collection, singleton } from '@keystatic/core';

// Content images routed through astro:assets (see image note above).
const imagePaths = (kind: string) => ({
  directory: `src/assets/images/${kind}`,
  publicPath: `../../assets/images/${kind}/`,
});

const contentImage = (label: string, kind: string) =>
  fields.image({ label, ...imagePaths(kind), validation: { isRequired: true } });

const optionalContentImage = (label: string, kind: string) =>
  fields.image({ label, ...imagePaths(kind) });

export default config({
  storage: { kind: 'local' },

  singletons: {
    home: singleton({
      label: 'Home page',
      path: 'src/content/pages/home',
      schema: {
        hero_headline: fields.text({ label: 'Hero headline', validation: { isRequired: true } }),
        hero_image: contentImage('Hero photograph', 'uploads'),
        hero_image_alt: fields.text({ label: 'Hero image alt text', validation: { isRequired: true } }),
        registration_state: fields.select({
          label: 'Registration state',
          options: [
            { label: 'Open', value: 'open' },
            { label: 'Coming soon', value: 'coming_soon' },
            { label: 'Closed (in-season)', value: 'closed' },
          ],
          defaultValue: 'closed',
        }),
        cta_open_label: fields.text({ label: 'CTA label when open', defaultValue: 'Register for the season' }),
        cta_open_url: fields.url({ label: 'CTA URL when open' }),
        cta_coming_soon_label: fields.text({ label: 'CTA label when coming soon', defaultValue: 'Get on the list' }),
        cta_coming_soon_url: fields.url({ label: 'CTA URL when coming soon' }),
        cta_closed_label: fields.text({ label: 'CTA label when closed', defaultValue: 'Member area' }),
        cta_closed_url: fields.url({ label: 'CTA URL when closed' }),
        mission_paragraph: fields.text({ label: 'Mission paragraph', multiline: true }),
      },
    }),

    about: singleton({
      label: 'About page',
      path: 'src/content/pages/about',
      format: { contentField: 'body' },
      schema: {
        headline: fields.text({ label: 'Headline' }),
        intro: fields.text({ label: 'Intro paragraph', multiline: true }),
        body: fields.markdoc({ label: 'Body' }),
      },
    }),

    community: singleton({
      label: 'Community page',
      path: 'src/content/pages/community',
      format: { contentField: 'body' },
      schema: {
        headline: fields.text({ label: 'Headline' }),
        intro: fields.text({ label: 'Intro', multiline: true }),
        body: fields.markdoc({ label: 'Body' }),
        team_bonding_activities: fields.array(fields.text({ label: 'Activity' }), {
          label: 'Team bonding activities',
        }),
        takeaways: fields.array(
          fields.object({
            group: fields.text({ label: 'Group heading', validation: { isRequired: true } }),
            items: fields.array(
              fields.object({
                line: fields.text({ label: 'Line', validation: { isRequired: true } }),
                detail: fields.text({ label: 'Detail', multiline: true }),
                href: fields.text({ label: 'Link target (optional)' }),
              }),
              { label: 'Items', itemLabel: (p) => p.fields.line.value || 'Item' },
            ),
          }),
          { label: "What we've done (takeaways)", itemLabel: (p) => p.fields.group.value || 'Group' },
        ),
      },
    }),

    racing: singleton({
      label: 'Racing page',
      path: 'src/content/pages/racing',
      format: { contentField: 'body' },
      schema: {
        headline: fields.text({ label: 'Headline' }),
        intro: fields.text({ label: 'Intro', multiline: true }),
        races: fields.array(
          fields.object({
            name: fields.text({ label: 'Name' }),
            location: fields.text({ label: 'Location' }),
            date: fields.text({ label: 'Date or window' }),
            notes: fields.text({ label: 'Notes', multiline: true }),
            href: fields.text({ label: 'Link target (club-hosted events only)' }),
          }),
          { label: 'Races' },
        ),
        body: fields.markdoc({ label: 'Body' }),
      },
    }),

    sponsors_page: singleton({
      label: 'Sponsors page',
      path: 'src/content/pages/sponsors_page',
      schema: {
        headline: fields.text({ label: 'Headline', validation: { isRequired: true } }),
        intro: fields.text({ label: 'Intro', multiline: true, validation: { isRequired: true } }),
        impact_heading: fields.text({ label: 'Impact heading', validation: { isRequired: true } }),
        impact_intro: fields.text({ label: 'Impact intro', multiline: true, validation: { isRequired: true } }),
        impact_items: fields.array(
          fields.object({
            title: fields.text({ label: 'Title', validation: { isRequired: true } }),
            detail: fields.text({ label: 'Detail', multiline: true, validation: { isRequired: true } }),
          }),
          {
            label: 'Completed impact',
            itemLabel: (p) => p.fields.title.value || 'Impact item',
            validation: { length: { min: 1 } },
          },
        ),
        recognition_heading: fields.text({ label: 'Recognition heading', validation: { isRequired: true } }),
        recognition_body: fields.text({ label: 'Recognition body', multiline: true, validation: { isRequired: true } }),
        recognition_caption: fields.text({ label: 'Recognition photo caption', validation: { isRequired: true } }),
        priorities_heading: fields.text({ label: 'Priorities heading', validation: { isRequired: true } }),
        priorities_intro: fields.text({ label: 'Priorities intro', multiline: true, validation: { isRequired: true } }),
        priority_items: fields.array(
          fields.object({
            title: fields.text({ label: 'Title', validation: { isRequired: true } }),
            detail: fields.text({ label: 'Detail', multiline: true, validation: { isRequired: true } }),
          }),
          {
            label: 'Future priorities',
            itemLabel: (p) => p.fields.title.value || 'Priority',
            validation: { length: { min: 1 } },
          },
        ),
        contact_heading: fields.text({ label: 'Contact heading', validation: { isRequired: true } }),
        contact_body: fields.text({ label: 'Contact body', multiline: true, validation: { isRequired: true } }),
        contact_email: fields.text({
          label: 'Contact email',
          validation: {
            isRequired: true,
            pattern: {
              regex: /^[^\s@]+@[^\s@]+\.[^\s@]+$/,
              message: 'Enter a valid email address.',
            },
          },
        }),
        contact_cta_label: fields.text({ label: 'Contact CTA label', validation: { isRequired: true } }),
        disclosure: fields.text({ label: 'Sponsor disclosure', multiline: true, validation: { isRequired: true } }),
      },
    }),

    // Photos on the two pages below use kind 'photos' on purpose: page
    // images must come from the consent-cleared pool, so a Keystatic
    // replacement lands next to the rest of the pool.
    extra_training: singleton({
      label: 'Extra training fun page',
      path: 'src/content/pages/extra_training',
      format: { contentField: 'body' },
      schema: {
        headline: fields.text({ label: 'Headline' }),
        intro: fields.text({ label: 'Intro', multiline: true }),
        body: fields.markdoc({ label: 'Body' }),
        fixtures: fields.array(
          fields.object({
            name: fields.text({ label: 'Name', validation: { isRequired: true } }),
            when: fields.text({ label: 'When' }),
            what: fields.text({ label: 'What', multiline: true }),
          }),
          { label: 'Standing invitations', itemLabel: (p) => p.fields.name.value || 'Fixture' },
        ),
        annuals: fields.array(
          fields.object({
            name: fields.text({ label: 'Name', validation: { isRequired: true } }),
            detail: fields.text({ label: 'Detail', multiline: true }),
          }),
          { label: 'The annuals', itemLabel: (p) => p.fields.name.value || 'Annual' },
        ),
        photo_1: optionalContentImage('Photo 1', 'photos'),
        photo_1_alt: fields.text({ label: 'Photo 1 alt text' }),
        photo_1_caption: fields.text({ label: 'Photo 1 caption' }),
        photo_2: optionalContentImage('Photo 2', 'photos'),
        photo_2_alt: fields.text({ label: 'Photo 2 alt text' }),
        photo_2_caption: fields.text({ label: 'Photo 2 caption' }),
      },
    }),

    dry_tri: singleton({
      label: 'Dry Tri page',
      path: 'src/content/pages/dry_tri',
      format: { contentField: 'body' },
      schema: {
        headline: fields.text({ label: 'Headline' }),
        intro: fields.text({ label: 'Intro', multiline: true }),
        body: fields.markdoc({ label: 'Body' }),
        courses: fields.array(
          fields.object({
            name: fields.text({ label: 'Course name', validation: { isRequired: true } }),
            legs: fields.text({ label: 'Legs' }),
            start: fields.text({ label: 'Start time' }),
          }),
          { label: 'Courses (2025 format)', itemLabel: (p) => p.fields.name.value || 'Course' },
        ),
        roll_photo: optionalContentImage('Roll photo', 'photos'),
        roll_photo_alt: fields.text({ label: 'Roll photo alt text' }),
        ride_photo: optionalContentImage('Ride photo', 'photos'),
        ride_photo_alt: fields.text({ label: 'Ride photo alt text' }),
        run_photo: optionalContentImage('Run photo', 'photos'),
        run_photo_alt: fields.text({ label: 'Run photo alt text' }),
        register_url: fields.url({ label: 'Registration URL' }),
        results_url: fields.url({ label: 'Latest results URL' }),
      },
    }),

    nav: singleton({
      label: 'Navigation',
      path: 'src/content/nav',
      schema: {
        top_links: fields.array(
          fields.object({
            label: fields.text({ label: 'Label', validation: { isRequired: true } }),
            href: fields.text({ label: 'href', validation: { isRequired: true } }),
          }),
          { label: 'Top nav links' },
        ),
      },
    }),

    site_meta: singleton({
      label: 'Site metadata',
      path: 'src/content/site_meta',
      schema: {
        title: fields.text({ label: 'Site title', defaultValue: 'Twin Cities Ski Club' }),
        description: fields.text({ label: 'Default meta description', multiline: true }),
        og_image: fields.image({ label: 'Default OG image', directory: 'public/og', publicPath: '/og/' }),
      },
    }),
  },

  collections: {
    coaches: collection({
      label: 'Coaches',
      path: 'src/content/coaches/*',
      slugField: 'slug',
      format: { contentField: 'bio' },
      schema: {
        slug: fields.slug({ name: { label: 'Name (display)' } }),
        role: fields.text({ label: 'Role line', validation: { isRequired: true } }),
        photo: contentImage('Coach photo', 'coaches'),
        photo_alt: fields.text({ label: 'Photo alt text', validation: { isRequired: true } }),
        bio: fields.markdoc({ label: 'Bio' }),
        credentials: fields.array(fields.text({ label: 'Credential' }), { label: 'Credentials' }),
        order: fields.integer({ label: 'Sort order', defaultValue: 0 }),
      },
    }),

    practice_seasons: collection({
      label: 'Practice seasons',
      path: 'src/content/practice_seasons/*',
      slugField: 'slug',
      schema: {
        slug: fields.slug({ name: { label: 'Season name' } }),
        date_range: fields.text({ label: 'Date range (display)', validation: { isRequired: true } }),
        fee_cents: fields.integer({ label: 'Fee (cents)', validation: { isRequired: true } }),
        summary: fields.text({ label: 'Summary', multiline: true, validation: { isRequired: true } }),
        registration_note: fields.text({ label: 'Registration status line', validation: { isRequired: true } }),
        registration_open: fields.checkbox({ label: 'Highlight registration line (accent color)', defaultValue: false }),
        when: fields.text({ label: 'When (fact line)', validation: { isRequired: true } }),
        where: fields.text({ label: 'Where (fact line)', validation: { isRequired: true } }),
        trips: fields.text({ label: 'Trips (fact line)', validation: { isRequired: true } }),
        order: fields.integer({ label: 'Sort order', defaultValue: 0 }),
      },
    }),

    trips: collection({
      label: 'Trips (marketing pages)',
      path: 'src/content/trips/*',
      slugField: 'slug',
      format: { contentField: 'what_to_expect' },
      schema: {
        slug: fields.slug({ name: { label: 'Trip name' } }),
        location: fields.text({ label: 'Location', validation: { isRequired: true } }),
        dates: fields.text({ label: 'Dates', validation: { isRequired: true } }),
        cost_summary: fields.text({ label: 'Cost summary', multiline: true, validation: { isRequired: true } }),
        signup_deadline: fields.text({ label: 'Sign-up deadline' }),
        capacity: fields.text({ label: 'Capacity' }),
        what_to_expect: fields.markdoc({ label: 'What to expect' }),
        refund_policy: fields.text({ label: 'Refund policy', multiline: true }),
        signup_url: fields.url({ label: 'Sign-up URL (external; Flask app)' }),
        // POLICY: hero photos must come from the consent-cleared pool (the
        // photos collection consent flag only covers that collection).
        hero_photo: optionalContentImage('Hero photo', 'trips'),
        hero_photo_alt: fields.text({ label: 'Hero photo alt text' }),
        order: fields.integer({ label: 'Sort order', defaultValue: 0 }),
      },
    }),

    photos: collection({
      label: 'Photos (mosaic)',
      path: 'src/content/photos/*',
      slugField: 'slug',
      schema: {
        slug: fields.slug({ name: { label: 'Photo identifier' } }),
        image: contentImage('Image', 'photos'),
        alt_text: fields.text({ label: 'Alt text', validation: { isRequired: true } }),
        caption: fields.text({ label: 'Caption', multiline: true }),
        event_tag: fields.select({
          label: 'Event tag',
          options: [
            { label: 'Practice', value: 'practice' },
            { label: 'Birkie', value: 'birkie' },
            { label: 'Sisu', value: 'sisu' },
            { label: 'Travel', value: 'travel' },
            { label: 'Social', value: 'social' },
            { label: 'Race', value: 'race' },
          ],
          defaultValue: 'practice',
        }),
        member_names: fields.array(fields.text({ label: 'Name' }), { label: 'Members in photo' }),
        order: fields.integer({ label: 'Sort order', defaultValue: 0 }),
        show_on_home: fields.checkbox({ label: 'Show on home mosaic', defaultValue: false }),
        photo_consent_recorded: fields.checkbox({
          label: 'Photo consent recorded (required to render)',
          description:
            'Confirm that this photo is covered by the site-use policy documented in migration/CONSENT.md.',
          defaultValue: false,
        }),
      },
    }),

    sponsors: collection({
      label: 'Sponsors',
      path: 'src/content/sponsors/*',
      slugField: 'slug',
      schema: {
        slug: fields.slug({ name: { label: 'Sponsor name' } }),
        logo: contentImage('Logo', 'sponsors'),
        tier: fields.select({
          label: 'Tier',
          options: [
            { label: 'Trailblazer', value: 'trailblazer' },
            { label: 'Community Partner', value: 'community_partner' },
            { label: 'Supporter', value: 'supporter' },
          ],
          defaultValue: 'supporter',
        }),
        url: fields.url({ label: 'URL' }),
        order: fields.integer({ label: 'Sort order', defaultValue: 0 }),
      },
    }),

    wax_entries: collection({
      label: 'Wax Room entries',
      path: 'src/content/wax_entries/*',
      slugField: 'slug',
      format: { contentField: 'body' },
      schema: {
        slug: fields.slug({ name: { label: 'Title' } }),
        date: fields.date({ label: 'Date', validation: { isRequired: true } }),
        author_name: fields.text({ label: 'Author name' }),
        author_role: fields.select({
          label: 'Author role',
          options: [
            { label: 'Coach', value: 'coach' },
            { label: 'Member', value: 'member' },
            { label: 'Board', value: 'board' },
          ],
          defaultValue: 'coach',
        }),
        lede: fields.text({ label: 'Lede paragraph', multiline: true }),
        body: fields.markdoc({ label: 'Body' }),
        // POLICY: photos must come from the consent-cleared pool (the photos
        // collection consent flag only covers that collection).
        photo: optionalContentImage('Photo (optional)', 'wax'),
        photo_alt: fields.text({ label: 'Photo alt text' }),
        conditions_snapshot: fields.object(
          {
            location: fields.text({ label: 'Location' }),
            temp_f: fields.integer({ label: 'Temp (°F)' }),
            wax_used: fields.text({ label: 'Wax used' }),
          },
          { label: 'Conditions snapshot (optional)' },
        ),
      },
    }),
  },
});
