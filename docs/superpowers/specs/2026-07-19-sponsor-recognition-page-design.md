# Sponsor Recognition Page Design

## Summary

Redesign `/sponsors` as a recognition-first page that gives current partners clear, tiered visibility and shows what collective sponsor support makes possible for Twin Cities Ski Club. The page must feel specific to TCSC, avoid inflated fundraising language, and distinguish completed investments from future priorities.

Twin Cities Orthopedics and Kwik Trip are both `Trailblazer Partners`. The page names that tier but does not describe it as the highest level. Sponsorship prices and package details remain private; prospective sponsors contact club leadership at `contact@twincitiesskiclub.org`.

## Success Criteria

- A current sponsor sees its logo and tier immediately after the page introduction.
- A prospective sponsor can understand the club, recent sponsor-enabled work, future priorities, and the contact path within one short scroll.
- Impact copy uses collective attribution (`Sponsor support helped TCSC...`) and never claims that a particular sponsor funded a particular item.
- The page represents training, waxing, travel, community, and racing rather than presenting sponsorship as race-only support.
- The design follows the existing paper-page, navy-band, real-photography, and logo-wall system without introducing tiles or a generic three-card layout.
- The page remains accessible and usable on small screens, with keyboard-visible sponsor links and descriptive image alternatives.

## Information Architecture

The page uses the approved recognition-first order:

1. **Page introduction** — a concise explanation of the role sponsor support plays across the club.
2. **Tiered sponsor recognition** — populated tiers and linked logos, beginning with `Trailblazer Partners`.
3. **Completed impact** — verified examples under the exact framing `Sponsor support helped TCSC...`.
4. **Recognition in use** — the six sponsor-logo jackets and a real Great Bear Chase awards photo.
5. **Future priorities** — coaching capacity, shared wax replacement, and shared equipment, explicitly framed as what continued support can make possible.
6. **Sponsor contact** — the existing public email address in a single CTA strip.

Pricing, package benefits, sponsor testimonials, sponsor-specific funding attribution, and a downloadable rate card are outside this page's scope.

## Approved Copy

### Introduction

- **Headline:** `Our sponsors`
- **Intro:** `Support from our sponsors strengthens the shared resources behind training, team waxing, travel, and race support while helping TCSC keep participation costs in reach.`

### Current sponsor tier

- **Heading:** `Trailblazer Partners`
- Twin Cities Orthopedics and Kwik Trip receive equal visual weight within the tier.
- Do not add `highest level`, contribution amounts, or a tier description.

Future populated tiers use these headings in this order:

1. `Trailblazer Partners`
2. `Community Partners`
3. `Supporters`

### Completed impact

- **Heading:** `Sponsor support helped TCSC...`
- **Intro:** `Recent investments strengthened everyday team activities as well as travel, with shared resources available to racers and non-racers.`

Impact rows:

1. **Host team waxing sessions**  
   `Two team drills support organized waxing sessions, and shared waxing supplies remain available to members whether or not they race.`
2. **Make team travel easier**  
   `Rental vans carried food, equipment, and team supplies to the Pre-Birkie and Great Bear Chase, reducing the logistics handled by volunteer trip leaders.`
3. **Build a useful team base**  
   `A team tent and Birkie start parking created space for waxing, warming up, testing skis, cheering, and moving people and gear.`

### Recognition in use

- **Heading:** `Visible support at team events`
- **Body:** `TCSC purchased six team jackets featuring sponsor logos for use at races and podium photos.`
- **Caption:** `A sponsor-logo team jacket at the Great Bear Chase.`

This is recognition delivered to sponsors, not shared member equipment. It must be visually and semantically separate from the completed-impact rows.

### Future priorities

- **Heading:** `What continued support makes possible`
- **Intro:** `As the team grows, sponsor support gives TCSC flexibility to invest where it can have the most impact.`

Priority rows:

1. **Shared wax resources**  
   `Move the team's shared wax collection away from products containing PFAS, often called forever chemicals.`
2. **Coaching and training capacity**  
   `Add coaches and secure larger training spaces as the team grows.`
3. **Shared team equipment**  
   `Invest in equipment that lowers the upfront cost of participating and helps new members get up to speed.`

These are forward-looking priorities, not restricted-use promises or claims about completed spending.

### Contact

- **Heading:** `Interested in supporting TCSC?`
- **Body:** `Contact club leadership to discuss sponsorship opportunities and current team needs.`
- **CTA label:** `Email club leadership`
- **CTA target:** `mailto:contact@twincitiesskiclub.org`
- **Quiet disclosure:** `Sponsor recognition acknowledges support and does not constitute endorsement of a sponsor's products or services.`

## Visual Design

The page remains an inner paper page and reuses the existing TCSC visual system.

### Sponsor wall

- Place the wall immediately after the intro with generous white space.
- Always show the heading for every populated tier, including when only one tier exists.
- Use a shared, invisible logo footprint so differently shaped marks feel equally prominent within a tier; do not put logos in bordered cards or combine them into a joint lockup.
- Trailblazer logos are larger than lower-tier logos. Community Partner and Supporter sizing steps down without making either tier illegible.
- Linked logos open in the same tab and retain visible focus styles.

### Impact band

