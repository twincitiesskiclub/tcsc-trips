# Admin UI Unification Design

**Date:** 2026-01-19
**Status:** Approved
**Scope:** Reorganize existing admin UI for consistency (no new features)

## Overview

Unify all admin pages to use a consistent component system with standardized buttons, filters, toolbars, tables, and modals. This is a reorganization effort - all existing features are preserved.

## Design Decisions

| Decision | Choice |
|----------|--------|
| Button approach | CSS component classes with Tailwind design tokens |
| Visual style | Clean & minimal (approachable for non-techy admins) |
| Action placement | Both toolbar (bulk) and inline (row-specific), clearly separated |
| Toolbar layout | Single line: filters left, count center, actions right |
| Filter controls | Pill buttons for common filters, dropdowns for longer lists |
| Inline table buttons | Small pill buttons with text labels |
| Button colors | Navy primary, gray secondary, red danger (TCSC brand) |
| Tables | Convert all to Tabulator with standardized styling |
| Modals | Standardize to one modal component (480px, consistent structure) |
| Page headers | Title + primary action button |

## Component System

### Buttons

Three sizes, four variants:

**Sizes:**
- `.admin-btn-sm` - 28px height, pill shape (inline table actions)
- `.admin-btn-md` - 36px height, 6px radius (toolbar actions)
- `.admin-btn-lg` - 40px height, 6px radius (page header primary)

**Variants:**
- `.admin-btn-primary` - Navy background, white text
- `.admin-btn-secondary` - White background, gray border
- `.admin-btn-danger` - Red background tint, red text
- `.admin-btn-success` - Green background tint, green text

All buttons have 150ms transitions, focus rings, and disabled states.

### Filters

**Pill groups (`.admin-pill-group`, `.admin-pill`):**
- Connected buttons with shared border
- Active state: navy background, white text
- For: status toggles, view switches

**Dropdowns (`.admin-select`):**
- 36px height, consistent border styling
- For: seasons, types, longer option lists

**Search (`.admin-search`):**
- 36px height, magnifying glass icon
- 176px width (w-44)

**Count badge (`.admin-count`):**
- Small navy pill showing filtered count
- Sits between filters and actions

### Layout

**Page header (`.admin-header`):**
```
┌─────────────────────────────────┐  ┌───────────────┐
│ Page Title                      │  │ + Create New  │
└─────────────────────────────────┘  └───────────────┘
```

**Toolbar (`.admin-toolbar`):**
```
┌────────┐ ┌────────┐ ┌────────────┐  ┌──┐  ┌────┐┌────┐
│🔍Search│ │Dropdown│ │All│Act│Alum│  │47│  │Bulk││Exp │
└────────┘ └────────┘ └────────────┘  └──┘  └────┘└────┘
 (search)  (dropdown)  (pills)       (count) (actions)
```

### Tables

All tables use Tabulator with consistent styling:
- Header: light gray background, semibold navy text
- Rows: 44px height, subtle hover highlight
- Frozen columns: drop shadow to separate from scroll area
- Selection: light navy tint on selected rows

### Modals

Standard structure:
```
┌─────────────────────────────────────────┐
│ Modal Title                         ✕   │
├─────────────────────────────────────────┤
│  Content area (forms, confirmations)    │
├─────────────────────────────────────────┤
│                    [Cancel] [Primary]   │
└─────────────────────────────────────────┘
```

- Width: 480px max
- Backdrop click closes
- Escape key closes
- Focus trapped inside

## Frozen Column Plan

| Page | Frozen Left | Frozen Right | Scrollable Middle |
|------|-------------|--------------|-------------------|
| Users | ☐ Select, Name | Actions | Email, Status, Roles, Slack, Seasons |
| Payments | ☐ Select, Name | Actions | Amount, For, Type, Status, Date |
| Roles | Name | Actions | Display Name, Emoji, Gradient, User Count |
| Trips | Name | Actions | Dates, Location, Capacity, Status |
| Seasons | Name | Actions | Dates, Registration Windows, Status |
| Social Events | Name | Actions | Date, Location, Price, Status |
| Slack Sync | Name | Actions | Email, Slack Name, Match Status |

**Minimum column widths:**
- Name columns: 150-200px
- Email: 180px
- Status badges: 100px
- Actions: 80px per button + padding

## Page-by-Page Implementation

### Users Page (`users.html`, `admin_users.js`)
- Replace `.toolbar-btn-*` with `.admin-btn-*` classes
- Replace `.seg-btn` with `.admin-pill` in view switcher
- Replace `.tbl-btn-*` with `.admin-btn-sm` for inline Edit
- Standardize role filter dropdown to `.admin-select`
- Move member count badge to center of toolbar
- Update modal buttons to `.admin-btn-md`
- No structural changes (template for others)

### Payments Page (`payments.html`, `admin_payments.js`)
- Replace `.toolbar-btn-*` with `.admin-btn-*`
- Replace `.tbl-btn-*` with `.admin-btn-sm` for inline buttons
- Move payment count to center of toolbar
- Replace `.tbl-select` with `.admin-select`
- Replace `.tbl-search` with `.admin-search`
- Update status filter to pill group: All | Pending | Captured | Refunded
- Update bulk confirmation modal to `.admin-modal` structure

### Roles Page (`roles.html`, inline JS)
- Move "Add New Role" button to page header (`.admin-btn-lg`)
- Replace toolbar role count styling to `.admin-count`
- Replace Delete button with `.admin-btn-sm .admin-btn-danger`
- Keep inline editing behavior unchanged

