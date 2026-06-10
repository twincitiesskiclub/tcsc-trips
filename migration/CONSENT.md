# Photo Consent Provenance

## Basis

Two bases exist, by photo source:

1. **Re-published from the public Wix site** (27 photos): already publicly
   displayed on twincitiesskiclub.org. That prior public display is the
   recorded basis for `photo_consent_recorded: true` on each entry.
2. **Sourced from the club Slack #photos-videos channel** (2026-06-10 polish
   pass; 7 images, see the second table): posted to the club-wide channel by
   the members named in `migration/slack_photos/manifest.csv`. Posting to the
   club's shared photo channel is the provisional basis; these were NOT
   previously on the public web, so they need explicit attention in the board
   re-confirmation below. Professional race-gallery photos found in the
   channel were deliberately excluded (rights unclear).

**Board re-confirmation is required before DNS cutover.** Until the board
re-confirms, this basis is provisional: any photo the board does not
re-confirm must have `photo_consent_recorded` set to `false` (which removes
it from every mosaic) or be deleted outright.

To trace any photo back to its Wix source, see the `source_url` and
`consent_basis` columns in `migration/port-manifest.csv`.

## Covered photos (27)

| Content entry | Image file |
|---|---|
| backyard-bbq | site/src/assets/images/photos/backyard-bbq.jpg |
| beach-day-dock | site/src/assets/images/photos/beach-day-dock.jpg |
| ben-jerrys-ride | site/src/assets/images/photos/ben-jerrys-ride.jpg |
| bike-shop-party | site/src/assets/images/photos/bike-shop-party.jpg |
| birkie-bib-pickup | site/src/assets/images/photos/birkie-bib-pickup.jpg |
| birkie-cheer-selfie | site/src/assets/images/photos/birkie-cheer-selfie.jpg |
| birkie-flag-crew | site/src/assets/images/photos/birkie-flag-crew.jpg |
| chain-of-lakes-paddle | site/src/assets/images/photos/chain-of-lakes-paddle.jpg |
| costume-ski-trio | site/src/assets/images/photos/costume-ski-trio.jpg |
| ice-skating-night | site/src/assets/images/photos/ice-skating-night.jpg |
| lakeside-picnic | site/src/assets/images/photos/lakeside-picnic.jpg |
| loppet-finish-trio | site/src/assets/images/photos/loppet-finish-trio.jpg |
| mini-golf-night | site/src/assets/images/photos/mini-golf-night.jpg |
| mnufc-match | site/src/assets/images/photos/mnufc-match.jpg |
| onesie-crew | site/src/assets/images/photos/onesie-crew.jpg |
| pole-hike-sunset | site/src/assets/images/photos/pole-hike-sunset.jpg |
| rollerski-clinic | site/src/assets/images/photos/rollerski-clinic.jpg |
| sisu-medals | site/src/assets/images/photos/sisu-medals.jpg |
| ski-bite-line | site/src/assets/images/photos/ski-bite-line.jpg |
| snowfall-practice | site/src/assets/images/photos/snowfall-practice.jpg |
| survivor-relay | site/src/assets/images/photos/survivor-relay.jpg |
| tcsc-banner-lake | site/src/assets/images/photos/tcsc-banner-lake.jpg |
| tcsc-flag-trail | site/src/assets/images/photos/tcsc-flag-trail.jpg |
| team-on-snow | site/src/assets/images/photos/team-on-snow.jpg |
| techno-corner-flag | site/src/assets/images/photos/techno-corner-flag.jpg |
| usa-cheer-crew | site/src/assets/images/photos/usa-cheer-crew.jpg |
| utepils-apres | site/src/assets/images/photos/utepils-apres.jpg |

## Covered photos, Slack-sourced (7)

Source files (with poster, date, original message) are traceable through
`migration/slack_photos/manifest.csv` by the date-stamped filename.

| Content entry | Image file | Slack source file |
|---|---|---|
| (home hero) | site/src/assets/images/uploads/home-hero-trail.jpg | 2025-11-29_1764449909-984339_0.jpg |
| barkie-birkie-bauer | site/src/assets/images/photos/barkie-birkie-bauer.jpg | 2024-02-07_1707360103-835559_0.jpg |
| loppet-medals | site/src/assets/images/photos/loppet-medals.jpg | 2024-02-04_1707061600-648209_0.jpg |
| suits-on-snow | site/src/assets/images/photos/suits-on-snow.jpg | 2024-01-28_1706480968-360759_0.jpg |
| season-banquet | site/src/assets/images/photos/season-banquet.jpg | 2024-03-30_1711812078-797759_0.jpg |
| vasaloppet-duo | site/src/assets/images/photos/vasaloppet-duo.jpg | 2026-02-14_1771088334-691999_0.jpg |
| fall-relay-crew | site/src/assets/images/photos/fall-relay-crew.jpg | 2024-11-04_1730751832-916119_0.png |
