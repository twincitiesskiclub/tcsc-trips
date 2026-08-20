# Trip Registration Slack Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Slack lifecycle for trip registrations — DM on registration and confirmation, auto-invite to the trip channel on confirmation, tcsc.ski link unfurling, and an admin "post announcement" button.

**Architecture:** All Slack side-effects hang off the webhook transitions built in the core plan (`_transition_trip_registration` in `app/routes/payments.py`) and must **never block or fail a registration** — log and continue. Block builders live in `app/slack/blocks/trips.py`; senders in `app/slack/trips.py`. Depends on the core plan being fully merged.

**Tech Stack:** slack_sdk WebClient via `get_slack_client()`, Bolt (`app/slack/bolt_app.py`) for the `link_shared` event, existing Block Kit conventions (`app/slack/blocks/text.py` guards).

## Global Constraints

- Spec: `docs/superpowers/specs/2026-07-31-trip-registration-redesign-design.md` (Slack Integration section).
- Slack failures log and never raise into registration/webhook/admin flows. Follow the guard idiom: check `user.slack_user and user.slack_user.slack_uid` before any DM.
- Every builder is a pure function returning `list[dict]` plus a fallback-text function; run blocks through `guard_slack_blocks` / `guard_fallback_text` (`app/slack/blocks/text.py`).
- Mock Slack in tests by patching `get_slack_client` **at the importing module's path** with a `MagicMock()`.
- New Slack scopes (`links:read`, `links:write`) and the unfurl-domain registration are **manual app-config steps for Rob** — the plan flags them; code must degrade gracefully until they're granted.
- Base URL for links: use `EXTERNAL_BASE_URL` env var, default `https://tcsc.ski` (add to `.env.example`).

---

### Task 1: Trip block builders + DM senders

**Files:**
- Create: `app/slack/blocks/trips.py`, `app/slack/trips.py`
- Modify: `app/slack/blocks/__init__.py` (re-export)
- Test: `tests/trips/test_slack.py`

**Interfaces:**
- Produces (`app/slack/blocks/trips.py`):
  - `build_trip_announcement_blocks(trip, series, spots_left=None) -> list[dict]` — header (trip name), section (destination, `trip.formatted_date_range`, prices low/high, signup window via `format_datetime_central`), optional spots-left context, actions block with a URL button "Sign up" → `f"{base_url}/{series.slug}/register"`
  - `trip_announcement_fallback(trip) -> str`
  - `build_registration_dm_blocks(registration, trip, series) -> list[dict]` — "You're signed up (hold placed)" + their answers rendered as fields + what happens next
  - `build_confirmation_dm_blocks(registration, trip, series) -> list[dict]` — "You're confirmed" + charged amount + channel pointer
  - corresponding `registration_dm_fallback(...)`, `confirmation_dm_fallback(...)`
- Produces (`app/slack/trips.py`):
  - `send_registration_dm(registration) -> bool`
  - `send_confirmation_dm(registration) -> bool`
  - `invite_to_trip_channel(registration) -> bool` — resolves `registration.trip.series.slack_channel_name` → `get_channel_id_by_name` → `add_user_to_channel(slack_uid, channel_id, email)`; returns False (logged) when the series has no channel, the user has no linked SlackUser, or Slack fails
  - `base_url() -> str` — `os.environ.get('EXTERNAL_BASE_URL', 'https://tcsc.ski')`
- Consumes: `get_slack_client`, `get_channel_id_by_name`, `add_user_to_channel` from `app/slack/client.py`; `guard_slack_blocks`, `guard_fallback_text` from `app/slack/blocks/text.py`; `TripRegistration` with `.user`, `.trip`, `.trip.series`.

- [ ] **Step 1: Write failing tests**

`tests/trips/test_slack.py` (reuse `tests/trips/conftest.py`; builders tested pure, senders tested with a patched client):

