# Photo Consent Provenance

## Basis

As of the 2026-06-10 photo refresh, every photo on the site is sourced from
the club Slack #photos-videos channel (posted there by the members named in
`migration/slack_photos/manifest.csv`, traceable by the date-stamped source
filename). Posting to the club's shared photo channel is the provisional
basis for `photo_consent_recorded: true` on each entry. These images were
NOT previously on the public web, so the board re-confirmation below is a
hard gate, not a formality. Professional race-gallery photos circulating in
the channel (brockit / official Birkie galleries) were deliberately
excluded: rights unclear.

History: the original 27 photos re-published from the public Wix site
(prior-public-display basis) were removed from the site in this refresh in
favor of an all-recent pool; see git history of this file and
`site/src/content/photos/` before commit range 2026-06-10 if they are ever
wanted back.

**Board re-confirmation is required before DNS cutover.** Until the board
re-confirms, this basis is provisional: any photo the board does not
re-confirm must have `photo_consent_recorded` set to `false` (which removes
it from every mosaic) or be deleted outright.

To trace any photo back to its source, see the `source_migration_file` and
`consent_basis` columns in `migration/port-manifest.csv`.

## Covered photos (23 mosaic + hero + 1 coach)

| Content entry | Image file | Slack source file |
|---|---|---|
| (home hero) | site/src/assets/images/uploads/home-hero-trail.jpg | 2025-11-29_1764449909-984339_0.jpg |
| (coach Michael) | site/src/assets/images/coaches/coach-michael.jpg | 2025-08-07_1754622922-641059_0.jpg (posted by Michael himself) |
| oo-corridor | site/src/assets/images/photos/oo-corridor.jpg | 2025-11-27_1764268748-158379_0.jpg |
| recess-ski | site/src/assets/images/photos/recess-ski.jpg | 2025-12-01_1764613340-935069_0.jpg |
| breadwinners | site/src/assets/images/photos/breadwinners.jpg | 2025-12-20_1766246168-871389_0.jpg |
| night-practice | site/src/assets/images/photos/night-practice.jpg | 2026-01-08_1767926187-104029_0.jpg |
| ashwabay-podiums | site/src/assets/images/photos/ashwabay-podiums.jpg | 2026-01-31_1769909408-073549_1.jpg |
| loppet-skijor | site/src/assets/images/photos/loppet-skijor.jpg | 2025-02-03_1738622884-996139_0.jpg |
| techno-corner | site/src/assets/images/photos/techno-corner.jpg | 2025-02-22_1740268459-587669_0.jpg |
| finlandia-axes | site/src/assets/images/photos/finlandia-axes.jpg | 2026-02-14_1771096714-097109_1.jpg |
| vasaloppet-duo | site/src/assets/images/photos/vasaloppet-duo.jpg | 2026-02-14_1771088334-691999_0.jpg |
| fire-danger-maria | site/src/assets/images/photos/fire-danger-maria.jpg | 2026-02-21_1771713439-032779_0.jpg |
| great-bear-chase | site/src/assets/images/photos/great-bear-chase.jpg | 2026-03-07_1772920012-712389_0.jpg |
| boom-island-run | site/src/assets/images/photos/boom-island-run.jpg | 2026-03-15_1773592205-437209_0.jpg |
| pi-day | site/src/assets/images/photos/pi-day.jpg | 2026-03-12_1773367918-011079_0.jpg |
| half-dome-tee | site/src/assets/images/photos/half-dome-tee.jpg | 2025-04-25_1745623183-951729_0.jpg |
| first-track-club | site/src/assets/images/photos/first-track-club.jpg | 2026-04-23_1776954511-019769_0.jpg |
| city-trail-loppet | site/src/assets/images/photos/city-trail-loppet.jpg | 2025-05-18_1747586445-653709_3.jpg |
| track-club-storm | site/src/assets/images/photos/track-club-storm.jpg | 2025-05-29_1748527629-477279_0.jpg |
| rollerski-treats | site/src/assets/images/photos/rollerski-treats.jpg | 2026-05-24_1779640641-920619_0.jpg |
| dry-tri-rider | site/src/assets/images/photos/dry-tri-rider.jpg | 2025-10-25_1761420816-201549_6.jpg |
| pride-ski | site/src/assets/images/photos/pride-ski.jpg | 2025-06-26_1750984748-186189_0.jpg |
| borah-epic | site/src/assets/images/photos/borah-epic.jpg | 2026-06-06_1780772360-139449_0.jpg |
| northshore-inline | site/src/assets/images/photos/northshore-inline.jpg | 2025-09-14_1757886642-466169_0.jpg |
| dry-tri-runner | site/src/assets/images/photos/dry-tri-runner.jpg | 2025-10-25_1761420816-201549_5.jpg |
