# Practice List Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the desktop-only Tabulator grid on the practice list page with an on-brand, mobile-friendly single-scroll agenda list and a click-to-preview slide-over drawer, matching the workout editor's "Quiet Precision" design.

**Architecture:** Pure front-end rebuild of two files — `app/templates/admin/practices/list.html` (markup + scoped CSS) and `app/static/admin_practices.js` (rendering + drawer). No backend changes: the list renders from the existing `GET /admin/practices/data` payload; the drawer renders instantly from the cached row, auto-loads RSVP counts from `GET /admin/practices/<id>/rsvps`, and loads the Skipper verdict from `GET /admin/practices/<id>/evaluation` only behind a manual button gated to today/tomorrow. The visual source of truth is a committed mockup (Task 1).

**Tech Stack:** Flask + Jinja2; raw scoped `<style>` in the template's `extra_css` block (NOT Tailwind utilities — no build step); vanilla JS (no ES modules, no JS test harness; helpers are global); pytest + PostgreSQL fixtures for the one render guard.

**Design spec:** `docs/superpowers/specs/2026-06-04-practice-list-redesign-design.md`

---

## File Structure

| File | Responsibility | Action |
|------|----------------|--------|
| `docs/superpowers/specs/2026-06-04-practice-list-mockup.html` | Committed visual source of truth (desktop + 375px), all CSS | Create |
| `app/templates/admin/practices/list.html` | List page: toolbar, single-scroll list container, drawer dialog markup, cancel modal; scoped CSS pasted from the mockup | Rewrite |
| `app/static/admin_practices.js` | Render the agenda list from the payload + drive the preview drawer; keep cancel/delete | Rewrite |
| `tests/routes/test_admin_practices_routes.py` | Add one render guard for the list page | Modify |

**Conventions to follow (verified in repo):**
- `admin_required` (`app/auth.py`) gates admin routes via `session['user']['email']` on the `@twincitiesskiclub.org` domain. The test file already exists (created during the editor work) with `app` / `client` / `db_session` / `admin_client` fixtures — reuse them.
- `showToast(msg, type)` is a global from `js/toast.js`, loaded by `admin_base.html` before `extra_js`. No import needed.
- `admin_base.html` provides blocks `title`, `extra_css` (in `<head>`), `content`, `extra_js` (end of body). Tabulator's CSS/JS are still loaded globally there; harmless if unused.
- **Styling is raw scoped CSS** inside the template's `extra_css` `<style>` (the editor's `detail.html` does exactly this). Do **not** add new Tailwind utility classes — they would require a `tailwind-output.css` rebuild. All new classes are scoped under `#practice-list`.
- The list payload `GET /admin/practices/data` returns `{practices: [...]}` where each item is:
  `{id, date (ISO, Central wall-clock, naive), day_of_week, location_name, location_id, social_location_id, social_location_name, activities[] (names), practice_types[] (names), status, has_social, is_dark_practice, leads[]{id,user_id,name,confirmed}, coaches[]{...}, assists[]{...}, cancellation_reason, warmup_description, workout_description, cooldown_description}`.
- RSVP endpoint `GET /admin/practices/<id>/rsvps` → `{rsvps[], summary:{going, maybe, not_going}}`. Evaluation endpoint `GET /admin/practices/<id>/evaluation` → `{success, evaluation:{is_go, confidence, weather:{...}, violations:[{threshold_name, severity, message}], ...}}`.
- **Date assumption (verified):** `practice.date` is stored as the Central wall-clock datetime the practice occurs on (the editor writes the `datetime-local` value verbatim). So `iso.slice(0,10)` is the practice's Central calendar date — bucket on that string; never reinterpret through `new Date()` for bucketing.

---

## Task 1: Build the committed visual source-of-truth mockup

The spec gates the build on an approved 375px row frame. This task produces the standalone mockup whose `<style>` is the literal CSS the template will paste, and which shows both the desktop list+drawer and the 375px reflow.

**Files:**
- Create: `docs/superpowers/specs/2026-06-04-practice-list-mockup.html`

- [ ] **Step 1: Write the mockup file**

Create `docs/superpowers/specs/2026-06-04-practice-list-mockup.html` with the complete content below. The `<style>` block is the source of truth for Task 2 (its selectors are already scoped under `#practice-list`).

