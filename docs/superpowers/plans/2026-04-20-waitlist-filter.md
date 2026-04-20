# Waitlist Filter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a "Waitlist" pill to the admin users view switcher that filters to users who registered for the lottery but never became active members.

**Architecture:** Pure client-side filtering. The existing `/admin/users/data` endpoint already returns each user's `seasons` dict with statuses for all seasons. No backend changes needed.

**Tech Stack:** HTML (Jinja2 template), vanilla JavaScript, Tabulator.js

---

### Task 1: Add Waitlist pill button to HTML template

**Files:**
- Modify: `app/templates/admin/users.html:352-356`

- [ ] **Step 1: Add the Waitlist pill button**

In `app/templates/admin/users.html`, find the pill group (line 352-356):

```html
<div class="admin-pill-group">
    <button class="admin-pill active" data-view="all">All</button>
    <button class="admin-pill" data-view="current">Current</button>
    <button class="admin-pill" data-view="alumni">Alumni</button>
</div>
```

Replace with:

```html
<div class="admin-pill-group">
    <button class="admin-pill active" data-view="all">All</button>
    <button class="admin-pill" data-view="current">Current</button>
    <button class="admin-pill" data-view="alumni">Alumni</button>
    <button class="admin-pill" data-view="waitlist">Waitlist</button>
</div>
```

- [ ] **Step 2: Commit**

```bash
git add app/templates/admin/users.html
git commit -m "feat: add Waitlist pill button to admin users toolbar"
```

---

### Task 2: Add waitlist filtering logic to JavaScript

**Files:**
- Modify: `app/static/admin_users.js:227-242` (applyGlobalView title logic)
- Modify: `app/static/admin_users.js:296-318` (applyFilters view filter logic)

- [ ] **Step 1: Add waitlist title in `applyGlobalView`**

In `app/static/admin_users.js`, find the title logic in `applyGlobalView()` (lines 230-242):

```javascript
    let seasonIdToUse = selectedSeasonId;
    let title = 'All Members';

    if (currentView === 'current' && currentSeason) {
        seasonIdToUse = currentSeason.id;
        title = `${currentSeason.name} Members`;
    } else if (currentView === 'season' && selectedSeasonId) {
        const season = allSeasons.find(s => s.id === selectedSeasonId);
        title = `${season ? season.name : 'Season'} Members`;
    } else if (currentView === 'alumni') {
        title = 'Alumni Members';
    } else {
        title = 'All Members';
    }
```

Replace with:

```javascript
    let seasonIdToUse = selectedSeasonId;
    let title = 'All Members';

    if (currentView === 'current' && currentSeason) {
        seasonIdToUse = currentSeason.id;
        title = `${currentSeason.name} Members`;
    } else if (currentView === 'season' && selectedSeasonId) {
        const season = allSeasons.find(s => s.id === selectedSeasonId);
        title = `${season ? season.name : 'Season'} Members`;
    } else if (currentView === 'alumni') {
        title = 'Alumni Members';
    } else if (currentView === 'waitlist') {
        title = 'Waitlist Members';
    } else {
        title = 'All Members';
    }
```

- [ ] **Step 2: Add waitlist filter logic in `applyFilters`**

In the same file, find the view filter section inside `applyFilters()` (lines 303-318):

```javascript
        // Global view filter
        if (currentView === 'alumni') {
            if (data.status !== 'ALUMNI') {
                return false;
            }
        } else if (currentView === 'current' && currentSeason) {
            // Only show members registered for current season
            if (!data.seasons || !data.seasons[currentSeason.id]) {
                return false;
            }
        } else if (currentView === 'season' && selectedSeasonId) {
            // Only show members registered for selected season
            if (!data.seasons || !data.seasons[selectedSeasonId]) {
                return false;
            }
        }
```

Replace with:

```javascript
        // Global view filter
        if (currentView === 'alumni') {
            if (data.status !== 'ALUMNI') {
                return false;
            }
        } else if (currentView === 'waitlist') {
            const statuses = Object.values(data.seasons || {});
            const hasLotteryStatus = statuses.some(s => s === 'PENDING_LOTTERY' || s === 'DROPPED_LOTTERY');
            const hasBeenActive = statuses.some(s => s === 'ACTIVE');
            if (!hasLotteryStatus || hasBeenActive) {
                return false;
            }
        } else if (currentView === 'current' && currentSeason) {
            // Only show members registered for current season
            if (!data.seasons || !data.seasons[currentSeason.id]) {
                return false;
            }
        } else if (currentView === 'season' && selectedSeasonId) {
            // Only show members registered for selected season
            if (!data.seasons || !data.seasons[selectedSeasonId]) {
                return false;
            }
        }
```

- [ ] **Step 3: Commit**

```bash
git add app/static/admin_users.js
git commit -m "feat: add waitlist view filtering logic"
```

---

### Task 3: Manual verification

- [ ] **Step 1: Start the dev server**

```bash
./scripts/dev.sh
```

- [ ] **Step 2: Verify in browser**

Navigate to `https://tcsc.ski/admin/users` (or localhost equivalent) and verify:

1. The "Waitlist" pill appears in the toolbar after "Alumni"
2. Clicking "Waitlist" filters the grid and shows "Waitlist Members" title
3. The member count updates correctly
4. Clicking other pills ("All", "Current", "Alumni") still works correctly
5. The season dropdown still works (deselects pills, shows season view)
6. Other filters (search, status, roles, season status) still compose correctly when in waitlist view
