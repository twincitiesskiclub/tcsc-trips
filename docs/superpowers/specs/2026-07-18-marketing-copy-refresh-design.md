# TCSC Marketing Copy Refresh

**Date:** 2026-07-18
**Status:** Approved for implementation planning

## Goal

Replace the site's corny, corporate, repetitive, or unclear copy without flattening the member-written details that make TCSC recognizable. The finished site should sound like a knowledgeable club member explaining TCSC plainly.

This is a copy-only pass. It does not change page structure, content schemas, routes, visual design, or factual policy.

## Voice rules

1. Prefer concrete activities and named details over claims about values.
2. Prefer direct verbs over nonprofit abstractions such as "fostering," "promoting," and "providing."
3. Use at most one playful ski reference on a surface. Club-specific language such as Techno Corner and Birkie Fever stays.
4. Remove slogan structures, inflated claims, filler adjectives, and repeated points.
5. Keep eligibility, fees, registration dates, and optional racing language explicit.
6. Do not invent facts to improve a sentence. Leave uncertain copy unchanged until the club confirms it.

## Approved replacement set

### About page

In `site/src/content/pages/about.mdoc`:

- Replace the intro with the user-selected line:

  > TCSC brings young adult skiers together for year-round training, optional racing, and an active community beyond practice.

- Replace the founding paragraph with:

  > TCSC started in 2020 to help young adult cross-country skiers in the Twin Cities find one another. Members now train, race, volunteer, and spend time together year-round.

- Replace the age paragraph with:

  > New registration is currently limited to skiers ages 21-35.

- Replace the ability paragraph with:

  > New members should already have intermediate cross-country ski skills. Speed and racing experience do not matter. We cannot offer beginner lessons yet, but [Three Rivers](https://www.threeriversparks.org/activity/cross-country-skiing#lessons) and the [Loppet Foundation](https://loppet.org/Experiences/learn-to-ski/) do.

- Replace the "crucial third space" paragraph with:

  > For many members, TCSC is where they train, volunteer, and make friends outside work and home. See what that looks like on our [Community page](/community).

- Replace the coaching paragraph with:

  > TCSC's four [coaches](/coaches) plan and lead practices throughout the dryland and snow seasons.

### Home page and shared metadata


In `site/src/layouts/BaseLayout.astro`, replace the corporate fallback description with the existing plain site description:

> Year-round cross-country ski training and community for adults 21-35 in Minneapolis-St. Paul, with coached practices, racing, and trips.

In `site/src/pages/index.astro`:

- Change the photo-mosaic heading from `A welcoming community` to `Beyond practice`.
- Change its link label from `More from the community` to `See what members do`.
- Keep `Come ski with us.` and the factual hero subline unchanged.

### Community page

In `site/src/content/pages/community.mdoc`:

- Change the headline to `What members do beyond practice`.
- Change the intro to `Volunteer nights, socials, member coaching, and extra workouts organized by TCSC members.`
- Replace the opening body paragraph with:

  > TCSC welcomes intermediate cross-country skiers ages 21-35 who live in the greater Minneapolis and St. Paul area. Skiers of every race, gender, sexual orientation, and religion are welcome. Our members include Twin Cities transplants meeting skiers their age, former high school and college racers looking for a new team, and apres-ski lovers who put up with intervals for post-practice brews.

- Change `The club is 100% volunteer run` to `Members run the club`, with this detail:

  > A volunteer board holds monthly meetings open to every member, with committees for practices, socials, trips, marketing, apparel, and the Dry Tri.

- Change `National-level trip staff` to `Coaching and waxing at national races`, with this detail:

  > Members have joined CXC Midwest Team trips to U.S. Junior Nationals and Canadian Nationals as coaches and wax techs.

- Change `Standing invitations, all season.` to `Both run throughout dryland season.`
- Change `Member-invented annuals.` to `Members started both events, and each returns once a year.`

In `site/src/pages/community.astro`, change the section seam to `Member-led`, change the heading to `How members pitch in`, and remove the redundant subhead.

### Coaches

In `site/src/pages/coaches.astro`, replace the generic description with:

> KJ, Greg, Rebecca, and Michael lead TCSC's ski technique, endurance, and strength sessions.

In `site/src/content/coaches/rebecca.mdoc`, replace the bio with:

> Rebecca started skiing in middle school and later joined the University of Minnesota ski team. She has coached high school skiers and now coaches Finn Sisu's Vakava team.

In `site/src/content/coaches/greg.mdoc`, replace the bio with:

> Greg is a sports scientist with a PhD in Kinesiology and Exercise Science from the University of Minnesota. He has also supported athletes at the MTB World Cup in Snowshoe, West Virginia.

KJ and Michael's bios stay unchanged. Michael's specific details are the strongest reference for the desired voice.

### Seasons and registration clarity

In `site/src/content/practice_seasons/fall-winter.yaml`:

- Change the registration note to `2026 registration: returning members Aug 28 · new members Sep 3`.
- Change the trips line to `Sisu Ski Fest and the American Birkebeiner`.

In `site/src/content/practice_seasons/spring-summer.yaml`, change the registration note to `2026 registration closed · 2027 opens Apr/May`.

In `site/src/components/SeasonsGrid.astro`, replace the dues sentence with:

> Practices run twice a week with KJ, Greg, Rebecca, and Michael. Dues cover coaching and reserved workout space.

### 404 page

In `site/src/pages/404.astro`, keep the single playful headline `This trail ends here.` and remove the stacked ski metaphors:

- Subhead: `The page may have moved, or the link may point to our old site.`
- Body heading: `Choose another page.`
- Body text: `Start at the home page or use one of the links below.`

The trail photograph stays. The page gets one ski reference rather than four.

### Conditions copy

In `site/src/components/LiveConditions.astro`, change the compact label from `Birkie` to `Birkie fever` so the fever number cannot be mistaken for a trail temperature.

In `site/src/components/LiveConditions.client.ts`, change the screen-reader announcement template to `${loc.name} wax recommendation changed: ${loc.wax_label}`.

## Copy that stays

The pass deliberately preserves:

- Techno Corner, Birkie Fever, the Symanski Glute Buster, Night of 1000 Salads, Everything is a Vegetable, Literary Loppet, Tour de Ice Cream, and the TCSC Classic.
- The Dry Tri page, Wax Room copy, trips index and trip collection copy, photo captions, alt text, all other live-condition messages, and Michael's bio.
- The concise CTA `Come ski with us.`
- The phrase about apres-ski lovers putting up with intervals for post-practice brews.

The two `everyone is welcome` statements about member-organized extra workouts stay unchanged because the source does not establish whether nonmembers may attend. That wording needs a factual answer, not a stylistic guess.

## Validation

Implementation is complete when:

1. The Astro content schemas accept every edited value.
2. The marketing site builds successfully.
3. Searches confirm that the rejected phrases and corporate boilerplate are gone from live source files.
4. About, Home, Racing, Community, Coaches, Seasons, and 404 are visually checked at desktop and mobile widths for awkward wrapping or overflow.
5. Metadata still stays within practical search-description length.
6. No migration archive, historical audit, photo record, or unrelated application copy changes.
