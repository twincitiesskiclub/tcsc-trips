# Lead schedule: restyle and self-serve Lead button

2026-10-09. Builds on #288 (the "Post schedule to leads" button, live 10/9).
Design settled with Rob over 15 rounds of Slack samples (final: "v15") and a
five-reviewer UI/UX pass.

## Problem

The lead schedule post in #coord-practices-leads-assists (`build_lead_schedule`)
works but reads like a data dump, and it goes to all 60 leads. An open session
says "No leads yet" and asks nothing of anyone. Filling it takes a practices
director: today Chris asked for 💪 reactions in the thread, read them, and
assigned someone in the Assign modal.

## Goals

- The post looks good to a large group, with some emoji, and is not overdone.
  Leads feel good being on it; others feel some interest in an open spot.
- Anyone in the lead pool can take an open spot with one click. No director in
  the loop.
- Subs stay community organized in the thread.

## Non-goals

- A drop-out button. Rob chose "thread only for now": a lead who can't make it
  says so in the thread, and the post keeps their name until someone edits the
  session in Assign. Revisit if stale posts become a problem.
- Notifying leads when their session is cancelled or moved, or when Assign adds
  them later. Real gaps, separate follow-up.
- Any change to the #practices-core block post's look.
- Thank-you lines, a list of all leads, dividers, a "9 of 60" stat, a
  next-block nudge, a small-text alert line. All tried in samples and rejected.

## The post

```
🎿 Lead schedule · Oct 12 – Oct 25                          header
*Week of Oct 12*                                             section, one per week
> 🏃  *Tue 10/13* · 6:15p · <maps|French Park, Visitor Center> · Intervals
> @Katrin and @Gunnar
>
> 💪  *Thu 10/15* · 6:05p · <maps|Balance Fitness Studio> · Circuit
> 🙋 *Needs 2 leads*
>
> 💪  *Thu 10/15* · 7:20p · <maps|Balance Fitness Studio> · Circuit
> @Eleanor and @Jena
[ Lead Thu 10/15 · 6:05p ]                                   actions, only if the week has a takeable session
*Week of Oct 19*
> ...
⭐ @Katrin is leading twice.                                  context footer
Can't make yours? Ask in this thread for a sub.
```

Rules:

- **Week.** Sessions are grouped by the Monday of their week, labeled
  "Week of Oct 12" in bold. All of a week's sessions sit in one mrkdwn quote,
  separated by a bare `>` line, in one section block.
- **Session line.** `{emoji}  *{Dow M/D}* · {time} · {where}`. `where` is the
  location as a Google Maps link (`location.google_maps_url`) labeled
  "Name, Spot" (or "Name" with no spot), then ` · ` and the type names
  (falling back to activity names). No location: "location TBD", unlinked.
  Names are mrkdwn-escaped (`&`, `<`, `>`) and a `|` in a link label
  becomes a space, so a name can't break the link.
- **Leads line.** Mentions joined "@a", "@a and @b", "@a, @b and @c". A lead
  with no linked Slack account shows their short name. Coaches follow as
  "· coach KJ" and never count toward `leads_needed`.
- **Short sessions.** None assigned: `🙋 *Needs N leads*`. Some assigned:
  `@Sarah · 🙋 *Needs N more*`. N is `leads_needed - leads`.
- **Cancelled.** `~Thu 10/15 · 6:05p · Balance Fitness Studio~ _Cancelled_`:
  plain text inside the tildes (no emoji, bold or link), and no button.
- **Activity emoji.** From the practice's first activity by keyword, a dict in
  code: strength 💪, bike 🚴, ski (covers rollerski) 🎿, run or hike 🏃. No
  match or no activity: 🎿.
