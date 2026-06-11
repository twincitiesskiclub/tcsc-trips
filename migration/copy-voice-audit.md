# TCSC Marketing Site — Copy & Voice Audit

**Audited:** 2026-06-10  
**Source of truth (original voice):** `migration/pages/*.txt` + live site https://twincitiesskiclub.org  
**New site files:** `site/src/content/`, `site/src/pages/*.astro`, `site/src/components/*.astro`

---

## Summary Table

| # | Surface | File(s) | Verdict | Action |
|---|---------|---------|---------|--------|
| 1 | Home hero headline | `content/pages/home.yaml` | INVENTED | Replace — no original basis |
| 2 | Home SectionBand heading "Two seasons. Year-round group ski." | `pages/index.astro:63` | INVENTED | Replace — AI construct |
| 3 | Home CTAStrip heading "Ready to find your winter people?" | `pages/index.astro:69` | INVENTED | Flag — charming but no original; keep or replace |
| 4 | Home CTAStrip subhead "Adults 21-35 · intermediate ability · all paces welcome." | `pages/index.astro:70` | INVENTED | Replace — AI-list flavour; original has real specifics |
| 5 | Home CTA closed label "Member area" | `content/pages/home.yaml:11` | INVENTED | Minor — no original CTA label; acceptable |
| 6 | Home mission paragraph | `content/pages/home.yaml:13-17` | VERBATIM | No action |
| 7 | About headline | `content/pages/about.mdoc:2` | ADAPTED | Fine (original: "ABOUT TWIN CITIES SKI CLUB") |
| 8 | About intro / founding story | `content/pages/about.mdoc:4-11` | VERBATIM | No action |
| 9 | About body copy (Who joins, practices, coaching) | `content/pages/about.mdoc:13-30` | VERBATIM | No action |
| 10 | About SectionBand heading "Two seasons." | `pages/about.astro:25` | INVENTED | Replace — truncated, unexplained |
| 11 | Coaches page subhead | `pages/coaches.astro:24` | ADAPTED | Borderline — see detail |
| 12 | Coach KJ bio | `content/coaches/kj.mdoc` | VERBATIM | No action |
| 13 | Coach Greg bio | `content/coaches/greg.mdoc` | VERBATIM | No action |
| 14 | Coach Rebecca bio | `content/coaches/rebecca.mdoc` | ADAPTED (trailing dot fixed) | No action |
| 15 | Racing headline + intro | `content/pages/racing.mdoc` | VERBATIM | No action |
| 16 | Racing body + Techno Corner | `content/pages/racing.mdoc` | VERBATIM | No action |
| 17 | Community headline + intro | `content/pages/community.mdoc` | VERBATIM | No action |
| 18 | Community body copy | `content/pages/community.mdoc` | VERBATIM | No action |
| 19 | Community activities list | `content/pages/community.mdoc` | VERBATIM | No action |
| 20 | Sponsors headline + intro | `content/pages/sponsors_page.yaml` | VERBATIM | No action |
| 21 | Trips index page subhead | `pages/trips/index.astro:10` | INVENTED | Replace — sounds like a brochure |
| 22 | Trips empty-state copy | `components/TripsTable.astro:13-17` | INVENTED | Replace — functional but cold |
| 23 | Sisu Ski Fest trip body | `content/trips/sisu-ski-fest.mdoc` | VERBATIM | No action |
| 24 | Fall/Winter season summary | `content/practice_seasons/fall-winter.yaml` | ADAPTED | Fine — original content re-phrased cleanly |
| 25 | Spring/Summer season summary | `content/practice_seasons/spring-summer.yaml` | ADAPTED | Fine |
| 26 | Wax Room page headline | `pages/wax-room/index.astro:15` | INVENTED | New section, no original; acceptable |
| 27 | Wax Room page subhead | `pages/wax-room/index.astro:16` | INVENTED | New section, no original; acceptable |
| 28 | Wax Room empty state | `pages/wax-room/index.astro:20` | INVENTED | Charming; acceptable |
| 29 | Wax Room feed heading "From the Wax Room" | `components/WaxRoomFeed.astro:21` | INVENTED | New section; acceptable |
| 30 | Contact page description | `pages/contact.astro:14` | INVENTED | Replace — sterile |
| 31 | Contact headline "Contact" | `pages/contact.astro:15` | ADAPTED | Original: "CONTACT TWIN CITIES SKI CLUB" — truncated fine |
| 32 | Footer org blurb | `components/Footer.astro:16-18` | INVENTED | Replace — different wording from original mission |
| 33 | BaseLayout default meta description | `layouts/BaseLayout.astro:16` | INVENTED | Replace — AI-polished rewording |
| 34 | Wax Room detail fallback description | `pages/wax-room/[slug].astro:33` | INVENTED | Fine — fallback only |
| 35 | Community page headline "A welcoming community" | `content/pages/community.mdoc:2` | VERBATIM | No action |

