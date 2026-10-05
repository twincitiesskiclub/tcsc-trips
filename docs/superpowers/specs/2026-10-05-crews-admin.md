# Crews admin page

Date: 2026-10-05. Requested by Mitchell Campbell (Adventure), built for Rob.
Revised the same day after a simplicity review: see "What was cut".

## Problem

Mitchell's "TCSC Crews" proposal (#leadership-general, 9/17) splits the season's
members into about 12 crews of 12. Every crew gets at least one board member and
a mix of age, intensity, gender and tenure. A scratchpad script made the first
draw on 10/5. Mitchell needs to run it himself: make a few draws, pick one, fix
it by hand and save it as the season's crews.

## What an admin sees

`/admin/crews` opens the current season's page. Another season can be picked
from a menu.

```
Crews: 2026 Fall/Winter                                   Season [2026 Fall/Winter v]

144 members. Speedy group 16 (from #thots, read Oct 5). Board members 6. [Refresh from Slack]
Final crews: none yet.
[ Make 5 drafts ]

Drafts (best first)
  Draft 1   imbalance 48.8    Best  all rules met
  Draft 4   imbalance 52.1          all rules met
  Draft 3   imbalance 131.0         1 crew with no board member

> Crew settings: 12 crews, every crew gets a board member, balancing speedy group,
  seasons on team, gender, ski experience, age.
> Rules (2)
> Members: 0 with no gender, 6 board.
```

- **Make 5 drafts.** The server picks the seeds. The first draft of a season uses
  seed 2026, and later drafts count up. Drafts are labeled "Draft N".
- **Drafts list.** Drafts are sorted by imbalance score. Each row shows the
  score, a "Best" or "Final" badge, and two red flags: crews with no board
  member, and rules not met.
- **Crew settings** (collapsed):
  - Number of crews.
  - The board rule: every crew gets at least one board member.
  - A weight of off, low, normal or high for each of speedy group, seasons on
    team, gender, ski experience and age.
- **Rules** (collapsed): keep two people together, keep two people apart, or
  put someone in a set crew.
- **Members** (collapsed): one row per active member with the computed gender
  (from pronouns), age, ski experience, seasons on team, speedy and board.
  Gender, speedy and board can be changed for crews only, and changed cells
  are highlighted. A "Clear hand-set values" link resets them.

**Draft page.** At the top: Mark as final, Download CSV and Delete. Then the
balance table, one row per crew plus an "All" row, then one form:
- A draft name field.
- One card per crew, with a crew name field in the card header.
- A crew number picker next to each person.

One Save posts the whole form. The page reloads with the new balance table.

**Launch crews in Slack** (final draft only). The button opens a confirmation
page that lists each crew's channel name, how many members will be invited,
and anyone who can't be invited because no Slack account is linked. Nothing
happens until "Make channels and invite" is pressed. For each crew, the TCSC
bot creates a private channel (so the app is a member) and invites the crew in
one call (`conversations.invite`, `force=true`). The channel ID and name are
stored per crew on the draft. A result page then shows, per crew: New or
existing, invited, already in, could not invite (with the Slack error), and no
Slack account.

- **Idempotent:** a crew with a stored channel is not created again. The
  launch reads the channel members and invites only the missing ones. After
  the first launch, the button reads "Update crews in Slack".
- **Errors stay per crew:**
  - `name_taken`: retry once as `<name>-<season year>`.
  - `already_in_channel`: counted as already in.
  - `user_not_found` and other per-user errors: listed by name.
  - Anything else (rate limited after the client's retries, a deleted
    channel): marks that crew "Stopped" and the launch moves on to the next
    crew.
- **Channel names:** `crew-` plus the crew name as a Slack-safe slug
  (lowercase, runs of anything but a-z, 0-9, `-` and `_` become `-`, at most
  80 characters), or `crew-<number>` when the crew has no name. The prefix
  keeps the channels together in Slack's sidebar and clear of existing
  channels.
- **Not in v1:** renaming a channel when a crew is renamed, archiving
  channels, removing people who moved crews after launch, setting a topic or
  welcome post, and adding a non-member admin (Mitchell) to every channel.

## Method (defaults reproduce the 10/5 scratchpad draw)

1. Pinned people and keep-together groups are placed first and don't move.
2. If the board rule is on, the free board members are shuffled and dealt one
   per crew.
3. Everyone else is sorted by the traits that are on (speedy, seasons, gender,
   ski, age). The list is cut into bands of K, where K is the crew count, and
   each band is dealt one per crew.
4. Even-out pass: trade two people in the same band when the trade lowers the
   imbalance score. Then split keep-apart pairs and level crew sizes.

Score = weight × (count − expected)² summed over crews and traits, plus an
age-mean term, plus 100 per crew with no board member, plus 1000 per rule not
met. Default weights are speedy 2 and everything else 1. Low halves a weight,
high doubles it, and off drops the trait. Board has no weight of its own: the
board rule turns its term on (weight 1 plus the penalty) or off.

Checked read-only against prod on 10/5: the default settings at seed 2026,
given the same gender, speedy and board inputs, put all 144 members in the same
crews as the scratchpad.

## Data

- **Tenure** follows the scratchpad: prior ACTIVE non-legacy seasons, plus
  archive season labels from practice attendance before records began, counted
  as one set of labels. A legacy member with no attendance counts as one
  season.
- **Gender** comes from pronouns (F/M/X), otherwise "?". Overrides are stored
  on the season's crew config, not on User. It is a guessed or hand-entered
  balancing input, not member data.
- **Board** comes from the BOARD_MEMBER tag. On 10/5 prod the tag is stale (6
  people, 2 of them from last year), so the page links to Roles and allows
  overrides.
- **Speedy group** is the members of #thots, a constant in
  `app/crews/slack.py`, read with the bot token when someone presses "Refresh
  from Slack".

## Storage

- `crew_configs`: one row per season, created on the first POST, not on a GET.
  It holds settings (crews, levels, board_rule), overrides
  `{user_id: {gender, thot, board}}`, rules, speedy_user_ids and
  speedy_refreshed_at.
- `crew_drafts`:
  - season_id, label, seed and status (draft or final).
  - Snapshots of the settings and rules used.
  - A members snapshot of {user_id, name, email, gender, age, ski, tenure,
    thot, board, crew}.
  - crew_names, and crew_channels ({crew: {id, name}}), which the Slack launch sets.
  - A partial unique index allows one final draft per season.
  - The score is computed when the draft is read, not stored.

## Access

Every `/admin` page uses `admin_required`: a Google sign-in on a
`@twincitiesskiclub.org` account. Mitchell signs in with
adventures@twincitiesskiclub.org.

## What was cut (simplicity review, Rob's calls)

- CSV import of a draft. The first draft already reproduces the scratchpad draw.
- CSV upload of member overrides. The row form is the only way in.
- The seed and "how many" inputs. Seeds are chosen server-side, 5 drafts per click.
- The swap form, and live fetch-and-replace editing. One form and a Save button
  do the same job.
- The Slack channel field. #thots is a constant.
- The separate "Board members" weight, merged into the board rule.
- The stored score, created_by and band fields.
- The per-trait spread columns in the drafts list. They still show on the
  draft page.

## Out of scope

Syncing Slack after launch beyond inviting missing members (see "Not in v1"
above).

## Open decisions

- Are crews final for the whole season? We assume yes.
- Keep the stale BOARD_MEMBER tag as the source, or switch to officer tags?
  Today it is the tag plus overrides.
