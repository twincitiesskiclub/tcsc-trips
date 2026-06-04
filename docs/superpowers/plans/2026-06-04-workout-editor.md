# Unified Workout Editor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the two inconsistent practice/workout editors (full-page + grid modal) with one polished, mobile-friendly full-page editor.

**Architecture:** The full-page editor at `app/templates/admin/practices/detail.html` becomes the single canonical editor. A new shared JS module holds the pill/person-search/assists logic (lifted from the modal). The grid's Edit/Create buttons navigate to the page instead of opening a modal; the modal markup and its JS are deleted. A new `GET /admin/practices/new` route renders the page in create mode. The two POST endpoints (`create_practice`, `edit_practice`) are unchanged.

**Tech Stack:** Flask + Jinja2, Tailwind (compiled `tailwind-output.css`) + per-template inline `<style>`, vanilla JS (no build step, no JS test harness), Tabulator grid, pytest + PostgreSQL fixtures.

**Visual source of truth:** `docs/superpowers/specs/2026-06-04-workout-editor-mockup.html` (the approved, committed mockup). Where this plan says "port the mockup," that file's `<style>` and markup are the literal reference — de-scope its `#dir-final` selector to the page.

**Design spec:** `docs/superpowers/specs/2026-06-04-workout-editor-design.md`

---

## File Structure

| File | Responsibility | Action |
|------|----------------|--------|
| `app/routes/admin_practices.py` | Add `GET /admin/practices/new` (create-mode render) | Modify |
| `tests/routes/test_admin_practices_routes.py` | Route tests for new + detail render | Create |
| `app/static/practice_editor.js` | Reusable pill / person-pill / search / assists / collect helpers (`pe*` globals) | Create |
| `app/templates/admin/practices/detail.html` | The single polished full-page editor (form + context rail) | Rewrite |
| `app/static/admin_practices.js` | Grid only: Edit/Create navigate to the page; modal JS removed | Modify |
| `app/templates/admin/practices/list.html` | Grid + cancel modal only; edit/create modal removed | Modify |
| `app/templates/admin/partials/sidebar.html` | Verify active-state for editor routes | Verify |
| `app/templates/admin/practices/calendar.html` | Already links to the page | Verify only |

**Conventions to follow (verified in repo):**
- `admin_required` (`app/auth.py`) gates admin routes via `session['user']['email']` on the `@twincitiesskiclub.org` domain. Tests authenticate by setting that session key.
- Each test file defines its own `app` / `client` / `db_session` fixtures (no shared `conftest.py`). Mirror `tests/routes/test_payments.py`.
- The people endpoint `/admin/practices/people/data` returns `{coaches, leads, assists}` where each person has `id` (User.id), `name`, `tags[]`. Selected-people arrays in Jinja are User ids.
- Activities/types endpoints return objects with `id` and `name`; Jinja selected arrays are activity/type ids.
- POST payload shape (unchanged, consumed by `create_practice`/`edit_practice`): `{date, location_id, social_location_id, activity_ids[], type_ids[], coach_ids[], lead_ids[], assist_ids[], warmup_description, workout_description, cooldown_description, is_dark_practice, status?}`.

---

## Task 1: Add the create-mode route (`GET /admin/practices/new`)

**Files:**
- Modify: `app/routes/admin_practices.py` (add route near `practice_detail`, ~line 132)
- Create: `tests/routes/test_admin_practices_routes.py`

- [ ] **Step 1: Write the failing test**

Create `tests/routes/test_admin_practices_routes.py`:

```python
"""Tests for app.routes.admin_practices page renders."""

import pytest

from app import create_app
from app.models import db


@pytest.fixture
def app():
    app = create_app()
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = (
        'postgresql://tcsc:tcsc@localhost:5432/tcsc_trips'
    )
    return app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def db_session(app):
    with app.app_context():
        db.create_all()
        yield db
        db.session.rollback()


@pytest.fixture
def admin_client(client):
    """A test client with an authenticated admin session."""
    with client.session_transaction() as sess:
        sess['user'] = {'email': 'tester@twincitiesskiclub.org', 'name': 'Tester'}
    return client


def test_new_practice_route_renders_create_mode(admin_client, db_session):
    resp = admin_client.get('/admin/practices/new')
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    # Create mode: title says "New Practice" and there is no context rail yet.
    assert 'New Practice' in body
    assert 'Lead Confirmations' not in body


def test_new_practice_route_requires_auth(client, db_session):
    resp = client.get('/admin/practices/new')
    # Unauthenticated users are redirected to login.
    assert resp.status_code == 302
    assert '/login' in resp.headers.get('Location', '')
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/routes/test_admin_practices_routes.py -v`
Expected: `test_new_practice_route_renders_create_mode` FAILS (404, route does not exist yet).

- [ ] **Step 3: Add the route**

In `app/routes/admin_practices.py`, immediately after the `practice_detail` function (after line 138), add:

```python
@admin_practices_bp.route('/new')
@admin_required
def practice_new():
    """Render the editor in create mode (no practice)."""
    social_locations = SocialLocation.query.order_by(SocialLocation.name).all()
    return render_template(
        'admin/practices/detail.html',
        practice=None,
        social_locations=social_locations,
    )
```

