# Admin UI Unification Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Unify all admin pages to use a consistent component system with standardized buttons, filters, toolbars, tables, and modals.

**Architecture:** CSS component classes using Tailwind's `@apply` directive with TCSC design tokens. Single-line toolbar layout with filters left, count center, actions right. All tables converted to Tabulator with consistent frozen column patterns.

**Tech Stack:** Tailwind CSS, Tabulator.js 5.5.2, vanilla JavaScript

---

## Task 1: CSS Foundation - Add Admin Component Classes

**Files:**
- Modify: `app/static/css/tailwind-input.css`

**Step 1: Add the admin component classes to tailwind-input.css**

Add the following at the end of the `@layer components` block (before the closing `}`):

```css
  /* ===========================================
     ADMIN UI COMPONENT SYSTEM
     =========================================== */

  /* --- Base Button --- */
  .admin-btn {
    @apply inline-flex items-center justify-center font-medium
           transition-all duration-150 ease-in-out
           focus:outline-none focus:ring-2 focus:ring-tcsc-navy/20;
  }

  .admin-btn:disabled {
    @apply opacity-50 cursor-not-allowed;
  }

  /* --- Button Sizes --- */
  .admin-btn-sm {
    @apply text-xs px-3 py-1 rounded-full;
  }

  .admin-btn-md {
    @apply text-sm px-4 py-2 rounded-tcsc;
  }

  .admin-btn-lg {
    @apply text-sm px-5 py-2.5 rounded-tcsc;
  }

  /* --- Button Variants --- */
  .admin-btn-primary {
    @apply bg-tcsc-navy text-white hover:bg-tcsc-navy/90 hover:shadow-md;
  }

  .admin-btn-secondary {
    @apply bg-white text-tcsc-gray-600 border border-tcsc-gray-100
           hover:bg-tcsc-gray-50 hover:border-tcsc-gray-200;
  }

  .admin-btn-danger {
    @apply bg-status-error-bg text-status-error-text hover:bg-red-200;
  }

  .admin-btn-success {
    @apply bg-status-success-bg text-status-success-text hover:bg-green-200;
  }

  /* --- Pill Filter Group --- */
  .admin-pill-group {
    @apply inline-flex rounded-tcsc border border-tcsc-gray-100
           overflow-hidden shadow-sm;
  }

  .admin-pill {
    @apply px-3 py-1.5 text-sm font-medium bg-white text-tcsc-gray-600
           border-r border-tcsc-gray-100 last:border-r-0
           transition-colors duration-150 cursor-pointer;
  }

  .admin-pill:hover:not(.active) {
    @apply bg-tcsc-gray-50;
  }

  .admin-pill.active {
    @apply bg-tcsc-navy text-white;
  }

  /* --- Form Inputs --- */
  .admin-select {
    @apply h-9 px-3 pr-8 text-sm rounded-tcsc
           border border-tcsc-gray-100 bg-white shadow-sm
           focus:outline-none focus:border-tcsc-navy
           focus:ring-2 focus:ring-tcsc-navy/10 cursor-pointer;
    appearance: none;
    background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 12 12'%3E%3Cpath fill='%231c2c44' d='M2.5 4.5L6 8l3.5-3.5'/%3E%3C/svg%3E");
    background-repeat: no-repeat;
    background-position: right 0.75rem center;
  }

  .admin-search {
    @apply h-9 px-3 pl-9 text-sm rounded-tcsc w-44
           border border-tcsc-gray-100 bg-white shadow-sm
           placeholder:text-tcsc-gray-400
           focus:outline-none focus:border-tcsc-navy
           focus:ring-2 focus:ring-tcsc-navy/10;
    background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='%231c2c44' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Ccircle cx='11' cy='11' r='8'/%3E%3Cpath d='m21 21-4.35-4.35'/%3E%3C/svg%3E");
    background-repeat: no-repeat;
    background-position: 0.75rem center;
  }

  /* --- Layout --- */
  .admin-header {
    @apply flex items-center justify-between mb-6;
  }

  .admin-header h1 {
    @apply text-xl font-semibold text-tcsc-gray-800 m-0;
  }

  .admin-toolbar {
    @apply flex flex-wrap items-center gap-3 mb-4;
  }

  .admin-toolbar-spacer {
    @apply flex-1 min-w-[1rem];
  }

  .admin-count {
    @apply px-2.5 py-1 text-xs font-semibold rounded-full
           bg-tcsc-navy text-white tabular-nums;
  }

  /* --- Badges --- */
  .admin-badge {
    @apply inline-flex items-center gap-1 px-2 py-0.5
           text-xs font-medium rounded-full;
  }

  .admin-badge-active {
    @apply bg-status-success-bg text-status-success-text;
  }

  .admin-badge-pending {
    @apply bg-status-warning-bg text-status-warning-text;
  }

  .admin-badge-inactive {
    @apply bg-status-neutral-bg text-status-neutral-text;
  }

  .admin-badge-error {
    @apply bg-status-error-bg text-status-error-text;
  }

  /* --- Modal --- */
  .admin-modal-backdrop {
    @apply fixed inset-0 bg-black/50 flex items-center justify-center z-50;
  }

  .admin-modal {
    @apply relative bg-white rounded-tcsc w-full max-w-md mx-4 shadow-xl animate-fade-in;
  }

  .admin-modal-header {
    @apply flex items-center justify-between px-5 py-4 border-b border-tcsc-gray-100;
  }

  .admin-modal-header h2 {
    @apply text-base font-semibold text-tcsc-gray-800 m-0;
  }

  .admin-modal-close {
    @apply text-2xl text-tcsc-gray-400 hover:text-tcsc-gray-600 leading-none cursor-pointer;
  }

  .admin-modal-body {
    @apply p-5;
  }

  .admin-modal-footer {
    @apply flex justify-end gap-3 px-5 py-4 border-t border-tcsc-gray-100;
  }

  /* --- Table Enhancements for admin-table wrapper --- */
  .admin-table .tabulator-header {
    background-color: rgba(28,44,68,0.03);
    border-bottom: 1px solid rgba(28,44,68,0.15);
  }

  .admin-table .tabulator-header .tabulator-col {
    background-color: transparent;
  }

  .admin-table .tabulator-header .tabulator-col-title {
    @apply text-sm font-semibold text-tcsc-navy;
  }

  .admin-table .tabulator-row {
    border-bottom: 1px solid rgba(28,44,68,0.08);
  }

  .admin-table .tabulator-row:hover {
    background-color: rgba(28,44,68,0.03);
  }

  .admin-table .tabulator-row.tabulator-selected {
    background-color: rgba(28,44,68,0.08);
  }

  .admin-table .tabulator-frozen-left {
    box-shadow: 2px 0 4px -2px rgba(0,0,0,0.1);
  }

  .admin-table .tabulator-frozen-right {
    box-shadow: -2px 0 4px -2px rgba(0,0,0,0.1);
  }

  /* Actions cell helper */
  .admin-actions {
    @apply flex items-center gap-1.5;
  }
```