---

## Detailed Findings

### 1. Home hero headline

**File:** `site/src/content/pages/home.yaml`, line 1  
**Current text:** `Cross-country skiing, built around community.`  
**Original equivalent:** The original home page has no hero tagline. The h1 is "TWIN CITIES SKI CLUB" and the first body text is:

> "Twin Cities Ski Club is a 501(c)(3) nonprofit dedicated to fostering a supportive community for young adults (ages 21 - 35) by promoting a healthy lifestyle through cross-country ski training sessions and educational programming."

The h2 intro is: "INTRODUCING TWIN CITIES SKI CLUB" + "Welcome"

**Verdict:** INVENTED — "built around community" is a generic parallel construction with no original basis. It could describe a yoga studio or a running club. The original voice is direct and specific.

**AI-ism flags:** parallel triad noun-phrase construction; "community" is overused as a value-word in nonprofit marketing.

**Proposed replacement:**  
The hero h1 slot is the club name (display typography); what's needed is a short declarative that plants a flag. Take the original's self-description and cut to its punch:

```
We put skiers on snow, and even on podiums, surrounded by their friends.
```

Or, pulling the age + specificity from the original mission:

```
Year-round cross-country ski training for young adults in the Twin Cities.
```

The second option is plain but true. The first is the club's own words (from `about.txt` line 13) and carries personality. Either is better than "built around community."

---

### 2. Home SectionBand heading "Two seasons. Year-round group ski."

**File:** `site/src/pages/index.astro`, line 63  
**Current text (hardcoded prop):** `"Two seasons. Year-round group ski."`  
**Original equivalent:** From `home.txt` line 17:

> "YEAR-ROUND CROSS-COUNTRY SKI TRAINING"

And the body (line 18):

> "We offer two training seasons each year: a Fall / Winter season that runs from September - March and a Spring / Summer season that runs from May - August."

**Verdict:** INVENTED — "Year-round group ski" reads like a subtitle from a fitness app. "group ski" is not a phrase TCSC uses; the original says "training sessions," "practices," and "coaching."

**AI-ism flags:** Noun stacking. Fragment style without personality.

**Proposed replacement:**

```
Two seasons a year. Practices twice a week.
```

Or, closer to the original voice:

```
Year-round cross-country ski training.
```

The latter is the exact h2 wording from the original home page.

---

### 3. Home CTAStrip heading "Ready to find your winter people?"

**File:** `site/src/pages/index.astro`, line 69  
**Current text (hardcoded prop):** `"Ready to find your winter people?"`  
**Original equivalent:** No CTA strip on the original home page. The closest original phrase is from `community.txt` line 17:

> "What does it mean to be a part of TCSC?"

**Verdict:** INVENTED — but this one has personality and is not generic agency copy. "Your winter people" is specific to the season and community framing without being clinical. No strong AI-ism. Worth keeping if the owner likes it.