- **Lead buttons.** One actions block under a week's section with one button
  per *takeable* session: short, not cancelled, and not yet started (compared
  with `now_central_naive()` at render). Label `Lead {Dow M/D} · {time}`, no
  emoji. `action_id` is `lead_signup_{practice_id}` (must be unique within
  the block; Slack rejects the whole message otherwise), `value` is the
  practice id. Confirm dialog: title "Lead this practice?", text
  "{Dow M/D} at {time}, {kind} at {location}. You'll lead with {names}.
  You're added right away. If plans change, ask in the thread." (the "You'll
  lead with" sentence only when someone is already on it), buttons "I'll lead
  it" / "Cancel". `{kind}` is the type names (else activity names, else
  "Practice"); `{location}` is the location name or "location TBD"; `{names}`
  are short names (plain text can't mention). Under Slack's 300-character limit.
- **Footer.** One context block. First line, only when someone leads 2+
  sessions in the block: `⭐ @a is leading twice.` / `⭐ @a and @b are
  leading twice.` / `3 times` for three. People with different counts get one
  line each. Last line always: "Can't make yours? Ask in this thread for a sub."
- **Notification text** (the `text` fallback, what mention pushes show):
  "Lead schedule for Oct 12 – Oct 25 is up · 1 practice still needs leads",
  "· 2 practices still need leads", or "· every practice has leads". Counts
  takeable sessions.
- `chat_postMessage` passes `unfurl_links=False, unfurl_media=False`.
- The block count is about 2 per week plus 2. Fine at any realistic block.

The Post schedule confirm text on the block post gains one sentence: "Open
sessions get a Lead button anyone in the lead pool can take."

## Lead button

`sign_up_as_lead(practice_id, slack_uid) -> dict` in `app/practices/blocks.py`,
called from a Bolt handler registered with a regex on `^lead_signup_\d+$`
(ack, call, private ephemeral on any refusal, same pattern as the
`block_poll_open` handler).

1. Resolve the clicker: `SlackUser.slack_uid` to `User`. Not found, or not in
   `eligible_leads()`: refuse with "Leading is open to the lead pool. Want in?
   Ask in this thread."
2. Lock the practice row: `SELECT ... FOR UPDATE NOWAIT` with
   `populate_existing()` (the `_lock_poll` pattern). Lock taken: "Someone just
   signed up. Try again in a second."
3. Under the lock, refuse with a specific private message when the session is
   gone, cancelled, already started, already has the clicker in any role
   ("You're already on it."), or already has `leads_needed` leads ("Just
   filled, thanks!").
4. Append `PracticeLead(user_id, role="lead")`, commit (releases the lock).
5. `refresh_practice_posts(practice, change_type="edit", notify=False)`. This
   redraws the schedule post, the #practices-core block post, the member
   announcement and the other surfaces, exactly as an Assign save does.
6. If the block's poll has `schedule_ts`, post in its thread:
   `🙌 @Mike is leading Thu 10/15 · 6:05p` plus ` with @Sarah` when others
   lead it. Never raises: a failed reply is logged, the sign-up stands.

Slack shows the edit to everyone with the channel open, so the post updates
live. Two people can each take one spot of a session that needs two. A session
hidden from members (no location or type yet) can still be taken: leads see
it on the schedule, and `refresh_practice_posts` handles hidden practices.

## Assign keeps self-signups

Today `save_assignment` deletes every lead and re-adds the modal's list, so a
self-signup that lands while a director has the modal open is silently
removed on save.

Fix: the modal records who it opened with. `build_assign_modal` writes
`private_metadata` as JSON `{"practice_id": N, "initial_lead_ids": [...]}`.
`_save_block_assign` reads it (a bare integer, from a modal opened before the
deploy, still parses, with `initial_lead_ids=None`). `save_assignment` gains
`initial_lead_ids=None`: when given, it removes only leads the director
unchecked (`initial - submitted`) and adds only leads they checked
(`submitted - initial`), leaving anyone else on the session alone. `None`
keeps today's replace behavior.

## Redraws

Every redraw is a full re-render from the database, so stars, "Needs" lines
and buttons always match the current state. The post redraws on any practice
edit in the block (existing `block_post` refresh surface) and every morning at
8:00 for open polls (`run_lead_availability_nudge_job` already calls
`refresh_block_post`). A past session's button disappears on the next redraw;
the server-side "already started" check covers the gap and covers closed
polls, like the Oct 12-25 cutover block, which get no morning redraw.

## Testing

Real local DB per `tests/practices/conftest.py`.

- Builder (pure): week grouping and labels; one quote per week; map link
  label with and without spot; escaping; mention joining; coach suffix;
  "Needs N leads" vs "Needs N more"; cancelled row; emoji keyword map and
  fallback; buttons only for takeable sessions, unique action ids, no button
  for past sessions; confirm text with and without co-leads, under 300 chars;
  star wording for none, one person, two people, mixed counts; notification
  text plural forms.
- `sign_up_as_lead`: adds and refreshes and replies; refuses not-in-pool,
  unlinked Slack user, cancelled, past, full, already a lead, already a coach;
  lock held by another connection refuses; reply failure does not undo.
- Assign: initial ids round-trip through `private_metadata`; a lead added
  after the modal opened survives a save; unchecking removes; bare-int
  metadata keeps replace behavior.
- Handler: regex registration matches `lead_signup_123`; refusal posts an
  ephemeral.
- `scripts/preview_lead_blocks.py` renders the new post (open and covered).

## Rollout

One PR, no migration. After deploy, refresh the Oct 12-25 block (closed, no
morning redraw) once with the prod one-off pattern so Chris's live post
switches to the new format and shows the Thu 10/15 6:05p Lead button. Verify
in Slack, then update the `lead-availability` skill.