> Note: `detail.html` already handles `practice=None` (it renders the "New Practice" title and skips the context sections via `{% if practice %}`). This route only needs to pass `practice=None` and the social locations list, mirroring `practice_detail`.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/routes/test_admin_practices_routes.py -v`
Expected: both tests PASS.

- [ ] **Step 5: Commit**

```bash
git add app/routes/admin_practices.py tests/routes/test_admin_practices_routes.py
git commit -m "feat(practices): add GET /admin/practices/new create-mode route"
```

---

## Task 2: Create the shared editor JS module

Lift the reusable pill/person logic out of the modal into a standalone module the page loads. Functions are global (the app uses plain `<script src>`, no ES modules), namespaced with a `pe` prefix to avoid collisions.

**Files:**
- Create: `app/static/practice_editor.js`

- [ ] **Step 1: Write the module**

Create `app/static/practice_editor.js` with the following content. (The person-pill helpers are lifted verbatim from `admin_practices.js` lines 411–531; `peRenderTagPills` is the id-based equivalent of the modal's name-based activity/type pills; `peCollectIds` reads selections for the submit handler.)

```javascript
/* Reusable controls for the practice editor page (pills, person search, assists).
   Loaded by admin/practices/detail.html. Globals are prefixed `pe`. */

function peRoleEmoji(person) {
    if (!person.tags || person.tags.length === 0) return null;
    const preferred = ['HEAD_COACH', 'ASSISTANT_COACH', 'PRACTICES_LEAD', 'PRACTICES_DIRECTOR'];
    for (const tagName of preferred) {
        const tag = person.tags.find(t => t.name === tagName);
        if (tag && tag.emoji) return tag.emoji;
    }
    const withEmoji = person.tags.find(t => t.emoji);
    return withEmoji ? withEmoji.emoji : null;
}

/* Activity / Type pills, selected by id. Toggles `.selected` on click. */
function peRenderTagPills(containerId, data, selectedIds) {
    const container = document.getElementById(containerId);
    if (!container) return;
    container.innerHTML = '';
    if (!data || data.length === 0) {
        container.innerHTML = '<span class="pe-empty">None defined</span>';
        return;
    }
    for (const item of data) {
        const label = document.createElement('button');
        label.type = 'button';
        label.className = 'pe-pill' + (selectedIds.includes(item.id) ? ' selected' : '');
        label.dataset.value = item.id;
        label.setAttribute('aria-pressed', selectedIds.includes(item.id) ? 'true' : 'false');
        label.textContent = item.name;
        label.onclick = () => {
            const on = label.classList.toggle('selected');
            label.setAttribute('aria-pressed', on ? 'true' : 'false');
        };
        container.appendChild(label);
    }
}

function peCreatePersonPill(person, isSelected, containerId, summaryId) {
    const label = document.createElement('button');
    label.type = 'button';
    label.className = 'person-pill' + (isSelected ? ' selected' : '');
    label.dataset.value = person.id;
    label.dataset.name = person.name.toLowerCase();
    label.setAttribute('aria-pressed', isSelected ? 'true' : 'false');

    const check = document.createElement('span');
    check.className = 'check-icon';
    check.setAttribute('aria-hidden', 'true');
    check.innerHTML = '<svg viewBox="0 0 10 10" fill="none"><path d="M2 5.5L4 7.5L8 3" stroke="white" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>';
    label.appendChild(check);

    const nameSpan = document.createElement('span');
    nameSpan.textContent = person.name;
    label.appendChild(nameSpan);

    const roleEmoji = peRoleEmoji(person);
    if (roleEmoji) {
        const emojiSpan = document.createElement('span');
        emojiSpan.className = 'role-emoji';
        emojiSpan.textContent = roleEmoji;
        label.appendChild(emojiSpan);
    }

    label.onclick = () => {
        const on = label.classList.toggle('selected');
        label.setAttribute('aria-pressed', on ? 'true' : 'false');
        peUpdateSummary(containerId, summaryId);
    };
    return label;
}

function peRenderPersonPills(containerId, summaryId, data, selectedIds) {
    const container = document.getElementById(containerId);
    if (!container) return;
    container.innerHTML = '';
    for (const person of data) {
        container.appendChild(peCreatePersonPill(person, selectedIds.includes(person.id), containerId, summaryId));
    }
    if (!data || data.length === 0) {
        container.innerHTML = '<span class="pe-empty">No people available</span>';
    }
    peUpdateSummary(containerId, summaryId);
}

function peUpdateSummary(containerId, summaryId) {
    const summary = document.getElementById(summaryId);
    if (!summary) return;
    const container = document.getElementById(containerId);
    const selected = container.querySelectorAll('.person-pill.selected');

    summary.innerHTML = '';
    if (selected.length === 0) {
        const none = document.createElement('span');
        none.className = 'none-text';
        none.textContent = 'None selected';
        summary.appendChild(none);
        return;
    }
    selected.forEach(label => {
        const chip = document.createElement('span');
        chip.className = 'selected-chip';
        chip.textContent = label.querySelector('span:nth-child(2)').textContent;

        const removeBtn = document.createElement('button');
        removeBtn.type = 'button';
        removeBtn.setAttribute('aria-label', 'Remove');
        removeBtn.innerHTML = '&times;';
        removeBtn.onclick = (e) => {
            e.stopPropagation();
            label.classList.remove('selected');
            label.setAttribute('aria-pressed', 'false');
            peUpdateSummary(containerId, summaryId);
        };
        chip.appendChild(removeBtn);
        summary.appendChild(chip);
    });
}