**Step 2: Rebuild Tailwind CSS**

Run: `npx tailwindcss -i app/static/css/tailwind-input.css -o app/static/css/tailwind-output.css`

**Step 3: Verify the build succeeds**

Run: `head -50 app/static/css/tailwind-output.css`
Expected: CSS output with no errors

**Step 4: Commit**

```bash
git add app/static/css/tailwind-input.css app/static/css/tailwind-output.css
git commit -m "feat(admin): Add unified admin component CSS classes

Adds .admin-btn, .admin-pill, .admin-select, .admin-search,
.admin-header, .admin-toolbar, .admin-count, .admin-badge,
.admin-modal, and .admin-table component classes using TCSC
design tokens."
```

---

## Task 2: Users Page - Update to Admin Components

**Files:**
- Modify: `app/templates/admin/users.html`
- Modify: `app/static/admin_users.js`

**Step 1: Update users.html toolbar classes**

Replace the view switcher from `seg-group`/`seg-btn` to `admin-pill-group`/`admin-pill`:

Find:
```html
<div class="seg-group">
    <button class="seg-btn active" data-view="all">All</button>
    <button class="seg-btn" data-view="current">Current</button>
    <button class="seg-btn" data-view="alumni">Alumni</button>
</div>
```

Replace with:
```html
<div class="admin-pill-group">
    <button class="admin-pill active" data-view="all">All</button>
    <button class="admin-pill" data-view="current">Current</button>
    <button class="admin-pill" data-view="alumni">Alumni</button>
</div>
```

**Step 2: Update select elements to admin-select**

Replace all instances of `class="tbl-select"` with `class="admin-select"` in the template (4 occurrences: global-season-select, status-filter, role-filter-btn, season-filter).

**Step 3: Update search input to admin-search**

Find:
```html
<input type="text" id="users-search" class="tbl-search" placeholder="Search...">
```

Replace with:
```html
<input type="text" id="users-search" class="admin-search" placeholder="Search...">
```

**Step 4: Update count badge to admin-count**

Find:
```html
<span id="member-count" class="toolbar-count"><strong>0</strong> members</span>
```

Replace with:
```html
<span id="member-count" class="admin-count">0</span>
```

Note: The admin-count uses tabular-nums and doesn't need the "members" text - but we can keep it if preferred. Update JS to set just the number.

**Step 5: Update toolbar class**

Find:
```html
<div class="toolbar">
```

Replace with:
```html
<div class="admin-toolbar">
```

**Step 6: Update Export CSV button**

Find:
```html
<button id="export-csv" class="toolbar-btn toolbar-btn-secondary">Export CSV</button>
```

Replace with:
```html
<button id="export-csv" class="admin-btn admin-btn-md admin-btn-secondary">Export CSV</button>
```

**Step 7: Update modal buttons**

In the edit-modal, find:
```html
<button type="button" class="toolbar-btn toolbar-btn-secondary" onclick="closeModal()">Cancel</button>
<a href="#" class="toolbar-btn toolbar-btn-secondary" id="view-details-link">View Details</a>
<button type="submit" form="edit-user-form" class="toolbar-btn toolbar-btn-primary">Save Changes</button>
```

Replace with:
```html
<button type="button" class="admin-btn admin-btn-md admin-btn-secondary" onclick="closeModal()">Cancel</button>
<a href="#" class="admin-btn admin-btn-md admin-btn-secondary" id="view-details-link">View Details</a>
<button type="submit" form="edit-user-form" class="admin-btn admin-btn-md admin-btn-primary">Save Changes</button>
```

**Step 8: Update tag-modal buttons**

In the tag-modal, find:
```html
<button type="button" class="toolbar-btn toolbar-btn-secondary" onclick="closeTagModal()">Cancel</button>
<button type="button" class="toolbar-btn toolbar-btn-primary" onclick="saveUserTags()">Save Tags</button>
```

Replace with:
```html
<button type="button" class="admin-btn admin-btn-md admin-btn-secondary" onclick="closeTagModal()">Cancel</button>
<button type="button" class="admin-btn admin-btn-md admin-btn-primary" onclick="saveUserTags()">Save Tags</button>
```

**Step 9: Update admin_users.js - Edit button in table**

Find in admin_users.js (around line 81):
```javascript
return `<button class="tbl-btn tbl-btn-primary" onclick="openEditModal(${id}); event.stopPropagation();">Edit</button>`;
```

