# Product

## Register

brand

## Users

Three audiences, ordered by frequency:

1. **Prospective members who want to contribute, not just consume.** Adults 21–35 in the Twin Cities looking for a third place — community, training, and shared adventure. They're not shopping for the cheapest practice plan; they want to see whether this is the kind of group they'd show up for. Decisions get made in the first 20 seconds: does this feel like a real club run by real people?
2. **Potential and current sponsors.** Local businesses, ski-industry partners, foundations. They need to see organizational legitimacy quickly — 501(c)(3) status, who the coaches are, who the team is, why supporting TCSC reflects well on them. They land here for due diligence before a board calls them; the site has to read as professional.
3. **Current members + their people.** Returning visitors, parents, friends, partners. They share links, look up upcoming trips, point to the photo wall after a race. The site doubles as proof and pride.

## Product Purpose

A nonprofit ski-club marketing site, replacing a Wix site (`twincitiesskiclub.org`) the club has outgrown. Communicates who TCSC is, the two training seasons, the coaches, the racing program, the trips, and how to join — using language and photography that reflect the real community. Sits alongside the existing Flask registration/practices app at `tcsc.ski` but is fully isolated from it operationally.

Success looks like: a sponsor lands on the site and within 30 seconds has decided TCSC is a real, well-run organization worth supporting; a prospective member lands and feels welcome enough to fill out registration without needing to ask a friend "is this place legit?"; current members reach for the URL when introducing the club to anyone in their life.

## Brand Personality

Three words: **warm, sporty, inclusive.**

The voice (already established on the current Wix site) does the heavy lifting — specific, welcoming, slightly nerdy about skiing (Tour de Finn, Techno Corner, "after-practice brews"). Reads like a member wrote it, not a marketing agency. Design's job is to elevate that voice without overpowering it.

Aesthetic lane: a blend of **Tracksmith** (editorial running brand: heritage feel, real photography, restrained typography, sport-meets-craft) and **Patagonia** (outdoor heritage: real stories, warm photography, no slick marketing). Slightly granola, slightly sophisticated. Not corporate. Not glossy.

The brand identity (navy + mint, with coral accent) is already established and not up for redesign in this engagement — design adapts to it.

## Anti-references

- **Other ski club sites (Loppet Foundation et al).** Volunteer-built, all-caps headings, gallery-heavy, low-information-density. Reads as well-meaning but dated. TCSC should feel professional enough that sponsors don't lump it in with these.
- **Wix / Squarespace template look.** Theme-y, predictable section flow (hero → 3-card grid → parallax photo → footer), drop-shadow-everywhere, slick-but-soulless. Leaving Wix means leaving the look too.
- **Generic SaaS / "AI-templated" marketing.** Inter font everywhere, gradient hero text, stat boxes ("80+ skiers / 2 seasons / 3 coaches"), ✦ pill badges, → arrows on every link, identical 3-column grids, hover-card decoration. If a stranger could guess "AI made that" in two seconds, the page has failed.
- **Corporate non-profit (United Way etc.).** Donate-button-first, stock photography of diverse smiling people, mission-paragraph-everywhere. TCSC's specificity (real names, real races, real after-practice activities) is its strongest defense against this trap.

## Design Principles

1. **Specifics over abstractions.** Every paragraph names a real thing — KJ, Greg, Rebecca; Sisu Ski Fest; the American Birkebeiner; Theodore Wirth; Techno Corner. Generic copy is forbidden. If a sentence could appear on any club's site, rewrite it.
2. **Photography is the proof.** Real members in real moments — Birkie wave starts, costume relays, post-practice gatherings — not stock. The photo mosaic is the centerpiece of the community story, not a teaser. If photography is sparse, design contracts gracefully rather than padding with vector illustrations.
3. **One signature, not many flourishes.** The mint ski-track motif (left-margin scroll trail desktop / hero ambient draw-in mobile) is the only animated brand device. No micro-animations on every card, no hover decorations, no parallax. Restraint is what separates "real brand" from "Squarespace deluxe."
4. **Sponsor-legible in 20 seconds.** A sponsor on a board prep call should be able to assess organizational quality without scrolling past three paragraphs. Mission, two seasons, coaches, racing, sponsors — visible, scannable, not buried under storytelling.
5. **Year-round correctness.** The site looks right in May with no upcoming trips, just as much as November with five. Empty states, seasonal CTA modes, and sparse-content fallbacks are first-class concerns — not "we'll add that later."

## Accessibility & Inclusion

- WCAG AA across all text/UI combinations (the navy+mint+coral palette has been pre-checked: navy/white 14:1, navy/mint 8:1, mint/navy CTA 9:1).
- `prefers-reduced-motion` honored for the ski-track signature animation; reduced-motion users get a static decorative variant.
- Full keyboard navigation: photo mosaic and lightbox usable without a mouse (←/→ navigation, Esc closes, focus rings everywhere).
- Alt text required by Keystatic schema on every image upload — editors can't skip it.
- `photo_consent_recorded` boolean required on every photo collection entry — protects members and reflects the inclusive ethos.
- Touch parity on mobile: no hover-only affordances; tap behavior maps to lightbox open.
- Plain language: the voice is already inclusive; design must not undermine it with jargon or icon-only labels.