**Note:** If it needs replacing to stay closer to the original voice, the community page's line "Many are Twin Cities transplants just looking to establish roots with skiers their own age" suggests an alternative angle.

---

### 4. Home CTAStrip subhead "Adults 21-35 · intermediate ability · all paces welcome."

**File:** `site/src/pages/index.astro`, line 70  
**Current text (hardcoded prop):** `"Adults 21-35 · intermediate ability · all paces welcome."`  
**Original equivalent:** From `about.txt`:

> "TCSC is a group built for young adults in the Twin Cities area. For that reason, we currently limit new registration to skiers 21 - 35 years old."
> "We only ask that our members have an intermediate grasp of cross-country skiing! We do not vet based on ability."

**Verdict:** INVENTED — "all paces welcome" is an invented phrase not on the original site and has the ring of a gym's marketing disclaimer. "intermediate ability" is accurate but the original sites it with a disclaimer about what TCSC cannot do (beginner lessons), not as a selling point.

**AI-ism flags:** bullet-point compression into a single line reads as AI synthesis rather than voice. "all paces welcome" is a generic inclusivity phrase.

**Proposed replacement (drawing directly from original):**

```
Young adults, ages 21-35 · intermediate skiers · we do not vet by ability.
```

Or, more conversational and true to how the original reads:

```
Ages 21-35 in the Twin Cities. Intermediate ability and up. No racing required.
```

---

### 5. Home CTA labels (open/coming soon/closed)

**File:** `site/src/content/pages/home.yaml`, lines 7-12  
**Current text:**  
- open: `"Register for the season →"`  
- coming_soon: `"Get on the list"`  
- closed: `"Member area"`

**Original equivalent:** The original site's CTA is simply `"Click here to register"` (from `register.txt` line 39) and `"FIND OUT MORE"` (from `home.txt` line 19). The mailing list mention is: "Signing up for the mailing list here ensures you will receive an email when our registration opens."

**Verdict:** INVENTED labels, but they are functional and appropriate for state-based CTAs. "Get on the list" is more direct than the original's mailing list copy. No significant issue.

**Note:** "Member area" for closed state is fine; it correctly directs existing members to Slack. No change needed.

---

### 10. About SectionBand heading "Two seasons."

**File:** `site/src/pages/about.astro`, line 25  
**Current text (hardcoded prop):** `"Two seasons."`  
**Original equivalent:** From `about.txt` line 31:

> "PRACTICES"

With the body:

> "We offer two training seasons each year around the Minneapolis / St. Paul area for skiers ages 21 - 35."

**Verdict:** INVENTED — "Two seasons." is truncated to the point of being cryptic on this page. The original heading is "PRACTICES" and introduces the season breakdown. A visitor who doesn't already know the club won't know what "two seasons" means.

**Proposed replacement:**

```
Practices
```

Or, slightly more descriptive:

```
Two training seasons a year.
```

---

### 11. Coaches page subhead

**File:** `site/src/pages/coaches.astro`, line 24  
**Current text (hardcoded prop):** `"An exceptional team bringing joy, excitement, and knowledge to every practice."`  
**Original equivalent:** From `coaches.txt` line 13 (verbatim):

> "At Twin Cities Ski Club, we are proud to have KJ, Greg, and Rebecca as our coaches. They are an exceptional team that brings joy, excitement, and knowledge to our members. We are grateful for their hard work, passion, and commitment to making skiing accessible and fun for everyone."

**Verdict:** ADAPTED — the subhead takes the second sentence of the original intro paragraph. It works as a one-liner. However:
- "bringing joy, excitement, and knowledge" is a parallel triad. The original has it too, so it's legitimate.
- The new version drops "KJ, Greg, and Rebecca" and the gratitude sentence. Those are two of the most charming lines on the original page.

**Proposed replacement (uses more of the original):**

```
KJ, Greg, and Rebecca bring joy, excitement, and knowledge to every practice.
```

This uses the actual names (which give it specificity and warmth) and is still short enough for a subhead.