/* Live name filter across the three people containers. */
function peFilterPeople(searchInputId, sectionIds) {
    const query = document.getElementById(searchInputId).value.toLowerCase().trim();
    for (const sectionId of sectionIds) {
        const container = document.getElementById(sectionId);
        if (!container) continue;
        container.querySelectorAll('.person-pill').forEach(pill => {
            const name = pill.dataset.name || '';
            pill.classList.toggle('hidden', !!query && !name.includes(query));
        });
    }
}

/* Collect selected ids (ints) from a pill container. */
function peCollectIds(containerId) {
    return Array.from(document.querySelectorAll('#' + containerId + ' .selected'))
        .map(el => parseInt(el.dataset.value));
}
```

- [ ] **Step 2: Sanity check syntax**

Run: `node --check app/static/practice_editor.js`
Expected: no output, exit 0 (valid JS).

- [ ] **Step 3: Commit**

```bash
git add app/static/practice_editor.js
git commit -m "feat(practices): add shared practice editor pill/person module"
```

---

## Task 3: Rewrite `detail.html` — layout, styles, and data wiring

Rewrite the editor page to the approved two-column layout using the mockup as the styling source. This task delivers the full page structure, the inline CSS (ported from the mockup), and the Jinja data bindings (including the new **assists** array). The pill/person wiring uses the Task 2 module.

**Files:**
- Rewrite: `app/templates/admin/practices/detail.html`

- [ ] **Step 1: Replace the template with the unified editor**

Overwrite `app/templates/admin/practices/detail.html` with the structure below. For the `<style>` block, copy the CSS from `docs/superpowers/specs/2026-06-04-workout-editor-mockup.html` and **replace every `#dir-final` selector prefix with `#workout-editor`** (the page wrapper id); keep all token values identical. The markup uses real Jinja bindings and the container ids the JS expects.

```html
{% extends 'admin/admin_base.html' %}

{% block title %}{{ 'Edit Practice' if practice else 'New Practice' }}{% endblock %}

{% block extra_css %}
<style>
/* PASTE the mockup's <style> here, replacing `#dir-final` with `#workout-editor`.
   It already defines: .cols (2-col grid -> 1-col under 768px), .card, .section-label,
   .field, .pe-pill / .pe-pill.selected (compact pills), .person-pill / .selected-chip,
   the rail-card styles, the sticky save bar, .btn-primary / .btn-ghost, focus rings,
   the accessible toggle, and the 360px mobile demo frame is NOT needed in production
   (omit the .mobile-demo block — real viewport handles mobile). */
</style>
{% endblock %}