```python
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from app.constants import UserStatus
from app.models import db, SlackUser, Trip, User
from app.slack.blocks.trips import (
    build_confirmation_dm_blocks,
    build_registration_dm_blocks,
    build_trip_announcement_blocks,
    trip_announcement_fallback,
)
from app.slack import trips as slack_trips
from app.trips.models import TripRegistration, TripRegistrationStatus, TripSeries


@pytest.fixture
def linked_registration(db_session):
    series = TripSeries(slug="test-trip-slack", name="TEST Trip",
                        destination="Testville",
                        slack_channel_name="test-trip-channel")
    db.session.add(series)
    db.session.flush()
    trip = Trip(
        slug="test-trip-slack-2027", name="TEST Trip 2027",
        destination="Testville", series_id=series.id,
        max_participants_standard=20, max_participants_extra=0,
        start_date=datetime(2099, 1, 10), end_date=datetime(2099, 1, 12),
        signup_start=datetime.utcnow() - timedelta(days=1),
        signup_end=datetime.utcnow() + timedelta(days=30),
        price_low=10000, price_high=15000, status="active",
        custom_questions=[],
    )
    slack_user = SlackUser(slack_uid="U_TEST_TRIP", email="trip-member@example.com")
    db.session.add_all([trip, slack_user])
    db.session.flush()
    user = User(first_name="Test", last_name="Member",
                email="trip-member@example.com", status=UserStatus.ACTIVE,
                slack_user_id=slack_user.id)
    db.session.add(user)
    db.session.flush()
    registration = TripRegistration(
        trip_id=trip.id, user_id=user.id,
        status=TripRegistrationStatus.PENDING,
        answers={"chore_preference": "Cooking"},
        price_tier="low", amount_cents=10000,
        payment_intent_id="pi_trip_slack",
    )
    db.session.add(registration)
    db.session.commit()
    return registration


def test_announcement_blocks_have_signup_button(linked_registration):
    trip = linked_registration.trip
    blocks = build_trip_announcement_blocks(trip, trip.series, spots_left=5)
    actions = [b for b in blocks if b["type"] == "actions"]
    assert actions
    button = actions[0]["elements"][0]
    assert button["url"].endswith("/test-trip-slack/register")
    assert trip_announcement_fallback(trip)


def test_registration_dm_includes_answers(linked_registration):
    blocks = build_registration_dm_blocks(
        linked_registration, linked_registration.trip,
        linked_registration.trip.series)
    flat = str(blocks)
    assert "Cooking" in flat


def test_send_registration_dm_posts_to_slack_uid(linked_registration):
    client = MagicMock()
    with patch("app.slack.trips.get_slack_client", return_value=client):
        assert slack_trips.send_registration_dm(linked_registration) is True
    kwargs = client.chat_postMessage.call_args.kwargs
    assert kwargs["channel"] == "U_TEST_TRIP"
    assert kwargs["blocks"]


def test_send_dm_without_linked_slack_user_returns_false(db_session,
                                                         linked_registration):
    linked_registration.user.slack_user_id = None
    db.session.commit()
    client = MagicMock()
    with patch("app.slack.trips.get_slack_client", return_value=client):
        assert slack_trips.send_registration_dm(linked_registration) is False
    client.chat_postMessage.assert_not_called()


def test_invite_to_trip_channel(linked_registration):
    with patch("app.slack.trips.get_channel_id_by_name",
               return_value="C_TRIPCH") as get_channel, \
         patch("app.slack.trips.add_user_to_channel",
               return_value=True) as add:
        assert slack_trips.invite_to_trip_channel(linked_registration) is True
    get_channel.assert_called_once_with("test-trip-channel")
    add.assert_called_once_with("U_TEST_TRIP", "C_TRIPCH",
                                "trip-member@example.com")


def test_invite_without_channel_configured_returns_false(db_session,
                                                         linked_registration):
    linked_registration.trip.series.slack_channel_name = None
    db.session.commit()
    assert slack_trips.invite_to_trip_channel(linked_registration) is False
```