Replace with:
```javascript
return `<button class="admin-btn admin-btn-sm admin-btn-primary" onclick="openEditModal(${id}); event.stopPropagation();">Edit</button>`;
```

**Step 10: Update admin_users.js - View switcher click handler**

Find the click handler that toggles `seg-btn` active class and update it to use `admin-pill`:

Find:
```javascript
document.querySelectorAll('.seg-btn').forEach(btn => {
```

Replace with:
```javascript
document.querySelectorAll('.admin-pill').forEach(btn => {
```

And update the class toggle from `seg-btn` to `admin-pill` if there are any `.classList.add('active')` or similar operations.

**Step 11: Verify the page renders correctly**

Run: `./scripts/dev.sh`
Navigate to `/admin/users` and verify:
- Pill buttons work for All/Current/Alumni
- Dropdowns styled correctly
- Search input has magnifying glass icon
- Edit buttons in table are pill-shaped
- Modal buttons are styled correctly

**Step 12: Commit**

```bash
git add app/templates/admin/users.html app/static/admin_users.js
git commit -m "feat(admin): Update users page to admin component system

Replaces toolbar-btn, tbl-btn, seg-btn, tbl-select, tbl-search
with new admin-btn, admin-pill, admin-select, admin-search classes."
```

---

## Task 3: Payments Page - Update to Admin Components

**Files:**
- Modify: `app/templates/admin/payments.html`
- Modify: `app/static/admin_payments.js`

**Step 1: Update payments.html toolbar class**

Find:
```html
<div class="toolbar">
```

Replace with:
```html
<div class="admin-toolbar">
```

**Step 2: Update search input**

Find:
```html
<input type="text" id="payments-search" class="tbl-search" placeholder="Search...">
```

Replace with:
```html
<input type="text" id="payments-search" class="admin-search" placeholder="Search...">
```

**Step 3: Update select elements**

Find:
```html
<select id="type-filter" class="tbl-select">
```

Replace with:
```html
<select id="type-filter" class="admin-select">
```

And:
```html
<select id="status-filter" class="tbl-select">
```

Replace with:
```html
<select id="status-filter" class="admin-select">
```

**Step 4: Update count badge**

Find:
```html
<span id="payment-count" class="toolbar-count"><strong>0</strong> payments</span>
```

Replace with:
```html
<span id="payment-count" class="admin-count">0</span>
```

**Step 5: Update bulk action buttons**

Find:
```html
<button id="bulk-accept" class="toolbar-btn toolbar-btn-success" disabled>Accept Selected</button>
<button id="bulk-refund" class="toolbar-btn toolbar-btn-danger" disabled>Refund Selected</button>
```

Replace with:
```html
<button id="bulk-accept" class="admin-btn admin-btn-md admin-btn-success" disabled>Accept Selected</button>
<button id="bulk-refund" class="admin-btn admin-btn-md admin-btn-danger" disabled>Refund Selected</button>
```

**Step 6: Update Export CSV button**

Find:
```html
<button id="export-csv" class="toolbar-btn toolbar-btn-secondary">Export CSV</button>
```

Replace with:
```html
<button id="export-csv" class="admin-btn admin-btn-md admin-btn-secondary">Export CSV</button>
```

**Step 7: Update modal buttons**

Find:
```html
<button type="button" class="toolbar-btn toolbar-btn-secondary" id="cancel-action">Cancel</button>
<button type="button" class="toolbar-btn toolbar-btn-success" id="confirm-action">Confirm</button>
```

Replace with:
```html
<button type="button" class="admin-btn admin-btn-md admin-btn-secondary" id="cancel-action">Cancel</button>
<button type="button" class="admin-btn admin-btn-md admin-btn-success" id="confirm-action">Confirm</button>
```

**Step 8: Update admin_payments.js - inline action buttons**

Find where Accept/Refund buttons are rendered in the Tabulator formatter (search for `tbl-btn`):

Replace all instances of:
- `tbl-btn tbl-btn-success` with `admin-btn admin-btn-sm admin-btn-success`
- `tbl-btn tbl-btn-danger` with `admin-btn admin-btn-sm admin-btn-danger`

**Step 9: Verify the page**

Navigate to `/admin/payments` and verify all styling is correct.

**Step 10: Commit**

```bash
git add app/templates/admin/payments.html app/static/admin_payments.js
git commit -m "feat(admin): Update payments page to admin component system"
```

---

## Task 4: Roles Page - Update to Admin Components

**Files:**
- Modify: `app/templates/admin/roles.html`

**Step 1: Restructure to use admin-header**

Find:
```html
<h1 class="text-xl font-semibold text-tcsc-navy mb-3">Role Management</h1>
<div class="toolbar">
    <button class="toolbar-btn toolbar-btn-primary" onclick="addNewRole()">Add New Role</button>
    <div class="toolbar-spacer"></div>
    <span class="toolbar-count">Total: <strong id="role-count">0</strong> roles</span>
</div>
```

Replace with:
```html
<div class="admin-header">
    <h1>Role Management</h1>
    <button class="admin-btn admin-btn-lg admin-btn-primary" onclick="addNewRole()">+ Add New Role</button>
</div>
<div class="admin-toolbar">
    <div class="admin-toolbar-spacer"></div>
    <span class="admin-count" id="role-count">0</span>
</div>
```

**Step 2: Update delete button in Tabulator formatter**

Find in the inline `<script>` section:
```javascript
const deleteBtn = canDelete
    ? `<button class="tbl-btn tbl-btn-danger" onclick="deleteRole(${data.id}, '${data.display_name}')">Delete</button>`
    : `<button class="tbl-btn tbl-btn-danger" disabled title="Cannot delete - has users">Delete</button>`;
return `<div class="tbl-actions">${deleteBtn}</div>`;
```