{% block content %}
<div id="workout-editor">
  <div class="page-header">
    <div>
      <h1>{{ 'Edit Practice' if practice else 'New Practice' }}</h1>
      {% if practice %}<p class="meta" id="header-meta"></p>{% endif %}
    </div>
    <a href="{{ url_for('admin_practices.practices_list') }}" class="btn-ghost">Back to Practices</a>
  </div>

  <form id="practice-form"
        action="{{ url_for('admin_practices.edit_practice', practice_id=practice.id) if practice else url_for('admin_practices.create_practice') }}"
        class="cols">

    <!-- LEFT: edit form -->
    <div class="form-col">

      <!-- 1. When & Where -->
      <section class="card">
        <h2 class="section-label">When &amp; Where</h2>
        <div class="field-row">
          <div class="field">
            <label for="date">Date &amp; Time</label>
            <input type="datetime-local" id="date" name="date" required
                   value="{{ practice.date.strftime('%Y-%m-%dT%H:%M') if practice else '' }}">
          </div>
          <div class="field">
            <label for="location_id">Location</label>
            <select id="location_id" name="location_id" required>
              <option value="">Select a location…</option>
            </select>
            <p class="field-hint">Weather-check location for Skipper</p>
          </div>
        </div>
        <div class="field-row">
          <div class="field">
            <label for="social_location_id">Post-Practice Social</label>
            <select id="social_location_id" name="social_location_id">
              <option value="">No Social</option>
              {% for sl in social_locations %}
              <option value="{{ sl.id }}" {% if practice and practice.social_location_id == sl.id %}selected{% endif %}>{{ sl.name }}</option>
              {% endfor %}
            </select>
          </div>
          <div class="field">
            <span class="label-text" id="dark-label">Dark Practice</span>
            <label class="toggle-row" for="is_dark_practice">
              <span>Lights needed</span>
              <input type="checkbox" id="is_dark_practice" name="is_dark_practice"
                     {% if practice and practice.is_dark_practice %}checked{% endif %}>
              <span class="toggle-track" aria-hidden="true"></span>
            </label>
          </div>
        </div>
      </section>

      <!-- 2. Activity & Type -->
      <section class="card">
        <h2 class="section-label">Activity &amp; Type</h2>
        <div class="field">
          <label>Activities</label>
          <div id="activities-pills" class="pe-pill-group"></div>
        </div>
        <div class="field">
          <label>Practice Types</label>
          <div id="types-pills" class="pe-pill-group"></div>
        </div>
      </section>

      <!-- 3. Coaches, Leads & Assists -->
      <section class="card">
        <div class="section-head">
          <h2 class="section-label">Coaches · Leads · Assists</h2>
          <input type="text" id="people-search" class="people-search" placeholder="Filter by name…" aria-label="Filter people by name">
        </div>
        <div class="field">
          <label>Coaches</label>
          <div id="coaches-summary" class="selected-summary"></div>
          <div id="coaches-pills" class="person-pill-group"></div>
        </div>
        <div class="field">
          <label>Leads</label>
          <div id="leads-summary" class="selected-summary"></div>
          <div id="leads-pills" class="person-pill-group"></div>
        </div>
        <div class="field">
          <div class="assists-head">
            <label>Assists</label>
            <button type="button" id="assists-toggle" class="assists-toggle" aria-expanded="false" onclick="toggleAssists()">
              <span class="chevron" aria-hidden="true">&#9654;</span><span id="assists-toggle-text">Show</span>
            </button>
          </div>
          <div id="assists-summary" class="selected-summary"></div>
          <div id="assists-collapsible" class="hidden">
            <div id="assists-pills" class="person-pill-group"></div>
          </div>
        </div>
      </section>

      <!-- 4. Workout Plan (anchor) -->
      <section class="card workout-anchor">
        <h2 class="section-label">Workout Plan</h2>
        <div class="field">
          <label for="warmup_description">Warmup</label>
          <textarea id="warmup_description" name="warmup_description" placeholder="e.g., 15 min easy classic, dynamic mobility, 4× pickups">{{ practice.warmup_description if practice else '' }}</textarea>
        </div>
        <div class="field">
          <label for="workout_description">Main Workout</label>
          <textarea id="workout_description" name="workout_description" class="workout-main" placeholder="e.g., 4 × 6 min @ threshold, 3 min easy between. Cue: relaxed tempo, strong kick.">{{ practice.workout_description if practice else '' }}</textarea>
        </div>
        <div class="field">
          <label for="cooldown_description">Cooldown</label>
          <textarea id="cooldown_description" name="cooldown_description" placeholder="e.g., 10 min easy ski, light stretching">{{ practice.cooldown_description if practice else '' }}</textarea>
        </div>
      </section>
    </div>

    <!-- RIGHT: context rail (edit mode only) -->
    {% if practice %}
    <aside class="rail-col">
      <div class="rail-card">
        <div class="rail-head"><span>Status &amp; Skipper</span></div>
        <div class="rail-body">
          <div class="field">
            <label for="status">Status</label>
            <select id="status" name="status">
              <option value="scheduled" {% if practice.status == 'scheduled' %}selected{% endif %}>Scheduled</option>
              <option value="confirmed" {% if practice.status == 'confirmed' %}selected{% endif %}>Confirmed</option>
              <option value="in_progress" {% if practice.status == 'in_progress' %}selected{% endif %}>In Progress</option>
              <option value="cancelled" {% if practice.status == 'cancelled' %}selected{% endif %}>Cancelled</option>
              <option value="completed" {% if practice.status == 'completed' %}selected{% endif %}>Completed</option>
            </select>
          </div>
          <div id="evaluation-container">
            <button type="button" class="btn-ghost btn-sm" onclick="loadEvaluation()">Load Skipper evaluation</button>
          </div>
        </div>
      </div>

      <div class="rail-card">
        <div class="rail-head"><span>RSVPs</span></div>
        <div class="rail-body">
          <div id="rsvp-summary"></div>
          <div id="rsvp-list"></div>
        </div>
      </div>

      <div class="rail-card">
        <div class="rail-head"><span>Lead Confirmations</span></div>
        <div class="rail-body">
          <div id="lead-confirmations-container"><p class="pe-empty">Loading…</p></div>
        </div>
      </div>
    </aside>
    {% endif %}

    <!-- Sticky action bar -->
    <div class="sticky-bar">
      <a href="{{ url_for('admin_practices.practices_list') }}" class="btn-ghost">Cancel</a>
      <button type="submit" class="btn-primary">{{ 'Save Changes' if practice else 'Create Practice' }}</button>
    </div>
  </form>
</div>
{% endblock %}

{% block extra_js %}
<script src="{{ url_for('static', filename='practice_editor.js') }}"></script>
<script src="{{ url_for('static', filename='js/toast.js') }}"></script>
<script>
{% include 'admin/practices/_detail_script.js' %}
</script>
{% endblock %}
```

> The page script is large, so it lives in a separate included partial (`_detail_script.js`) written in the next task. The mockup's `.mobile-demo` block is for the brainstorm only — do **not** include it; real responsive CSS (the `.cols` grid collapsing under 768px) handles mobile.

- [ ] **Step 2: Verify the template parses (no script yet — create an empty partial so the include resolves)**

Create an empty placeholder so Jinja can render: `app/templates/admin/practices/_detail_script.js` containing only `// script added in Task 4`.

Run: `pytest tests/routes/test_admin_practices_routes.py -v`
Expected: PASS (create-mode renders; `New Practice` present, `Lead Confirmations` absent because `{% if practice %}` is false).

- [ ] **Step 3: Commit**

```bash
git add app/templates/admin/practices/detail.html app/templates/admin/practices/_detail_script.js
git commit -m "feat(practices): rebuild editor page layout (two-column + rail)"
```

---

## Task 4: Wire the page script (pills, people, submit)

Fill in the page logic: fetch option lists, render pills via the Task 2 module, populate selected state from Jinja, wire the assists collapsible + people search, and submit the JSON payload (including `assist_ids`).

