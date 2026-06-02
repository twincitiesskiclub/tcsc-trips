# Practice ↔ Slack Surface Sync — Design

**Date:** 2026-06-02
**Status:** Approved (design); pending implementation plan
**Scope:** Fix two reported bugs and unify how a practice's information stays
consistent across all Slack surfaces.

## Background

Two user-reported bugs seeded this work:

1. **"Practice post in coord-coaches-practices only shows 2 coaches when three
   are selected."** Confirmed surface: the **coach weekly summary** post in
   `#collab-coaches-practices`.
2. **"Add trigger so that when TCSC Admin is updated it triggers an update to
   Slack."** Plus a broader ask: review how the many surfaces that display
   practice info stay in sync and refactor for consistency, simplicity, and
   future extensibility (e.g. a future lead-scheduling DM system).

### Current architecture (as found)

`app/slack/practices/refresh.py::refresh_practice_posts(practice, change_type,
actor_slack_id, notify)` is already the central dispatcher. It updates each
surface via a bespoke `_refresh_X(practice, change_type)` helper, gated on a
per-surface timestamp column on the `Practice` model:

| Surface | TS column | Update fn |
|---|---|---|
| Announcement (`#announcements-practices`) | `slack_message_ts` / `slack_channel_id` | `update_practice_slack_post` (or cancel/delete/rsvp variants) |
| Collab review (`#collab-coaches-practices`) | `slack_collab_message_ts` | `update_collab_post` |
| Coach weekly summary (`#collab-coaches-practices`) | `slack_coach_summary_ts` | inline rebuild in `_refresh_coach_summary` |
| Weekly summary (`#announcements-practices`) | `slack_weekly_summary_ts` | inline rebuild in `_refresh_weekly_summary` |
| Edit logs (thread replies) | various | `_post_edit_logs` (only when `notify` and `change_type in ('edit','workout')`) |

Practices are **announced** by scheduled jobs (8am for evening practices, 8pm
for next-morning ones), *not* at admin-create time. The dispatcher only ever
**updates existing** posts; it cleanly no-ops when the relevant timestamp is
absent.

### Surfaces that are intentionally NOT in the sync model

- **App Home** — already fresh-on-open. `publish_app_home(user_id)` queries
  live data on the `app_home_opened` event and after a user's own RSVP. Pushing
  it per-change to every user is expensive and unnecessary. Stays out.
- **Create** — defers to the scheduled announce jobs (product decision). The
  dispatcher updates existing posts only.
- **Lead DMs** (current) — one-way messages, not a synced surface. The *future*
  lead-scheduling DM system will join the registry (see §4).

## Decisions (from brainstorming)

- **Bug 1 surface:** coach weekly summary.
- **Refactor ambition:** close the gaps **and** unify the model behind one
  consistent dispatcher contract, ready for future surfaces. (Not a full
  event-bus redesign.)
- **Create timing:** keep deferring to scheduled jobs; dispatcher updates
  existing posts only.

---

## §1 — Bug 1: the dropped coach

**Primary root cause.** `app/practices/service.py::convert_lead_to_info`
returns `None` whenever `lead.user` does not resolve:

```python
def convert_lead_to_info(lead):
    if not lead or not lead.user:   # silently drops the lead
        return None
```

`convert_practice_to_info` (`service.py:136-146`) swallows the `None` with only
a `logger.warning`, so the coach disappears from `PracticeInfo.leads`. The
weekly-summary builder
(`app/slack/blocks/coach_review.py::build_coach_weekly_summary_blocks`,
lines 210-213) renders whatever survives, joined with `", "` and **uncapped** —
so the rendering is not at fault; the data is short one entry. Result: 3
selected, 2 shown.

**Fix.**

1. **Never silently lose a name.** When `lead.user` is unresolved, render a
   degraded but visible entry (e.g. `⚠️ Unknown coach (uid N)`) instead of
   dropping it. A misconfiguration becomes *visible* rather than invisible.
   This is the agreed behavior (degrade-visible, not hard-fail the whole post).
2. **Reproduce against real data.** Query the offending practice's
   `PracticeLead` rows to confirm whether the cause is an orphaned `user_id`
   (User hard-deleted / unlinked) or the modal-resave path below.
3. **Secondary hardening — edit-full modal resave.** The Slack edit-full
   handler (`app/slack/bolt_app.py:952-956`) deletes all `role='coach'`
   `PracticeLead` rows then re-adds from the modal's selected options:

   ```python
   if "coaches_block" in values:
       PracticeLead.query.filter_by(practice_id=practice.id, role='coach').delete()
       for uid in coach_user_ids:
           db.session.add(PracticeLead(practice_id=practice.id, user_id=uid, role='coach'))
   ```

   If the coach multi-select's *option list* is tag-filtered and a currently
   assigned coach isn't in it, Slack cannot pre-select them (initial_options
   must be a subset of options) and they are dropped on save. Verify the option
   list is the full eligible set, or at minimum always includes currently
   assigned coaches.