Add `"test-trip-slack"` / `"test-trip-slack-2027"` to `TEST_TRIP_SLUGS` in `tests/trips/conftest.py`, and delete `SlackUser` rows with `slack_uid == "U_TEST_TRIP"` in `_delete_test_trips()` (after deleting the users that reference them).

- [ ] **Step 2: Run tests to verify they fail**

Run: `./run-tests.sh tests/trips/test_slack.py -v`
Expected: FAIL, `No module named 'app.slack.blocks.trips'`.

- [ ] **Step 3: Write `app/slack/blocks/trips.py`**

```python
"""Block Kit builders for trip registration surfaces. Pure functions."""
from app.slack.blocks.text import guard_slack_blocks, guard_fallback_text
from app.utils import format_datetime_central


def _money(cents):
    return f"${cents / 100:.2f}"


def build_trip_announcement_blocks(trip, series, spots_left=None,
                                   base_url="https://tcsc.ski"):
    price = (_money(trip.price_low) if trip.price_low == trip.price_high
             else f"{_money(trip.price_low)}–{_money(trip.price_high)}")
    blocks = [
        {"type": "header",
         "text": {"type": "plain_text", "text": trip.name, "emoji": True}},
        {"type": "section", "fields": [
            {"type": "mrkdwn", "text": f"*Where:* {trip.destination}"},
            {"type": "mrkdwn", "text": f"*When:* {trip.formatted_date_range}"},
            {"type": "mrkdwn", "text": f"*Price:* {price}"},
            {"type": "mrkdwn",
             "text": ("*Signup closes:* "
                      f"{format_datetime_central(trip.signup_end)}")},
        ]},
        {"type": "actions", "elements": [
            {"type": "button",
             "text": {"type": "plain_text", "text": "Sign up", "emoji": True},
             "style": "primary",
             "url": f"{base_url}/{series.slug}/register"},
        ]},
    ]
    if spots_left is not None:
        blocks.insert(2, {"type": "context", "elements": [
            {"type": "mrkdwn", "text": f"{spots_left} spots left"}]})
    return guard_slack_blocks(blocks, surface="trip_announcement")


def trip_announcement_fallback(trip):
    return guard_fallback_text(
        f"{trip.name} — {trip.formatted_date_range} — sign up now",
        surface="trip_announcement")


def _answer_fields(registration):
    fields = []
    for key, value in (registration.answers or {}).items():
        rendered = ", ".join(value) if isinstance(value, list) else str(value)
        fields.append({"type": "mrkdwn", "text": f"*{key}:* {rendered}"})
    return fields[:10]  # Slack caps section fields


def build_registration_dm_blocks(registration, trip, series):
    blocks = [
        {"type": "section", "text": {"type": "mrkdwn", "text": (
            f":ski: *You're signed up for {trip.name}!*\n"
            f"A hold of {_money(registration.amount_cents)} is on your card. "
            "You'll only be charged when the roster is confirmed.")}},
    ]
    fields = _answer_fields(registration)
    if fields:
        blocks.append({"type": "section", "fields": fields})
    blocks.append({"type": "context", "elements": [{"type": "mrkdwn", "text": (
        "We'll DM you when you're confirmed. Questions? Ask in the trip "
        "channel.")}]})
    return guard_slack_blocks(blocks, surface="trip_registration_dm")


def registration_dm_fallback(registration, trip):
    return guard_fallback_text(
        f"You're signed up for {trip.name} — hold placed, charge on "
        "roster confirmation.", surface="trip_registration_dm")


def build_confirmation_dm_blocks(registration, trip, series):
    channel_note = (f"You've been added to #{series.slack_channel_name}."
                    if series.slack_channel_name else "")
    blocks = [
        {"type": "section", "text": {"type": "mrkdwn", "text": (
            f":tada: *You're confirmed for {trip.name}!*\n"
            f"Your card was charged {_money(registration.amount_cents)}. "
            f"{channel_note}")}},
    ]
    return guard_slack_blocks(blocks, surface="trip_confirmation_dm")


def confirmation_dm_fallback(registration, trip):
    return guard_fallback_text(
        f"You're confirmed for {trip.name} — card charged.",
        surface="trip_confirmation_dm")
```

