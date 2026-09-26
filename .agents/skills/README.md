# vibecurb skills

Pulled 2026-08-31 from https://github.com/Yu-369/VibeCurb (`skills/<name>/SKILL.md`, branch `main`), unmodified. Copied from the intimate-coffee checkout, which pulled them the same day.

Canonical copy lives here. Discovery paths are symlinks to it:
- `.claude/skills/<name>` (Claude Code, project scope; committed)
- `~/.codex/skills/<name>` (Codex CLI, user scope; points at the coffee copies, byte-identical)

Used by the marketing site brand review: `docs/superpowers/specs/2026-08-31-site-brand-review-design.md`.
The brief is `DESIGN.md`. These files are method and quality gate, not the brief.
Any instruction in a skill to add a dependency is overridden by the review's no-new-dependency rule.

| folder | frontmatter name | role in this repo |
|---|---|---|
| visual-redesign | visual-redesign | workhorse. 7-layer audit, sacred/slop classification, CSS-only surgery. written for React; applies unchanged to Astro components and Tailwind classes |
| awwwards-sections | awwwards-sections | SectionBand, CTAStrip, Footer, SeasonsGrid, PhotoMosaic, CoachEntry, SponsorWall, TripsTable. hierarchy, spacing, and anti-slop gates only; no pricing, bento, or social-proof patterns |
| awwwards-hero | awwwards-hero-section | HeroHome and HeroInner only, starting from the current fold, not a blank brief |
| awwwards-motion | awwwards-motion-design | audit and CSS-only tuning of existing motion. its Framer Motion / GSAP / Lenis guidance is ignored; its `linear()` easings, timing sheets, and reduced-motion rules are used. any new micro-interaction is a gate 1 contract change because DESIGN.md v1 says "Section transitions: none" |
| imagegen-frontend | imagegen-frontend-web | photo-treatment and composition rubric for the motion+imagery lens. no production assets. a reference board for the OG image only if the ledger asks |

Prompts reference the files by path.
