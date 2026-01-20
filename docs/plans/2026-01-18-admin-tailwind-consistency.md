# Admin UI Tailwind Consistency Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Standardize all admin templates to use consistent Tailwind component classes, eliminating inline styles and creating a unified look.

**Architecture:** Replace inline Tailwind classes with reusable component classes defined in `tailwind-input.css`. All pages follow the same structure: white card wrapper, h1 inside, toolbar for actions.

**Tech Stack:** Tailwind CSS, Jinja2 templates, Flask

---

## Reference: Component Classes

These classes are already defined in `app/static/css/tailwind-input.css`:

| Use Case | Classes |
|----------|---------|
| Page card | `bg-white rounded-tcsc p-5` |
| Page title | `text-xl font-semibold text-tcsc-navy mb-3` |
| Toolbar | `toolbar` (flex container with gap) |
| Toolbar spacer | `toolbar-spacer` (pushes items right) |
| Toolbar button primary | `toolbar-btn toolbar-btn-primary` |
| Toolbar button secondary | `toolbar-btn toolbar-btn-secondary` |
| Toolbar button danger | `toolbar-btn toolbar-btn-danger` |
| Toolbar button success | `toolbar-btn toolbar-btn-success` |
| Table cell button | `tbl-btn tbl-btn-{primary/secondary/danger/success}` |
| Button container in cell | `tbl-actions` |

---

### Task 1: Update trips.html

**Files:**
- Modify: `app/templates/admin/trips.html`

**Step 1: Replace page structure**

Change the header and wrapper from:
```html
<div class="max-w-6xl mx-auto">
  <div class="flex justify-between items-center mb-6">
    <h1 class="text-2xl font-semibold text-tcsc-navy">Trips Management</h1>
    <div class="flex gap-3">
      <a href="{{ url_for('admin.get_admin_page') }}" class="bg-gray-200 text-gray-600 px-4 py-2 rounded-tcsc text-sm font-medium hover:bg-gray-300 transition-all">Back to Dashboard</a>
      <a href="{{ url_for('admin.new_trip') }}" class="bg-tcsc-navy text-white px-4 py-2 rounded-tcsc text-sm font-medium hover:opacity-90 transition-all">Create New Trip</a>
    </div>
  </div>
```

To:
```html
<div class="bg-white rounded-tcsc p-5">
  <h1 class="text-xl font-semibold text-tcsc-navy mb-3">Trips Management</h1>
  <div class="toolbar">
    <div class="toolbar-spacer"></div>
    <a href="{{ url_for('admin.new_trip') }}" class="toolbar-btn toolbar-btn-primary">Create New Trip</a>
  </div>
```

**Step 2: Update table action buttons**

Change from:
```html
<a href="{{ url_for('admin.edit_trip', trip_id=trip.id) }}" class="bg-tcsc-navy text-white px-3 py-1.5 rounded-tcsc text-xs font-medium hover:opacity-90 transition-all">Edit</a>
<button
  class="bg-status-error-bg text-status-error-text px-3 py-1.5 rounded-tcsc text-xs font-medium hover:bg-red-200 transition-all"
  onclick="confirmDelete('trip', '{{ trip.id }}', '{{ trip.name }}')"
>
  Delete
</button>
```

To:
```html
<div class="tbl-actions">
  <a href="{{ url_for('admin.edit_trip', trip_id=trip.id) }}" class="tbl-btn tbl-btn-primary">Edit</a>
  <button class="tbl-btn tbl-btn-danger" onclick="confirmDelete('trip', '{{ trip.id }}', '{{ trip.name }}')">Delete</button>
</div>
```

**Step 3: Remove outer max-w wrapper and close card properly**

Remove `<div class="max-w-6xl mx-auto">` wrapper (admin_base.html already has max-w-6xl).
Close the card div after the table.

**Step 4: Verify**

Run: `python -c "from app import create_app; app = create_app(); print('OK')"`
Expected: OK (no template syntax errors)

**Step 5: Visual check**

Browse to `/admin/trips` and verify:
- Page wrapped in white card
- "Create New Trip" button in toolbar
- No "Back to Dashboard" button
- Table action buttons are compact and consistent

**Step 6: Commit**

```bash
git add app/templates/admin/trips.html
git commit -m "refactor(admin): standardize trips.html to Tailwind components"
```

---

### Task 2: Update seasons.html

**Files:**
- Modify: `app/templates/admin/seasons.html`

**Step 1: Replace page structure**