Re-export the six names from `app/slack/blocks/__init__.py` (append to the imports and `__all__`, matching the existing style).

- [ ] **Step 4: Write `app/slack/trips.py`**

```python
"""Slack side-effects for trip registrations. Every function returns bool
and never raises - trip flows must not fail because Slack did."""
import os

from flask import current_app
from slack_sdk.errors import SlackApiError

from app.slack.client import (
    add_user_to_channel, get_channel_id_by_name, get_slack_client,
)
from app.slack.blocks.trips import (
    build_confirmation_dm_blocks, build_registration_dm_blocks,
    confirmation_dm_fallback, registration_dm_fallback,
)


def base_url():
    return os.environ.get('EXTERNAL_BASE_URL', 'https://tcsc.ski')


def _slack_uid(registration):
    user = registration.user
    if user and user.slack_user and user.slack_user.slack_uid:
        return user.slack_user.slack_uid
    return None


def _send_dm(registration, blocks, fallback):
    slack_uid = _slack_uid(registration)
    if not slack_uid:
        current_app.logger.info(
            "trip slack: no linked SlackUser for registration %s",
            registration.id)
        return False
    try:
        get_slack_client().chat_postMessage(
            channel=slack_uid, blocks=blocks, text=fallback)
        return True
    except (SlackApiError, Exception) as exc:
        current_app.logger.warning(
            "trip slack: DM failed for registration %s: %s",
            registration.id, exc)
        return False


def send_registration_dm(registration):
    trip = registration.trip
    return _send_dm(
        registration,
        build_registration_dm_blocks(registration, trip, trip.series),
        registration_dm_fallback(registration, trip))


def send_confirmation_dm(registration):
    trip = registration.trip
    return _send_dm(
        registration,
        build_confirmation_dm_blocks(registration, trip, trip.series),
        confirmation_dm_fallback(registration, trip))


def invite_to_trip_channel(registration):
    trip = registration.trip
    channel_name = trip.series.slack_channel_name if trip.series else None
    if not channel_name:
        return False
    slack_uid = _slack_uid(registration)
    if not slack_uid:
        return False
    try:
        channel_id = get_channel_id_by_name(channel_name)
        if not channel_id:
            current_app.logger.warning(
                "trip slack: channel %s not found", channel_name)
            return False
        return add_user_to_channel(slack_uid, channel_id,
                                   registration.user.email)
    except Exception as exc:
        current_app.logger.warning(
            "trip slack: invite failed for registration %s: %s",
            registration.id, exc)
        return False
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `./run-tests.sh tests/trips/test_slack.py -v` → all PASS.

- [ ] **Step 6: Commit**

```bash
git add app/slack/blocks/trips.py app/slack/trips.py app/slack/blocks/__init__.py tests/trips/test_slack.py tests/trips/conftest.py
git commit -m "feat(trips): Slack block builders, DMs, channel invite"
```

---

### Task 2: Hook DMs + invite into the webhook transitions

**Files:**
- Modify: `app/routes/payments.py` (`_transition_trip_registration`)
- Test: `tests/trips/test_webhook.py` (extend)

**Interfaces:**
- Consumes: Task 1 senders; the core plan's `_transition_trip_registration(payment_intent, new_status)`.
- Produces: hold placed (`PENDING`) → `send_registration_dm`; captured (`CONFIRMED`) → `send_confirmation_dm` + `invite_to_trip_channel`. Only on actual transitions (idempotent webhooks must not re-DM).

- [ ] **Step 1: Write failing tests**

Append to `tests/trips/test_webhook.py`:

```python
@patch("app.routes.payments.trip_slack")
def test_capturable_sends_registration_dm(trip_slack, client, db_session,
                                          pending_registration):
    payload = _webhook_payload("payment_intent.amount_capturable_updated",
                               pending_registration.id,
                               pending_registration.trip_id)
    _post_development_webhook(client, payload)
    trip_slack.send_registration_dm.assert_called_once()