**Files:**
- Rewrite: `app/templates/admin/practices/_detail_script.js`

- [ ] **Step 1: Write the page script partial**

Replace `app/templates/admin/practices/_detail_script.js` with:

```javascript
// Selected ids injected server-side (ids match the option-list endpoints).
const practiceId = {{ practice.id if practice else 'null' }};
const selLocationId = {{ practice.location_id if practice else 'null' }};
const selActivities = {{ (practice.activities | map(attribute='id') | list) | tojson if practice else '[]' }};
const selTypes = {{ (practice.practice_types | map(attribute='id') | list) | tojson if practice else '[]' }};
const selCoaches = {{ (practice.leads | selectattr('role','equalto','coach') | map(attribute='user_id') | select | list) | tojson if practice else '[]' }};
const selLeads = {{ (practice.leads | selectattr('role','equalto','lead') | map(attribute='user_id') | select | list) | tojson if practice else '[]' }};
const selAssists = {{ (practice.leads | selectattr('role','equalto','assist') | map(attribute='user_id') | select | list) | tojson if practice else '[]' }};

document.addEventListener('DOMContentLoaded', async () => {
    await loadFormData();
    {% if practice %}
    document.getElementById('header-meta').textContent = new Date('{{ practice.date.isoformat() }}')
        .toLocaleString([], {weekday: 'long', month: 'long', day: 'numeric', hour: '2-digit', minute: '2-digit'});
    loadRSVPs();
    loadLeadConfirmations();
    {% endif %}
});

async function loadFormData() {
    try {
        const [locs, acts, types, people] = await Promise.all([
            fetch('/admin/practices/locations/data').then(r => r.json()),
            fetch('/admin/practices/activities/data').then(r => r.json()),
            fetch('/admin/practices/types/data').then(r => r.json()),
            fetch('/admin/practices/people/data').then(r => r.json()),
        ]);

        // Location select
        const locationSelect = document.getElementById('location_id');
        (locs.locations || []).forEach(loc => {
            const opt = document.createElement('option');
            opt.value = loc.id;
            opt.textContent = loc.name + (loc.spot ? ` — ${loc.spot}` : '');
            if (loc.id === selLocationId) opt.selected = true;
            locationSelect.appendChild(opt);
        });

        // Pills
        peRenderTagPills('activities-pills', acts.activities || [], selActivities);
        peRenderTagPills('types-pills', types.types || [], selTypes);
        peRenderPersonPills('coaches-pills', 'coaches-summary', people.coaches || [], selCoaches);
        peRenderPersonPills('leads-pills', 'leads-summary', people.leads || [], selLeads);
        peRenderPersonPills('assists-pills', 'assists-summary', people.assists || [], selAssists);

        // Auto-expand assists if any pre-selected
        if (selAssists.length > 0) toggleAssists();

        // People search
        document.getElementById('people-search').addEventListener('input', () =>
            peFilterPeople('people-search', ['coaches-pills', 'leads-pills', 'assists-pills']));
    } catch (err) {
        console.error('Error loading form data:', err);
        showToast('Error loading form data', 'error');
    }
}

function toggleAssists() {
    const box = document.getElementById('assists-collapsible');
    const btn = document.getElementById('assists-toggle');
    const chevron = btn.querySelector('.chevron');
    const text = document.getElementById('assists-toggle-text');
    const nowOpen = box.classList.toggle('hidden') === false;
    btn.setAttribute('aria-expanded', nowOpen ? 'true' : 'false');
    chevron.classList.toggle('expanded', nowOpen);
    text.textContent = nowOpen ? 'Hide' : 'Show';
}

document.getElementById('practice-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const form = e.target;
    const fd = new FormData(form);

    const locationId = parseInt(fd.get('location_id'));
    if (!fd.get('date') || isNaN(locationId)) {
        showToast('Date and Location are required', 'error');
        return;
    }

    const socialVal = fd.get('social_location_id');
    const payload = {
        date: fd.get('date'),
        location_id: locationId,
        social_location_id: socialVal ? parseInt(socialVal) : null,
        activity_ids: peCollectIds('activities-pills'),
        type_ids: peCollectIds('types-pills'),
        coach_ids: peCollectIds('coaches-pills'),
        lead_ids: peCollectIds('leads-pills'),
        assist_ids: peCollectIds('assists-pills'),
        warmup_description: fd.get('warmup_description') || null,
        workout_description: fd.get('workout_description') || null,
        cooldown_description: fd.get('cooldown_description') || null,
        is_dark_practice: fd.get('is_dark_practice') === 'on',
    };
    if (practiceId) payload.status = fd.get('status');

    form.classList.add('form-loading');
    try {
        const resp = await fetch(form.action, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload),
        });
        const result = await resp.json();
        if (resp.ok && result.success) {
            showToast(result.message || 'Practice saved', 'success');
            setTimeout(() => { window.location.href = '/admin/practices'; }, 800);
        } else {
            showToast(result.error || 'Failed to save practice', 'error');
            form.classList.remove('form-loading');
        }
    } catch (err) {
        showToast('Error saving practice: ' + err.message, 'error');
        form.classList.remove('form-loading');
    }
});

{% if practice %}
{% include 'admin/practices/_detail_context.js' %}
{% endif %}
```

