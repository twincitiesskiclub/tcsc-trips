# Waitlist Filter — Admin Users Page

## Summary

Add a "Waitlist" view pill to the admin users page (`/admin/users`) view switcher, alongside the existing "All | Current | Alumni" pills. This lets admins quickly see members who tried to register but never got in.

## Waitlist Definition

A user is on the waitlist if:
- They have `PENDING_LOTTERY` or `DROPPED_LOTTERY` status in **any** season
- AND they have **never** had `ACTIVE` status in any season

This captures people who expressed interest (registered for the lottery) but were never accepted as members.

## UI

The view switcher row changes from:

```
[ All ] [ Current ] [ Alumni ]
```

to:

```
[ All ] [ Current ] [ Alumni ] [ Waitlist ]
```

Clicking "Waitlist" filters the grid to show only waitlisted users and updates the view title to "Waitlist Members".

## Implementation

**Approach:** Client-side filtering. The existing `/admin/users/data` endpoint already returns each user's `seasons` dict (`{season_id: status}` for all seasons). No backend changes required.

### Files Changed

1. **`app/templates/admin/users.html`** — Add "Waitlist" pill button to the view switcher row (same styling/pattern as existing pills).

2. **`app/static/admin_users.js`** — Three changes:
   - Add `'waitlist'` as a valid `currentView` value
   - Implement filter: check if any value in `user.seasons` is `PENDING_LOTTERY` or `DROPPED_LOTTERY`, and no value is `ACTIVE`
   - Wire up click handler to set view, filter data, and update title to "Waitlist Members"

### Filter Logic (pseudocode)

```javascript
function isWaitlisted(user) {
  const statuses = Object.values(user.seasons);
  const hasLotteryStatus = statuses.some(s =>
    s === 'PENDING_LOTTERY' || s === 'DROPPED_LOTTERY'
  );
  const hasBeenActive = statuses.some(s => s === 'ACTIVE');
  return hasLotteryStatus && !hasBeenActive;
}
```

## Scope

- No backend changes
- No new endpoints
- No email functionality (existing CSV export covers that need)
- Estimated: ~20 lines across 2 files
