you are implementing one workstream of a brand consistency, elevation, and de-slop pass on twincitiesskiclub.org, the Twin Cities Ski Club marketing site: Astro 7 static site + Tailwind 4 under site/ in this repo. you are working in a git worktree on branch brand/{{WORKSTREAM}}, branched from site/brand-review. commit on this branch; never merge, never push, never touch other branches, never touch main. do not stop or start docker containers.

## your workstream: {{WORKSTREAM}}
{{WORKSTREAM_DESCRIPTION}}

## the contract (read in full, first)
DESIGN.md at the repo root is the v2 contract. its "Theme" section names the two scenes the site reads for. docs/superpowers/specs/2026-07-18-marketing-copy-refresh-design.md holds the voice rules. every change you make must move the site toward these.

## your ledger rows
these are the only changes you may make. each row cites the contract clause it implements.

{{LEDGER_ROWS}}

## your method
{{SKILLS}}
read the whole skill file. run its pipeline: extract the target from the contract; gate (does the proposal serve the two scenes and the quiet register?); build; verify by screenshot; reject drift (anything in your diff that isn't a ledger row gets reverted). where the skill says to add a library, ignore it. where it says "louder", "massive", "cinematic", or "viewport-scale", translate to this brand: navy, mint, paper; hairline rules; near-zero motion.

## hard rules
- presentation only: astro component markup and classes, css in site/src/styles/global.css, tokens in site/tailwind.config.ts, copy strings under site/src/content and in the copy helpers. no js behavior changes. these files are sacred and must not be edited: site/src/lib/registrationState.ts, registrationFlip.ts, seasonData.ts, seasonSlug.ts, pageScrollLock.ts, samePageAnchor.ts, conditionsDisplayMode.ts, site/src/components/registrationCta.ts, LiveConditions.client.ts, PhotoMosaic.client.ts. also untouchable: site/src/content.config.ts, site/keystatic.config.ts, site/astro.config.mjs, render.yaml, anything outside site/ except your report and screenshots.
- no new dependencies. site/package.json and site/package-lock.json must be unchanged.
- every change cites a ledger id in its commit message. if you find something worth fixing that has no ledger id, do not fix it; add it to `## proposed` in your report.
- keep prefers-reduced-motion behavior: global.css collapses every animation and transition under the media query; do not add anything that escapes it.
- copy: no em dashes (use commas, periods, or middots), no exclamation points, sentence case, no invented facts. if a row's proposal contains an em dash, fix the proposal's punctuation, not the rule.
- no photo may be added, replaced, or generated. crop and object-position changes to existing photos are fine when a row asks.
- fixed identity: do not change the nine color token values, the two font families, or the Live Conditions strip's data or behavior.
- tests and build must pass from site/ before you report done: `npm run check`, `npm run build`, `npm run test:refinement`, `npm run test:sponsors`, `npm run test:fallback`. if a test asserts old copy or an old class that a ledger row changes, update the test and cite the row.
- do not edit anything under docs/superpowers/specs/2026-08-31-site-brand-review/ except your report and your after-screenshots.
- nothing fake under site/src/content: the harness copies fixtures in and out for you; if a build fails and leaves sisu-ski-fest.mdoc or first-snow-wax.mdoc behind, delete them before committing.

## verify by screenshot
the harness lives in scripts/brand-review (node_modules is linked into your worktree). the fixture api is shared on port 4499 (`curl -s http://127.0.0.1:4499/season/open | head -c 80`; if it is down, `nohup node fixture-api.mjs &` from that directory). to see your branch:
  cd scripts/brand-review
  node build-state.mjs open          # also: soon, closed, populated. rebuild after every change you want to see
  PORT={{PORT}} node screenshot.mjs after-{{WORKSTREAM}} <stateIds you touched>
state ids are in scripts/brand-review/states.mjs; the matrix is docs/superpowers/specs/2026-08-31-site-brand-review/state-matrix.md. your port is {{PORT}}; other workstreams use other ports, so never use 4400 to 4405 for anything else. the before screenshots are on this machine at /workspace/tcsc-trips/docs/superpowers/specs/2026-08-31-site-brand-review/screens/before/ (the main checkout; screens are not committed). compare each after image against the before image with the same filename. look at them. if a change reads louder, busier, or more generic than before, it fails the gate: revert and try a quieter version. leave no serve-dist.mjs process running when done (`pkill -f "serve-dist.mjs .* --port {{PORT}}"`).

## report
write docs/superpowers/specs/2026-08-31-site-brand-review/{{WORKSTREAM}}-report.md:
- `# {{WORKSTREAM}} report`
- `## rows`: one line per ledger id: `L-nnn: fixed (<file:line>, <commit sha>)` or `L-nnn: skipped (<reason>)`.
- `## screens`: list of after screenshots you produced (they live in screens/after-{{WORKSTREAM}}/ in your worktree; screens are gitignored, so do not try to commit them).
- `## proposed`: anything you noticed that has no ledger id.
- `## test/build`: paste the last line of each of the five commands.
commit the report on your branch as the last commit.

work through the rows in ledger order (P1 first). commit small and often: one commit per row or per tightly related group, message `brand({{WORKSTREAM}}): <what> (L-nnn)`.
