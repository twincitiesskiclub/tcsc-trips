# Practice Authoring Preview Design

**Date:** 2026-07-14
**Status:** Approved
**Scope:** A discard-only Slack practice modal preview and one admin autosave
interaction correction

## 1. Context

Practice Plan reactions can now be configured as defaults on Activities and
Workout Types, inherited into a practice, and overridden for one practice in
the admin editor or Slack create modal. Automated coverage verifies the data
and Block Kit payloads, and the admin editor has been exercised in a real
browser. There is not yet a safe way to open the native Slack create modal for
visual review: a normal create submission persists a practice, while a normal
edit submission targets an existing practice.

The Practices Configuration page also autosaves Plan reaction defaults on
field `change`. When a coordinator enters an emoji and moves naturally to the
adjacent label, the incomplete row is treated as an error before the
coordinator has had a chance to enter that label. The premature red message
and focus movement make an otherwise ordinary two-field entry feel broken.

## 2. Considered Slack preview approaches

### 2.1 `/tcsc practice-preview` with a discard-only modal — selected

Branch directly in the existing `/tcsc` Bolt command listener, require the
dedicated test channel, and open the production create-modal builder with
synthetic values. Give the resulting view a preview-specific callback and
make its submission acknowledge and close without invoking creation logic.

This exercises Slack's native modal renderer and the actual production field
layout without creating a practice or a persistent test message.

### 2.2 Post a Preview button in the test channel

A button would also provide the `trigger_id` required to open a modal, but it
would leave a channel message to manage and add another action handler solely
to reach the same view.

### 2.3 Block Kit Builder only

The Builder is useful for a static visual check, but it does not prove the
workspace command, native trigger, modal callback, or discard behavior. It
also depends on a separate authenticated browser session.

## 3. Slack command contract

The exact command is:

```text
/tcsc practice-preview
```

It is accepted only when Slack supplies channel ID `C07G9RTMRT3`. No role or
tag lookup is performed because this is a test-only surface and the channel's
membership policy is the access boundary. When invoked elsewhere, the bot
responds ephemerally that Practice Preview is available only in the test
channel and does not attempt to open a view.

The command listener acknowledges immediately. A missing `trigger_id` returns
an ephemeral retry message. A Slack `views.open` failure is logged and returns
an ephemeral retry message; neither failure path touches practice data.

Normal `/tcsc` subcommands continue through the existing command processor.
The preview command is not added to member-facing `/tcsc help` because it is a
test-channel diagnostic rather than a public workflow.

## 4. Preview modal contract

The preview reuses `build_practice_create_modal()` so field order, labels,
hints, limits, selectors, and Plan reaction formatting are the same as the
real create flow. It supplies in-memory synthetic values for:

- Theodore Wirth - Trailhead;
- a 6:15 PM practice on the current Central calendar date;
- Rollerski and Running Activities;
- Intervals and Technique Workout Types;
- a Preview Coach and Preview Lead;
- `:evergreen_tree:` for endurance instead of intervals;
- `:hatching_chick:` for new rollerskier;
- `:older_adult::skin-tone-4:` for experienced rollerskier; and
- `:athletic_shoe:` for runner.

Only safety-facing view metadata changes after the production builder returns:

- title: `Practice Preview`;
- submit label: `Close Preview`;
- callback ID: `practice_preview`; and
- private metadata: empty, because no persistence target exists.

The Plan reactions input remains the approved multiline snapshot with one
`:emoji: member-facing label` pair per line. Changing Activity or Practice
Type selectors does not recalculate the field. Dynamic `views.update`
behavior, a row editor inside Slack, and changes to the real create/edit
flows remain out of scope.

## 5. Zero-persistence guarantee

`practice_preview` has its own view-submission listener. The listener only
acknowledges the submission, which closes the modal. It does not call the
practice-create parser or handler and does not open an application context.

Invoking, closing, or submitting the preview creates or changes none of the
following:

- `Practice`, Activity, Workout Type, location, lead, or RSVP rows;
- `AppConfig` or saved Plan reaction defaults;
- Slack channel messages, threads, reactions, or timestamps;
- weekly or coach summaries; or
- announcement validation-harness state.

Consequently, the preview requires no production database cleanup and no
Slack teardown. Slack owns the temporary modal surface and dismisses it when
the user closes or submits it.

## 6. Admin autosave correction

The inline Activity and Workout Type editors keep the existing controls and
autosave vocabulary. No button, layout, or data-model change is introduced.

When any row has only an emoji or only a label at an autosave boundary:

- do not send a mutation request;
- do not mark the status as an error;
- do not redirect focus; and
- show the neutral status `Complete both fields to save.`

After both fields are present, the next ordinary `change` event performs the
existing autosave and shows `Saving…` followed by `Saved.`. Reorder, Remove,
and a complete new row retain their existing immediate-save behavior.
Server rejection of a complete row, including a reserved, malformed, or
duplicate emoji, remains an error in the live status region.

## 7. Boundaries and non-goals

- No role authorization is added to preview, create, or edit flows.
- No production practice or settings data is used to populate the preview.
- No database migration, model, or stored configuration is added.
- No new Slack message, shortcut, button, or public command is introduced.
- No change is made to Plan reaction inheritance or saved-snapshot semantics.
- No change is made to announcements, reaction seeding, attendance, or RSVP
  persistence.
- No new frontend framework, emoji picker, debounce queue, or autosave
  subsystem is introduced.

## 8. Verification design

Automated tests will prove:

- the preview view uses the production create builder's field structure;
- the preview callback cannot be mistaken for `practice_create`;
- all four synthetic Plan reactions, including the skin-tone shortcode, are
  prefilled exactly;
- preview title, submit label, and empty metadata make the discard behavior
  explicit;
- the submission listener acknowledges without parsing or persistence;
- the test-channel guard accepts only `C07G9RTMRT3`;
- missing triggers and `views.open` failures return ephemeral retry copy;
- ordinary `/tcsc` subcommands retain their current behavior; and
- an incomplete admin row stays neutral and sends no mutation, while a
  completed row still reaches autosave and server errors remain errors.

After deployment, the native smoke test is:

1. In `C07G9RTMRT3`, invoke `/tcsc practice-preview`.
2. Inspect the modal on desktop and mobile, including all four reaction lines.
3. Edit, reorder, and clear text locally in the modal.
4. Select `Close Preview` and confirm the modal dismisses.
5. Confirm that no practice, Slack message, reaction, or summary was created.

Invoking the command outside the test channel must return the ephemeral guard
message and open no modal.
