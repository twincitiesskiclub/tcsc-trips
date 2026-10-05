# Crews admin page

Date: 2026-10-05. Requested by Mitchell Campbell (Adventure), built for Rob.

## Problem

Mitchell's "TCSC Crews" proposal (#leadership-general, 9/17) splits the season's
members into about 12 crews of 12. Every crew gets at least one board member and
a mix of age, intensity, gender and tenure. A scratchpad script built the first
draw on 10/5. Mitchell needs to run it himself: tune how the crews are built,
compare several draws, fix things by hand, and save the one the club uses.

## What an admin sees

`/admin/crews` opens the current season's crews page (another season can be
picked).

**1. Settings.** The form holds:
- The number of crews (default 12).
- The traits that count: speedy group, tenure, gender, ski experience, age.
  Each has a weight of off, low, normal or high.
- A board rule checkbox: at least one board member per crew.
- The Slack channel that defines the speedy group (default #thots,
  C0ATRS011FA), plus a "Refresh from Slack" button.

**2. Members.** One row per ACTIVE member of the season. The row shows the
computed values: gender from pronouns, age from birthdate, ski experience from
registration, tenure in seasons, board from the BOARD_MEMBER tag, and speedy
from the channel. An admin can override gender, speedy and board for this
season's crews. An uploaded CSV (Email plus any of gender, thot, board) fills
in many overrides at once, which is how Mitchell's own sheet gets in.

**3. Rules.** Admins can add these and remove them:
- Keep together: two people.
- Keep apart: two people.
- Pin a person to a crew.

**4. Drafts.** "Make drafts" builds N drafts (default 5) from consecutive
seeds. The comparison table shows each draft's imbalance score, how far each
trait is from even, crews without a board member, and broken rules. A draft
can be opened, deleted or marked final, and only one draft per season can be
final. A crews CSV (Email, Crew) can also be imported as a draft, so the 10/5
scratchpad draw becomes draft 1.

**Draft page.** It shows the balance table, then one card per crew. Each card
has a name field and its roster. Every roster row has a crew picker. Moving
someone posts to the server, which saves the draft and sends back the updated
balance table and cards, so the effect shows right away. A "swap" picker
trades two people. From this page an admin can export the CSV or mark the
draft final.

## Method (defaults match the 10/5 scratchpad run)

1. If the board rule is on, the board members are shuffled and dealt one per
   crew. Extras join everyone else.
2. Everyone else is sorted by the enabled traits, in the order speedy, tenure,
   gender, ski, age, with a random tie-break. The list is cut into bands of K
   (K is the crew count), and each band is dealt one per crew. A short band
   goes to the smallest crews.
3. Even-out pass: the pass trades two people in the same band when the trade
   lowers the imbalance score. The score is the sum over crews and traits of
   weight × (count − expected)², plus an age-mean term and 100 per crew
   without a board member.

Default weights are thot 2, everything else 1. Low and high multiply a weight
by 0.5 and 2, and off drops the trait from both the sort and the score. Same
inputs and seed give the same crews.

**Rules.** Rules are hard constraints, applied like this:
- Together-groups are merged (union-find). Groups and pinned people are placed
  before dealing: a pinned group goes to its pin, and any other group goes to
  the smallest crew that breaks no apart rule.
- Placed people never move during balancing.
- Every swap that would break an apart rule is rejected, and a broken rule
  adds 1000 to the score.
- A repair pass moves people out of broken apart pairs.
- Rules that can't all be met (for example A pinned to 1, B pinned to 2, and
  A together with B) show up as broken in the comparison table rather than
  failing.

## Data

- **Tenure.** This uses the same count as the scratchpad:
  - Prior non-legacy seasons where the member was ACTIVE.
  - Plus earlier half-seasons where the member appears in practice attendance
    (non-decline roles), from before the first non-legacy season.
  - A legacy member with no attendance counts as one season.
  Members are grouped as new, 1-2, 3-5 or 6+.
- **Gender.** Pronouns give F, M or X. With no pronouns, gender is "?" until
  an admin sets it or a CSV fills it.
  - Gender overrides are stored on the season's crew config, not on User. It
    is a crew-balancing input that was guessed or hand-entered, it isn't
    member-supplied, and storing it on User would turn it into member data
    the club then has to care for.
- **Board.** Board comes from the BOARD_MEMBER tag. On 10/5 prod tags only 6
  people, and 2 of them (Gaby Haire, Julia Reich) are from last year's board,
  so the tag is stale. The page shows the tagged count and links to Roles.
  Per-season overrides cover the gap until Rob updates the tags.
- **Speedy group.** The bot reads the members of the configured channel
  (conversations.members, bot token, bot is in #thots) and matches them to
  users through slack_users. The result is stored on the config with a
  refreshed-at time.

## Storage

These are two new tables, and both use JSON columns for the parts that change
shape.

`crew_configs` (one row per season):
- season_id, unique.
- settings: crews, weights, board rule, speedy channel.
- overrides: {user_id: {gender, thot, board}}.
- rules: [{type, a, b, crew}].
- speedy_user_ids and speedy_refreshed_at.

`crew_drafts`:
- season_id, label, seed and status (draft or final).
- Snapshots of the settings and rules used.
- members: a list of {user_id, name, email, crew, band, gender, age, ski,
  tenure, thot, board}, so a draft keeps its numbers after the roster moves.
- crew_names, score, created_by and timestamps.
- A partial unique index allows one final draft per season.

## Access

Every `/admin` page uses `admin_required`: a Google sign-in on a
`@twincitiesskiclub.org` account. Mitchell already edits trips through
adventures@twincitiesskiclub.org, so signing in with that account gets him in.
Roles and tags are not used for this.

## Out of scope (seams left)

- Creating Slack channels or posting crews. `app/crews/slack.py` holds the
  channel read and is where a later "create channels" step goes.
- Members who join after a draft show as "not in this draft" with an "add to
  smallest crew" button. If v1 runs long, this waits for v2.

## Open decisions

- Are crews final for the whole season? We assume yes, with one final draft
  per season.
- Keep the stale BOARD_MEMBER tag as the source, or switch to the officer
  tags plus a new tag? Today: the tag plus overrides.
- Should the gender guess come from first names in-app? Today: no.
  Mitchell's sheet or an override fills it.