@patch("app.routes.payments.send_payment_notification")
@patch("app.routes.payments.trip_slack")
def test_succeeded_sends_confirmation_and_invite(trip_slack, notify, client,
                                                 db_session,
                                                 pending_registration):
    from app.trips.models import TripRegistrationStatus
    pending_registration.status = TripRegistrationStatus.PENDING
    db_session.session.commit()
    payload = _webhook_payload("payment_intent.succeeded",
                               pending_registration.id,
                               pending_registration.trip_id)
    _post_development_webhook(client, payload)
    trip_slack.send_confirmation_dm.assert_called_once()
    trip_slack.invite_to_trip_channel.assert_called_once()


@patch("app.routes.payments.send_payment_notification")
@patch("app.routes.payments.trip_slack")
def test_repeat_succeeded_webhook_does_not_re_dm(trip_slack, notify, client,
                                                 db_session,
                                                 pending_registration):
    from app.trips.models import TripRegistrationStatus
    pending_registration.status = TripRegistrationStatus.CONFIRMED
    db_session.session.commit()
    payload = _webhook_payload("payment_intent.succeeded",
                               pending_registration.id,
                               pending_registration.trip_id)
    _post_development_webhook(client, payload)
    trip_slack.send_confirmation_dm.assert_not_called()
```

Run: `./run-tests.sh tests/trips/test_webhook.py -v` → new tests FAIL (`trip_slack` attribute missing).

- [ ] **Step 2: Wire it up**

In `app/routes/payments.py`, add near the other imports:

```python
from app.slack import trips as trip_slack
```

Rework `_transition_trip_registration` to return whether a transition happened and fire the side-effects:

```python
def _transition_trip_registration(payment_intent, new_status):
    from app.trips.models import TripRegistrationStatus
    metadata = _stripe_object_value(payment_intent, 'metadata', {}) or {}
    registration = _trip_registration_from_metadata(metadata)
    if registration is None:
        return
    if registration.status == new_status:
        return  # idempotent webhook redelivery - no re-DM
    if (new_status == TripRegistrationStatus.CANCELLED
            and registration.status == TripRegistrationStatus.CONFIRMED):
        return
    registration.status = new_status
    db.session.commit()
    if new_status == TripRegistrationStatus.PENDING:
        trip_slack.send_registration_dm(registration)
    elif new_status == TripRegistrationStatus.CONFIRMED:
        trip_slack.send_confirmation_dm(registration)
        trip_slack.invite_to_trip_channel(registration)
```

- [ ] **Step 3: Run tests**

Run: `./run-tests.sh tests/trips/test_webhook.py tests/events/test_webhook.py -v` → all PASS.

- [ ] **Step 4: Commit**

```bash
git add app/routes/payments.py tests/trips/test_webhook.py
git commit -m "feat(trips): DM + channel invite on registration lifecycle"
```

---

### Task 3: Admin "Post announcement to Slack" button

**Files:**
- Modify: `app/routes/admin.py`, `app/static/admin_trips.js`
- Test: `tests/trips/test_admin.py` (extend)

**Interfaces:**
- Produces: `POST /admin/trips/<int:trip_id>/announce` — JSON body `{"channel": "<name-or-empty>"}`; empty channel defaults to the series channel. Returns `{"success": true}` or `{"success": false, "error": ...}` (400/502).
- Consumes: `build_trip_announcement_blocks`, `trip_announcement_fallback`, `get_channel_id_by_name`, `get_slack_client`, `base_url()` from `app/slack/trips.py`; the core plan's `_active_count`-style spots calculation via `app.trips.service.capacity_available` internals — compute `spots_left = max(0, (standard + extra) - active_count)` using `app.trips.service._active_count(trip)`.

- [ ] **Step 1: Write failing test**

```python
from unittest.mock import MagicMock, patch


