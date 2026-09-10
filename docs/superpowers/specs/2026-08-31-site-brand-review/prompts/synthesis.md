you are the synthesis agent for a brand consistency, elevation, and de-slop audit of twincitiesskiclub.org. eight reviewers have written findings. you merge them, write the ledger, and rewrite DESIGN.md as the v2 contract. you may write only these three files:
- /workspace/tcsc-trips/docs/superpowers/specs/2026-08-31-site-brand-review/ledger.md
- /workspace/tcsc-trips/docs/superpowers/specs/2026-08-31-site-brand-review/contract-changes.md
- /workspace/tcsc-trips/DESIGN.md
do not run git commands that change state. do not start or stop servers or containers.

read, in order: /workspace/tcsc-trips/DESIGN.md (v1), the spec /workspace/tcsc-trips/docs/superpowers/specs/2026-08-31-site-brand-review-design.md (especially "contract posture": what is fixed and what is open), the two feedback specs (2026-06-11 and 2026-07-10 under docs/superpowers/specs/) and the copy refresh spec (2026-07-18), then all eight inputs in /workspace/tcsc-trips/docs/superpowers/specs/2026-08-31-site-brand-review/: lens-typography.md, lens-color.md, lens-sections-spacing.md, lens-copy.md, lens-motion-imagery.md, lens-components-slop.md, gestalt-mobile.md, gestalt-desktop.md. look at screens/before/ (Read tool) when a finding is ambiguous.

## ledger.md
- one block per merged finding. merge when surface + observation are the same thing; keep every source id in `sources`.
- schema: the finding schema from the spec plus `id: L-<nnn>` (zero-padded, sequential), `sources: [<ids>]`, `status: open`. block shape:

### L-<nnn>
- sources: [TY-3, GD-7]
- surface: <surface> / <state> / <mobile|tablet|desktop|all>
- kind: drift | elevation | slop
- severity: P1 | P2 | P3
- contract: <DESIGN.md v2 clause, quoted>
- evidence: <file:line> and/or <screenshot filename>
- observation: <what is>
- proposal: <what should be, concrete>
- workstream: foundations | copy | motion-components | sections
- status: open

- exactly one workstream per row. if a finding needs two, split it into two rows and cross-reference. ownership: foundations owns site/src/styles/global.css, site/tailwind.config.ts, type scale, spacing rhythm, dividers, contrast. copy owns strings under site/src/content and in registrationCopy.ts, metaDescription.ts, heroFacts.ts. motion-components owns transitions, keyframes, reduced-motion, component consolidation, class dedup, dead css. sections owns the structure of HeroHome, HeroInner, SectionBand, MissionPanel, SeasonsGrid, CTAStrip, Footer, PhotoMosaic, CoachEntry, SponsorWall, TripsTable, WaxRoomFeed, WaxEntry, LiveConditions.astro markup, and site/src/pages.
- order: P1 first, then P2, then P3; within a severity, group by workstream.
- when two reviewers disagree, decide using DESIGN.md's "Theme" (the two scenes) and the july round's stated posture (quiet ledger language, hairline rules, near-zero motion) and say which decided it in the observation.
- a row that touches a sacred file (registrationState.ts, registrationFlip.ts, seasonData.ts, seasonSlug.ts, pageScrollLock.ts, samePageAnchor.ts, conditionsDisplayMode.ts, registrationCta.ts, LiveConditions.client.ts, PhotoMosaic.client.ts) or content.config.ts goes under `## rejected` with reason `sacred`, unless the proposal can be met at the call site; then rewrite the proposal that way.
- a row that proposes changing a fixed identity item (the nine tokens, the two fonts, real photos only, the conditions strip) goes under `## rejected` with reason `fixed identity`.
- drop nothing silently. any other rejection goes under `## rejected` with the reason.
- start the file with `## summary`: count by severity, by kind, and by workstream, and the five rows you'd fix first if only five could be fixed.

## DESIGN.md (v2)
rewrite the whole file as the contract for the site we want. keep its section structure (Theme, Color, Typography, Layout, Components, the signature device, Motion, Iconography, Imagery, Banned, Accessibility) so readers of v1 find their way. rules:
- fixed identity items stay verbatim: the token table values, the two font families and the no-serif/no-mono rule, real consented photos only, the Live Conditions section.
- every other token, type role, spacing value, component spec, motion rule: state what it should be. where v1 is right, keep it. where the site is already better than v1, adopt the site. where a reviewer proposed a change and it serves the two scenes, adopt it and cite the finding id in the changelog.
- v1's Typography section still names Söhne and PolySans Median as choices; the site ships Archivo Variable and PolySans BulkyWide (tailwind.config.ts, global.css). describe what ships.
- the motion clause is open. if you admit any new motion, write the exact rule (what, duration, easing, reduced-motion behavior) and keep "no scroll reveals" unless a finding makes the case; the july round rejected a carousel on that clause.
- add clauses v1 lacks and the ledger needs: the og image, the 404 page, empty-state rules for trips and the wax room, the registration CTA copy per state and per render site, meta description length, a contrast floor (WCAG AA on every text pair), the de-slop rules the components-slop lens established (one component per pattern, no duplicated class strings, no dead css).
- every ledger row's `contract:` line must quote a clause that exists in your v2. if a row needs a clause, write the clause.
- end with `## changelog from v1`: one line per change, `- <what changed>: <why> (<finding ids>)`.

## contract-changes.md
the changelog as a checklist for rob: `- [ ] <change>: <why> (unlocks L-nnn, L-nnn)`. one line each. add a two-line note at the top explaining that striking a line rejects that change and its ledger rows move to `## rejected`.

lowercase, short sentences, no em dashes. when you finish, reply with only the `## summary` block of the ledger.