> The context-rail loaders (`loadEvaluation`, `loadRSVPs`, `loadLeadConfirmations`, `toggleLeadConfirmation`) move into a second partial `_detail_context.js` in Task 5, included only in edit mode.

- [ ] **Step 2: Create a temporary stub for the context partial so includes resolve**

Create `app/templates/admin/practices/_detail_context.js` with: `function loadRSVPs(){} function loadLeadConfirmations(){} function loadEvaluation(){}`

- [ ] **Step 3: Verify create-mode still renders**

Run: `pytest tests/routes/test_admin_practices_routes.py -v`
Expected: PASS.

- [ ] **Step 4: Manual smoke (create mode)**

Run `./scripts/dev.sh 5001`, open `http://localhost:5001/admin/practices/new` (log in if prompted). Verify: location loads, activity/type pills render and toggle, coach/lead pills render with name search filtering, assists expand/collapse, and the sticky Save bar is visible. Submitting creates a practice and returns to the grid.

- [ ] **Step 5: Commit**

```bash
git add app/templates/admin/practices/_detail_script.js app/templates/admin/practices/_detail_context.js
git commit -m "feat(practices): wire editor page pills, people search, submit"
```

---

## Task 5: Context rail loaders (Skipper / RSVP / Lead Confirmations)

Port the three loaders from the old `detail.html` JS, restyled for the restrained rail with accessible status (color **+** text label, AA GO badge).

**Files:**
- Rewrite: `app/templates/admin/practices/_detail_context.js`

- [ ] **Step 1: Write the context partial**

Replace `app/templates/admin/practices/_detail_context.js` with the loaders below. These reuse the existing endpoints (`/evaluation`, `/rsvps`, `/leads/data`, `/leads/<id>/toggle-confirm`). Status pills always render a text label alongside the color; the GO badge uses `rail-go` (mint `#acf3c4` bg, `#166534` text — AA).

```javascript
async function loadEvaluation() {
    const c = document.getElementById('evaluation-container');
    c.innerHTML = '<p class="pe-empty">Loading…</p>';
    try {
        const data = await fetch(`/admin/practices/${practiceId}/evaluation`).then(r => r.json());
        if (!data.success) { c.innerHTML = `<p class="rail-error">${data.error}</p>`; return; }
        const ev = data.evaluation;
        let h = `<div class="rail-go-row"><span class="rail-go ${ev.is_go ? 'go' : 'nogo'}">${ev.is_go ? 'GO' : 'NO-GO'}</span>`
              + `<span class="rail-muted">${Math.round(ev.confidence * 100)}% confidence</span></div>`;
        if (ev.weather) {
            h += `<div class="rail-chips">`
               + `<span class="rail-chip">${ev.weather.temperature_f?.toFixed(0) ?? '–'}°F (feels ${ev.weather.feels_like_f?.toFixed(0) ?? '–'}°)</span>`
               + `<span class="rail-chip">wind ${ev.weather.wind_speed_mph?.toFixed(0) ?? '–'} mph</span>`
               + `<span class="rail-chip">precip ${ev.weather.precipitation_chance ?? 0}%</span></div>`;
        }
        if (ev.violations && ev.violations.length) {
            for (const v of ev.violations) {
                h += `<div class="rail-violation ${v.severity}"><b>${v.severity.toUpperCase()}</b> ${v.message}</div>`;
            }
        } else {
            h += `<p class="rail-ok">No violations detected</p>`;
        }
        c.innerHTML = h;
    } catch (err) { c.innerHTML = `<p class="rail-error">${err.message}</p>`; }
}

async function loadRSVPs() {
    try {
        const { rsvps, summary } = await fetch(`/admin/practices/${practiceId}/rsvps`).then(r => r.json());
        document.getElementById('rsvp-summary').innerHTML =
            `<div class="rsvp-strip">`
          + `<div class="rsvp-cell"><span class="n">${summary.going}</span><span class="lbl">Going</span></div>`
          + `<div class="rsvp-cell"><span class="n">${summary.maybe}</span><span class="lbl">Maybe</span></div>`
          + `<div class="rsvp-cell"><span class="n">${summary.not_going}</span><span class="lbl">Out</span></div></div>`;
        const list = document.getElementById('rsvp-list');
        if (!rsvps.length) { list.innerHTML = '<p class="pe-empty">No RSVPs yet</p>'; return; }
        list.innerHTML = rsvps.map(r =>
            `<div class="rsvp-row"><span class="dot ${r.status}" aria-hidden="true"></span>`
          + `<span class="rsvp-name">${r.user_name}</span><span class="rsvp-tag">${r.status.replace('_',' ')}</span></div>`
        ).join('');
    } catch (err) {
        document.getElementById('rsvp-list').innerHTML = `<p class="rail-error">${err.message}</p>`;
    }
}

async function loadLeadConfirmations() {
    const c = document.getElementById('lead-confirmations-container');
    try {
        const { leads } = await fetch(`/admin/practices/${practiceId}/leads/data`).then(r => r.json());
        if (!leads.length) { c.innerHTML = '<p class="pe-empty">No leads assigned</p>'; return; }
        c.innerHTML = leads.map(l => {
            const role = l.role === 'coach' ? 'Coach' : l.role === 'lead' ? 'Lead' : 'Assist';
            return `<div class="conf-row">`
                 + `<span class="conf-name">${l.name} <span class="conf-role">${role}</span></span>`
                 + `<label class="toggle-row mini"><input type="checkbox" ${l.confirmed ? 'checked' : ''} `
                 + `onchange="toggleLeadConfirmation(${l.id})" aria-label="Confirm ${l.name}">`
                 + `<span class="toggle-track" aria-hidden="true"></span></label>`
                 + `<span class="conf-state ${l.confirmed ? 'on' : ''}">${l.confirmed ? 'Confirmed' : 'Pending'}</span></div>`;
        }).join('');
    } catch (err) { c.innerHTML = `<p class="rail-error">${err.message}</p>`; }
}

async function toggleLeadConfirmation(leadId) {
    try {
        const result = await fetch(`/admin/practices/${practiceId}/leads/${leadId}/toggle-confirm`, {
            method: 'POST', headers: {'Content-Type': 'application/json'}
        }).then(r => r.json());
        showToast(result.success ? result.message : (result.error || 'Failed'), result.success ? 'success' : 'error');
    } catch (err) { showToast('Error: ' + err.message, 'error'); }
    loadLeadConfirmations();
}
```