def test_announce_posts_blocks_to_channel(admin_client, db_session):
    series, trip = _series_with_edition(db_session)
    client_mock = MagicMock()
    with patch("app.routes.admin.get_slack_client",
               return_value=client_mock), \
         patch("app.routes.admin.get_channel_id_by_name",
               return_value="C_ANNOUNCE"):
        response = admin_client.post(f"/admin/trips/{trip.id}/announce",
                                     json={"channel": ""})
    assert response.get_json()["success"] is True
    kwargs = client_mock.chat_postMessage.call_args.kwargs
    assert kwargs["channel"] == "C_ANNOUNCE"
    assert any(b["type"] == "actions" for b in kwargs["blocks"])


def test_announce_without_channel_errors(admin_client, db_session):
    series, trip = _series_with_edition(db_session)
    series.slack_channel_name = None
    db.session.commit()
    response = admin_client.post(f"/admin/trips/{trip.id}/announce",
                                 json={"channel": ""})
    assert response.status_code == 400
```

Run: `./run-tests.sh tests/trips/test_admin.py -v` → FAIL 404.

- [ ] **Step 2: Implement the route**

In `app/routes/admin.py`:

```python
from ..slack.client import get_channel_id_by_name, get_slack_client
from ..slack.blocks.trips import (
    build_trip_announcement_blocks, trip_announcement_fallback,
)


@admin.route('/admin/trips/<int:trip_id>/announce', methods=['POST'])
@admin_required
def announce_trip(trip_id):
    from app.slack.trips import base_url
    from app.trips.service import _active_count
    trip = db.session.get(Trip, trip_id)
    if trip is None:
        return {'success': False, 'error': 'Trip not found'}, 404
    data = request.get_json(silent=True) or {}
    channel_name = (data.get('channel') or '').strip() or (
        trip.series.slack_channel_name if trip.series else None)
    if not channel_name:
        return {'success': False,
                'error': 'No channel configured for this trip.'}, 400
    capacity = (trip.max_participants_standard or 0) + (
        trip.max_participants_extra or 0)
    spots_left = max(0, capacity - _active_count(trip)) if capacity else None
    try:
        channel_id = get_channel_id_by_name(channel_name)
        if not channel_id:
            return {'success': False,
                    'error': f'Channel #{channel_name} not found.'}, 400
        get_slack_client().chat_postMessage(
            channel=channel_id,
            blocks=build_trip_announcement_blocks(
                trip, trip.series, spots_left=spots_left,
                base_url=base_url()),
            text=trip_announcement_fallback(trip),
            unfurl_links=False, unfurl_media=False,
        )
    except Exception as exc:
        return {'success': False, 'error': str(exc)}, 502
    return {'success': True}
```

- [ ] **Step 3: Button in `admin_trips.js`**

In the trip drawer (`tripsOpenDrawer`), add a "Post announcement" button: `window.prompt('Channel (blank = trip channel):', '')` → POST `{channel}` to `'/admin/trips/' + trip.id + '/announce'` → toast success/error via the page's existing `showSuccess`/`showError` helpers.

- [ ] **Step 4: Run tests + manual, commit**

Run: `./run-tests.sh tests/trips/test_admin.py -v` → PASS. Manual: post to a private test channel; verify the card and Sign up button.

```bash
git add app/routes/admin.py app/static/admin_trips.js tests/trips/test_admin.py
git commit -m "feat(trips): admin post-announcement-to-Slack button"
```

---

### Task 4: Link unfurling for tcsc.ski trip links

**Files:**
- Modify: `app/slack/bolt_app.py`, `.env.example`
- Test: `tests/trips/test_slack.py` (extend)

**Interfaces:**
- Produces: `@bolt_app.event("link_shared")` handler → `client.chat_unfurl(channel, ts, unfurls={url: <section block card>})` for any shared link whose path matches a `TripSeries` slug (with or without `/register` suffix). Non-trip links are ignored.
- Consumes: `TripSeries`, `current_edition()`, `build_trip_announcement_blocks` (reused as the unfurl body, minus the actions block — unfurls render buttons poorly in some clients; keep the button, Slack supports it).
- **Manual prerequisite (Rob, flagged at handoff):** in the Slack app config, add `links:read` + `links:write` scopes, register `tcsc.ski` as an unfurl domain (Event Subscriptions → App unfurl domains), reinstall the app. Until then the handler simply never fires.

- [ ] **Step 1: Write failing test**

Append to `tests/trips/test_slack.py`:

```python
def test_unfurl_payload_for_trip_link(linked_registration):
    from app.slack.bolt_app import build_trip_unfurls
    trip = linked_registration.trip
    unfurls = build_trip_unfurls([
        {"url": "https://tcsc.ski/test-trip-slack/register"},
        {"url": "https://tcsc.ski/not-a-trip"},
    ])
    assert "https://tcsc.ski/test-trip-slack/register" in unfurls
    assert "https://tcsc.ski/not-a-trip" not in unfurls
    card = unfurls["https://tcsc.ski/test-trip-slack/register"]
    assert card["blocks"]