---

## §2 — Unified surface-sync model

Today each surface is a bespoke `_refresh_X` function with copy-pasted
week-window math, hardcoded fallback channel IDs (e.g. `'C053T1AR48Y'`), and
inconsistent `change_type` handling. Adding a surface means hand-writing another
function and remembering to wire it in.

**Proposal: a declarative surface registry.** Each surface is described once
with a uniform contract:

```
PracticeSurface:
    name        # 'announcement' | 'collab' | 'coach_summary' | 'weekly_summary' | ...
    ts_field    # the Practice.slack_*_ts attribute that gates it (skip if falsy)
    applies_to  # set/list of change_types this surface reacts to
    refresh(practice, change_type) -> dict   # returns {'success': ...} / {'skipped': ...} / {'error': ...}
```

`refresh_practice_posts()` becomes a thin loop:

1. For each registered surface, read `ts_field`; if absent → `{'skipped': True}`.
2. If `change_type not in surface.applies_to` → `{'skipped': True}`.
3. Otherwise call `surface.refresh(practice, change_type)`, capture result.
4. Edit-log thread replies remain a post-pass keyed on `notify` + change_type.

**Shared helpers extracted once** (remove duplication across the inline
rebuilds):

- `week_window(practice.date) -> (week_start, week_end)` — currently duplicated
  in `_refresh_coach_summary` and `_refresh_weekly_summary`.
- Channel resolution / fallback — replace inline literals with a single
  resolver so fallback channel IDs live in `_config.py`, not scattered in
  `refresh.py`.

**Behavior preserved.** Same per-surface gating, same `chat_update` calls, same
result-dict shape returned by `refresh_practice_posts()` (so existing callers
and `tests/slack/test_refresh.py` keep working). This is a structural refactor,
not a behavior change — except where §3 adds missing call sites.

**Why not the full event-bus.** A domain-event/observer layer was considered and
rejected for this pass: larger blast radius and risk than the consistency win
requires. The registry gives the "consistent, simple, abstracted" property the
user asked for while keeping the call graph easy to follow.

---

## §3 — Close the gaps (full mutation-site audit)

Inventory **every** path that mutates a practice or its leads/RSVPs and assert
each routes through the dispatcher. The audit table itself is a deliverable so
coverage is provably complete.

| Mutation site | Location | Today | Action |
|---|---|---|---|
| Admin edit | `admin_practices.py:298` | ✅ `refresh('edit')` | keep |
| Admin cancel | `admin_practices.py:351` | ✅ `refresh('cancel')` | keep |
| Admin delete | `admin_practices.py:320` | ✅ `refresh('delete')` | keep |
| Admin **toggle lead confirmation** | `admin_practices.py:964-987` | ❌ none | **add** `refresh_practice_posts(practice, 'edit')` after commit |
| Admin create | `admin_practices.py:114-201` | defers to jobs | leave (intentional) |
| Slack modal `practice_edit` | `bolt_app.py:884` | ✅ `refresh('edit')` | keep |
| Slack modal `practice_edit_full` | `bolt_app.py:980` | ✅ `refresh('edit', notify=…)` | keep |
| Slack modal `workout_entry` | `bolt_app.py:1046` | ✅ `refresh('workout')` | keep |
| RSVP (button + modal) | `_process_rsvp*` | ✅ `update_practice_rsvp_counts` | keep |

Note: an earlier pass suspected the RSVP *modal* path missed count updates; it
does **not** — `_process_rsvp_with_notes` calls `update_practice_rsvp_counts`.
The one genuine gap is **toggle lead confirmation**, whose state renders on the
announcement, collab, and coach-summary posts.

---

## §4 — Future-proofing for lead-scheduling DMs

When the lead-DM scheduling system lands, it becomes a single registry entry —
no dispatcher or call-site changes:

- New nullable column `Practice.slack_lead_dm_ts` (migration).
- Registry entry: `ts_field='slack_lead_dm_ts'`,
  `applies_to=['edit','cancel','workout']`, `refresh()` re-renders the DM.

This extension recipe is documented in the spec so the pattern is obvious to the
next contributor.

---

## §5 — Testing

Follow the repo's existing pytest + PostgreSQL fixture pattern. Build on
`tests/slack/test_refresh.py` (11 tests).

1. **Regression (bug 1):** a practice with a coach whose `user` is unresolved
   still renders all coach slots (degraded-visible entry), proving none are
   silently dropped.
2. **Refactor safety:** the registry refactor keeps all existing
   `test_refresh.py` tests green (result-dict shape and per-surface gating
   unchanged).
3. **Gap closure:** `toggle_lead_confirmation` triggers a refresh
   (assert the dispatcher is invoked).

---

## Out of scope

- Full domain-event / observer architecture.
- Posting announcements at admin-create time (kept on scheduled jobs).
- Per-change App Home pushes (App Home is fresh-on-open).
- Any redesign of the lead-DM scheduling feature itself (only its future hook
  point is reserved).