```html
<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Practice list — visual source</title>
<style>
/* ===== Practice list — scoped "Quiet Precision" styles (source of truth) ===== */
#practice-list, #practice-list *{box-sizing:border-box;margin:0;padding:0}
#practice-list{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;color:#1c2c44;font-size:15px;line-height:1.5}

/* header + toolbar */
#practice-list .pl-head{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap;margin-bottom:16px}
#practice-list .pl-head h1{font-size:20px;font-weight:700;letter-spacing:-.01em}
#practice-list .pl-toolbar{display:flex;align-items:center;gap:9px;flex-wrap:wrap;margin-bottom:18px}
#practice-list .pl-search{flex:1;min-width:180px;height:38px;border:1.5px solid #e5e7eb;border-radius:10px;padding:0 12px;font-size:14px;color:#1c2c44;background:#fff;font-family:inherit}
#practice-list .pl-select{height:38px;border:1.5px solid #e5e7eb;border-radius:10px;padding:0 10px;font-size:14px;color:#475569;background:#fff;font-family:inherit}
#practice-list .pl-search:focus,#practice-list .pl-select:focus{outline:none;border-color:#1c2c44}
#practice-list .pl-btn{height:38px;display:inline-flex;align-items:center;border-radius:10px;padding:0 16px;font-size:14px;font-weight:600;cursor:pointer;font-family:inherit;text-decoration:none;border:1.5px solid transparent}
#practice-list .pl-btn-primary{background:#1c2c44;color:#fff}
#practice-list .pl-btn-ghost{background:#fff;color:#475569;border-color:#e5e7eb}
#practice-list .pl-btn-ghost:hover{border-color:#1c2c44;color:#1c2c44}

/* section heading */
#practice-list .pl-sec{display:flex;align-items:center;gap:10px;margin:22px 2px 10px;font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.07em;color:#64748b}
#practice-list .pl-sec:first-of-type{margin-top:2px}
#practice-list .pl-sec.today{color:#1e40af}
#practice-list .pl-sec .ln{flex:1;height:1px;background:#eceff3}
#practice-list .pl-sec.today .ln{background:#dbeafe}
#practice-list .pl-sec .ct{color:#94a3b8;font-weight:700}

/* day group: date block once per day, rows stacked right */
#practice-list .pl-day{display:flex;align-items:stretch;gap:14px;margin-bottom:8px}
#practice-list .pl-db{display:flex;flex-direction:column;align-items:center;width:50px;flex-shrink:0;padding-top:12px}
#practice-list .pl-db .dow{font-size:10.5px;font-weight:700;text-transform:uppercase;color:#64748b}
#practice-list .pl-db .dn{font-size:23px;font-weight:700;line-height:1;color:#1c2c44}
#practice-list .pl-db .mo{font-size:10px;color:#64748b;text-transform:uppercase}
#practice-list .pl-db.is-today .dn{color:#1e40af}
#practice-list .pl-rows{flex:1;min-width:0;display:flex;flex-direction:column;gap:7px}

/* row (a button) */
#practice-list .pl-row{width:100%;text-align:left;background:#fff;border:1px solid #e9edf3;border-radius:11px;padding:11px 15px;display:flex;align-items:center;gap:12px;cursor:pointer;font-family:inherit;color:inherit;transition:border-color .12s,box-shadow .12s}
#practice-list .pl-row:hover{border-color:#cdd5e0}
#practice-list .pl-row.today{border-color:#bfdbfe;background:#f6faff}
#practice-list .pl-row:focus-visible{outline:2px solid #1c2c44;outline-offset:2px}
#practice-list .pl-row.is-active{border-color:#1c2c44;box-shadow:inset 3px 0 0 #1c2c44}
#practice-list .pl-row-main{flex:1;min-width:0;display:flex;flex-direction:column;gap:6px}
#practice-list .pl-row-top{display:flex;align-items:center;gap:9px;flex-wrap:wrap}
#practice-list .pl-loc{font-size:15px;font-weight:600}
#practice-list .pl-time{font-size:12.5px;color:#64748b}
#practice-list .pl-today-flag{font-size:9.5px;font-weight:800;letter-spacing:.05em;color:#1e40af;background:#dbeafe;border-radius:5px;padding:1px 6px;text-transform:uppercase}
#practice-list .pl-meta{display:flex;align-items:center;gap:6px;flex-wrap:wrap}
#practice-list .pl-pill{display:inline-flex;align-items:center;border:1.5px solid #e5e7eb;border-radius:20px;padding:1px 9px;font-size:11.5px;font-weight:500;color:#475569}
#practice-list .pl-ind{font-size:11.5px;color:#475569;display:inline-flex;align-items:center;gap:3px}
#practice-list .pl-row-aside{display:flex;flex-direction:column;align-items:flex-end;gap:7px;flex-shrink:0}

/* staffing chip */
#practice-list .pl-chip{display:inline-flex;align-items:center;gap:4px;font-size:11px;font-weight:600;padding:2px 8px;border-radius:7px;background:#f1f5f9;color:#475569;white-space:nowrap}
#practice-list .pl-chip.warn{background:#fefce8;color:#854d0e}

/* status badge — all five states (color + text; never color alone) */
#practice-list .pl-status{display:inline-flex;align-items:center;gap:5px;font-size:11px;font-weight:600;padding:3px 9px;border-radius:7px;white-space:nowrap}
#practice-list .pl-status::before{content:"";width:6px;height:6px;border-radius:50%;background:currentColor}
#practice-list .pl-status.is-scheduled{background:#dbeafe;color:#1e40af}
#practice-list .pl-status.is-confirmed{background:#dcfce7;color:#166534}
#practice-list .pl-status.is-in_progress{background:#fefce8;color:#854d0e}
#practice-list .pl-status.is-completed{background:#f1f5f9;color:#64748b}
#practice-list .pl-status.is-cancelled{background:#fde8e8;color:#c53030}

/* past section */
#practice-list .pl-past-toggle{width:100%;display:flex;align-items:center;gap:8px;background:#fff;border:1px dashed #d6dbe3;border-radius:11px;padding:12px 15px;color:#475569;font-size:13px;font-weight:600;cursor:pointer;font-family:inherit;margin-top:8px}
#practice-list .pl-past-toggle .chev{transition:transform .15s;color:#94a3b8}
#practice-list .pl-past-toggle[aria-expanded="true"] .chev{transform:rotate(90deg)}
#practice-list .pl-past-toggle .dim{color:#94a3b8;font-weight:500}
#practice-list .pl-loadmore{display:block;margin:8px auto 0;background:#fff;border:1.5px solid #e5e7eb;border-radius:9px;padding:8px 16px;font-size:13px;font-weight:600;color:#475569;cursor:pointer;font-family:inherit}
#practice-list .pl-empty{padding:28px 8px;text-align:center;color:#94a3b8;font-size:14px}

/* ===== preview drawer (dialog) ===== */
#practice-list .pl-scrim{position:fixed;inset:0;background:rgba(20,30,50,.18);z-index:1000}
#practice-list .pl-drawer{position:fixed;top:0;right:0;bottom:0;width:400px;max-width:100%;background:#fff;border-left:1px solid #e5e7eb;box-shadow:-14px 0 40px rgba(20,30,50,.16);z-index:1001;display:flex;flex-direction:column;transform:translateX(0);transition:transform .2s ease}
#practice-list .pl-drawer.hidden,#practice-list .pl-scrim.hidden{display:none}
#practice-list .pl-dwh{padding:16px 18px 14px;border-bottom:1px solid #eef1f5}
#practice-list .pl-dwh-top{display:flex;align-items:flex-start;justify-content:space-between;gap:10px}
#practice-list .pl-dw-title{font-size:18px;font-weight:700;letter-spacing:-.01em}
#practice-list .pl-dw-sub{font-size:13px;color:#475569;margin-top:3px}
#practice-list .pl-x{width:44px;height:44px;margin:-8px -8px 0 0;border-radius:8px;border:none;background:transparent;color:#64748b;font-size:18px;cursor:pointer;flex-shrink:0;display:flex;align-items:center;justify-content:center}
#practice-list .pl-x:hover{background:#f1f5f9}
#practice-list .pl-x:focus-visible{outline:2px solid #1c2c44;outline-offset:2px}
#practice-list .pl-badges{display:flex;align-items:center;gap:7px;margin-top:11px;flex-wrap:wrap}
#practice-list .pl-go{display:inline-flex;align-items:center;gap:5px;font-size:11px;font-weight:700;letter-spacing:.04em;padding:3px 9px;border-radius:6px;background:#acf3c4;color:#166534}
#practice-list .pl-go.nogo{background:#fde8e8;color:#c53030}
#practice-list .pl-dwbody{flex:1;overflow-y:auto;padding:6px 18px 16px}
#practice-list .pl-blk{padding:15px 0;border-bottom:1px solid #f1f5f9}
#practice-list .pl-blk:last-child{border-bottom:none}
#practice-list .pl-blk-h{font-size:10.5px;font-weight:700;text-transform:uppercase;letter-spacing:.06em;color:#64748b;margin-bottom:10px}
#practice-list .pl-kv{display:flex;gap:10px;margin-bottom:8px;font-size:13.5px}
#practice-list .pl-kv:last-child{margin-bottom:0}
#practice-list .pl-kv .k{color:#64748b;width:74px;flex-shrink:0}
#practice-list .pl-kv .v{color:#1c2c44;font-weight:500}
#practice-list .pl-pills{display:flex;gap:6px;flex-wrap:wrap}
#practice-list .pl-wblk{margin-bottom:12px}
#practice-list .pl-wblk:last-child{margin-bottom:0}
#practice-list .pl-wblk .wl{font-size:11.5px;font-weight:700;color:#1c2c44;margin-bottom:3px}
#practice-list .pl-wblk .wt{font-size:13px;color:#475569;line-height:1.55;white-space:pre-wrap;background:#f8fafb;border:1px solid #eef1f5;border-left:3px solid #cbd5e1;border-radius:8px;padding:9px 11px}
#practice-list .pl-wblk.main .wt{border-left-color:#1c2c44}
#practice-list .pl-person{display:flex;align-items:center;gap:8px;padding:6px 0;font-size:13.5px;border-bottom:1px solid #f6f8fa}
#practice-list .pl-person:last-child{border-bottom:none}
#practice-list .pl-person .role{font-size:10.5px;font-weight:700;text-transform:uppercase;color:#64748b;width:54px;flex-shrink:0}
#practice-list .pl-person .pn{flex:1;color:#1c2c44}
#practice-list .pl-conf{font-size:11px;font-weight:600;padding:2px 7px;border-radius:5px}
#practice-list .pl-conf.yes{background:#dcfce7;color:#166534}
#practice-list .pl-conf.no{background:#fef3c7;color:#92660b}
#practice-list .pl-rsvp{display:grid;grid-template-columns:1fr 1fr 1fr;border:1px solid #e5e7eb;border-radius:9px;overflow:hidden}
#practice-list .pl-rcell{display:flex;flex-direction:column;align-items:center;padding:9px 4px;background:#f8fafb}
#practice-list .pl-rcell+.pl-rcell{border-left:1px solid #e5e7eb}
#practice-list .pl-rcell .n{font-size:19px;font-weight:700;color:#1c2c44;line-height:1}
#practice-list .pl-rcell .l{font-size:9.5px;font-weight:700;text-transform:uppercase;color:#64748b;margin-top:3px}
#practice-list .pl-skipper-btn{background:#fff;color:#475569;border:1.5px solid #e5e7eb;border-radius:9px;padding:7px 12px;font-size:13px;font-weight:600;cursor:pointer;font-family:inherit}
#practice-list .pl-muted{font-size:12.5px;color:#64748b}
#practice-list .pl-dwacts{padding:13px 18px;border-top:1px solid #eef1f5;display:flex;gap:9px}
#practice-list .pl-act{height:40px;border-radius:10px;font-size:13.5px;font-weight:600;cursor:pointer;display:flex;align-items:center;justify-content:center;gap:6px;border:1.5px solid transparent;font-family:inherit;text-decoration:none}
#practice-list .pl-act-pri{flex:1;background:#1c2c44;color:#fff}
#practice-list .pl-act-ghost{background:#fff;color:#475569;border-color:#e5e7eb;padding:0 14px}
#practice-list .pl-act-danger{background:#fff;color:#c53030;border-color:#f3c9c9;padding:0 14px}
#practice-list .pl-act:focus-visible,#practice-list .pl-skipper-btn:focus-visible,#practice-list .pl-past-toggle:focus-visible,#practice-list .pl-loadmore:focus-visible{outline:2px solid #1c2c44;outline-offset:2px}

/* ===== mobile: full-height sheet + row reflow (the 375px gate) ===== */
@media (max-width:767px){
  #practice-list .pl-drawer{width:100%;border-left:none}
  #practice-list .pl-row-aside{flex-direction:row;align-self:flex-start}
  #practice-list .pl-db{width:42px}
}
@media (prefers-reduced-motion:reduce){
  #practice-list .pl-drawer{transition:none}
}
</style></head>
<body style="background:#f8fafb;padding:24px">
<div id="practice-list" style="max-width:780px;margin:0 auto">
  <div class="pl-head"><h1>Practice Management</h1>
    <div style="display:flex;gap:8px"><a class="pl-btn pl-btn-ghost" href="#">Calendar View</a><a class="pl-btn pl-btn-primary" href="#">+ New Practice</a></div></div>
  <div class="pl-toolbar"><input class="pl-search" placeholder="Search location, activity, type, person…"><select class="pl-select"><option>All Status</option></select><select class="pl-select"><option>All Locations</option></select></div>

  <div class="pl-sec today">Today<span class="ln"></span><span class="ct">1</span></div>
  <div class="pl-day">
    <div class="pl-db is-today"><span class="dow">Tue</span><span class="dn">9</span><span class="mo">Jun</span></div>
    <div class="pl-rows">
      <button class="pl-row today is-active">
        <div class="pl-row-main">
          <div class="pl-row-top"><span class="pl-loc">Theodore Wirth</span><span class="pl-time">6:00 PM</span><span class="pl-today-flag">Today</span></div>
          <div class="pl-meta"><span class="pl-pill">Skate</span><span class="pl-pill">Intervals</span><span class="pl-ind"><span aria-hidden="true">🔦</span> Dark</span></div>
        </div>
        <div class="pl-row-aside"><span class="pl-status is-confirmed">Confirmed</span><span class="pl-chip">✓ 2/3</span></div>
      </button>
    </div>
  </div>

  <div class="pl-sec">This week<span class="ln"></span><span class="ct">1</span></div>
  <div class="pl-day">
    <div class="pl-db"><span class="dow">Thu</span><span class="dn">11</span><span class="mo">Jun</span></div>
    <div class="pl-rows">
      <button class="pl-row">
        <div class="pl-row-main">
          <div class="pl-row-top"><span class="pl-loc">Hyland Park</span><span class="pl-time">6:00 PM</span></div>
          <div class="pl-meta"><span class="pl-pill">Classic</span><span class="pl-pill">Distance</span><span class="pl-ind"><span aria-hidden="true">🍺</span> Social</span></div>
        </div>
        <div class="pl-row-aside"><span class="pl-status is-scheduled">Scheduled</span><span class="pl-chip warn">needs leads</span></div>
      </button>
    </div>
  </div>

  <button class="pl-past-toggle" aria-expanded="false"><span class="chev">▸</span> Past practices <span class="dim">— 142</span></button>
</div>
</body></html>
```

