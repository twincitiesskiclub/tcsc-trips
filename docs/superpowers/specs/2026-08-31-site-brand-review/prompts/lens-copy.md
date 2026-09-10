you are one of six lens reviewers in a brand consistency, elevation, and de-slop audit of twincitiesskiclub.org, the Twin Cities Ski Club marketing site (Astro + Tailwind, under /workspace/tcsc-trips/site). you are read-only: do not edit any file except your output file. do not run git commands that change state. do not start or stop docker containers.

## your lens
copy: voice per the july 18 copy refresh spec: plain register, concrete activities over values, direct verbs, at most one playful ski reference per surface, no slogan structures, no invented facts; no em dashes anywhere (commas, periods, middots instead); no exclamation points; sentence case (this brand is not lowercase); CTA labels in all three registration states across all four render sites (nav, mobile panel, hero, CTA strip) and the dates line; season card notes; meta descriptions (site/src/lib/metaDescription.ts, under 155 characters, no mid-thought truncation); alt text and captions in site/src/content/photos and coaches; 404 copy; footer and nav labels; the racing table's date labels; anything that repeats itself across pages

## the brand (read all of these first, in this order)
- /workspace/tcsc-trips/DESIGN.md  (v1 contract; you may propose changes to it. its "Theme" section names the two scenes the site reads for; its "Banned" list is the de-slop baseline)
- /workspace/tcsc-trips/docs/superpowers/specs/2026-08-31-site-brand-review-design.md (the spec: "goal", "contract posture", "non-goals", "finding schema")
- /workspace/tcsc-trips/docs/superpowers/specs/2026-06-11-marketing-site-design-feedback-design.md and 2026-07-10-marketing-site-feedback-round-2-design.md (what was accepted and rejected in the last two rounds, and why; do not re-propose a rejected item without a new argument)
- /workspace/tcsc-trips/docs/superpowers/specs/2026-07-18-marketing-copy-refresh-design.md (the voice rules)

fixed identity (never propose changing these): the nine color tokens in site/tailwind.config.ts; Archivo Variable for body and PolySans BulkyWide for display; no serif, no mono; real consented club photos only; the Live Conditions strip.

## your rubric
none. the rubric is /workspace/tcsc-trips/docs/superpowers/specs/2026-07-18-marketing-copy-refresh-design.md "voice rules" plus the accepted and rejected copy decisions in the two feedback specs.
treat the skill as a method and a quality gate, not the brief. where it says to add a library, ignore that. where it says "louder", "massive", "cinematic", or "viewport-scale", translate to this brand: navy, mint, paper; quiet ledger language; hairline rules; near-zero motion. the reference set is Tracksmith and Patagonia (photography, voice, and color carry the warmth; the type stays a grotesque). not awwwards showcase sites.

## what to sweep
every row in /workspace/tcsc-trips/docs/superpowers/specs/2026-08-31-site-brand-review/state-matrix.md. screenshots are in /workspace/tcsc-trips/docs/superpowers/specs/2026-08-31-site-brand-review/screens/before/ (view them with the Read tool; both viewports, three for the hero). for each state, read the code that renders it too:
- pages: site/src/pages/*.astro, site/src/pages/trips/index.astro, site/src/pages/wax-room/*.astro
- layouts: site/src/layouts/BaseLayout.astro, InnerPageLayout.astro
- components: site/src/components/*.astro (all of them), and the two client scripts LiveConditions.client.ts, PhotoMosaic.client.ts (read-only context; they are sacred)
- tokens and global css: site/tailwind.config.ts, site/src/styles/global.css
- content and copy: site/src/content/** (pages/*.mdoc and *.yaml, coaches, photos, practice_seasons, sponsors, nav.yaml, site_meta.yaml), site/src/lib/registrationCopy.ts, site/src/lib/metaDescription.ts, site/src/components/heroFacts.ts
- og image: site/public/og/og-default.jpg

if you need to see a state live (hover, focus, motion), serve a build and drive the remote browser: from /workspace/tcsc-trips/scripts/brand-review run `node serve-dist.mjs open --port 4414` in the background (builds: open, soon, closed, populated), then write a small node script in a scratch directory that imports { getBrowser } from /workspace/tcsc-trips/scripts/brand-review/browser.mjs (run it with `node` from that directory so playwright-core resolves) and opens http://127.0.0.1:4414/. the conditions fetch goes to http://127.0.0.1:4499/conditions/live (fixture api; start it with `node fixture-api.mjs` if it is not up). kill your server when done.

## three mandates, equal weight
1. consistency: where does this surface disagree with DESIGN.md, or with another surface? (kind: drift)
2. elevation: where would raising the standard make this something we'd put next to Tracksmith without flinching? (kind: elevation). be concrete. "more whitespace" is not a finding; "increase SectionBand's navy y-padding from py-20 to py-28 on desktop so the mission panel breathes (DESIGN.md: 96-144px on home)" is.
3. de-slop: where does this read as a template or AI default, or where does the code duplicate instead of reuse? (kind: slop). cite the skill rule that names the pattern. examples: identical padding on every band, `→` outside the home hero CTA, a three-up grid, hover-lift on a non-interactive element, a class string copied across pages instead of a component prop, dead rules in global.css.

## output
write /workspace/tcsc-trips/docs/superpowers/specs/2026-08-31-site-brand-review/lens-copy.md:

1. `# lens: copy` and a five-line summary: the three biggest problems, the one biggest opportunity, and your overall read of this lens in one sentence.
2. `## findings`, one block per finding, using exactly this schema:

### CP-<n>
- surface: <surface> / <state> / <mobile|tablet|desktop|all>
- kind: drift | elevation | slop
- severity: P1 | P2 | P3
- contract: <DESIGN.md clause, quoted, or "proposed: <new clause>">
- evidence: <file:line> and/or <screenshot filename>
- observation: <what is, one or two sentences>
- proposal: <what should be, concrete: token, value, copy, layout>
- workstream: foundations | copy | motion-components | sections

severity: P1 = a normal visitor sees it as broken or inconsistent, or it fails WCAG AA. P2 = a designer notices. P3 = polish.
workstreams: foundations owns global.css, tailwind.config.ts, type scale, spacing rhythm, dividers, contrast. copy owns strings in site/src/content and the copy helpers. motion-components owns transitions, keyframes, reduced-motion, component consolidation, class dedup, dead css. sections owns the structure of HeroHome, HeroInner, SectionBand, MissionPanel, SeasonsGrid, CTAStrip, Footer, PhotoMosaic, CoachEntry, SponsorWall, TripsTable, WaxRoomFeed, WaxEntry, LiveConditions.astro markup, and the pages.

3. `## proposed contract changes`: each DESIGN.md change you want, one per line, with the finding ids that need it. only the synthesis agent edits DESIGN.md; you propose.

aim for completeness over brevity: sweep every state, every viewport, and the og image. dedupe within your own file. write in lowercase, short sentences, no em dashes. when you finish, reply with only the five-line summary.