### Trips Page (`trips.html` → convert to Tabulator)
- Create page header with "Create New Trip" button
- Add toolbar with search, status pills (All|Active|Draft|Past), count, Export
- Convert HTML table to Tabulator
- Columns: Name (frozen), Dates, Location, Capacity, Status, Actions (frozen)
- Create `admin_trips.js`
- Add delete confirmation modal

### Seasons Page (`seasons.html` → convert to Tabulator)
- Create page header with "Create New Season" button
- Add toolbar with count badge only
- Convert HTML table to Tabulator
- Columns: Name (frozen), Start/End Dates, Registration Opens, Status, Actions (frozen)
- Actions: Edit, Export, Activate, Delete pills
- Create `admin_seasons.js`
- Add confirmation modals for Activate and Delete

### Social Events Page (`social_events.html` → convert to Tabulator)
- Create page header with "Create New Event" button
- Add toolbar with search, status pills (All|Upcoming|Past), count
- Convert HTML table to Tabulator
- Columns: Name (frozen), Date, Location, Price, Capacity, Status, Actions (frozen)
- Create `admin_social_events.js`
- Add delete confirmation modal

### Slack Sync Page (`slack_sync.html`, `admin_slack.js`)
- Standardize page header (no primary action)
- Update toolbar with pills, count, action buttons
- Replace inline Link/Unlink with `.admin-btn-sm` pills
- Update modals to `.admin-modal` structure
- Standardize stats cards styling

### Channel Sync Page (`channel_sync.html`)
- Standardize page header
- Replace inline-styled buttons with `.admin-btn-md`
- Standardize status cards borders/shadows
- Keep log output area as-is

## CSS Implementation

Add to `tailwind-input.css`:

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
         transition-colors duration-150;
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
         focus:ring-2 focus:ring-tcsc-navy/10;
}

.admin-search {
  @apply h-9 px-3 pl-9 text-sm rounded-tcsc w-44
         border border-tcsc-gray-100 bg-white shadow-sm
         focus:outline-none focus:border-tcsc-navy
         focus:ring-2 focus:ring-tcsc-navy/10;
}

/* --- Layout --- */
.admin-header {
  @apply flex items-center justify-between mb-6;
}

.admin-header h1 {
  @apply text-xl font-semibold text-tcsc-gray-800;
}

.admin-toolbar {
  @apply flex flex-wrap items-center gap-3 mb-4;
}

.admin-toolbar-spacer {
  @apply flex-1;
}

.admin-count {
  @apply px-2.5 py-1 text-xs font-semibold rounded-full
         bg-tcsc-navy text-white;
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
  @apply bg-white rounded-tcsc w-full max-w-md mx-4 shadow-xl animate-fade-in;
}

.admin-modal-header {
  @apply flex items-center justify-between px-5 py-4 border-b border-tcsc-gray-100;
}

.admin-modal-header h2 {
  @apply text-base font-semibold text-tcsc-gray-800;
}

.admin-modal-body {
  @apply p-5;
}

.admin-modal-footer {
  @apply flex justify-end gap-3 px-5 py-4 border-t border-tcsc-gray-100;
}

/* --- Table Enhancements --- */
.admin-table .tabulator-header {
  @apply bg-tcsc-gray-50 border-b border-tcsc-gray-100;
}

.admin-table .tabulator-col-title {
  @apply text-sm font-semibold text-tcsc-navy;
}

.admin-table .tabulator-row {
  @apply border-b border-tcsc-gray-100;
}

.admin-table .tabulator-row:hover {
  @apply bg-tcsc-navy/5;
}

.admin-table .tabulator-row.tabulator-selected {
  @apply bg-tcsc-navy/10;
}

.admin-table .tabulator-frozen-left {
  @apply shadow-[2px_0_4px_-2px_rgba(0,0,0,0.1)];
}

.admin-table .tabulator-frozen-right {
  @apply shadow-[-2px_0_4px_-2px_rgba(0,0,0,0.1)];
}
```

## File Changes

```
app/static/css/
├── tailwind-input.css      # Add new .admin-* component classes

app/static/
├── admin.js                # Shared utilities (modal, toast)
├── admin_users.js          # Update class references
├── admin_payments.js       # Update class references
├── admin_slack.js          # Update class references
├── admin_trips.js          # NEW - Tabulator for trips
├── admin_seasons.js        # NEW - Tabulator for seasons
├── admin_social_events.js  # NEW - Tabulator for social events

app/templates/admin/
├── admin_base.html         # Update shared button classes
├── users.html              # Update to new classes
├── payments.html           # Update to new classes
├── roles.html              # Update classes, move header button
├── trips.html              # Rebuild with Tabulator
├── seasons.html            # Rebuild with Tabulator
├── social_events.html      # Rebuild with Tabulator
├── slack_sync.html         # Update to new classes
├── channel_sync.html       # Update to new classes
```

## Implementation Order

1. **CSS Foundation** - Add all `.admin-*` classes to `tailwind-input.css`, rebuild Tailwind
2. **Users page** - Update classes (template for all others)
3. **Payments page** - Update classes
4. **Roles page** - Update classes, move header button
5. **Trips page** - Convert to Tabulator, create JS file
6. **Seasons page** - Convert to Tabulator, create JS file
7. **Social Events page** - Convert to Tabulator, create JS file
8. **Slack Sync page** - Update classes
9. **Channel Sync page** - Update classes
10. **Cleanup** - Remove old `.toolbar-btn-*`, `.tbl-btn-*`, `.seg-btn` classes