- Use one deliberate navy band with mint heading text and paper body text.
- Pair the copy with `site/src/assets/images/photos/rollerski-golden-hour.jpg` to represent year-round group training beyond races.
- Render the three completed outcomes as editorial rows separated by hairlines, not cards or icon boxes.
- Use accurate alternative text: `A large group of TCSC members posing with roller skis and poles after a summer training session.`

### Jacket recognition and future priorities

- Return to paper after the impact band.
- Use an asymmetric editorial split featuring `site/src/assets/images/photos/great-bear-chase.jpg`, cropped so the black TCSC jacket and its Kwik Trip and Twin Cities Orthopedics marks remain clear.
- Use accurate alternative text: `A TCSC member wearing a black team jacket with Kwik Trip and Twin Cities Orthopedics logos beside another member and the Great Bear Chase mascot.`
- Place the jacket statement adjacent to the photo.
- Follow it with the future-priority ledger, separated by a clear section seam and wording that distinguishes planned uses from completed investments.

### Contact strip

- Close with the existing navy/mint/coral `CTAStrip` component.
- Keep one action only: the `mailto:` link.
- Place the quiet non-endorsement disclosure below or immediately adjacent to the CTA content without competing with the action.

## Content Model and Rendering

### Sponsor records

Update the sponsor tier contract in both Astro and Keystatic:

- `trailblazer`
- `community_partner`
- `supporter`

Remove the unused `friend` value. No current record uses it, so no content migration is required. Existing sponsor names, URLs, order, and logo assets remain unchanged.

Move tier metadata and deterministic grouping into a small shared sponsor-tier module. `SponsorWall.astro` consumes that module for both variants:

- `wall`: grouped tiers, populated headings always visible, tier-aware logo sizing.
- `strip`: the existing compact home-page row, no tier headings, same tier/order sorting.

Empty tiers do not render. Items sort by numeric `order`, then entry ID.

Sponsor logo links retain `rel="sponsored"`. Their accessible image text identifies the destination as `<Sponsor name> website`; non-linked logos use the sponsor name alone.

### Sponsors page singleton

Keep the page copy in `src/content/pages/sponsors_page.yaml` so it remains editable through Keystatic. Extend the singleton with:

- `headline`, `intro`
- `impact_heading`, `impact_intro`, `impact_items[]` (`title`, `detail`)
- `recognition_heading`, `recognition_body`, `recognition_caption`
- `priorities_heading`, `priorities_intro`, `priority_items[]` (`title`, `detail`)
- `contact_heading`, `contact_body`, `contact_email`, `contact_cta_label`
- `disclosure`

The two chosen photos remain direct imports because they are established site assets and their selection/crop is part of the page composition. Keystatic does not own or replace these shared files.

Astro's strict content schema and the Keystatic singleton definition must stay synchronized. Required public copy fields fail the build when omitted rather than silently producing an incomplete page.

## Responsive and Empty-State Behavior

- On narrow screens, sponsor logos stack or wrap with equal centered footprints and no horizontal overflow.
- Editorial photo/text splits become single-column, with the photo before its related copy.
- Impact and priority rows remain readable without relying on hover or icons.
- If a future tier is empty, its heading and spacing do not render.
- If all sponsor records are absent, the page still renders its introduction, impact, priorities, and contact CTA without an orphaned tier heading.
- Long sponsor names and wide logos stay within their assigned footprint.

## Accessibility and Semantics

- Preserve one `h1` from `HeroInner`; major sections use `h2`; outcome and priority titles use `h3` or semantically equivalent heading markup.
- Sponsor links are normal keyboard-focusable anchors with the site's existing `:focus-visible` treatment.
- Linked logo alternative text communicates the link destination; editorial photos use the exact descriptive alternatives above.
- Text and rules use existing WCAG-AA brand tokens (`navy`, `mint`, `paper`, `ink`, `mint-deep`).
- The CTA exposes the email purpose in visible text; no icon-only controls or new motion are introduced.

## Testing and Verification

Implementation follows red-green-refactor:

1. Add failing unit tests for tier order, labels, empty-tier omission, deterministic item ordering, and removal of the `friend` tier.
2. Add a failing built-page test for the approved headings/copy, current sponsor links, `rel="sponsored"`, contact address, and absence of public prices or `highest level` language.
3. Implement the smallest tier/model/page changes that make those tests pass.
4. Run `astro check` and the production build.
5. Inspect desktop and mobile renders for hierarchy, cropping, overflow, focus behavior, and heading order.
6. Run an independent adversarial review against this specification, including copy accuracy, unsupported attribution, accessibility, responsive behavior, content-schema parity, and regression risk to the home sponsor strip.
7. Fix all Critical and Important findings, re-run targeted tests, and repeat the final review until clean.
8. Verify the merged `main` branch again before pushing and confirm the production deployment serves the updated page.

Known baseline behavior: local builds warn when the optional `trips` and `wax_entries` collections are empty. Those warnings are pre-existing and are not part of this change.

## Non-Goals

- Publishing tier prices or package benefits.
- Claiming a tax deduction or endorsing sponsor products or services.
- Attributing a specific purchase to TCO or Kwik Trip individually.
- Adding sponsor testimonials, lead forms, analytics, UTM parameters, start/end dates, or a downloadable opportunity packet.
- Refactoring unrelated marketing pages or changing the home-page sponsor band beyond preserving compatibility with the updated tiers.