- [ ] **Step 2: Open it and eyeball both breakpoints**

Open the file in a browser. At full width confirm the agenda reads cleanly; then narrow the window to ~375px and confirm the row stays legible (date block shrinks, status badge + staffing chip move inline, pills wrap without breaking the date-block alignment). This is the spec's pre-build gate — adjust the `@media (max-width:767px)` rules here until the 375px row looks right.

- [ ] **Step 3: Commit**

```bash
git add docs/superpowers/specs/2026-06-04-practice-list-mockup.html
git commit -m "docs(practices): visual source-of-truth mockup for list redesign"
```

---

## Task 2: Rewrite `list.html` — markup, drawer dialog, and scoped CSS

**Files:**
- Rewrite: `app/templates/admin/practices/list.html`

- [ ] **Step 1: Replace the template**

Overwrite `app/templates/admin/practices/list.html` with the content below. For the `<style>` block, **paste the entire `<style>` contents from `docs/superpowers/specs/2026-06-04-practice-list-mockup.html`** (everything between `<style>` and `</style>`). The markup keeps the existing **cancel modal** verbatim and adds the empty list container + the drawer dialog.

```html
{% extends 'admin/admin_base.html' %}

{% block title %}Practice Management{% endblock %}

{% block extra_css %}
<style>
/* PASTE the <style> body from docs/superpowers/specs/2026-06-04-practice-list-mockup.html here.
   All selectors are already scoped under #practice-list. */
</style>
{% endblock %}

{% block content %}
<div id="practice-list">
  <div class="pl-head">
    <h1>Practice Management</h1>
    <div style="display:flex;gap:8px;flex-wrap:wrap">
      <a href="{{ url_for('admin_practices.practices_calendar') }}" class="pl-btn pl-btn-ghost">Calendar View</a>
      <a href="{{ url_for('admin.get_admin_page') }}" class="pl-btn pl-btn-ghost">Back to Dashboard</a>
      <a href="{{ url_for('admin_practices.practice_new') }}" class="pl-btn pl-btn-primary">+ New Practice</a>
    </div>
  </div>

  <div class="pl-toolbar">
    <input type="text" id="pl-search" class="pl-search" placeholder="Search location, activity, type, person…" aria-label="Search practices">
    <select id="pl-status-filter" class="pl-select" aria-label="Filter by status">
      <option value="">All Status</option>
      <option value="scheduled">Scheduled</option>
      <option value="confirmed">Confirmed</option>
      <option value="in_progress">In Progress</option>
      <option value="cancelled">Cancelled</option>
      <option value="completed">Completed</option>
    </select>
    <select id="pl-location-filter" class="pl-select" aria-label="Filter by location">
      <option value="">All Locations</option>
    </select>
  </div>

  <div id="pl-list" aria-live="off"><p class="pl-empty">Loading practices…</p></div>
</div>

<!-- Preview drawer (dialog) -->
<div id="pl-scrim" class="pl-scrim hidden"></div>
<aside id="pl-drawer" class="pl-drawer hidden" role="dialog" aria-modal="true" aria-labelledby="pl-dw-title" hidden>
  <div class="pl-dwh">
    <div class="pl-dwh-top">
      <div>
        <div class="pl-dw-title" id="pl-dw-title"></div>
        <div class="pl-dw-sub" id="pl-dw-sub"></div>
      </div>
      <button type="button" class="pl-x" id="pl-close" aria-label="Close preview">&times;</button>
    </div>
    <div class="pl-badges" id="pl-badges"></div>
  </div>
  <div class="pl-dwbody" id="pl-dwbody"></div>
  <div class="pl-dwacts">
    <a href="#" class="pl-act pl-act-pri" id="pl-edit">Edit in full editor</a>
    <button type="button" class="pl-act pl-act-ghost" id="pl-cancel-btn">Cancel</button>
    <button type="button" class="pl-act pl-act-danger" id="pl-delete-btn">Delete</button>
  </div>
</aside>

<!-- Cancel Modal (unchanged) -->
<div id="cancel-modal" class="hidden fixed inset-0 bg-black/50 z-[1000] items-center justify-center">
    <div class="absolute inset-0" onclick="closeCancelModal()"></div>
    <div class="relative bg-white rounded-lg p-6 w-[90%] max-w-md max-h-[90vh] overflow-y-auto z-[1001]">
        <div class="flex justify-between items-center mb-5">
            <h2 class="m-0 text-lg font-semibold text-tcsc-navy">Cancel Practice</h2>
            <button class="bg-transparent border-none text-2xl text-gray-500 cursor-pointer p-0 w-8 h-8" onclick="closeCancelModal()">&times;</button>
        </div>
        <div class="mb-5">
            <div class="mb-4">
                <label class="block mb-1.5 font-medium text-sm text-tcsc-navy">Cancellation Reason</label>
                <textarea id="cancel-reason" placeholder="Why is this practice being cancelled?" required class="w-full py-2 px-3 border border-gray-300 rounded-md text-sm min-h-[80px] resize-y focus:outline-none focus:border-tcsc-navy"></textarea>
            </div>
        </div>
        <div class="flex justify-end gap-2">
            <button type="button" class="bg-gray-200 text-gray-600 px-4 py-2 rounded-tcsc text-sm font-medium hover:bg-gray-300 transition-all" onclick="closeCancelModal()">Nevermind</button>
            <button type="button" class="bg-red-500 text-white px-4 py-2 rounded-tcsc text-sm font-medium hover:bg-red-600 transition-all" onclick="confirmCancel()">Cancel Practice</button>
        </div>
    </div>
</div>
{% endblock %}

{% block extra_js %}
<script src="{{ url_for('static', filename='admin_practices.js') }}"></script>
{% endblock %}
```