Replace with:
```javascript
const deleteBtn = canDelete
    ? `<button class="admin-btn admin-btn-sm admin-btn-danger" onclick="deleteRole(${data.id}, '${data.display_name}')">Delete</button>`
    : `<button class="admin-btn admin-btn-sm admin-btn-danger" disabled title="Cannot delete - has users">Delete</button>`;
return `<div class="admin-actions">${deleteBtn}</div>`;
```

**Step 3: Verify the page**

Navigate to `/admin/roles` and verify:
- Page header has title on left, "Add New Role" button on right
- Delete buttons are pill-shaped
- Count badge shows number

**Step 4: Commit**

```bash
git add app/templates/admin/roles.html
git commit -m "feat(admin): Update roles page to admin component system

Moves Add New Role to page header, updates button classes."
```

---

## Task 5: Trips Page - Convert to Tabulator

**Files:**
- Modify: `app/templates/admin/trips.html`
- Create: `app/static/admin_trips.js`
- Modify: `app/routes/admin.py` (add JSON endpoint)

**Step 1: Add JSON data endpoint to admin.py**

Find the `trips()` function in `app/routes/admin.py` and add a new endpoint after it:

```python
@admin_bp.route('/trips/data')
@require_admin
def trips_data():
    """JSON data endpoint for trips Tabulator grid."""
    trips = Trip.query.order_by(Trip.start_date.desc()).all()
    return jsonify({
        'trips': [{
            'id': t.id,
            'name': t.name,
            'destination': t.destination,
            'start_date': t.start_date.strftime('%Y-%m-%d') if t.start_date else None,
            'end_date': t.end_date.strftime('%Y-%m-%d') if t.end_date else None,
            'date_range': t.formatted_date_range,
            'signup_start': t.signup_start.strftime('%Y-%m-%d') if t.signup_start else None,
            'signup_end': t.signup_end.strftime('%Y-%m-%d') if t.signup_end else None,
            'capacity_standard': t.max_participants_standard,
            'capacity_extra': t.max_participants_extra,
            'price_low': t.price_low,
            'price_high': t.price_high,
            'status': t.status
        } for t in trips]
    })
```

**Step 2: Create admin_trips.js**

Create new file `app/static/admin_trips.js`:

```javascript
let tripsTable;
let tripsData = [];

// Format price from cents
function formatPrice(cents) {
    if (!cents) return '—';
    return '$' + (cents / 100).toFixed(2);
}

// Status badge HTML
function getStatusBadge(status) {
    const classes = {
        'active': 'admin-badge admin-badge-active',
        'draft': 'admin-badge admin-badge-inactive',
        'closed': 'admin-badge admin-badge-error'
    };
    return `<span class="${classes[status] || 'admin-badge'}">${status}</span>`;
}

document.addEventListener('DOMContentLoaded', async () => {
    // Fetch trips data
    const response = await fetch('/admin/trips/data');
    const data = await response.json();
    tripsData = data.trips;

    document.getElementById('trip-count').textContent = tripsData.length;

    // Initialize Tabulator
    tripsTable = new Tabulator("#trips-table", {
        data: tripsData,
        layout: "fitDataStretch",
        height: "calc(100vh - 320px)",

        columns: [
            {
                title: "Name",
                field: "name",
                frozen: true,
                minWidth: 180,
                formatter: function(cell) {
                    const id = cell.getRow().getData().id;
                    return `<a href="/admin/trips/${id}/edit" class="text-tcsc-navy hover:underline font-medium">${cell.getValue()}</a>`;
                }
            },
            {title: "Destination", field: "destination", minWidth: 150},
            {title: "Dates", field: "date_range", minWidth: 150},
            {
                title: "Capacity",
                minWidth: 100,
                formatter: function(cell) {
                    const data = cell.getRow().getData();
                    return `${data.capacity_standard}/${data.capacity_extra}`;
                }
            },
            {
                title: "Price",
                minWidth: 120,
                formatter: function(cell) {
                    const data = cell.getRow().getData();
                    if (data.price_low === data.price_high) {
                        return formatPrice(data.price_low);
                    }
                    return `${formatPrice(data.price_low)} - ${formatPrice(data.price_high)}`;
                }
            },
            {
                title: "Status",
                field: "status",
                minWidth: 100,
                formatter: function(cell) {
                    return getStatusBadge(cell.getValue());
                }
            },
            {
                title: "Actions",
                frozen: true,
                hozAlign: "right",
                minWidth: 140,
                formatter: function(cell) {
                    const data = cell.getRow().getData();
                    return `<div class="admin-actions">
                        <a href="/admin/trips/${data.id}/edit" class="admin-btn admin-btn-sm admin-btn-primary">Edit</a>
                        <button class="admin-btn admin-btn-sm admin-btn-danger" onclick="confirmDeleteTrip(${data.id}, '${data.name.replace(/'/g, "\\'")}')">Delete</button>
                    </div>`;
                },
                headerSort: false
            }
        ]
    });

    // Search filter
    document.getElementById('trips-search').addEventListener('input', function(e) {
        const value = e.target.value.toLowerCase();
        tripsTable.setFilter(function(data) {
            return data.name.toLowerCase().includes(value) ||
                   data.destination.toLowerCase().includes(value);
        });
        updateCount();
    });

    // Status filter pills
    document.querySelectorAll('.admin-pill[data-status]').forEach(pill => {
        pill.addEventListener('click', function() {
            document.querySelectorAll('.admin-pill[data-status]').forEach(p => p.classList.remove('active'));
            this.classList.add('active');

            const status = this.dataset.status;
            if (status === 'all') {
                tripsTable.clearFilter();
            } else {
                tripsTable.setFilter('status', '=', status);
            }
            updateCount();
        });
    });
});

function updateCount() {
    const count = tripsTable.getDataCount('active');
    document.getElementById('trip-count').textContent = count;
}

function confirmDeleteTrip(id, name) {
    if (!confirm(`Delete trip "${name}"?\n\nThis cannot be undone.`)) {
        return;
    }

    fetch(`/admin/trips/${id}/delete`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showToast('Trip deleted', 'success');
            tripsTable.deleteRow(id);
            updateCount();
        } else {
            showToast(data.error || 'Failed to delete trip', 'error');
        }
    })
    .catch(err => {
        showToast('Error: ' + err.message, 'error');
    });
}
```