Change the header and wrapper from:
```html
<div class="max-w-6xl mx-auto">
  <div class="flex justify-between items-center mb-6">
    <h1 class="text-2xl font-semibold text-tcsc-navy">Seasons Management</h1>
    <div class="flex gap-3">
      <a href="{{ url_for('admin.get_admin_page') }}" class="bg-gray-200 text-gray-600 px-4 py-2 rounded-tcsc text-sm font-medium hover:bg-gray-300 transition-all">Back to Dashboard</a>
      <a href="{{ url_for('admin.new_season') }}" class="bg-tcsc-navy text-white px-4 py-2 rounded-tcsc text-sm font-medium hover:opacity-90 transition-all">Create New Season</a>
    </div>
  </div>
```

To:
```html
<div class="bg-white rounded-tcsc p-5">
  <h1 class="text-xl font-semibold text-tcsc-navy mb-3">Seasons Management</h1>
  <div class="toolbar">
    <div class="toolbar-spacer"></div>
    <a href="{{ url_for('admin.new_season') }}" class="toolbar-btn toolbar-btn-primary">Create New Season</a>
  </div>
```

**Step 2: Update table action buttons**

Change all inline button styles to component classes:
- Edit button: `tbl-btn tbl-btn-primary`
- Export button: `tbl-btn tbl-btn-primary`
- Activate button: `tbl-btn tbl-btn-success`
- Delete button: `tbl-btn tbl-btn-danger`

Wrap in `<div class="tbl-actions">...</div>`

**Step 3: Remove outer max-w wrapper and close card**

**Step 4: Verify**

Run: `python -c "from app import create_app; app = create_app(); print('OK')"`
Expected: OK

**Step 5: Visual check**

Browse to `/admin/seasons` and verify consistent styling.

**Step 6: Commit**

```bash
git add app/templates/admin/seasons.html
git commit -m "refactor(admin): standardize seasons.html to Tailwind components"
```

---

### Task 3: Update roles.html

**Files:**
- Modify: `app/templates/admin/roles.html`

**Step 1: Replace page structure**

Change from:
```html
<div class="flex items-center justify-between mb-6">
    <h1 class="text-2xl font-semibold text-tcsc-navy">Role Management</h1>
    <div class="flex gap-3">
        <a href="{{ url_for('admin.get_admin_page') }}" class="bg-gray-200 text-gray-600 px-4 py-2 rounded-tcsc text-sm font-medium hover:bg-gray-300 transition-all">Back to Dashboard</a>
    </div>
</div>

<div class="bg-white rounded-tcsc p-5">
```

To:
```html
<div class="bg-white rounded-tcsc p-5">
    <h1 class="text-xl font-semibold text-tcsc-navy mb-3">Role Management</h1>
```

**Step 2: Verify**

Run: `python -c "from app import create_app; app = create_app(); print('OK')"`
Expected: OK

**Step 3: Visual check**

Browse to `/admin/roles` and verify:
- Title inside card
- No "Back to Dashboard" button
- Existing toolbar styling preserved

**Step 4: Commit**

```bash
git add app/templates/admin/roles.html
git commit -m "refactor(admin): standardize roles.html page structure"
```

---

### Task 4: Update social_events.html

**Files:**
- Modify: `app/templates/admin/social_events.html`

**Step 1: Read current file to understand structure**

Run: Read the file first to see current state

**Step 2: Apply same pattern as trips.html**

- Wrap in card with `bg-white rounded-tcsc p-5`
- Move h1 inside card
- Remove "Back to Dashboard" button
- Use toolbar for "Create" button
- Update table action buttons to `tbl-btn` classes

**Step 3: Verify and commit**

```bash
git add app/templates/admin/social_events.html
git commit -m "refactor(admin): standardize social_events.html to Tailwind components"
```

---

### Task 5: Update modal buttons in slack_sync.html

**Files:**
- Modify: `app/templates/admin/slack_sync.html`

**Step 1: Update Link Modal buttons (lines 124-125)**

Change from:
```html
<button class="bg-gray-200 text-gray-600 px-4 py-2 rounded-tcsc text-sm font-medium hover:bg-gray-300 transition-all" onclick="closeLinkModal()">Cancel</button>
<button class="bg-tcsc-navy text-white px-4 py-2 rounded-tcsc text-sm font-medium hover:opacity-90 transition-all" onclick="confirmLink()">Link</button>
```

To:
```html
<button class="toolbar-btn toolbar-btn-secondary" onclick="closeLinkModal()">Cancel</button>
<button class="toolbar-btn toolbar-btn-primary" onclick="confirmLink()">Link</button>
```

**Step 2: Update Message Modal small buttons (lines 143-144)**

Change from:
```html
<button type="button" class="bg-gray-200 text-gray-600 px-3 py-1.5 rounded-tcsc text-xs font-medium hover:bg-gray-300 transition-all flex-shrink-0" onclick="selectAllUsers()">Select All</button>
<button type="button" class="bg-gray-200 text-gray-600 px-3 py-1.5 rounded-tcsc text-xs font-medium hover:bg-gray-300 transition-all flex-shrink-0" onclick="deselectAllUsers()">Deselect All</button>
```