- [ ] **Step 2: Verify the page renders**

Run: `pytest tests/routes/test_admin_practices_routes.py -v`
Expected: existing tests still PASS (the list route renders; the page now contains `id="practice-list"`). If no list-route test exists yet, that is added in Task 4 — for now confirm no template syntax error by loading the page manually in Step 3.

- [ ] **Step 3: Manual smoke (static shell)**

Run `./scripts/dev.sh 5001`, open `http://localhost:5001/admin/practices`. The toolbar + "Loading practices…" placeholder render with the new styling and no console errors (the JS is rewritten in Task 3, so the list stays on the placeholder for now — that is expected).

- [ ] **Step 4: Commit**

```bash
git add app/templates/admin/practices/list.html
git commit -m "feat(practices): rebuild list page shell + preview drawer markup"
```

---

## Task 3: Rewrite `admin_practices.js` — render the agenda list + drive the drawer

Replace the whole file. It loads the payload, buckets by Central date, renders the single-scroll agenda (day-grouped date-block rows as buttons), wires search/filters and the render-gated Past section, and drives the preview drawer (instant render from cache, RSVP auto-load, gated Skipper button, focus management, Edit/Cancel/Delete). The cancel-modal and delete flows are kept.

**Files:**
- Rewrite: `app/static/admin_practices.js`