- [ ] **Step 2: Add the rail/status CSS**

In `detail.html`'s `<style>` block, confirm the mockup CSS already defines `.rail-go`, `.rsvp-strip`, `.rsvp-cell`, `.conf-row`, `.toggle-row.mini`, `.rail-chip`, `.rail-violation`. If any are missing (the mockup may name them differently), add rules using tokens: `.rail-go.go{background:#acf3c4;color:#166534}` / `.rail-go.nogo{background:#fde8e8;color:#c53030}`; status dots `.dot.going{background:#166534}` `.dot.maybe{background:#854d0e}` `.dot.not_going{background:#c53030}`; `.conf-state.on{color:#166534}`. Every status keeps its **text label** (never color alone).

- [ ] **Step 3: Manual smoke (edit mode)**

With `./scripts/dev.sh` running, open `http://localhost:5001/admin/practices/<id>` for an existing practice. Verify: header shows the date; the rail shows Status select, "Load Skipper evaluation" works, RSVP strip + list render, lead confirmation toggles flip and persist (reload). Confirm GO badge and status tags show text + color.

- [ ] **Step 4: Commit**

```bash
git add app/templates/admin/practices/_detail_context.js app/templates/admin/practices/detail.html
git commit -m "feat(practices): restrained context rail with accessible status"
```

---

## Task 6: Accessibility & polish pass

**Files:**
- Modify: `app/templates/admin/practices/detail.html` (`<style>` block)

- [ ] **Step 1: Apply the firm accessibility rules**

In the `<style>` block, verify/ensure:
- A visible **2px navy focus ring** on every interactive element: `#workout-editor input:focus-visible, #workout-editor select:focus-visible, #workout-editor textarea:focus-visible, #workout-editor button:focus-visible, #workout-editor .pe-pill:focus-visible, #workout-editor .person-pill:focus-visible { outline: 2px solid #1c2c44; outline-offset: 2px; }`
- The dark-practice checkbox is visually hidden but focusable, with the `.toggle-track` reflecting `:checked` and `:focus-visible` (focus ring on the track via the adjacent-sibling selector).
- Compact pills: `.pe-pill { min-height: 28px; padding: 4px 10px; font-size: 12.5px; border-radius: 20px; }` and `.pe-pill.selected { border: 2px solid #1c2c44; background: #eef2f9; color: #1c2c44; }`.
- `.cols` collapses to one column at `max-width: 767px`, and `.sticky-bar { position: sticky; bottom: 0; }` so the save bar stays reachable on mobile.

- [ ] **Step 2: Keyboard + responsive verification**

With the app running on the edit page:
- Tab through the whole form: every control shows the navy focus ring; pills and the assists toggle are reachable and operable with Enter/Space (they are `<button>`s).
- Resize the window to ~375px wide: layout becomes a single column, the rail stacks under the form, and the Save bar stays pinned at the bottom.
- Spot-check contrast: GO badge, status tags, selected pills are all legible.

- [ ] **Step 3: Commit**

```bash
git add app/templates/admin/practices/detail.html
git commit -m "polish(practices): accessibility (focus rings, compact pills, mobile)"
```

---

## Task 7: Repoint the grid; remove modal JS

**Files:**
- Modify: `app/static/admin_practices.js`

- [ ] **Step 1: Make Edit/Create navigate to the page**

In `app/static/admin_practices.js`:
- In the Actions formatter (line ~216), change the Edit button to navigate:
  `btns += '<button class="tbl-btn tbl-btn-primary" onclick="window.location.href=\'/admin/practices/' + id + '\'">Edit</button>';`
- In `attachEventListeners` (line ~253), change the create handler:
  `document.getElementById('create-practice-btn').addEventListener('click', () => { window.location.href = '/admin/practices/new'; });`

- [ ] **Step 2: Delete the now-unused modal code**

