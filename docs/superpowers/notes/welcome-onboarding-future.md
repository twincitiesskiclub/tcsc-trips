# Welcome / Onboarding — Future Work

Captured during the 2026-05-15 rewrite of the `#a-welcome-to-tcsc` pinned messages. The pinned-message edit (welcome + channel map) is the surface fix; the items below are the strategic onboarding work an 8-agent consulting review surfaced. They are intentionally out of scope for the pin edit and recorded here so they don't get lost.

The pinned welcome is a **reference document**, not the activation mechanism. None of the items below should be implemented by adding more to the pin.

## Highest-leverage items

### 1. `team_join` event handler → bot DM sequence
The Behaviorist and Growth PM agents both ranked this as the actual activation lever. A new member joining the workspace gets a bot DM within 60 seconds with one CTA per message:
- DM 1: "Finish your Slack profile" with the tap-path
- DM 2: Pre-filled RSVP for the soonest upcoming practice ("Tuesday 6:15pm at Wirth — want me to RSVP you as going?")
- DM 3 (day of): location, parking, what to bring
- DM 4 (post-practice): "how'd it go — coming back Saturday?"

Wires into existing `bolt_app.py` event handlers and `PracticeRSVP` infra. The hard part is sequencing and idempotency.

### 2. Per-member practice attendance instrumentation
Right now `Practice` has `coach_approved` but no per-member attendance capture. The Growth PM agent's bluntest line: "you literally cannot tell me what % of new members ever attended a practice."

Cheapest version: post-practice button for the coach/lead to tap each name that showed up. Stored on a new `PracticeAttendance` table or as a status on existing `PracticeRSVP` rows.

Unlocks the only metric that matters: **% of new members who attend a practice within 21 days**.

### 3. Lead/coach "new member at this practice" heads-up DM
When a new member RSVPs `going` for the first time, the bot DMs the practice lead: *"[Name] is new, this is their first practice — they'll be in [whatever profile photo / signal]. Say hi."*

The Behaviorist's "named-tether formed" insight: the leading indicator of retention isn't profile completion, it's whether the member leaves practice #1 with at least one named human who expects to see them at practice #2.

## Medium-leverage items

### 4. App Home "New here?" header
The IA agent's recommendation: App Home is for *doing*, the pin is for reference. Add a "New here?" section to the top of `publish_app_home()` that surfaces:
- Profile completion status (photo + name filled? if not, prompt)
- Next upcoming practice with RSVP buttons
- Quick links to `#fresh-tracks` template and the Practice Guide

Auto-hides after first RSVP or 14 days post-join.

### 5. Welcome buddy rotation
Community Manager agent's recommendation: rotate one current member (board / coach / vocal regular) each week as the *named* welcome contact, with face and Slack handle, in the welcome pin or a bot DM.

Currently the welcome names @gude/@augie/@rob as fixed contacts. A rotating named buddy de-abstracts "ping @leadership" further.

## Operational / one-time

### 6. Lurker audit (Monday-morning move)
Community Manager's call: identify the last ~20-30 members who joined Slack and never RSVP'd to a practice. DM each one personally — *"Hey, saw you joined a while back — anything we can do to get you out to a Tuesday?"*

This is a one-time admin task, not a code change. Expected yield: 3-4 honest answers about what's broken (intimidation, schedule, gear, didn't know where Wirth was). Those answers shape the next round of onboarding edits more than any further copy refinement.

## Voice / content notes

### 7. The pinned channel map needs an admin to pin
`#a-welcome-to-tcsc` is the workspace's `#general` channel (`is_general: True`), which restricts pinning to workspace admins. The bot has `pins:write` but is blocked. The `scripts/post_welcome_message.py` script will warn `restricted_action` on pinning the channel map; an admin needs to pin manually after each repost.

Workarounds considered: granting bot admin role (too broad), using user token (also missing scope). Cleanest path remains manual pin by an admin after running the script.

### 8. Source of truth
Copy lives in `scripts/welcome_template.md`. Update there first, then re-run `scripts/post_welcome_message.py`. The script `chat.update`s the existing welcome pin (preserves reactions and pin date) and re-posts the channel map (manual pin needed).

## Reference — what was changed in the 2026-05-15 rewrite

- Replaced the old single-pin paragraph with two pins (welcome + channel map)
- Reframed photo-prompt around the in-practice name/pronouns/QOTD ritual
- Cut all em-dashes; tightened all 11 channel-map descriptions
- Replaced "ping @leadership" with named contacts (@gude, @augie, @rob) + the @leadership group
- Added link to Practice Guide canvas and to the `#fresh-tracks` intro template
- Used Block Kit for both pins (rich_text_list for the channel map, real channel mentions)