To:
```html
<button type="button" class="tbl-btn tbl-btn-secondary" onclick="selectAllUsers()">Select All</button>
<button type="button" class="tbl-btn tbl-btn-secondary" onclick="deselectAllUsers()">Deselect All</button>
```

**Step 3: Update Message Modal footer buttons (lines 178-179)**

Change to:
```html
<button class="toolbar-btn toolbar-btn-secondary" onclick="closeMessageModal()">Cancel</button>
<button class="toolbar-btn toolbar-btn-primary" id="send-message-btn" onclick="sendMessage()">Send Message</button>
```

**Step 4: Verify and commit**

```bash
git add app/templates/admin/slack_sync.html
git commit -m "refactor(admin): standardize slack_sync.html modal buttons"
```

---

### Task 6: Update modal buttons in users.html

**Files:**
- Modify: `app/templates/admin/users.html`

**Step 1: Check Edit Modal buttons (around line 423-425)**

Update to use component classes:
```html
<button type="button" class="toolbar-btn toolbar-btn-secondary" onclick="closeModal()">Cancel</button>
<a href="#" class="toolbar-btn toolbar-btn-secondary" id="view-details-link">View Details</a>
<button type="submit" form="edit-user-form" class="toolbar-btn toolbar-btn-primary">Save Changes</button>
```

**Step 2: Check Tag Modal buttons (around line 441-443)**

Update to use component classes:
```html
<button type="button" class="toolbar-btn toolbar-btn-secondary" onclick="closeTagModal()">Cancel</button>
<button type="button" class="toolbar-btn toolbar-btn-primary" onclick="saveUserTags()">Save Tags</button>
```

**Step 3: Verify and commit**

```bash
git add app/templates/admin/users.html
git commit -m "refactor(admin): standardize users.html modal buttons"
```

---

### Task 7: Update modal buttons in payments.html

**Files:**
- Modify: `app/templates/admin/payments.html`

**Step 1: Update Bulk Modal buttons (around line 104-105)**

Change from:
```html
<button type="button" class="bg-gray-200 text-gray-600 px-4 py-2 rounded-tcsc text-sm font-medium hover:bg-gray-300 transition-all" id="cancel-action">Cancel</button>
<button type="button" class="bg-green-100 text-green-700 px-4 py-2 rounded-tcsc text-sm font-medium hover:bg-green-200 transition-all" id="confirm-action">Confirm</button>
```

To:
```html
<button type="button" class="toolbar-btn toolbar-btn-secondary" id="cancel-action">Cancel</button>
<button type="button" class="toolbar-btn toolbar-btn-success" id="confirm-action">Confirm</button>
```

**Step 2: Verify and commit**

```bash
git add app/templates/admin/payments.html
git commit -m "refactor(admin): standardize payments.html modal buttons"
```

---

### Task 8: Build Tailwind CSS and final verification

**Step 1: Rebuild Tailwind CSS**

Run: `npx tailwindcss -i ./app/static/css/tailwind-input.css -o ./app/static/css/tailwind-output.css`
Expected: CSS file regenerated without errors

**Step 2: Start dev server**

Run: `./scripts/dev.sh`

**Step 3: Visual verification checklist**

Browse each admin page and verify:
- [ ] `/admin` - Dashboard cards look good
- [ ] `/admin/users` - Toolbar, buttons, modals consistent
- [ ] `/admin/payments` - Toolbar, buttons, modal consistent
- [ ] `/admin/roles` - Title in card, toolbar consistent
- [ ] `/admin/trips` - Card wrapper, toolbar, table buttons
- [ ] `/admin/seasons` - Card wrapper, toolbar, table buttons
- [ ] `/admin/social-events` - Card wrapper, toolbar, table buttons
- [ ] `/admin/slack` - Stats cards, modals consistent

**Step 4: Commit CSS if changed**

```bash
git add app/static/css/tailwind-output.css
git commit -m "build: regenerate tailwind output"
```

**Step 5: Update migration status**

Add to `docs/tailwind-migration/STATUS.md`:
```markdown
### [2026-01-18] - Admin Button Consistency
- Focus: Standardize all admin templates to use component classes
- Completed: trips, seasons, roles, social_events, modal buttons
- Issues: None
- Next: Public frontend migration
```

```bash
git add docs/tailwind-migration/STATUS.md
git commit -m "docs: update tailwind migration status"
```

---

## Summary

8 tasks total:
1. trips.html - page structure + buttons
2. seasons.html - page structure + buttons
3. roles.html - page structure
4. social_events.html - page structure + buttons
5. slack_sync.html - modal buttons
6. users.html - modal buttons
7. payments.html - modal buttons
8. Build + verify + docs