- [ ] **Step 1: Write the file**

Overwrite `app/static/admin_practices.js` with:

```javascript
/* Practice list page: agenda render + preview drawer.
   Renders from GET /admin/practices/data; drawer lazy-loads RSVP + (gated) Skipper. */

let practicesData = [];
let locationsData = [];
let pastExpanded = false;
let pastLimit = 20;
let lastFocusedEl = null;
let currentDrawerId = null;

const STATUS_LABEL = {
  scheduled: 'Scheduled', confirmed: 'Confirmed', in_progress: 'In Progress',
  cancelled: 'Cancelled', completed: 'Completed'
};

document.addEventListener('DOMContentLoaded', async () => {
  await Promise.all([loadPractices(), loadLocations()]);
  populateLocationFilter();
  attachEventListeners();
  render();
});

async function loadPractices() {
  try {
    const r = await fetch('/admin/practices/data');
    if (!r.ok) throw new Error('HTTP ' + r.status);
    practicesData = (await r.json()).practices || [];
  } catch (e) { console.error(e); showToast('Failed to load practices', 'error'); }
}

async function loadLocations() {
  try {
    const r = await fetch('/admin/practices/locations/data');
    if (!r.ok) throw new Error('HTTP ' + r.status);
    locationsData = (await r.json()).locations || [];
  } catch (e) { console.error(e); }
}

function populateLocationFilter() {
  const sel = document.getElementById('pl-location-filter');
  for (const loc of locationsData) {
    const o = document.createElement('option');
    o.value = loc.id;
    o.textContent = loc.spot ? `${loc.name} — ${loc.spot}` : loc.name;
    sel.appendChild(o);
  }
}

/* ---------- date helpers (Central, date-string based) ---------- */
function ymd(iso) { return (iso || '').slice(0, 10); }
function chicagoTodayYMD() {
  return new Intl.DateTimeFormat('en-CA', { timeZone: 'America/Chicago',
    year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date());
}
function addDaysYMD(s, n) {
  const d = new Date(s + 'T12:00:00Z'); d.setUTCDate(d.getUTCDate() + n);
  return d.toISOString().slice(0, 10);
}

/* ---------- escaping ---------- */
function esc(s) {
  return String(s == null ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

/* ---------- filtering ---------- */
function personNames(p) {
  return [].concat(p.coaches || [], p.leads || [], p.assists || [])
    .map(x => (x.name || '').toLowerCase());
}
function matchesFilters(p) {
  const q = document.getElementById('pl-search').value.toLowerCase().trim();
  const status = document.getElementById('pl-status-filter').value;
  const loc = document.getElementById('pl-location-filter').value;
  if (status && p.status !== status) return false;
  if (loc && String(p.location_id) !== String(loc)) return false;
  if (!q) return true;
  const hay = [p.location_name || '', ...(p.activities || []), ...(p.practice_types || []),
    ...personNames(p)].join(' ').toLowerCase();
  return hay.includes(q);
}

/* ---------- rendering ---------- */
function render() {
  const root = document.getElementById('pl-list');
  const today = chicagoTodayYMD();
  const weekEnd = addDaysYMD(today, 7);
  const rows = practicesData.filter(matchesFilters);

  const todayL = [], weekL = [], laterL = [], pastL = [];
  for (const p of rows) {
    const d = ymd(p.date);
    if (d < today) pastL.push(p);
    else if (d === today) todayL.push(p);
    else if (d <= weekEnd) weekL.push(p);
    else laterL.push(p);
  }
  const byDateAsc = (a, b) => new Date(a.date) - new Date(b.date);
  todayL.sort(byDateAsc); weekL.sort(byDateAsc); laterL.sort(byDateAsc);
  pastL.sort((a, b) => new Date(b.date) - new Date(a.date));

  let html = '';
  html += section('Today', todayL, true);
  html += section('This week', weekL, false);
  html += section('Later', laterL, false);

  if (pastL.length) {
    html += `<button type="button" class="pl-past-toggle" id="pl-past-toggle" aria-expanded="${pastExpanded}">`
      + `<span class="chev" aria-hidden="true">▸</span> Past practices <span class="dim">— ${pastL.length}</span></button>`;
    if (pastExpanded) {
      const shown = pastL.slice(0, pastLimit);
      html += dayGroups(shown, false);
      if (pastL.length > pastLimit) html += `<button type="button" class="pl-loadmore" id="pl-loadmore">Load more</button>`;
    }
  }

  if (!rows.length) html = '<p class="pl-empty">No practices match your filters.</p>';
  root.innerHTML = html;
}

function section(title, list, isToday) {
  if (!list.length) return '';
  return `<div class="pl-sec${isToday ? ' today' : ''}">${esc(title)}<span class="ln"></span>`
    + `<span class="ct">${list.length}</span></div>` + dayGroups(list, isToday);
}

function dayGroups(list, isToday) {
  // group consecutive items by their date (list already sorted)
  const groups = [];
  for (const p of list) {
    const key = ymd(p.date);
    const g = groups.length && groups[groups.length - 1].key === key ? groups[groups.length - 1] : null;
    if (g) g.items.push(p); else groups.push({ key, items: [p] });
  }
  return groups.map(g => {
    const d = new Date(g.items[0].date);
    const dow = d.toLocaleDateString([], { weekday: 'short' });
    const dn = d.toLocaleDateString([], { day: 'numeric' });
    const mo = d.toLocaleDateString([], { month: 'short' });
    const block = `<div class="pl-db${isToday ? ' is-today' : ''}"><span class="dow">${dow}</span>`
      + `<span class="dn">${dn}</span><span class="mo">${mo}</span></div>`;
    return `<div class="pl-day">${block}<div class="pl-rows">${g.items.map(p => rowHtml(p, isToday)).join('')}</div></div>`;
  }).join('');
}

function staffingChip(p) {
  const leads = p.leads || [], coaches = p.coaches || [];
  if (leads.length === 0) return '<span class="pl-chip warn">needs leads</span>';
  const total = leads.length + coaches.length;
  const confirmed = leads.filter(x => x.confirmed).length + coaches.filter(x => x.confirmed).length;
  return `<span class="pl-chip">✓ ${confirmed}/${total}</span>`;
}

function rowHtml(p, isToday) {
  const time = new Date(p.date).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
  const pills = [...(p.activities || []), ...(p.practice_types || [])]
    .map(n => `<span class="pl-pill">${esc(n)}</span>`).join('');
  let inds = '';
  if (p.has_social) inds += '<span class="pl-ind"><span aria-hidden="true">🍺</span> Social</span>';
  if (p.is_dark_practice) inds += '<span class="pl-ind"><span aria-hidden="true">🔦</span> Dark</span>';
  const st = p.status || 'scheduled';
  const status = `<span class="pl-status is-${esc(st)}">${esc(STATUS_LABEL[st] || st)}</span>`;
  const flag = isToday ? '<span class="pl-today-flag">Today</span>' : '';
  return `<button type="button" class="pl-row${isToday ? ' today' : ''}" data-id="${p.id}" `
    + `aria-label="${esc(p.location_name || 'Practice')} ${esc(time)}, ${esc(STATUS_LABEL[st] || st)}">`
    + `<div class="pl-row-main"><div class="pl-row-top"><span class="pl-loc">${esc(p.location_name || 'No Location')}</span>`
    + `<span class="pl-time">${esc(time)}</span>${flag}</div>`
    + `<div class="pl-meta">${pills}${inds}</div></div>`
    + `<div class="pl-row-aside">${status}${staffingChip(p)}</div></button>`;
}

/* ---------- events ---------- */
function attachEventListeners() {
  document.getElementById('pl-search').addEventListener('input', render);
  document.getElementById('pl-status-filter').addEventListener('change', render);
  document.getElementById('pl-location-filter').addEventListener('change', render);

  document.getElementById('pl-list').addEventListener('click', (e) => {
    const row = e.target.closest('.pl-row');
    if (row) { openDrawer(parseInt(row.dataset.id), row); return; }
    if (e.target.closest('#pl-past-toggle')) { pastExpanded = !pastExpanded; pastLimit = 20; render(); return; }
    if (e.target.closest('#pl-loadmore')) { pastLimit += 20; render(); return; }
  });

  document.getElementById('pl-close').addEventListener('click', closeDrawer);
  document.getElementById('pl-scrim').addEventListener('click', closeDrawer);
  document.getElementById('pl-cancel-btn').addEventListener('click', () => { if (currentDrawerId) openCancelModal(currentDrawerId); });
  document.getElementById('pl-delete-btn').addEventListener('click', () => { if (currentDrawerId) deletePractice(currentDrawerId); });

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      if (!document.getElementById('pl-drawer').classList.contains('hidden')) { closeDrawer(); return; }
      closeCancelModal();
    }
    if (e.key === 'Tab' && !document.getElementById('pl-drawer').classList.contains('hidden')) trapTab(e);
  });
}

/* ---------- drawer ---------- */
function findPractice(id) { return practicesData.find(p => p.id === id); }

function openDrawer(id, triggerEl) {
  const p = findPractice(id);
  if (!p) return;
  currentDrawerId = id;
  lastFocusedEl = triggerEl || document.activeElement;

  document.querySelectorAll('.pl-row.is-active').forEach(r => r.classList.remove('is-active'));
  if (triggerEl) triggerEl.classList.add('is-active');

  populateDrawer(p);

  const scrim = document.getElementById('pl-scrim'), drawer = document.getElementById('pl-drawer');
  scrim.classList.remove('hidden');
  drawer.classList.remove('hidden');
  drawer.removeAttribute('hidden');
  document.getElementById('pl-close').focus();

  loadDrawerRSVPs(id);
}

function closeDrawer() {
  const scrim = document.getElementById('pl-scrim'), drawer = document.getElementById('pl-drawer');
  scrim.classList.add('hidden');
  drawer.classList.add('hidden');
  drawer.setAttribute('hidden', '');
  document.querySelectorAll('.pl-row.is-active').forEach(r => r.classList.remove('is-active'));
  if (lastFocusedEl && document.contains(lastFocusedEl)) lastFocusedEl.focus();
  currentDrawerId = null;
}

function populateDrawer(p) {
  const d = new Date(p.date);
  document.getElementById('pl-dw-title').textContent = p.location_name || 'No Location';
  document.getElementById('pl-dw-sub').textContent =
    d.toLocaleString([], { weekday: 'long', month: 'long', day: 'numeric', hour: 'numeric', minute: '2-digit' });

  const st = p.status || 'scheduled';
  let badges = `<span class="pl-status is-${esc(st)}">${esc(STATUS_LABEL[st] || st)}</span>`;
  if (p.is_dark_practice) badges += '<span class="pl-pill"><span aria-hidden="true">🔦</span>&nbsp;Dark</span>';
  badges += '<span id="pl-skipper-slot"></span>';
  document.getElementById('pl-badges').innerHTML = badges;

  document.getElementById('pl-dwbody').innerHTML = drawerBody(p);

  const edit = document.getElementById('pl-edit');
  edit.setAttribute('href', '/admin/practices/' + p.id);

  // Skipper gated to today/tomorrow
  const today = chicagoTodayYMD();
  const isSoon = ymd(p.date) === today || ymd(p.date) === addDaysYMD(today, 1);
  const slot = document.getElementById('pl-skipper-slot');
  if (isSoon) {
    slot.innerHTML = `<button type="button" class="pl-skipper-btn" id="pl-skipper-btn">Load Skipper check</button>`;
    document.getElementById('pl-skipper-btn').addEventListener('click', () => loadDrawerEvaluation(p.id));
  } else {
    slot.innerHTML = '';
  }
}

function drawerBody(p) {
  const social = p.social_location_name ? esc(p.social_location_name) : 'None';
  const wo = (label, text, main) => {
    const t = (text && text.trim()) ? esc(text) : '—';
    return `<div class="pl-wblk${main ? ' main' : ''}"><div class="wl">${label}</div><div class="wt">${t}</div></div>`;
  };
  const pills = [...(p.activities || []), ...(p.practice_types || [])]
    .map(n => `<span class="pl-pill">${esc(n)}</span>`).join('') || '<span class="pl-muted">None</span>';
  const people = [].concat(
    (p.coaches || []).map(x => ['Coach', x]),
    (p.leads || []).map(x => ['Lead', x]),
    (p.assists || []).map(x => ['Assist', x])
  );
  const peopleHtml = people.length ? people.map(([role, x]) =>
    `<div class="pl-person"><span class="role">${role}</span><span class="pn">${esc(x.name || 'Unknown')}</span>`
    + `<span class="pl-conf ${x.confirmed ? 'yes' : 'no'}">${x.confirmed ? 'Confirmed' : 'Pending'}</span></div>`
  ).join('') : '<span class="pl-muted">No one assigned</span>';

  return `
    <div class="pl-blk"><div class="pl-blk-h">When &amp; Where</div>
      <div class="pl-kv"><span class="k">Location</span><span class="v">${esc(p.location_name || 'No Location')}</span></div>
      <div class="pl-kv"><span class="k">Social</span><span class="v">${social}</span></div>
    </div>
    <div class="pl-blk"><div class="pl-blk-h">Activity &amp; Type</div><div class="pl-pills">${pills}</div></div>
    <div class="pl-blk"><div class="pl-blk-h">Workout Plan</div>
      ${wo('Warmup', p.warmup_description, false)}
      ${wo('Main', p.workout_description, true)}
      ${wo('Cooldown', p.cooldown_description, false)}
    </div>
    <div class="pl-blk"><div class="pl-blk-h">Coaches · Leads · Assists</div>${peopleHtml}</div>
    <div class="pl-blk"><div class="pl-blk-h">RSVPs</div>
      <div id="pl-rsvp" aria-live="polite"><span class="pl-muted">Loading…</span></div>
    </div>`;
}

async function loadDrawerRSVPs(id) {
  try {
    const { summary } = await fetch(`/admin/practices/${id}/rsvps`).then(r => r.json());
    const el = document.getElementById('pl-rsvp');
    if (!el || currentDrawerId !== id) return;
    el.innerHTML = `<div class="pl-rsvp">`
      + `<div class="pl-rcell"><span class="n">${summary.going}</span><span class="l">Going</span></div>`
      + `<div class="pl-rcell"><span class="n">${summary.maybe}</span><span class="l">Maybe</span></div>`
      + `<div class="pl-rcell"><span class="n">${summary.not_going}</span><span class="l">Out</span></div></div>`;
  } catch (e) {
    const el = document.getElementById('pl-rsvp');
    if (el) el.innerHTML = '<span class="pl-muted">Could not load RSVPs</span>';
  }
}

async function loadDrawerEvaluation(id) {
  const btn = document.getElementById('pl-skipper-btn');
  if (btn) btn.textContent = 'Checking…';
  try {
    const data = await fetch(`/admin/practices/${id}/evaluation`).then(r => r.json());
    const slot = document.getElementById('pl-skipper-slot');
    if (!slot || currentDrawerId !== id) return;
    if (!data.success) { slot.innerHTML = `<span class="pl-muted">${esc(data.error || 'No evaluation')}</span>`; return; }
    const ev = data.evaluation;
    slot.innerHTML = `<span class="pl-go ${ev.is_go ? '' : 'nogo'}">${ev.is_go ? 'GO' : 'NO-GO'} `
      + `· ${Math.round((ev.confidence || 0) * 100)}%</span>`;
  } catch (e) {
    const slot = document.getElementById('pl-skipper-slot');
    if (slot) slot.innerHTML = '<span class="pl-muted">Check failed</span>';
  }
}

function trapTab(e) {
  const drawer = document.getElementById('pl-drawer');
  const f = drawer.querySelectorAll('a[href], button:not([disabled]), input, select, textarea, [tabindex]:not([tabindex="-1"])');
  if (!f.length) return;
  const first = f[0], last = f[f.length - 1];
  if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
  else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
}

/* ---------- cancel modal + delete (kept) ---------- */
let currentCancelPracticeId = null;

function openCancelModal(id) {
  currentCancelPracticeId = id;
  document.getElementById('cancel-reason').value = '';
  document.getElementById('cancel-modal').style.display = 'flex';
}
function closeCancelModal() {
  document.getElementById('cancel-modal').style.display = 'none';
  currentCancelPracticeId = null;
}
async function confirmCancel() {
  const reason = document.getElementById('cancel-reason').value.trim();
  if (!reason) { showToast('Please provide a cancellation reason', 'error'); return; }
  try {
    const result = await fetch(`/admin/practices/${currentCancelPracticeId}/cancel`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ reason })
    }).then(r => r.json());
    if (result.success) {
      showToast(result.message, 'success');
      closeCancelModal(); closeDrawer();
      await loadPractices(); render();
    } else { showToast(result.error || 'Failed to cancel practice', 'error'); }
  } catch (e) { showToast('Failed to cancel practice', 'error'); }
}
async function deletePractice(id) {
  if (!confirm('Are you sure you want to delete this practice? This cannot be undone.')) return;
  try {
    const result = await fetch(`/admin/practices/${id}/delete`, { method: 'POST' }).then(r => r.json());
    if (result.success) {
      showToast(result.message, 'success');
      closeDrawer();
      await loadPractices(); render();
    } else { showToast(result.error || 'Failed to delete practice', 'error'); }
  } catch (e) { showToast('Failed to delete practice', 'error'); }
}
```

