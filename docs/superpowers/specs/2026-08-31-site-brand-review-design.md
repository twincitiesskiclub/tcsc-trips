# Marketing site brand review: design

*2026-08-31. Multi-agent audit, elevation, and de-slop pass over every page of twincitiesskiclub.org (the Astro site under `site/`). Fable agents audit and verify; Codex `gpt-5.6-sol` at reasoning `max` implements; the VibeCurb skill set is the method and quality gate for the build phase. Rob approved approach B on 2026-08-31. Modeled on the intimate.coffee review of the same date (`intimate-coffee/docs/superpowers/specs/2026-08-31-brand-consistency-review-design.md`), trimmed for a static site with no auth, emails, or PDFs.*

## Goal

The site is at a solid v1 (site 2.1, PR #220, plus the June and July feedback rounds and the July 18 copy refresh). This effort evolves it into something the club is proud of: no rough edges, one brand language on every page, and a design that is better than v1, not merely more uniform.

Two mandates, weighted equally:

1. **Evolution.** Raise every surface to the standard `DESIGN.md` describes. Where the contract is holding the site back, change the contract.
2. **De-slop.** Remove vibe-coded patterns. Visual: uniform card grids, icon+heading+paragraph repeats, `→` on every link, identical padding on every section, decorative gradients, hover-lift on everything, eyebrow labels as section grammar. Code: one-off markup where a component exists, duplicated class strings, spacing values that differ by page for no reason, dead CSS.

### Contract posture

`DESIGN.md` (repo root) is the brief, and it is mildly mutable.

Fixed (identity):
- the color tokens in `tailwind.config.ts` (navy, navy-deep, mint, mint-deep, coral, paper, paper-card, ink, slate)
- the two type families: Archivo Variable for body and PolySans BulkyWide (licensed) for display; no serif, no mono
- real, consented club photography only; no stock, no generated production imagery, no decorative vectors
- the Live Conditions strip as the signature device

Open for synthesis to propose and Rob to approve at gate 1: the motion clause, section rhythm and band sequencing, eyebrow and numbered-marker rules, component shapes, the type scale values, the register split (drenched home / paper inner), and anything the contract is silent on. `DESIGN.md` v2 with a `## changelog from v1` section is a deliverable.

### Non-goals

- No Flask changes. The season and conditions APIs are consumed as they are.
- No new pages or routes. No content-schema (`content.config.ts`) or Keystatic changes.
- No new runtime dependencies. Motion stays CSS. Nothing added to `site/package.json` `dependencies`.
- No JS behavior changes. These files are sacred (the `visual-redesign` term): `registrationState.ts`, `registrationFlip.ts`, `registrationCta.ts`, `seasonData.ts`, `seasonSlug.ts`, `LiveConditions.client.ts`, `PhotoMosaic.client.ts`, `pageScrollLock.ts`, `samePageAnchor.ts`, `conditionsDisplayMode.ts`. Their call sites may be restyled; their logic is untouched.
- No changes to the CSP or other headers in `render.yaml`, apart from enabling previews (below).
- No new photos. Crop and focal-point fixes on existing consented photos are in scope; porting archive photos is not (consent is Rob's call, per the July round).
- Deploy is Rob's call at gate 2.

## Why VibeCurb, and how it is held

The five skills (`awwwards-hero`, `visual-redesign`, `awwwards-motion`, `imagegen-frontend`, `awwwards-sections`) from https://github.com/Yu-369/VibeCurb are generative by default. Pointed at a restrained navy/mint/paper site whose July feedback round rejected a carousel by citing "Section transitions: none," they make it louder unless held. So:

- `DESIGN.md` is the brief. The skill files are the method and the quality gate, never the brief.
- `visual-redesign` is the workhorse on every surface. Its sacred/slop classification and seven-layer audit (tokens, typography, spacing, color, components, atmosphere, motion) are exactly the de-slop mandate. It is written for React; its audit applies unchanged to Astro components and Tailwind classes.
- `awwwards-sections` audits and rebuilds supporting surfaces. Its anti-slop audit (no generic 3-card grids, no icon+heading+paragraph repeats) is used; its pricing, bento, and social-proof patterns are not.
- `awwwards-hero` applies to the home fold (`HeroHome`) and `HeroInner` only. The home fold is the strongest screen on the site (July round: "stays"); the hero agent starts from the current fold and the gestalt findings, not a blank brief.
- `awwwards-motion` audits and tunes existing motion. Its Framer Motion, GSAP, and Lenis guidance is ignored; its CSS `linear()` easings, timing sheets, and reduced-motion rules are used. It may propose CSS-only micro-interactions; each one is a contract-change row for gate 1 because the current clause forbids scroll reveals.
- `imagegen-frontend` produces no production assets on this site. It is a photo-treatment and composition rubric for the motion+imagery lens, and it may be used to generate a reference board for the OG image only if the ledger asks for one. The Gemini pipeline from the coffee project is available for that and nothing else.

Skill files are committed unmodified to `.agents/skills/<name>/SKILL.md` (copied from `intimate-coffee/.agents/skills/`), with `.claude/skills/<name>` symlinks for Claude Code. `~/.codex/skills/<name>` already links to the coffee copies; the content is identical, so Codex needs no relink.

## Scope: surfaces and states

Every row is a screenshot target at mobile (390 x 844) and desktop (1440 x 900). The home hero is also captured at 768 wide (the July focal-point rule checks three widths).

| surface | states |
|---|---|
| `/` | registration open / coming soon / closed; conditions live / dryland / unavailable; wax feed empty / populated; mobile nav open; lightbox open; one scroll capture per section band |
| `/about` | static; registration CTA in each of its three states |
| `/community` | static |
| `/racing` | static |
| `/dry-tri` | static |
| `/extra-training-fun` | static |
| `/coaches` | static (four entries) |
| `/sponsors` | static (two sponsors; tier headings) |
| `/trips` | empty (current production) / populated (fixture) |
| `/wax-room` | empty / populated (fixture) |
| `/wax-room/[slug]` | one fixture entry |
| `/404` | static |
| OG image | `public/og/og-default.jpg`, the only one |
| shared components | `Nav`, `MobileNavPanel`, `LiveConditions` (full and compact), `SectionBand` (navy, paper, paper-on-navy), `MissionPanel`, `SeasonsGrid` (navy and paper), `CTAStrip`, `Footer`, `HeroHome`, `HeroInner`, `PhotoMosaic`, `Lightbox`, `CoachEntry`, `SponsorWall`, `TripsTable`, `WaxRoomFeed`, `WaxEntry` |

State control:
- Registration state: the build reads `PUBLIC_SEASON_API_URL`. The harness runs a fixture server with three JSON responses (open, coming soon, closed) and builds once per state. Every capture asserts `data-season-source="api"` on `<body>`; a `fallback` capture is a harness failure, not a finding.
- Conditions: `PUBLIC_CONDITIONS_API_URL` points at the same fixture server (live, dryland) or is aborted at the browser (unavailable).
- Trips and wax entries: `content/trips/` and `content/wax_entries/` are empty on main. The harness copies fixture entries in before a screenshot build and removes them after. Fixtures live in `scripts/brand-review/fixtures/`; nothing fake is ever committed under `site/src/content/`.

## Artifacts

All under `docs/superpowers/specs/2026-08-31-site-brand-review/`:

```
site-brand-review/
  state-matrix.md            # the table above with urls, build env, and fixture recipe per state
  screens/before/<surface>-<state>-<viewport>.png
  screens/after/<surface>-<state>-<viewport>.png
  lens-typography.md
  lens-color.md
  lens-sections-spacing.md
  lens-copy.md
  lens-motion-imagery.md
  lens-components-slop.md
  gestalt-mobile.md
  gestalt-desktop.md
  ledger.md                  # merged, deduped, ordered findings
  contract-changes.md        # every DESIGN.md v2 change, for Rob's yes/no
  prompts/                   # phase 1, 2, 3 agent prompts as sent
  <workstream>-report.md     # phase 2 output, one per Codex agent
  verification.md            # phase 3 output
```

`DESIGN.md` v2 lives at the repo root, replacing v1, with `## changelog from v1` at the bottom.

Harness in `scripts/brand-review/` (repo root, mirroring the coffee layout): fixture server, content fixtures, `states.mjs`, `screenshot.mjs`, `browser.mjs`, `run-codex.sh`, `ledger-rows.sh`.

### Finding schema

Every lens and gestalt finding uses this block so synthesis is mechanical:

```
### <LENS>-<n>
- surface: <surface> / <state> / <viewport or all>
- kind: drift | elevation | slop
- severity: P1 | P2 | P3
- contract: <DESIGN.md clause, or "proposed: <new clause>">
- evidence: <file:line> and/or <screenshot filename>
- observation: <what is, one or two sentences>
- proposal: <what should be, concrete: token, value, copy, layout>
- workstream: foundations | copy | motion-components | sections
```

- `drift`: the site disagrees with the contract.
- `elevation`: the contract itself, or the site where the contract is silent, should be raised.
- `slop`: a pattern that reads as template or AI default, or code that duplicates instead of reusing. Cite the skill rule that names it.

Severity: P1 = visibly broken or inconsistent to a normal visitor, or fails WCAG AA; P2 = a designer notices; P3 = polish.

The ledger reuses the block and adds `id: L-<nnn>`, `sources: [<lens ids>]`, and `status`.

## Phase 1: audit (Fable, read-only, parallel)

### Step 0 (me, before any agent runs)

1. Copy the five skill files into `.agents/skills/` and add `.claude/skills` symlinks.
2. Land the `render.yaml` preview change on `main` via its own PR (see Preview below). It is the only thing that touches `main` before gate 2.
3. Write the fixture server (three season responses, two conditions responses) and the trips / wax content fixtures.
4. Adapt the coffee screenshot harness for Astro: build per registration state with `PUBLIC_SEASON_API_URL` pointed at the fixture server, serve `site/dist` with `astro preview`, capture through the sibling Playwright container (`intimate-brand-browser`, `ws://127.0.0.1:3333/`, already running and sharing this container's network namespace). Assert `data-season-source="api"` on every capture.
5. Write `state-matrix.md`.
6. Run the full before-capture and commit the screens.
7. Write the eight phase 1 prompts from one template and save them under `prompts/`.

### Agents

Nine Fable agents. Eight run in parallel, one after.

**Six lens agents.** Each receives: `DESIGN.md` v1; the June and July feedback specs and the July 18 copy refresh spec (they record which critiques were accepted and rejected, and why); `state-matrix.md`; the before-screenshots; the matching skill file(s) as rubric; the finding schema. Each sweeps every surface in the matrix and writes `lens-<name>.md` with findings in the schema plus a `## proposed contract changes` section.

| lens | rubric | looks at |
|---|---|---|
| typography | `visual-redesign` | every type role vs the scale table; display-cut count per page (max 2-3); measure caps (62ch paper, 56ch navy); reversed-type line-height bonus; eyebrow count per page (max 2, and only when informative); heading hierarchy per route |
| color | `visual-redesign` | token use vs raw values; WCAG AA on every real text/background pairing; coral count per page (max 4); mint used directly on paper (banned); navy/paper register discipline per route; focus ring color per surface |
| sections + spacing | `awwwards-sections`; `awwwards-hero` for `HeroHome` and `HeroInner` only | vertical rhythm variance (the contract requires 96-144 / 64-104 ranges, not one value); asymmetric two-up splits; band sequencing per page; card-shape audit (none on home); nested cards (banned); hero composition at 390 / 768 / 1440 with faces clear of the text block |
| copy | the July 18 voice rules and the two feedback specs; no VibeCurb skill | plain register; no em dashes; no exclamation points; one playful ski reference per surface; CTA labels in all three registration states across all four render sites; meta descriptions (`metaDescription.ts`, under 155 chars); alt text and captions; 404 copy; no invented facts |
| motion + imagery | `awwwards-motion`; `imagegen-frontend` as photo-treatment rubric only | every transition and keyframe vs the motion clause; hero entrance; mosaic hover scrim; lightbox; conditions refresh flicker; `prefers-reduced-motion` on each; transform/opacity only; crop and `object-position` audit of every `object-cover` image at both viewports; OG image composition |
| components + slop | `visual-redesign` sacred/slop classification; `awwwards-sections` anti-slop audit | one-off markup vs an existing component; duplicated class strings across pages; per-page spacing utilities that should be shared; dead rules in `global.css`; `→` outside the home hero CTA; icons in CTAs or headings; any three-up grid; stat boxes; pill badges; anything on the `DESIGN.md` banned list |

**Two gestalt agents** (mobile, desktop). Each walks every state in the matrix with the harness, reviews the before-screenshots for its viewport, and judges feel against the Theme section of `DESIGN.md` (the kitchen-table Tuesday evening and the sponsor's Monday morning). The question per surface: what would make this one we'd put next to Tracksmith or Patagonia without flinching? Findings use the same schema, mostly `kind: elevation`. Both must state a verdict on the home fold explicitly.

**One synthesis agent** (after the eight). Inputs: all eight files. Outputs:

1. `ledger.md`: deduped (same surface + same observation merges; `sources` keeps the lens ids), ordered by severity then workstream, every row assigned exactly one workstream.
2. `DESIGN.md` v2: a rewrite of the contract as the site should be. Accepts or rejects each proposed contract change with a one-line reason. Keeps the fixed identity items above verbatim. Adds any clause the ledger needs that v1 lacked (OG image, 404, empty-state rules for trips and wax room, per-state CTA copy). Ends with `## changelog from v1`.
3. `contract-changes.md`: the changelog as a checklist for Rob, one line each, with the ledger ids each change unlocks.

Only synthesis writes to `DESIGN.md`. Lens and gestalt agents propose.

### Gate 1 (Rob)

Rob reviews `contract-changes.md` and `ledger.md`. Strikes any change or row he doesn't want. Approves `DESIGN.md` v2. Nothing in phase 2 starts before this.

## Phase 2: implementation (Codex `gpt-5.6-sol`, reasoning `max`)

Four workstreams, one Codex agent each, each in its own git worktree on a branch off `site/brand-review`. Nothing branches from or merges to `main`; every commit on `main` is a Render deploy of both services.

| # | branch | workstream | skills | owns |
|---|---|---|---|---|
| 1 | `brand/foundations` | tokens, type scale, tracking, weights, spacing rhythm, dividers, contrast fixes | `visual-redesign` | `site/src/styles/global.css`, `site/tailwind.config.ts`, shared type and spacing utilities, per-surface class fixes that only change a token or scale value |
| 2 | `brand/copy` | every string on every surface | none | `site/src/content/**`, `registrationCopy.ts` strings, `metaDescription.ts`, `heroFacts.ts`, alt and caption fields, 404 copy |
| 3 | `brand/motion-components` | timing, easing, reduced-motion, CSS-only micro-interactions the ledger approved; component consolidation; class dedup; dead CSS | `awwwards-motion`, `visual-redesign` | transitions and keyframes; extracting repeated markup into existing components; removing dead rules |
| 4 | `brand/sections` | page and component structure | `awwwards-hero`, `awwwards-sections`, `visual-redesign` | `HeroHome`, `HeroInner`, `SectionBand`, `MissionPanel`, `SeasonsGrid`, `CTAStrip`, `Footer`, `PhotoMosaic`, `CoachEntry`, `SponsorWall`, `TripsTable`, `WaxRoomFeed`, `WaxEntry`, `LiveConditions.astro` markup, and the `pages/*.astro` files |

### Launch

```
bash scripts/brand-review/run-codex.sh <workstream>
```

Creates `.worktrees/brand-<ws>` on `brand/<ws>` from `site/brand-review`, symlinks `site/node_modules`, and runs `codex exec -C <worktree> -c model_reasoning_effort="max" - < prompts/codex-<ws>.md` under nohup with the log in the scratchpad. Prompts are fed on stdin (a `codex exec` file-argument does not work; noted from the August SDD sessions).

Each prompt carries: `DESIGN.md` v2 in full; only that workstream's ledger rows; the skill file(s) it may use, in full; the before-screenshots for its surfaces; `state-matrix.md`; the harness usage; and the rules below.

### Rules every Codex prompt enforces

- Presentation only. No JS behavior, no new dependencies, no schema, no API, no header changes. The sacred file list is in the prompt verbatim.
- Every change cites a ledger id. Changes without one are not allowed; new findings go in a `## proposed` section of the report instead of being fixed.
- Follow the skill's pipeline: extract from the contract, gate, build, verify by screenshot, reject drift.
- `npm run check`, `npm run build`, `npm run test:refinement`, `npm run test:sponsors`, and `npm run test:fallback` pass (run from `site/`) before the agent reports done. A build must report `data-season-source="api"` when the fixture server is up.
- An after-screenshot for every touched state at both viewports, saved to `screens/after/` with the same filenames as `before/`.
- Report file `<workstream>-report.md`: per ledger id, `fixed` (with file:line) or `skipped` (with reason).
- Commit on the branch with conventional messages. Do not merge. Do not touch `main`.

### Merge order

1 → 2 → 3 → 4 into `site/brand-review`. Workstream 4 starts in parallel with the others but rebases onto the merged 1-3 before its final screenshot pass, since sections depend on the tokens and type landing first. Conflicts in `global.css` and `tailwind.config.ts` are expected between 1 and 3 and are resolved by me at merge time.

## Preview before go-live

Two layers, both before anything reaches `main`.

**Render preview (the one to share).** `render.yaml` gains pull-request previews on the `tcsc-team-site` static service. That is a small blueprint change and lands on `main` via its own PR in step 0; it changes nothing about the live site. The PR from `site/brand-review` to `main` then gets a Render-built preview URL using the production build command, `PUBLIC_*_API_URL` values, and headers, including the live `/api/season` fetch. This is what Rob and leadership walk before gate 2. If Render's blueprint field for static-site previews turns out to be unavailable on the current plan, the fallback is a second static service pinned to the `site/brand-review` branch, created through the Render MCP and deleted after merge.

**Container preview (fast iteration).** `astro preview` on the merged branch, served through `preview.eaer.app` (the fixed-port proxy already in place for the brainstorm companion, pointed at the preview port). Used between Codex rounds so a worktree can be looked at without waiting for a Render build. Never hand out a `localhost` link.

Merge to `main`, which is the deploy, happens only at gate 2.

## Phase 3: verification (Fable)

Three agents on `site/brand-review` after the merges:

- **Two adversarial reviewers**, workstreams 1+2 and 3+4. For every `fixed` ledger id: read the diff, confirm it satisfies the cited contract clause, take a fresh screenshot (not the Codex agent's), and mark `verified` / `not fixed` / `regressed`. Also scan the whole diff for anything the rules forbid: a sacred file changed, a dependency added, a change with no ledger id, a raw color or size outside the tokens.
- **One cross-page consistency agent.** Repeats the gestalt walk at both viewports on the merged build, diffs before/after, and answers the only question that matters: is it one brand on every page, and is it better? States a verdict on the home fold explicitly.

Output: `verification.md` with the final ledger status and a merge recommendation. Anything `not fixed` or `regressed` goes back to the owning Codex worktree as a follow-up prompt, at most two rounds. After two rounds, remaining items are listed as deferred with reasons.

### Gate 2 (Rob)

Rob reviews the PR, `verification.md`, the before/after screens, and walks the Render preview. Merge to `main` is the deploy and is his call.

## Success criteria

- Every P1 in the ledger is `verified`.
- Every `slop` row is `verified` or explicitly deferred with a reason.
- Every text/background pairing on every page passes WCAG AA.
- No raw color and no ad-hoc font size outside the tokens on any page. `global.css` and `tailwind.config.ts` are the only places a value is defined.
- Every `object-cover` image has a deliberate `object-position` at both viewports; no cropped faces.
- `npm run check`, `npm run build`, `test:refinement`, `test:sponsors`, `test:fallback` pass; no new entry in `site/package.json` `dependencies`.
- `data-season-source="api"` on the Render preview.
- The cross-page agent's verdict is one brand, and better; Rob agrees at gate 2.

## Risks

- **Skills make it louder.** Mitigated by contract-as-brief, presentation-only rules, no-dependency rule, contract changes gated at gate 1, and the adversarial pass reading diffs against the contract.
- **Home fold regression.** Mitigated by the hero agent starting from the current fold, both gestalt agents and the cross-page agent stating a fold verdict, and three-width screenshots before and after.
- **Season fetch fails during a screenshot build.** Mitigated by the fixture server and the `data-season-source` assertion on every capture.
- **`global.css` / `tailwind.config.ts` conflicts** between workstreams 1 and 3. Mitigated by merge order and my resolving conflicts rather than the agents.
- **Render preview field.** Step 0 verifies it on the blueprint; the branch-pinned second service is the fallback.
- **Accidental deploy.** No branch is created from `main` except the preview-enabling PR; `run-codex.sh` branches from `site/brand-review` and the prompt forbids touching `main`.
- **Cost.** Roughly 9 + 3 Fable agents, 4 Codex agents at max reasoning, plus up to two rework rounds. Phases are separate fan-outs with a human gate between them, so spend is bounded per phase.

## Questions answered

| question | answer |
|---|---|
| Is `DESIGN.md` fixed or mutable? | Mildly mutable (Rob, 2026-08-31). Identity fixed; everything else open at gate 1. |
| Who implements? | Codex `gpt-5.6-sol`, reasoning `max`, one agent per workstream (Rob). |
| Per-page or per-lens agents? | Per-lens for audit, per-workstream for build. Consistency is cross-page; per-page agents can't see it, and per-page implementers would each touch the shared components. |
| Preview before go-live? | Yes (Rob). Render PR preview on the integration branch, plus `preview.eaer.app` for iteration. |
| Gemini imagery? | Reference boards for the OG image only, if the ledger asks. No production assets; the contract requires real photos. |
| New motion library? | No. Non-goal. Micro-interactions are CSS-only and each is a gate 1 contract change. |