```

Run: `./run-tests.sh tests/trips/test_slack.py -v` → FAIL (no `build_trip_unfurls`).

- [ ] **Step 2: Implement in `app/slack/bolt_app.py`**

Add a module-level pure helper (importable without Bolt being configured — place it near the top-level helpers, NOT inside the `if _bot_token:` block):

```python
def build_trip_unfurls(links):
    """Map shared tcsc.ski trip URLs to unfurl cards. Pure; safe without
    Slack credentials. Called from the link_shared handler."""
    from urllib.parse import urlparse
    from app.slack.blocks.trips import build_trip_announcement_blocks
    from app.slack.trips import base_url
    from app.trips.models import TripSeries
    unfurls = {}
    for link in links or []:
        url = link.get("url", "")
        path = urlparse(url).path.strip("/")
        slug = path[:-len("/register")] if path.endswith("/register") else path
        slug = slug.strip("/")
        if not slug or "/" in slug:
            continue
        series = TripSeries.query.filter_by(slug=slug).first()
        if series is None:
            continue
        trip = series.current_edition()
        if trip is None or trip.status != "active":
            continue
        unfurls[url] = {"blocks": build_trip_announcement_blocks(
            trip, series, base_url=base_url())}
    return unfurls
```

Inside the `if _bot_token:` block, next to the other `@bolt_app.event` handlers (~line 1181):

```python
    @bolt_app.event("link_shared")
    def handle_link_shared(event, client, logger):
        with get_app_context():
            unfurls = build_trip_unfurls(event.get("links", []))
            if not unfurls:
                return
            try:
                client.chat_unfurl(channel=event["channel"],
                                   ts=event["message_ts"], unfurls=unfurls)
            except Exception as exc:
                logger.warning("trip unfurl failed: %s", exc)
```

Add to `.env.example` under the Slack section:

```
# Link unfurling for tcsc.ski trip links requires the links:read and
# links:write scopes plus "tcsc.ski" registered as an app unfurl domain.
EXTERNAL_BASE_URL=https://tcsc.ski
```

- [ ] **Step 3: Run tests, commit**

Run: `./run-tests.sh tests/trips/test_slack.py tests/slack/ -v` → PASS, no Slack-suite regressions.

```bash
git add app/slack/bolt_app.py .env.example tests/trips/test_slack.py
git commit -m "feat(trips): unfurl tcsc.ski trip links into signup cards"
```

---

## Final verification (whole plan)

- [ ] `./run-tests.sh` — zero new failures.
- [ ] Manual with Stripe CLI + a test Slack channel: register → DM arrives; capture from roster → confirmation DM + channel invite.
- [ ] Announcement button posts the card to a test channel; Sign up button opens the register page.
- [ ] **Handoff note for Rob:** unfurling stays dormant until the Slack app gets `links:read`/`links:write` and the `tcsc.ski` unfurl domain (manual app-config step + reinstall). Then paste a trip link in any channel to verify the card.