- [ ] **Step 2: Syntax check**

Run: `node --check app/static/admin_practices.js`
Expected: exit 0, no output.

- [ ] **Step 3: Manual smoke (list render)**

With `./scripts/dev.sh 5001` running, open `http://localhost:5001/admin/practices`. Verify: Today / This week / Later sections render with counts and date blocks; rows show location, time, pills, social/dark indicators, the status badge (check a `completed` and a `cancelled` practice render correctly), and the staffing chip (`✓ N/M` or amber "needs leads"); search (try a coach's name), status filter, and location filter all narrow the list; the "Past practices (N)" bar expands and "Load more" pages through.

- [ ] **Step 4: Manual smoke (drawer)**

Click a row: the drawer slides in, populates instantly (When&Where, pills, Workout Plan, people with Confirmed/Pending, RSVP "Loading…" then counts). For a **today/tomorrow** practice the "Load Skipper check" button appears and produces a GO/NO-GO badge on press; for a practice further out, no Skipper button shows. **Edit in full editor** navigates to `/admin/practices/<id>`; **Cancel** opens the cancel modal; **Delete** confirms and removes. Scrim-click, the ✕, and Esc all close and return focus to the row.

- [ ] **Step 5: Commit**

```bash
git add app/static/admin_practices.js
git commit -m "feat(practices): agenda list render + preview drawer"
```

---

## Task 4: Render guard test, accessibility & responsive verification, final pass

**Files:**
- Modify: `tests/routes/test_admin_practices_routes.py`

- [ ] **Step 1: Add a render guard for the list page**

Append to `tests/routes/test_admin_practices_routes.py`:

```python
def test_practices_list_renders_new_shell(admin_client, db_session):
    resp = admin_client.get('/admin/practices')
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    # New shell present; old Tabulator grid container gone.
    assert 'id="practice-list"' in body
    assert 'id="pl-drawer"' in body
    assert 'practices-table' not in body
```

- [ ] **Step 2: Run it**

Run: `pytest tests/routes/test_admin_practices_routes.py -v`
Expected: all tests PASS (including the new guard).

- [ ] **Step 3: Keyboard & accessibility pass**

With the app running on `/admin/practices`:
- Tab to a row (it is a `<button>` with a visible navy focus ring), press Enter → drawer opens, focus moves to ✕.
- Inside the open drawer, Tab cycles within the drawer (focus does not escape to the list); Esc closes and focus returns to the originating row.
- Confirm status badges and the GO/NO-GO badge each show a **text label** beside the color, and the day-of-week label uses the darker `#64748b` (legible), not the faint grey.

- [ ] **Step 4: Responsive pass (375px) against the mockup**

Set the viewport to ~375px (DevTools device toolbar): the list is single-column, rows stay legible (date block narrows; status badge + staffing chip sit inline per the mockup's `@media` rules), and the drawer opens as a **full-height sheet** (full width). Enable "reduce motion" in the OS/DevTools and confirm the drawer no longer animates.

- [ ] **Step 5: Full regression**

Run: `pytest -q`
Expected: the existing suite (124 tests) plus the new list-render guard pass; no regressions.

- [ ] **Step 6: Final commit**

```bash
git add tests/routes/test_admin_practices_routes.py
git commit -m "test(practices): render guard for redesigned list page"
```

---

## Self-Review notes (author)

- **Spec coverage:** custom list + slide-over drawer everywhere (Tasks 2–3) ✓; single-scroll Today/This week/Later + render-gated Past (Task 3 `render`/`pastExpanded`/`pastLimit`) ✓; date-based Chicago grouping with rolling 7-day window (Task 3 `chicagoTodayYMD`/`addDaysYMD`/bucketing) ✓; date-block day-grouped rows with location headline, time, pills, social/dark (icon+text), staffing chip, status badge (Task 3 `rowHtml`/`staffingChip`) ✓; assists in drawer only ✓; row as a `<button>` ✓; preview drawer = read-only + pinned Edit/Cancel/Delete (Tasks 2–3) ✓; instant render from payload + RSVP auto-load + Skipper gated to today/tomorrow behind a button (Task 3 `populateDrawer`/`loadDrawerRSVPs`/`loadDrawerEvaluation`) ✓; unified editor tokens + all five status states + GO `#acf3c4` / NO-GO `#fde8e8` (Task 1 CSS) ✓; functional text uses `#64748b` not `#94a3b8` (Task 1 `.pl-db .dow`, Task 4 Step 3) ✓; modal-dialog semantics, focus trap, Esc, focus restore, `aria-live`, reduced-motion (Tasks 2–3 markup + `trapTab`/`closeDrawer`, Task 1 media query) ✓; people-aware search (Task 3 `personNames`/`matchesFilters`) ✓; no backend changes ✓; cancel modal + delete kept (Task 3) ✓.
- **Out of scope confirmed absent:** no inline drawer editing, no bulk actions, no editor/calendar/endpoint/model changes, no Past reporting console, no J/K nav, no windowed endpoint.
- **Type/name consistency:** element ids match across template and JS — `pl-list`, `pl-search`, `pl-status-filter`, `pl-location-filter`, `pl-scrim`, `pl-drawer`, `pl-close`, `pl-badges`, `pl-dwbody`, `pl-dw-title`, `pl-dw-sub`, `pl-edit`, `pl-cancel-btn`, `pl-delete-btn`, `pl-skipper-slot`, `pl-skipper-btn`, `pl-rsvp`, `pl-past-toggle`, `pl-loadmore`; CSS class names (`pl-row`, `pl-db`, `pl-status.is-*`, `pl-chip[.warn]`, `pl-go[.nogo]`, `pl-person`, `pl-conf.yes/.no`, `pl-rsvp`/`pl-rcell`) are defined in Task 1 and used in Task 3; status keys (`scheduled`/`confirmed`/`in_progress`/`cancelled`/`completed`) match between `STATUS_LABEL`, the CSS `is-*` classes, and the filter `<option>` values.
- **Testing reality:** only a backend render guard is unit-tested (matches the repo — admin JS has no harness); the list render, drawer behavior, accessibility, and responsive reflow rely on explicit manual smoke steps, called out rather than faked.
```
