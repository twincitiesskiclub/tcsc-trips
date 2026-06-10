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
import { config, fields, collection, singleton } from '@keystatic/core';

const requiredImage = (label: string) =>
  fields.image({
    label,
    directory: 'public/images/uploads',
    publicPath: '/images/uploads/',
    validation: { isRequired: true },
  });

export default config({
  storage: { kind: 'local' },

  singletons: {
    home: singleton({
      label: 'Home page',
      path: 'src/content/pages/home',
      schema: {
        hero_headline: fields.text({ label: 'Hero headline', validation: { isRequired: true } }),
        hero_image: requiredImage('Hero photograph'),
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
        cta_open_label: fields.text({ label: 'CTA label when open', defaultValue: 'Register for the season →' }),
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
        headline: fields.text({ label: 'Headline' }),
        intro: fields.text({ label: 'Intro', multiline: true }),
      },
    }),

    contact: singleton({
      label: 'Contact page',
      path: 'src/content/pages/contact',
      schema: {
        email: fields.text({ label: 'Email' }),
        mailing_address: fields.text({ label: 'Mailing address', multiline: true }),
        instagram_url: fields.url({ label: 'Instagram URL' }),
        slack_invite_url: fields.url({ label: 'Slack invite URL' }),
      },
    }),

    nav: singleton({
      label: 'Navigation',
      path: 'src/content/nav',
      schema: {
        top_links: fields.array(
          fields.object({
            label: fields.text({ label: 'Label' }),
            href: fields.text({ label: 'href' }),
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
        role: fields.text({ label: 'Role line' }),
        photo: requiredImage('Coach photo'),
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
        date_range: fields.text({ label: 'Date range (display)' }),
        fee_cents: fields.integer({ label: 'Fee (cents)' }),
        summary: fields.text({ label: 'Summary', multiline: true }),
        what_included: fields.array(fields.text({ label: 'Item' }), { label: 'What is included' }),
      },
    }),

    trips: collection({
      label: 'Trips (marketing pages)',
      path: 'src/content/trips/*',
      slugField: 'slug',
      format: { contentField: 'what_to_expect' },
      schema: {
        slug: fields.slug({ name: { label: 'Trip name' } }),
        location: fields.text({ label: 'Location' }),
        dates: fields.text({ label: 'Dates' }),
        cost_summary: fields.text({ label: 'Cost summary', multiline: true }),
        signup_deadline: fields.text({ label: 'Sign-up deadline' }),
        capacity: fields.text({ label: 'Capacity' }),
        what_to_expect: fields.markdoc({ label: 'What to expect' }),
        refund_policy: fields.text({ label: 'Refund policy', multiline: true }),
        signup_url: fields.url({ label: 'Sign-up URL (external; Flask app)' }),
        hero_photo: fields.image({ label: 'Hero photo', directory: 'public/photos', publicPath: '/photos/' }),
      },
    }),

    photos: collection({
      label: 'Photos (mosaic)',
      path: 'src/content/photos/*',
      slugField: 'slug',
      schema: {
        slug: fields.slug({ name: { label: 'Photo identifier' } }),
        image: requiredImage('Image'),
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
        logo: requiredImage('Logo'),
        tier: fields.select({
          label: 'Tier',
          options: [
            { label: 'Trailblazer', value: 'trailblazer' },
            { label: 'Supporter', value: 'supporter' },
            { label: 'Friend', value: 'friend' },
          ],
          defaultValue: 'supporter',
        }),
        url: fields.url({ label: 'URL' }),
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
        photo: fields.image({ label: 'Photo (optional)', directory: 'public/photos', publicPath: '/photos/' }),
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