Remove these functions entirely (modal-only): `openCreateModal`, `openEditModal`, `populateEditForm`, `createPersonPill`, `getPersonRoleEmoji`, `renderPersonPills`, `updateSelectedSummary`, `deselectPerson`, `filterPeopleBySearch`, `toggleAssistsSection`, `closeEditModal`, `savePractice`. Remove the now-unused loaders `loadSocialLocations`, `loadActivities`, `loadTypes`, `loadPeople` and their calls in the `DOMContentLoaded` `Promise.all` (lines ~15–22) and the module-level vars `socialLocationsData, activitiesData, typesData, coachesData, leadsData, assistsData, currentEditPracticeId`. Keep: `loadPractices`, `loadLocations` (used by the location filter), `initTable`, `populateLocationFilter`, `applyFilters`, the cancel-modal functions (`openCancelModal`, `closeCancelModal`, `confirmCancel`, `currentCancelPracticeId`), and `deletePractice`. In the Escape handler (line ~699) remove the `closeEditModal();` call, keeping `closeCancelModal();`.

- [ ] **Step 3: Syntax check**

Run: `node --check app/static/admin_practices.js`
Expected: exit 0.

- [ ] **Step 4: Manual smoke (grid)**

With the app running, open `http://localhost:5001/admin/practices`. The grid loads; **Edit** navigates to `/admin/practices/<id>`; **Create New Practice** navigates to `/admin/practices/new`; **Cancel** and **Delete** still work via their modal/confirm.

- [ ] **Step 5: Commit**

```bash
git add app/static/admin_practices.js
git commit -m "refactor(practices): grid edit/create navigate to editor page"
```

---

## Task 8: Remove the edit/create modal markup from `list.html`

**Files:**
- Modify: `app/templates/admin/practices/list.html`

- [ ] **Step 1: Delete the edit modal and its dead styles**

In `app/templates/admin/practices/list.html`:
- Delete the entire `#edit-modal` block (lines ~235–340).
- Keep the `#cancel-modal` block (lines ~342–361) and the grid/toolbar.
- In the `{% block extra_css %}` `<style>` (lines ~3–201), delete the now-unused modal-only rules: `.pill-grid`, `.person-pill*`, `.selected-summary`, `.selected-chip`, `.assists-toggle*`, and the `.toggle-slider*` rules. Keep `@media (max-width: 700px) .modal-content-wide` only if the cancel modal uses it; otherwise remove it. (These styles now live in `detail.html`.)

- [ ] **Step 2: Verify list still renders**

Run: `pytest tests/routes/test_admin_practices_routes.py -v` (the auth + new-route tests still pass; nothing imports the removed markup).
Then manual: reload `http://localhost:5001/admin/practices` — grid, filters, Create button, and Cancel modal all present and working.

- [ ] **Step 3: Commit**

```bash
git add app/templates/admin/practices/list.html
git commit -m "refactor(practices): remove edit/create modal from grid view"
```

---

## Task 9: Verify navigation surfaces & final pass

**Files:**
- Verify: `app/templates/admin/practices/calendar.html`, `app/templates/admin/partials/sidebar.html`

- [ ] **Step 1: Calendar → editor**

Open `http://localhost:5001/admin/practices/calendar`, click a practice. It should open `/admin/practices/<id>` (the new editor). No code change expected (calendar.html line ~214 already links there); if it points elsewhere, update the href to `/admin/practices/${practice.id}`.

- [ ] **Step 2: Sidebar active state**

Open `/admin/practices/new` and `/admin/practices/<id>`. Confirm the "Practice List" sidebar item highlights appropriately. `sidebar.html` (line ~90) checks the `admin_practices.practice_detail` endpoint; if `practice_new` should also highlight it, add `or request.endpoint == 'admin_practices.practice_new'` to that condition.

- [ ] **Step 3: Full regression smoke**

- Create a practice via `/admin/practices/new`, fill all sections, save → lands on grid, row present.
- Edit that practice via the grid → page loads with values populated (pills selected, people chips, workout text), change something, save → persists.
- Edit via the calendar → same page.
- Mobile width (~375px): single column, sticky save bar, everything operable.

- [ ] **Step 4: Run the full test suite**

Run: `pytest -q`
Expected: existing suite (124 tests) + the 2 new route tests pass; no regressions.

- [ ] **Step 5: Final commit**

```bash
git add -A
git commit -m "chore(practices): verify calendar/sidebar navigation to unified editor"
```

---

## Self-Review notes (author)

- **Spec coverage:** full-page form factor (Tasks 3–6) ✓; two-column desktop / single-column mobile + sticky bar (Tasks 3, 6) ✓; ported controls — pills, person search, collapsible assists, accessible toggle (Tasks 2, 4, 6) ✓; "Quiet Precision" merged visual via mockup (Task 3) ✓; accessibility requirements — color+text status, 2px navy focus, AA GO badge, labels (Tasks 5, 6) ✓; restrained rail (Task 5) ✓; new `/new` route (Task 1) ✓; grid repoint + modal deletion (Tasks 7, 8) ✓; calendar/sidebar verification (Task 9) ✓; POST endpoints unchanged ✓.
- **Out of scope confirmed absent:** no copy-from-previous, Slack preview, templates, or rich-text.
- **Type/name consistency:** container ids (`activities-pills`, `types-pills`, `coaches-pills`, `leads-pills`, `assists-pills` + matching `-summary`) are used identically across Tasks 3, 4, 6, 7; `pe*` helper names match between Task 2 (definition) and Task 4 (calls); payload keys match the documented `create_practice`/`edit_practice` contract.
- **Testing reality:** only the backend route is unit-tested (matches the repo — admin routes/JS have no harness). Frontend tasks rely on explicit manual smoke steps; this is called out rather than faking JS unit tests.