**Step 3: Update trips.html template**

Replace the entire `{% block content %}` with:

```html
{% block content %}
<div class="bg-white rounded-tcsc p-5">
    <div class="admin-header">
        <h1>Trips</h1>
        <a href="{{ url_for('admin.new_trip') }}" class="admin-btn admin-btn-lg admin-btn-primary">+ Create New Trip</a>
    </div>

    <div class="admin-toolbar">
        <input type="text" id="trips-search" class="admin-search" placeholder="Search trips...">
        <div class="admin-pill-group">
            <button class="admin-pill active" data-status="all">All</button>
            <button class="admin-pill" data-status="active">Active</button>
            <button class="admin-pill" data-status="draft">Draft</button>
            <button class="admin-pill" data-status="closed">Closed</button>
        </div>
        <div class="admin-toolbar-spacer"></div>
        <span class="admin-count" id="trip-count">0</span>
    </div>

    <div id="trips-table" class="admin-table tabulator-config"></div>
</div>
{% endblock %}

{% block extra_js %}
<script src="{{ url_for('static', filename='admin_trips.js') }}"></script>
{% endblock %}
```

**Step 4: Test the page**

Navigate to `/admin/trips` and verify:
- Tabulator grid loads with trip data
- Search filters by name/destination
- Status pills filter correctly
- Edit/Delete buttons work

**Step 5: Commit**

```bash
git add app/templates/admin/trips.html app/static/admin_trips.js app/routes/admin.py
git commit -m "feat(admin): Convert trips page to Tabulator with admin components

Adds /admin/trips/data JSON endpoint, creates admin_trips.js,
updates template with admin-header, admin-toolbar, admin-pill-group."
```

---

## Task 6: Seasons Page - Convert to Tabulator

**Files:**
- Modify: `app/templates/admin/seasons.html`
- Create: `app/static/admin_seasons.js`
- Modify: `app/routes/admin.py` (add JSON endpoint)

**Step 1: Add JSON data endpoint to admin.py**

```python
@admin_bp.route('/seasons/data')
@require_admin
def seasons_data():
    """JSON data endpoint for seasons Tabulator grid."""
    seasons = Season.query.order_by(Season.year.desc(), Season.start_date.desc()).all()
    return jsonify({
        'seasons': [{
            'id': s.id,
            'name': s.name,
            'is_current': s.is_current,
            'season_type': s.season_type,
            'year': s.year,
            'start_date': s.start_date.strftime('%Y-%m-%d') if s.start_date else None,
            'end_date': s.end_date.strftime('%Y-%m-%d') if s.end_date else None,
            'returning_start': s.returning_start.strftime('%Y-%m-%d %H:%M') if s.returning_start else None,
            'returning_end': s.returning_end.strftime('%Y-%m-%d %H:%M') if s.returning_end else None,
            'new_start': s.new_start.strftime('%Y-%m-%d %H:%M') if s.new_start else None,
            'new_end': s.new_end.strftime('%Y-%m-%d %H:%M') if s.new_end else None,
            'price_cents': s.price_cents,
            'registration_limit': s.registration_limit,
            'description': s.description
        } for s in seasons]
    })
```

**Step 2: Create admin_seasons.js**

Create new file `app/static/admin_seasons.js`:

```javascript
let seasonsTable;
let seasonsData = [];

function formatPrice(cents) {
    if (!cents) return '—';
    return '$' + (cents / 100).toFixed(2);
}

document.addEventListener('DOMContentLoaded', async () => {
    const response = await fetch('/admin/seasons/data');
    const data = await response.json();
    seasonsData = data.seasons;

    document.getElementById('season-count').textContent = seasonsData.length;

    seasonsTable = new Tabulator("#seasons-table", {
        data: seasonsData,
        layout: "fitDataStretch",
        height: "calc(100vh - 280px)",

        columns: [
            {
                title: "Name",
                field: "name",
                frozen: true,
                minWidth: 150,
                formatter: function(cell) {
                    const data = cell.getRow().getData();
                    const badge = data.is_current ? ' <span class="admin-badge admin-badge-active">Current</span>' : '';
                    return `<span class="font-medium">${cell.getValue()}</span>${badge}`;
                }
            },
            {title: "Type", field: "season_type", minWidth: 80},
            {title: "Year", field: "year", minWidth: 60},
            {
                title: "Dates",
                minWidth: 180,
                formatter: function(cell) {
                    const data = cell.getRow().getData();
                    if (!data.start_date) return '—';
                    return `${data.start_date} to ${data.end_date}`;
                }
            },
            {
                title: "Returning Reg",
                minWidth: 150,
                formatter: function(cell) {
                    const data = cell.getRow().getData();
                    if (!data.returning_start) return '—';
                    return `${data.returning_start}<br>to ${data.returning_end}`;
                }
            },
            {
                title: "New Reg",
                minWidth: 150,
                formatter: function(cell) {
                    const data = cell.getRow().getData();
                    if (!data.new_start) return '—';
                    return `${data.new_start}<br>to ${data.new_end}`;
                }
            },
            {
                title: "Price",
                field: "price_cents",
                minWidth: 80,
                formatter: function(cell) {
                    return formatPrice(cell.getValue());
                }
            },
            {title: "Limit", field: "registration_limit", minWidth: 60},
            {
                title: "Actions",
                frozen: true,
                hozAlign: "right",
                minWidth: 240,
                formatter: function(cell) {
                    const data = cell.getRow().getData();
                    let html = `<div class="admin-actions">
                        <a href="/admin/seasons/${data.id}/edit" class="admin-btn admin-btn-sm admin-btn-primary">Edit</a>
                        <a href="/admin/seasons/${data.id}/export" class="admin-btn admin-btn-sm admin-btn-secondary">Export</a>`;

                    if (!data.is_current) {
                        html += `<button class="admin-btn admin-btn-sm admin-btn-success" onclick="activateSeason(${data.id}, '${data.name.replace(/'/g, "\\'")}')">Activate</button>`;
                    }

                    html += `<button class="admin-btn admin-btn-sm admin-btn-danger" onclick="confirmDeleteSeason(${data.id}, '${data.name.replace(/'/g, "\\'")}')">Delete</button>
                    </div>`;
                    return html;
                },
                headerSort: false
            }
        ]
    });
});