---

### 21. Trips index page subhead

**File:** `site/src/pages/trips/index.astro`, line 10  
**Current text (hardcoded):** `"Race weekends, ski festivals, and team adventures organized by TCSC."`  
**Original equivalent:** From `trip-information.txt` line 15:

> "Come join ski friends new and old for what will hopefully be an early season weekend on snow! We plan to ski on the Birkie trails, but if snow eludes us, we will explore traveling to ABR for a day or getting up to some dryland activities in Birkie Country."

From `sisu-information.txt` line 13:

> "It's time to kick-off race season with the SISU Ski Fest! This is our largest team trip of the year! We'll head up to Ironwood to make the most of the trails at ABR and Wolverine."

From `racing.txt` line 24:

> "In the 2024-2025 season we organized team travel and lodging to the Sisu Ski Fest, the Prebirkie & North End Classic, the American Birkebeiner, and the Great Bear Chase races."

**Verdict:** INVENTED — "Race weekends, ski festivals, and team adventures" is a three-item marketing list with no original basis. The trips page on the original site is per-trip (no category-level intro).

**AI-ism flags:** parallel triad; "adventures" is a travel-brochure word TCSC never uses.

**Proposed replacement (uses real race names):**

```
Sisu Ski Fest, the Birkie, the Prebirkie, the Great Bear Chase. Plus training trips and team weekends.
```

Or shorter:

```
Team travel to the Birkie, Sisu Ski Fest, and more. Lodging and meals organized.
```

---

### 22. Trips empty-state copy

**File:** `site/src/components/TripsTable.astro`, lines 13-17  
**Current text:**

> "No trips currently scheduled. Join the Slack to hear about new trips first."

**Original equivalent:** No empty state exists on the original site (the trip pages are always populated). But the original does say about mailing list: "Signing up for the mailing list here ensures you will receive an email when our registration opens."

**Verdict:** INVENTED — functionally adequate but a bit cold. "Join the Slack" is correct but the phrasing sounds like support documentation.

**Proposed replacement (warmer, uses club's actual terminology):**

```
No trips posted yet. Check the Slack for what's coming up first.
```

Or, channeling the original's mailing list voice:

```
Nothing scheduled yet. The Slack is where trip announcements land first.
```

---

### 30. Contact page description (meta)

**File:** `site/src/pages/contact.astro`, line 14  
**Current text (hardcoded):** `"Get in touch with Twin Cities Ski Club."`  
**Original equivalent:** From `contact.txt`:

> "CONTACT TWIN CITIES SKI CLUB"
> "Minneapolis - St.Paul, Minnesota"
> "contact@twincitiesskiclub.org"

**Verdict:** INVENTED — the description is technically accurate but sterile. No real fix needed for meta description (users don't see it in the page itself), but it reads like auto-generated placeholder text.

**Proposed replacement:**

```
contact@twincitiesskiclub.org · Minneapolis - St. Paul, Minnesota
```

---

### 32. Footer org blurb

**File:** `site/src/components/Footer.astro`, lines 16-18  
**Current text:**

> "Twin Cities Ski Club, a 501(c)(3) nonprofit Nordic ski community in Minneapolis / St. Paul."

**Original equivalent:** From the original home page meta description (`home.json`, carried into `site_meta.yaml`):

> "Twin Cities Ski Club is a nonprofit dedicated to fostering a supportive community for young adults (21 - 35) by promoting a healthy lifestyle through cross-country ski training sessions and educational programing."

And the mission paragraph used on the new site:

> "Twin Cities Ski Club is a 501(c)(3) nonprofit dedicated to fostering a supportive community for young adults (ages 21 - 35) by promoting a healthy lifestyle through cross-country ski training sessions and educational programming."

**Verdict:** INVENTED — "Nordic ski community" is the new site's own phrase, not from the original. The original always says "cross-country ski training" or "cross-country ski training sessions." The footer blurb also silently drops the age range (21-35) and the "educational programming" element that the original treats as important.

**AI-ism flags:** "Nordic ski community" is a tighter, agency-approved phrase that replaces the club's own description with a genre label.

**Proposed replacement (trimmed from original mission copy):**

```
A 501(c)(3) nonprofit for young adults (21-35) in Minneapolis / St. Paul. Two seasons of cross-country ski training a year.
```

---

### 33. BaseLayout default meta description

**File:** `site/src/layouts/BaseLayout.astro`, line 16  
**Current text:**

> "Twin Cities Ski Club — a nonprofit cross-country ski community for young adults in Minneapolis / St. Paul."

**Original equivalent:** From the original meta description (verbatim, in `site_meta.yaml`):

> "Twin Cities Ski Club is a nonprofit dedicated to fostering a supportive community for young adults (21 - 35) by promoting a healthy lifestyle through cross-country ski training sessions and educational programing."

**Verdict:** INVENTED — the BaseLayout default is a rewording that introduces the em dash (see below), drops "21 - 35," and replaces "training sessions and educational programming" with the vaguer "community."

**AI-ism flags:** em dash; "community" replacing specific description.

**Proposed replacement (use the verbatim original meta description, which is already stored in `site_meta.yaml`):**

```
Twin Cities Ski Club is a nonprofit dedicated to fostering a supportive community for young adults (21 - 35) by promoting a healthy lifestyle through cross-country ski training sessions and educational programing.
```

(Note: "programing" is the original's spelling. The new site corrects it to "programming" in `site_meta.yaml`. Either is defensible; "programming" is correct English.)

---

## Unused Original Copy Worth Surfacing

The following lines appear on the original site and are genuinely charming. None currently appear on the new site. These are strong candidates for headings, CTAs, or pullquotes.

**1. The founding story punchline** (from `about.txt` line 13, also in `about.mdoc` but only as body text, never pulled into a heading or display element):

> "In short, we put skiers on snow, and even on podiums, surrounded by their friends and without breaking the bank."

This would work as the home hero headline or as a CTAStrip heading in place of "Ready to find your winter people?"

**2. The apres-ski confession** (from `community.txt` line 20, carried into `community.mdoc`):

> "Even still, plenty are 'Aprés ski' lovers who put up with intervals in exchange for post-practice brews."

This is the funniest line on the entire site. It currently only lives in the community page body prose. Could be a pullquote on the home page or community hero.

**3. Techno Corner** (from `racing.txt`, used in `racing.mdoc` but only in body text):

> "Our now famous Techno Corner cheering section is ever-present at most big Midwest races."

"Techno Corner" is a specific, memorable artifact of TCSC culture. It should be findable as a heading or callout, not buried mid-paragraph.

**4. The transplant framing** (from `community.txt` line 19, in `community.mdoc` body):

> "Many are Twin Cities transplants just looking to establish roots with skiers their own age."

This is a useful hook for the community page hero subhead. It names the actual situation a prospective member might be in.

**5. The volunteering line** (from `community.txt` line 24, in `community.mdoc` body):

> "TCSCers can be found in coaching positions from beginner to high school levels all over the metro, and are active volunteers in the Twin Cities and beyond."

Never surfaced as a heading. Could reinforce the community page's "what does it mean to be part of TCSC" section.

**6. Racing is voluntary line** (from `racing.txt` line 17, in `racing.mdoc` body):

> "Racing with TCSC is totally voluntary - but highly encouraged!"

The dash here is a hyphen (fine). This line would work as a callout or subhead on the racing page above the race list, to reassure non-competitive readers.

**7. Birkie scale stat** (from `racing.txt` line 20):

> "In 2025, TCSC had over 80 skiers represented at the American Birkebeiner ski race — in both the Birkebeiner and Korteloppet events."

(Note: the em dash here appears in the original scrape; the new site renders it correctly in `racing.mdoc`. The stat is the hook. "80 skiers" is a real number that belongs in a hero or callout context, not just body prose.)

---

## Em Dash Inventory

Per the project brief (no em dashes or en dashes in proposed copy):

- `community.mdoc` line 4: the original Wix text contains an em dash ("— regardless of race, gender..."). This was on the original site and is carried verbatim. Flagged: could be replaced with a comma or period. Proposed: "...ages 21 - 35 years old who lives in the greater Minneapolis / St. Paul area, regardless of race, gender, sexual orientation, religion."
- `BaseLayout.astro` line 16: em dash in default fallback description (see finding #33 above).
- `racing.mdoc` line 36: "placed in the Top 20. TCSC was represented..." — the original racing.txt uses an em dash here ("placed in\nthe\nTop 20."). The new site splits it correctly. Fine.

---

## Quick-Reference Edit Checklist

An engineer can apply these mechanically in the order listed:

| Priority | File | Old value | Proposed value |
|----------|------|-----------|----------------|
| HIGH | `site/src/content/pages/home.yaml` line 1 | `Cross-country skiing, built around community.` | `We put skiers on snow, and even on podiums, surrounded by their friends.` |
| HIGH | `site/src/pages/index.astro` line 63 | `"Two seasons. Year-round group ski."` | `"Year-round cross-country ski training."` |
| HIGH | `site/src/pages/index.astro` line 70 | `"Adults 21-35 · intermediate ability · all paces welcome."` | `"Ages 21-35 in the Twin Cities. Intermediate ability and up. No racing required."` |
| HIGH | `site/src/layouts/BaseLayout.astro` line 16 | `Twin Cities Ski Club — a nonprofit cross-country ski community for young adults in Minneapolis / St. Paul.` | `Twin Cities Ski Club is a nonprofit dedicated to fostering a supportive community for young adults (21 - 35) by promoting a healthy lifestyle through cross-country ski training sessions and educational programming.` |
| HIGH | `site/src/components/Footer.astro` line 17 | `Twin Cities Ski Club, a 501(c)(3) nonprofit Nordic ski community in Minneapolis / St. Paul.` | `A 501(c)(3) nonprofit for young adults (21-35) in Minneapolis / St. Paul. Two seasons of cross-country ski training a year.` |
| MEDIUM | `site/src/pages/coaches.astro` line 24 | `"An exceptional team bringing joy, excitement, and knowledge to every practice."` | `"KJ, Greg, and Rebecca bring joy, excitement, and knowledge to every practice."` |
| MEDIUM | `site/src/pages/about.astro` line 25 | `heading="Two seasons."` | `heading="Practices"` |
| MEDIUM | `site/src/pages/trips/index.astro` line 10 | `"Race weekends, ski festivals, and team adventures organized by TCSC."` | `"Sisu Ski Fest, the Birkie, the Prebirkie, the Great Bear Chase. Plus training trips and team weekends."` |
| MEDIUM | `site/src/components/TripsTable.astro` line 13 | `No trips currently scheduled.` | `No trips posted yet. The Slack is where trip announcements land first.` |
| LOW | `site/src/pages/contact.astro` line 14 | `"Get in touch with Twin Cities Ski Club."` | `"contact@twincitiesskiclub.org · Minneapolis - St. Paul, Minnesota"` |
| LOW | `site/src/content/pages/community.mdoc` line 4 | `— regardless of race, gender, sexual orientation, religion.` | `, regardless of race, gender, sexual orientation, religion.` |

---

## Notes on New Sections (Wax Room, Live Conditions)

The Wax Room and Live Conditions strip are genuinely new features with no original site equivalent. Their copy ("From the Wax Room," "Conditions, wax notes, race-day prep, technique. Field reports from TCSC coaches and members.") is invented but appropriate. The voice is compressed and practical, which fits the section. No action recommended.

The Wax Room empty state ("No entries yet. Come back after the first snow.") is the best line of invented copy on the entire new site. Keep it.