function activateSeason(id, name) {
    if (!confirm(`Activate season "${name}"?\n\nThis will:\n• Set this as the current season\n• Update all user statuses based on their registration\n• Recalculate seasons_since_active counters\n\nContinue?`)) {
        return;
    }

    fetch(`/admin/seasons/${id}/activate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showToast('Season activated', 'success');
            location.reload();
        } else {
            showToast(data.error || 'Failed to activate season', 'error');
        }
    })
    .catch(err => {
        showToast('Error: ' + err.message, 'error');
    });
}

function confirmDeleteSeason(id, name) {
    if (!confirm(`Delete season "${name}"?\n\nThis cannot be undone.`)) {
        return;
    }

    fetch(`/admin/seasons/${id}/delete`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showToast('Season deleted', 'success');
            seasonsTable.deleteRow(id);
            document.getElementById('season-count').textContent = seasonsTable.getDataCount();
        } else {
            showToast(data.error || 'Failed to delete season', 'error');
        }
    })
    .catch(err => {
        showToast('Error: ' + err.message, 'error');
    });
}
```

**Step 3: Update seasons.html template**

Replace the entire `{% block content %}` with:

```html
{% block content %}
<div class="bg-white rounded-tcsc p-5">
    <div class="admin-header">
        <h1>Seasons</h1>
        <a href="{{ url_for('admin.new_season') }}" class="admin-btn admin-btn-lg admin-btn-primary">+ Create New Season</a>
    </div>

    <div class="admin-toolbar">
        <div class="admin-toolbar-spacer"></div>
        <span class="admin-count" id="season-count">0</span>
    </div>

    <div id="seasons-table" class="admin-table tabulator-config"></div>
</div>
{% endblock %}

{% block extra_js %}
<script src="{{ url_for('static', filename='admin_seasons.js') }}"></script>
{% endblock %}
```

**Step 4: Test and commit**

```bash
git add app/templates/admin/seasons.html app/static/admin_seasons.js app/routes/admin.py
git commit -m "feat(admin): Convert seasons page to Tabulator with admin components"
```

---

## Task 7: Social Events Page - Convert to Tabulator

**Files:**
- Modify: `app/templates/admin/social_events.html`
- Create: `app/static/admin_social_events.js`
- Modify: `app/routes/admin.py` (add JSON endpoint)

**Step 1: Add JSON data endpoint**

```python
@admin_bp.route('/social-events/data')
@require_admin
def social_events_data():
    """JSON data endpoint for social events Tabulator grid."""
    events = SocialEvent.query.order_by(SocialEvent.event_date.desc()).all()
    return jsonify({
        'events': [{
            'id': e.id,
            'name': e.name,
            'location': e.location,
            'event_date': e.formatted_date if hasattr(e, 'formatted_date') else (e.event_date.strftime('%Y-%m-%d %H:%M') if e.event_date else None),
            'signup_start': e.signup_start.strftime('%Y-%m-%d') if e.signup_start else None,
            'signup_end': e.signup_end.strftime('%Y-%m-%d') if e.signup_end else None,
            'max_participants': e.max_participants,
            'price': e.price,
            'status': e.status
        } for e in events]
    })
```

**Step 2: Create admin_social_events.js**

```javascript
let eventsTable;
let eventsData = [];

function formatPrice(cents) {
    if (!cents) return 'Free';
    return '$' + (cents / 100).toFixed(2);
}

function getStatusBadge(status) {
    const classes = {
        'active': 'admin-badge admin-badge-active',
        'draft': 'admin-badge admin-badge-inactive',
        'closed': 'admin-badge admin-badge-error'
    };
    return `<span class="${classes[status] || 'admin-badge'}">${status}</span>`;
}

document.addEventListener('DOMContentLoaded', async () => {
    const response = await fetch('/admin/social-events/data');
    const data = await response.json();
    eventsData = data.events;

    document.getElementById('event-count').textContent = eventsData.length;

    eventsTable = new Tabulator("#events-table", {
        data: eventsData,
        layout: "fitDataStretch",
        height: "calc(100vh - 320px)",

        columns: [
            {
                title: "Name",
                field: "name",
                frozen: true,
                minWidth: 180,
                formatter: function(cell) {
                    const id = cell.getRow().getData().id;
                    return `<a href="/admin/social-events/${id}/edit" class="text-tcsc-navy hover:underline font-medium">${cell.getValue()}</a>`;
                }
            },
            {title: "Location", field: "location", minWidth: 150},
            {title: "Date", field: "event_date", minWidth: 150},
            {
                title: "Price",
                field: "price",
                minWidth: 80,
                formatter: function(cell) {
                    return formatPrice(cell.getValue());
                }
            },
            {title: "Capacity", field: "max_participants", minWidth: 80},
            {
                title: "Status",
                field: "status",
                minWidth: 100,
                formatter: function(cell) {
                    return getStatusBadge(cell.getValue());
                }
            },
            {
                title: "Actions",
                frozen: true,
                hozAlign: "right",
                minWidth: 140,
                formatter: function(cell) {
                    const data = cell.getRow().getData();
                    return `<div class="admin-actions">
                        <a href="/admin/social-events/${data.id}/edit" class="admin-btn admin-btn-sm admin-btn-primary">Edit</a>
                        <button class="admin-btn admin-btn-sm admin-btn-danger" onclick="confirmDeleteEvent(${data.id}, '${data.name.replace(/'/g, "\\'")}')">Delete</button>
                    </div>`;
                },
                headerSort: false
            }
        ]
    });

    // Search filter
    document.getElementById('events-search').addEventListener('input', function(e) {
        const value = e.target.value.toLowerCase();
        eventsTable.setFilter(function(data) {
            return data.name.toLowerCase().includes(value) ||
                   (data.location && data.location.toLowerCase().includes(value));
        });
        updateCount();
    });

    // Status filter pills
    document.querySelectorAll('.admin-pill[data-status]').forEach(pill => {
        pill.addEventListener('click', function() {
            document.querySelectorAll('.admin-pill[data-status]').forEach(p => p.classList.remove('active'));
            this.classList.add('active');

            const status = this.dataset.status;
            if (status === 'all') {
                eventsTable.clearFilter();
            } else {
                eventsTable.setFilter('status', '=', status);
            }
            updateCount();
        });
    });
});

function updateCount() {
    const count = eventsTable.getDataCount('active');
    document.getElementById('event-count').textContent = count;
}

function confirmDeleteEvent(id, name) {
    if (!confirm(`Delete event "${name}"?\n\nThis cannot be undone.`)) {
        return;
    }

    fetch(`/admin/social-events/${id}/delete`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showToast('Event deleted', 'success');
            eventsTable.deleteRow(id);
            updateCount();
        } else {
            showToast(data.error || 'Failed to delete event', 'error');
        }
    })
    .catch(err => {
        showToast('Error: ' + err.message, 'error');
    });
}
```

**Step 3: Update social_events.html template**

```html
{% block content %}
<div class="bg-white rounded-tcsc p-5">
    <div class="admin-header">
        <h1>Social Events</h1>
        <a href="{{ url_for('admin.new_social_event') }}" class="admin-btn admin-btn-lg admin-btn-primary">+ Create New Event</a>
    </div>

    <div class="admin-toolbar">
        <input type="text" id="events-search" class="admin-search" placeholder="Search events...">
        <div class="admin-pill-group">
            <button class="admin-pill active" data-status="all">All</button>
            <button class="admin-pill" data-status="active">Active</button>
            <button class="admin-pill" data-status="draft">Draft</button>
            <button class="admin-pill" data-status="closed">Closed</button>
        </div>
        <div class="admin-toolbar-spacer"></div>
        <span class="admin-count" id="event-count">0</span>
    </div>

    <div id="events-table" class="admin-table tabulator-config"></div>
</div>
{% endblock %}

{% block extra_js %}
<script src="{{ url_for('static', filename='admin_social_events.js') }}"></script>
{% endblock %}
```

**Step 4: Test and commit**

```bash
git add app/templates/admin/social_events.html app/static/admin_social_events.js app/routes/admin.py
git commit -m "feat(admin): Convert social events page to Tabulator with admin components"
```

---

## Task 8: Slack Sync Page - Update to Admin Components

**Files:**
- Modify: `app/templates/admin/slack_sync.html`
- Modify: `app/static/admin_slack.js`

**Step 1: Update toolbar buttons**

Find:
```html
<button class="toolbar-btn toolbar-btn-secondary" id="message-btn" onclick="openMessageModal()">
```

Replace with:
```html
<button class="admin-btn admin-btn-md admin-btn-secondary" id="message-btn" onclick="openMessageModal()">
```

And update the other two toolbar buttons similarly (sync-btn, profile-sync-btn):
```html
<button class="admin-btn admin-btn-md admin-btn-primary" id="sync-btn" onclick="runSync()">
<button class="admin-btn admin-btn-md admin-btn-primary" id="profile-sync-btn" onclick="runProfileSync()">
```

**Step 2: Update the view filter pills**

Find:
```html
<div class="seg-group">
    <button class="seg-btn active" data-filter="all" onclick="setUserFilter('all', this)">All</button>
    <button class="seg-btn" data-filter="matched" onclick="setUserFilter('matched', this)">Matched</button>
    <button class="seg-btn" data-filter="unmatched" onclick="setUserFilter('unmatched', this)">Unmatched</button>
</div>
```

Replace with:
```html
<div class="admin-pill-group">
    <button class="admin-pill active" data-filter="all" onclick="setUserFilter('all', this)">All</button>
    <button class="admin-pill" data-filter="matched" onclick="setUserFilter('matched', this)">Matched</button>
    <button class="admin-pill" data-filter="unmatched" onclick="setUserFilter('unmatched', this)">Unmatched</button>
</div>
```

**Step 3: Update modal buttons**

In link-modal:
```html
<button class="admin-btn admin-btn-md admin-btn-secondary" onclick="closeLinkModal()">Cancel</button>
<button class="admin-btn admin-btn-md admin-btn-primary" onclick="confirmLink()">Link</button>
```

In message-modal:
```html
<button class="admin-btn admin-btn-md admin-btn-secondary" onclick="closeMessageModal()">Cancel</button>
<button class="admin-btn admin-btn-md admin-btn-primary" id="send-message-btn" onclick="sendMessage()">Send Message</button>
```

**Step 4: Update small buttons in message modal**

Find:
```html
<button type="button" class="tbl-btn tbl-btn-secondary" onclick="selectAllUsers()">Select All</button>
<button type="button" class="tbl-btn tbl-btn-secondary" onclick="deselectAllUsers()">Deselect All</button>
```

Replace with:
```html
<button type="button" class="admin-btn admin-btn-sm admin-btn-secondary" onclick="selectAllUsers()">Select All</button>
<button type="button" class="admin-btn admin-btn-sm admin-btn-secondary" onclick="deselectAllUsers()">Deselect All</button>
```

**Step 5: Update admin_slack.js - inline buttons**

Search for `tbl-btn` in admin_slack.js and replace:
- `tbl-btn tbl-btn-primary` → `admin-btn admin-btn-sm admin-btn-primary`
- `tbl-btn tbl-btn-secondary` → `admin-btn admin-btn-sm admin-btn-secondary`
- `tbl-btn tbl-btn-danger` → `admin-btn admin-btn-sm admin-btn-danger`

Also update the filter class toggle from `seg-btn` to `admin-pill`.

**Step 6: Test and commit**

```bash
git add app/templates/admin/slack_sync.html app/static/admin_slack.js
git commit -m "feat(admin): Update slack sync page to admin component system"
```

---

## Task 9: Channel Sync Page - Update to Admin Components

**Files:**
- Modify: `app/templates/admin/channel_sync.html`

**Step 1: Update the header buttons**

Find the inline-styled action buttons and replace with admin classes:

Find:
```html
<button class="action-btn bg-gray-200 text-gray-600 border-none px-5 py-2.5 rounded-tcsc text-sm font-medium cursor-pointer inline-flex items-center gap-2 transition-all whitespace-nowrap hover:opacity-90 hover:-translate-y-px disabled:opacity-60 disabled:cursor-not-allowed disabled:transform-none" id="dry-run-btn" onclick="runSync(true)">
```

Replace with:
```html
<button class="admin-btn admin-btn-md admin-btn-secondary" id="dry-run-btn" onclick="runSync(true)">
```

And:
```html
<button class="action-btn bg-amber-500 text-white border-none px-5 py-2.5 rounded-tcsc..." id="live-run-btn" onclick="runSync(false)">
```

Replace with:
```html
<button class="admin-btn admin-btn-md admin-btn-primary" id="live-run-btn" onclick="runSync(false)" style="background-color: #f59e0b;">
```

**Step 2: Update Refresh button**

Find:
```html
<button class="bg-gray-200 text-gray-600 border-none px-4 py-2 rounded-tcsc text-sm font-medium cursor-pointer inline-flex items-center gap-2 transition-all hover:bg-gray-300" onclick="loadStatus()">
```

Replace with:
```html
<button class="admin-btn admin-btn-md admin-btn-secondary" onclick="loadStatus()">
```

**Step 3: Update ExpertVoice buttons**

Same pattern - replace inline-styled buttons with admin-btn classes.

**Step 4: Update Clear button**

```html
<button class="admin-btn admin-btn-md admin-btn-secondary" onclick="clearLog()">
```

**Step 5: Remove the action-btn CSS from the style block**

The `.action-btn` and `.action-btn.loading` CSS rules are no longer needed.

**Step 6: Test and commit**

```bash
git add app/templates/admin/channel_sync.html
git commit -m "feat(admin): Update channel sync page to admin component system"
```

---

## Task 10: Cleanup - Remove Old CSS Classes

**Files:**
- Modify: `app/static/css/tailwind-input.css`

**Step 1: Remove or deprecate old classes**

After verifying all pages work, you can optionally remove the old classes from tailwind-input.css:
- `.tbl-btn`, `.tbl-btn-primary`, `.tbl-btn-secondary`, `.tbl-btn-danger`, `.tbl-btn-success`
- `.toolbar-btn`, `.toolbar-btn-primary`, `.toolbar-btn-secondary`, `.toolbar-btn-danger`, `.toolbar-btn-success`
- `.seg-group`, `.seg-btn`
- `.tbl-select`, `.tbl-search`
- `.toolbar`, `.toolbar-spacer`, `.toolbar-group`, `.toolbar-count`
- `.tbl-actions`

**Note:** Only remove after thorough testing to ensure no pages still reference old classes.

**Step 2: Rebuild Tailwind**

```bash
npx tailwindcss -i app/static/css/tailwind-input.css -o app/static/css/tailwind-output.css
```

**Step 3: Final commit**

```bash
git add app/static/css/tailwind-input.css app/static/css/tailwind-output.css
git commit -m "chore(admin): Remove deprecated CSS classes after UI unification"
```

---

## Summary

This plan converts all admin pages to use a unified component system:

| Task | Page | Changes |
|------|------|---------|
| 1 | CSS | Add all `.admin-*` component classes |
| 2 | Users | Update classes (template for others) |
| 3 | Payments | Update classes |
| 4 | Roles | Update classes, move header button |
| 5 | Trips | Convert to Tabulator, new JS file |
| 6 | Seasons | Convert to Tabulator, new JS file |
| 7 | Social Events | Convert to Tabulator, new JS file |
| 8 | Slack Sync | Update classes |
| 9 | Channel Sync | Update inline styles to classes |
| 10 | Cleanup | Remove old CSS classes |

Each task has a commit, so progress can be reviewed incrementally.
