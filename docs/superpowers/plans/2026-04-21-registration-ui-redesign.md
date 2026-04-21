# Registration UI Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the dated Stripe-sample-based registration UI with a clean, modern design system across all public-facing pages — homepage, trip/social/season registration forms, triathlon page, and success/detail pages.

**Architecture:** Clean-slate CSS rewrite with new semantic tokens and BEM-lite class naming. HTML templates rewritten to use new classes while preserving the JS contract (specific element IDs, data attributes, and ~5 CSS classes that `script.js` and `social_event.js` depend on). New progress bar JS for the season registration form using IntersectionObserver. Mobile-first responsive design with breakpoints at 640px and 480px.

**Tech Stack:** HTML/Jinja2 templates, vanilla CSS (no preprocessor), vanilla JS for progress bar, Stripe Elements (unchanged)

**Spec:** `docs/superpowers/specs/2026-04-21-registration-ui-redesign-design.md`

---

### Task 1: CSS Foundation — Tokens, Reset, Layout

**Files:**
- Rewrite: `app/static/css/styles/base/_tokens.css`
- Rewrite: `app/static/css/styles/base/_reset.css`
- Create: `app/static/css/styles/components/_layout.css` (replaces `layout/_layout.css`)

- [ ] **Step 1: Write new `_tokens.css`**

```css
:root {
  --color-primary: #1c2c44;
  --color-mint: #acf3c4;

  --bg-page: #f8fafb;
  --bg-card: #ffffff;

  --border: #e5e7eb;
  --border-input: 1.5px solid #e5e7eb;

  --text-primary: #1c2c44;
  --text-secondary: #475569;
  --text-muted: #64748b;
  --text-faint: #94a3b8;

  --radius-card: 12px;
  --radius-input: 10px;
  --radius-badge: 12px;
  --radius-pill: 20px;

  --font-stack: -apple-system, BlinkMacSystemFont, sans-serif;

  --status-open-bg: #dcfce7;
  --status-open-text: #166534;
  --status-upcoming-bg: #dbeafe;
  --status-upcoming-text: #1e40af;
  --status-closed-bg: #f1f5f9;
  --status-closed-text: #64748b;

  --pill-membership-bg: #1c2c44;
  --pill-membership-text: #ffffff;
  --pill-trips-bg: #dbeafe;
  --pill-trips-text: #1e40af;
  --pill-social-bg: #d1fae5;
  --pill-social-text: #065f46;

  --notice-warn-bg: #fefce8;
  --notice-warn-border: #fde68a;
  --notice-warn-text: #854d0e;
  --notice-error-bg: #fde8e8;
  --notice-error-border: #e53e3e;
  --notice-error-text: #c53030;
}
```

- [ ] **Step 2: Write new `_reset.css`**

```css
* { box-sizing: border-box }

body {
  font: 16px var(--font-stack);
  color: var(--text-primary);
  -webkit-font-smoothing: antialiased;
  background: var(--bg-page);
  margin: 0;
}

h1, h2, h3, h4, h5, h6 {
  color: var(--text-primary);
  margin: 0;
}

a { color: inherit; }

img { max-width: 100%; height: auto; }
```

- [ ] **Step 3: Write new `_layout.css`**

This replaces `layout/_layout.css` (old `sr-root`/`sr-main`) and `components/_header.css` (old `sr-header`). Provides the shared page shell used by every template.

```css
.page {
  min-height: 100vh;
}

.page-header {
  background: var(--bg-card);
  border-bottom: 1px solid var(--border);
  padding: 16px 32px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.page-header__logo {
  height: 48px;
}

.page-content {
  max-width: 720px;
  margin: 0 auto;
  padding: 40px 32px;
}

.page-content--narrow {
  max-width: 420px;
}

.page-content--medium {
  max-width: 560px;
}

.section-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 16px;
}

@media (min-width: 640px) {
  .section-grid {
    grid-template-columns: 1fr 1fr;
  }
}

@media (max-width: 640px) {
  .page-content {
    padding: 24px 20px;
  }

  .page-header {
    padding: 16px 20px;
  }
}

.homepage-section {
  margin-bottom: 36px;
}

.homepage-section:last-child {
  margin-bottom: 0;
}
```

- [ ] **Step 4: Commit**

```bash
git add app/static/css/styles/base/_tokens.css app/static/css/styles/base/_reset.css app/static/css/styles/components/_layout.css
git commit -m "feat(css): new design tokens, reset, and page layout"
```

---

### Task 2: CSS Components — Cards, Badges, Buttons

**Files:**
- Create: `app/static/css/styles/components/_cards.css`
- Create: `app/static/css/styles/components/_badges.css`
- Create: `app/static/css/styles/components/_buttons.css`

- [ ] **Step 1: Write `_cards.css`**

Homepage cards shared by season, trip, and social event cards.

```css
.card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-card);
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  transition: transform 0.2s, box-shadow 0.2s;
}

.card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(28, 44, 68, 0.08);
}

.card__header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}

.card__title {
  font: 600 17px var(--font-stack);
  color: var(--text-primary);
}

.card__meta {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.card__meta-item {
  font: 13px var(--font-stack);
  color: var(--text-muted);
}

.card__description {
  font: 14px/1.5 var(--font-stack);
  color: var(--text-muted);
  margin: 0;
}

.card__footer {
  margin-top: auto;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.card__price {
  font: 700 17px var(--font-stack);
  color: var(--text-primary);
}

.card__subtext {
  font: 13px/1.4 var(--font-stack);
  color: var(--text-faint);
}
```

- [ ] **Step 2: Write `_badges.css`**

Status badges (Open/Upcoming/Closed) and section pills (Membership/Trips/Social Events).

```css
.badge {
  display: inline-block;
  font: 600 11px var(--font-stack);
  padding: 3px 10px;
  border-radius: var(--radius-badge);
}

.badge--open {
  background: var(--status-open-bg);
  color: var(--status-open-text);
}

.badge--upcoming {
  background: var(--status-upcoming-bg);
  color: var(--status-upcoming-text);
}

.badge--closed {
  background: var(--status-closed-bg);
  color: var(--status-closed-text);
}

.section-pill {
  display: inline-block;
  font: 600 12px var(--font-stack);
  padding: 5px 14px;
  border-radius: var(--radius-pill);
  letter-spacing: 0.3px;
}

.section-pill--membership {
  background: var(--pill-membership-bg);
  color: var(--pill-membership-text);
}

.section-pill--trips {
  background: var(--pill-trips-bg);
  color: var(--pill-trips-text);
}

.section-pill--social {
  background: var(--pill-social-bg);
  color: var(--pill-social-text);
}

.badge--social {
  background: var(--pill-social-bg);
  color: var(--pill-social-text);
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.3px;
}
```

- [ ] **Step 3: Write `_buttons.css`**

```css
.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: var(--color-primary);
  color: #fff;
  border: none;
  border-radius: var(--radius-input);
  padding: 14px 20px;
  font: 600 15px var(--font-stack);
  cursor: pointer;
  transition: opacity 0.2s, transform 0.2s;
  text-decoration: none;
  gap: 8px;
}

.btn:hover {
  opacity: 0.9;
  transform: translateY(-1px);
}

.btn:active {
  transform: translateY(1px);
  opacity: 0.8;
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  transform: none;
}

.btn--full {
  width: 100%;
}

.btn--small {
  padding: 10px 20px;
  font-size: 13px;
  font-weight: 600;
  border-radius: 8px;
}

.btn--secondary {
  background: transparent;
  color: var(--text-muted);
  border: 1px solid var(--border);
}

.btn--secondary:hover {
  background: var(--bg-page);
  opacity: 1;
}
```

- [ ] **Step 4: Commit**

```bash
git add app/static/css/styles/components/_cards.css app/static/css/styles/components/_badges.css app/static/css/styles/components/_buttons.css
git commit -m "feat(css): cards, badges, and button components"
```

---

### Task 3: CSS Components — Forms, Notices, States

**Files:**
- Create: `app/static/css/styles/components/_forms.css`
- Create: `app/static/css/styles/components/_notices.css`
- Rewrite: `app/static/css/styles/states/_states.css`

- [ ] **Step 1: Write `_forms.css`**

All form inputs, labels, pill selectors, side-by-side field layout, price selectors.

```css
.form-section {
  margin-bottom: 48px;
}

.form-section__title {
  font: 600 20px var(--font-stack);
  color: var(--text-primary);
  margin-bottom: 4px;
}

.form-section__subtitle {
  font: 14px var(--font-stack);
  color: var(--text-faint);
  margin-bottom: 24px;
}

.form-divider {
  height: 1px;
  background: var(--border);
  margin-bottom: 48px;
  border: none;
}

.form-field {
  margin-bottom: 20px;
}

.form-field__label {
  display: block;
  font: 500 13px var(--font-stack);
  color: var(--text-secondary);
  margin-bottom: 6px;
}

.form-field__hint {
  color: var(--text-faint);
  font-weight: 400;
}

.form-input {
  display: block;
  width: 100%;
  background: var(--bg-card);
  border: 1.5px solid var(--border);
  border-radius: var(--radius-input);
  padding: 12px 14px;
  font: 15px var(--font-stack);
  color: var(--text-primary);
  transition: border-color 0.2s, box-shadow 0.2s;
  appearance: none;
  height: 44px;
}

.form-input::placeholder {
  color: var(--text-faint);
}

.form-input:focus {
  outline: none;
  border-color: var(--color-primary);
  box-shadow: 0 0 0 3px rgba(28, 44, 68, 0.1);
}

select.form-input {
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 12 12'%3E%3Cpath fill='%2394a3b8' d='M6 8L1 3h10z'/%3E%3C/svg%3E");
  background-repeat: no-repeat;
  background-position: right 14px center;
  padding-right: 36px;
}

.form-row {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-bottom: 20px;
}

@media (min-width: 640px) {
  .form-row--pair {
    flex-direction: row;
  }

  .form-row--pair > .form-field {
    flex: 1;
    margin-bottom: 0;
  }
}

/* Pill selectors — clickable buttons wrapping hidden radio inputs */
.pill-group {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.pill-group__label {
  display: block;
  font: 500 13px var(--font-stack);
  color: var(--text-secondary);
  margin-bottom: 8px;
}

.pill {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  background: #f1f5f9;
  color: var(--text-muted);
  padding: 10px 20px;
  border-radius: var(--radius-input);
  font: 500 14px var(--font-stack);
  border: 1.5px solid var(--border);
  cursor: pointer;
  transition: background 0.15s, color 0.15s, border-color 0.15s;
}

.pill:hover {
  background: #e8ecf1;
}

.pill input[type="radio"] {
  position: absolute;
  opacity: 0;
  width: 0;
  height: 0;
  pointer-events: none;
}

.pill--selected,
.pill:has(input[type="radio"]:checked) {
  background: var(--color-primary);
  color: #fff;
  border-color: var(--color-primary);
}

.pill--selected:hover,
.pill:has(input[type="radio"]:checked):hover {
  background: var(--color-primary);
}

.pill__hint {
  font-size: 12px;
  opacity: 0.6;
}

/* Price selector cards */
.price-selector {
  display: flex;
  gap: 10px;
  margin-bottom: 24px;
}

.price-option-container {
  flex: 1;
  background: var(--bg-card);
  border: 1.5px solid var(--border);
  border-radius: var(--radius-input);
  padding: 14px;
  text-align: center;
  cursor: pointer;
  transition: background 0.15s, border-color 0.15s;
}

.price-option-container:hover {
  border-color: var(--text-faint);
}

.price-option-container--selected {
  background: var(--color-primary);
  border-color: var(--color-primary);
}

.price-option-container input[type="radio"] {
  position: absolute;
  opacity: 0;
  width: 0;
  height: 0;
  pointer-events: none;
}

.price-option__label {
  font: 12px var(--font-stack);
  color: var(--text-faint);
  margin-bottom: 2px;
}

.price-option-container--selected .price-option__label {
  color: rgba(255, 255, 255, 0.6);
}

.price-option__amount {
  font: 700 18px var(--font-stack);
  color: var(--text-primary);
}

.price-option-container--selected .price-option__amount {
  color: #fff;
}

/* Single price summary bar */
.price-summary {
  background: var(--bg-page);
  border: 1px solid var(--border);
  border-radius: var(--radius-input);
  padding: 14px 16px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.price-summary__label {
  font: 14px var(--font-stack);
  color: var(--text-muted);
}

.price-summary__amount {
  font: 700 18px var(--font-stack);
  color: var(--text-primary);
}

/* Stripe card element wrapper */
.card-element-wrapper {
  background: var(--bg-card);
  border: 1.5px solid var(--border);
  border-radius: var(--radius-input);
  padding: 12px 14px;
  transition: border-color 0.2s, box-shadow 0.2s;
}

.card-element-wrapper:focus-within {
  border-color: var(--color-primary);
  box-shadow: 0 0 0 3px rgba(28, 44, 68, 0.1);
}

/* Checkbox group (agreement section) */
.checkbox-group {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 16px;
  background: #fafafa;
  border-radius: var(--radius-input);
  border: 1px solid var(--border);
}

.checkbox-group input[type="checkbox"] {
  width: 18px;
  height: 18px;
  flex-shrink: 0;
  margin-top: 2px;
  cursor: pointer;
}

.checkbox-group label {
  font: 13px/1.5 var(--font-stack);
  color: var(--text-muted);
  cursor: pointer;
}

.checkbox-group a {
  color: var(--text-primary);
  text-decoration: underline;
}

/* Centered form header (trip/social pages) */
.form-header {
  text-align: center;
  margin-bottom: 28px;
}

.form-header__title {
  font: 600 22px var(--font-stack);
  color: var(--text-primary);
  margin-bottom: 6px;
}

.form-header__meta {
  display: flex;
  justify-content: center;
  gap: 16px;
  font: 13px var(--font-stack);
  color: var(--text-muted);
  flex-wrap: wrap;
}

/* Membership status feedback */
.membership-status {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 8px;
  font: 13px var(--font-stack);
}

.membership-status--found {
  color: var(--status-open-text);
}

.membership-status--not-found {
  color: var(--notice-warn-text);
}

.membership-status__icon {
  width: 16px;
  height: 16px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 10px;
}

.membership-status--found .membership-status__icon {
  background: var(--status-open-bg);
  color: var(--status-open-text);
}

.membership-status--not-found .membership-status__icon {
  background: var(--notice-warn-bg);
  color: var(--notice-warn-text);
}
```

- [ ] **Step 2: Write `_notices.css`**

```css
.notice {
  border-radius: var(--radius-input);
  padding: 14px 16px;
  font: 13px/1.5 var(--font-stack);
  margin-bottom: 20px;
}

.notice--warn {
  background: var(--notice-warn-bg);
  border: 1px solid var(--notice-warn-border);
  color: var(--notice-warn-text);
}

.notice--error {
  background: var(--notice-error-bg);
  border: 1px solid var(--notice-error-border);
  color: var(--notice-error-text);
}

.notice--info {
  background: #f0f4ff;
  border: 1px solid #c7d2fe;
  color: #3730a3;
}

/* Stripe card error display */
.card-error {
  color: #e44;
  font: 13px/1.5 var(--font-stack);
  margin-top: 8px;
}
```

- [ ] **Step 3: Write new `_states.css`**

Preserves all JS-coupled classes. Includes focus states, spinner animation, field-error, hidden, payment-view/completed-view.

```css
/* JS-coupled visibility classes — do not rename */
.hidden { display: none; }
.payment-view {}
.completed-view {}

/* Validation error state — applied by script.js */
.field-error {
  border-color: #e53e3e !important;
  box-shadow: 0 0 0 2px rgba(229, 62, 62, 0.2);
}

/* Spinner — used by trip payment button (#spinner) */
.spinner {
  color: #fff;
  font-size: 22px;
  text-indent: -99999px;
  margin: 0 auto;
  position: relative;
  width: 20px;
  height: 20px;
  box-shadow: inset 0 0 0 2px;
  transform: translateZ(0);
  border-radius: 50%;
}

.spinner::before,
.spinner::after {
  position: absolute;
  content: "";
  border-radius: 50%;
}

.spinner::before {
  width: 10.4px;
  height: 20.4px;
  background: var(--color-primary);
  border-radius: 20.4px 0 0 20.4px;
  top: -0.2px;
  left: -0.2px;
  transform-origin: 10.4px 10.2px;
  animation: spinner-rotate 2s infinite ease 1.5s;
}

.spinner::after {
  width: 10.4px;
  height: 10.2px;
  background: var(--color-primary);
  border-radius: 0 10.2px 10.2px 0;
  top: -0.1px;
  left: 10.2px;
  transform-origin: 0 10.2px;
  animation: spinner-rotate 2s infinite ease;
}

@keyframes spinner-rotate {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

/* SVG spinner animation (season form) */
.spin {
  animation: spinner-rotate 1s linear infinite;
}

/* Disabled button state */
button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
```

- [ ] **Step 4: Commit**

```bash
git add app/static/css/styles/components/_forms.css app/static/css/styles/components/_notices.css app/static/css/styles/states/_states.css
git commit -m "feat(css): forms, notices, and state components"
```

---

### Task 4: CSS Progress Bar + Manifest Switchover

**Files:**
- Create: `app/static/css/styles/components/_progress.css`
- Rewrite: `app/static/css/styles/main.css`
- Delete: `app/static/css/styles/layout/_layout.css`
- Delete: `app/static/css/styles/components/_header.css`
- Delete: `app/static/css/styles/components/_trips.css`
- Delete: `app/static/css/styles/components/_registration.css`
- Delete: `app/static/css/styles/components/_triathlon.css`
- Delete: `app/static/css/styles/animations/_animations.css`
- Delete: `app/static/css/styles/utils/_media-queries.css`

- [ ] **Step 1: Write `_progress.css`**

Sticky progress bar for the season registration form.

```css
.progress-bar {
  background: var(--bg-card);
  border-bottom: 1px solid var(--border);
  padding: 12px 32px;
  position: sticky;
  top: 0;
  z-index: 10;
}

.progress-bar__steps {
  max-width: 560px;
  margin: 0 auto;
  display: flex;
  align-items: center;
  gap: 6px;
}

.progress-step {
  display: flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
  border: none;
  background: none;
  padding: 0;
  font-family: var(--font-stack);
}

.progress-step__number {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: var(--border);
  color: var(--text-faint);
  font: 600 12px var(--font-stack);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: background 0.2s, color 0.2s;
}

.progress-step__label {
  font: 500 12px var(--font-stack);
  color: var(--text-faint);
  transition: color 0.2s, font-weight 0.2s;
}

.progress-step--active .progress-step__number,
.progress-step--completed .progress-step__number {
  background: var(--color-primary);
  color: #fff;
}

.progress-step--active .progress-step__label,
.progress-step--completed .progress-step__label {
  color: var(--text-primary);
  font-weight: 600;
}

.progress-bar__line {
  flex: 1;
  height: 2px;
  background: var(--border);
  margin: 0 4px;
}

.progress-bar__line--completed {
  background: var(--color-primary);
}

@media (max-width: 480px) {
  .progress-step__label {
    display: none;
  }

  .progress-bar {
    padding: 12px 20px;
  }
}

@media (max-width: 640px) {
  .progress-bar {
    padding: 12px 20px;
  }
}
```

- [ ] **Step 2: Rewrite `main.css` with new imports**

```css
@import 'base/_tokens.css';
@import 'base/_reset.css';
@import 'components/_layout.css';
@import 'components/_cards.css';
@import 'components/_forms.css';
@import 'components/_buttons.css';
@import 'components/_badges.css';
@import 'components/_notices.css';
@import 'components/_progress.css';
@import 'states/_states.css';
```

- [ ] **Step 3: Delete old CSS files**

```bash
rm app/static/css/styles/layout/_layout.css
rm app/static/css/styles/components/_header.css
rm app/static/css/styles/components/_trips.css
rm app/static/css/styles/components/_registration.css
rm app/static/css/styles/components/_triathlon.css
rm app/static/css/styles/animations/_animations.css
rm app/static/css/styles/utils/_media-queries.css
```

After deletion, also remove now-empty directories if any:

```bash
rmdir app/static/css/styles/layout/ 2>/dev/null
rmdir app/static/css/styles/animations/ 2>/dev/null
rmdir app/static/css/styles/utils/ 2>/dev/null
```

- [ ] **Step 4: Commit**

```bash
git add -A app/static/css/styles/
git commit -m "feat(css): progress bar, manifest switchover, delete old CSS files"
```

---

### Task 5: Homepage Template

**Files:**
- Rewrite: `app/templates/index.html`

**Context:** The route handler at `app/routes/main.py:8-42` passes `trips`, `social_events`, `season`, `now` (UTC), and `is_season_registration_open` to the template.

- [ ] **Step 1: Rewrite `index.html`**

```html
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <title>TCSC Registration</title>
    <meta name="description" content="Twin Cities Ski Club Registration" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <link rel="icon" href="{{ url_for('static', filename='favicon.ico') }}" type="image/x-icon">
    <link rel="stylesheet" href="{{ url_for('static', filename='css/normalize.css') }}" />
    <link rel="stylesheet" href="{{ url_for('static', filename='css/styles/main.css') }}" />
  </head>
  <body>
    <div class="page">
      <header class="page-header">
        <img src="{{ url_for('static', filename='images/tcsc-logo.svg') }}" alt="TCSC Logo" class="page-header__logo">
      </header>

      <div class="page-content">
        {% if season %}
        <div class="homepage-section">
          <div class="section-pill section-pill--membership">Membership</div>
          <div style="margin-top: 16px;">
            <div class="card">
              <div class="card__header">
                <span class="card__title">{{ season.name }}</span>
                {% if is_season_registration_open %}
                  <span class="badge badge--open">Open</span>
                {% elif season.returning_start and season.returning_start > now %}
                  <span class="badge badge--upcoming">Upcoming</span>
                {% elif season.new_start and season.new_start > now %}
                  <span class="badge badge--upcoming">Upcoming</span>
                {% else %}
                  <span class="badge badge--closed">Closed</span>
                {% endif %}
              </div>
              <div class="card__meta">
                <span class="card__meta-item">📅 {{ season.start_date.strftime('%b %d, %Y') }} — {{ season.end_date.strftime('%b %d, %Y') }}</span>
              </div>
              {% if is_season_registration_open %}
                {% if season.returning_start and season.returning_end and season.returning_start <= now <= season.returning_end %}
                  <span class="card__subtext">Returning member window closes {{ season.returning_end|central_time }}.</span>
                {% endif %}
                {% if season.new_start and season.new_end and season.new_start <= now <= season.new_end %}
                  <span class="card__subtext">New member window closes {{ season.new_end|central_time }}.</span>
                {% endif %}
              {% elif season.returning_start and season.returning_start > now %}
                <span class="card__subtext">Registration opens for returning members on {{ season.returning_start|central_time }}.</span>
              {% elif season.new_start and season.new_start > now %}
                <span class="card__subtext">Registration opens for new members on {{ season.new_start|central_time }}.</span>
              {% endif %}
              <div class="card__footer">
                {% if season.price_cents %}
                  <span class="card__price">${{ "%.2f"|format(season.price_cents/100) }}</span>
                {% else %}
                  <span class="card__price"></span>
                {% endif %}
                {% if is_season_registration_open %}
                  <a href="/seasons/{{ season.id }}" class="btn btn--small">Register</a>
                {% else %}
                  <a href="/seasons/{{ season.id }}" class="btn btn--small btn--secondary">Season Info</a>
                {% endif %}
              </div>
            </div>
          </div>
        </div>
        {% endif %}

        {% if trips %}
        <div class="homepage-section">
          <div class="section-pill section-pill--trips">Trips</div>
          <div class="section-grid" style="margin-top: 16px;">
            {% for trip in trips %}
            <a href="/{{ trip.slug }}" class="card" style="text-decoration: none;">
              <span class="card__title">{{ trip.name }}</span>
              <div class="card__meta">
                <span class="card__meta-item">📍 {{ trip.destination }}</span>
                <span class="card__meta-item">📅 {{ trip.formatted_date_range }}</span>
              </div>
              <p class="card__description">{{ trip.description }}</p>
              <div class="card__footer">
                <span class="card__price">
                  {% if trip.price_low == trip.price_high %}
                    ${{ "%.2f"|format(trip.price_low/100) }}
                  {% else %}
                    ${{ "%.2f"|format(trip.price_low/100) }}–${{ "%.2f"|format(trip.price_high/100) }}
                  {% endif %}
                </span>
                <span class="btn btn--small">Sign Up</span>
              </div>
            </a>
            {% endfor %}
          </div>
        </div>
        {% endif %}

        {% if social_events %}
        <div class="homepage-section">
          <div class="section-pill section-pill--social">Social Events</div>
          <div class="section-grid" style="margin-top: 16px;">
            {% for event in social_events %}
            <a href="/social/{{ event.slug }}" class="card" style="text-decoration: none;">
              <span class="card__title">{{ event.name }}</span>
              <div class="card__meta">
                <span class="card__meta-item">📍 {{ event.location }}</span>
                <span class="card__meta-item">📅 {{ event.formatted_date }}</span>
                <span class="card__meta-item">🕐 {{ event.formatted_time }}</span>
              </div>
              <p class="card__description">{{ event.description }}</p>
              <div class="card__footer">
                <span class="card__price">${{ "%.2f"|format(event.price/100) }}</span>
                <span class="btn btn--small">Sign Up</span>
              </div>
            </a>
            {% endfor %}
          </div>
        </div>
        {% endif %}
      </div>
    </div>
  </body>
</html>
```

- [ ] **Step 2: Start dev server and verify homepage renders**

```bash
./scripts/dev.sh 5001
```

Open `http://localhost:5001` and verify:
- Logo displays centered in header
- Section pills show with correct colors
- Cards render with correct structure
- Status badge appears on season card
- Grid is 2-column on desktop, 1-column on mobile (resize browser)
- Buttons work as links to registration pages

- [ ] **Step 3: Commit**

```bash
git add app/templates/index.html
git commit -m "feat: redesign homepage with sectioned card layout"
```

---

### Task 6: Trip Registration Template

**Files:**
- Rewrite: `app/templates/trips/base_trip.html`

**Context:** The route at `app/routes/trips.py:8-11` passes `trip` object. Individual trip templates (e.g., `birkie.html`) extend this with `{% extends "trips/base_trip.html" %}` and only override `{% block title %}` and `{% block meta_description %}`.

**JS contract:** `script.js` looks for: `#name`, `#email`, `#card-element`, `#card-errors`, `#submit`, `#spinner`, `#button-text`, `.price-option-container[data-value]`, `input[name="price-choice"]`, `.payment-view`, `.completed-view`, `.hidden`, `.price-amount`.

- [ ] **Step 1: Rewrite `base_trip.html`**

```html
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <title>{% block title %}TCSC Trip Registration{% endblock %}</title>
    <meta name="description" content="{% block meta_description %}TCSC Trip Registration and Payment{% endblock %}" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <link rel="icon" href="{{ url_for('static', filename='favicon.ico') }}" type="image/x-icon">
    <link rel="stylesheet" href="{{ url_for('static', filename='css/normalize.css') }}" />
    <link rel="stylesheet" href="{{ url_for('static', filename='css/styles/main.css') }}" />
    <script src="https://js.stripe.com/v3/"></script>
    <script src="{{ url_for('static', filename='script.js') }}" defer></script>
  </head>
  <body>
    <div class="page">
      <header class="page-header">
        <img src="{{ url_for('static', filename='images/tcsc-logo.svg') }}" alt="TCSC Logo" class="page-header__logo">
      </header>

      <div class="page-content page-content--narrow">
        <div class="form-header payment-view">
          <h1 class="form-header__title">{{ trip.name }} Registration</h1>
          <div class="form-header__meta">
            <span>📍 {{ trip.destination }}</span>
            <span>📅 {{ trip.formatted_date_range }}</span>
          </div>
        </div>

        {% if trip.price_low != trip.price_high %}
          <div class="payment-view">
            <div class="pill-group__label">Select Price</div>
            <div class="price-selector">
              <div class="price-option-container" data-value="{{ "%.2f"|format(trip.price_low/100) }}">
                <input type="radio" id="price-low" name="price-choice" value="{{ "%.2f"|format(trip.price_low/100) }}">
                <div class="price-option__label">Lower Price</div>
                <div class="price-option__amount">${{ "%.2f"|format(trip.price_low/100) }}</div>
              </div>
              <div class="price-option-container" data-value="{{ "%.2f"|format(trip.price_high/100) }}">
                <input type="radio" id="price-high" name="price-choice" value="{{ "%.2f"|format(trip.price_high/100) }}">
                <div class="price-option__label">Higher Price</div>
                <div class="price-option__amount">${{ "%.2f"|format(trip.price_high/100) }}</div>
              </div>
            </div>
          </div>
        {% else %}
          <div class="price-summary payment-view">
            <span class="price-summary__label">Trip Price</span>
            <span class="price-summary__amount price-amount">${{ "%.2f"|format(trip.price_low/100) }}</span>
          </div>
        {% endif %}

        <div class="payment-view">
          <div class="form-field">
            <label class="form-field__label" for="name">Full Name</label>
            <input type="text" id="name" class="form-input" placeholder="Full Name" autocomplete="name">
          </div>
          <div class="form-field">
            <label class="form-field__label" for="email">Email Address</label>
            <input type="email" id="email" class="form-input" placeholder="Email Address" autocomplete="email">
          </div>
          <div class="form-field">
            <label class="form-field__label" for="card-element">Card Details</label>
            <div class="card-element-wrapper" id="card-element"></div>
            <div class="card-error" id="card-errors" role="alert"></div>
          </div>

          <div class="notice notice--warn">
            A hold will be placed on your card. If selected in the lottery, your card will be charged.
          </div>

          <button class="btn btn--full" id="submit">
            <div class="spinner hidden" id="spinner"></div>
            <span id="button-text">Register for Trip</span>
          </button>
        </div>

        <div class="completed-view hidden">
          <div style="text-align: center; padding: 32px 0;">
            <h1>Payment Successful!</h1>
            <div class="notice notice--info" style="margin-top: 20px; text-align: left;">
              <p style="margin: 0 0 8px;">Your registration has been received and a hold has been placed on your card.</p>
              <p style="margin: 0;">If selected in the lottery, your card will be charged.</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  </body>
</html>
```

- [ ] **Step 2: Verify trip registration page**

Open `http://localhost:5001/<any-trip-slug>` (requires an active trip in the DB). Verify:
- Logo header shows
- Trip name, location, date display correctly
- Price selectors render (if multi-price trip) — clicking selects (navy fill)
- Name, email, and card fields render with correct styling
- Yellow lottery notice shows
- Button has correct text
- No JS console errors

- [ ] **Step 3: Commit**

```bash
git add app/templates/trips/base_trip.html
git commit -m "feat: redesign trip registration template"
```

---

### Task 7: Social Event Registration Template

**Files:**
- Rewrite: `app/templates/socials/registration.html`

**Context:** Route at `app/routes/socials.py` passes `event` object. JS contract from `social_event.js`: `#name`, `#email`, `#card-element`, `#card-errors`, `#submit`, `#spinner`, `#button-text`, `.single-price-display[data-event-id]`, `.payment-view`, `.completed-view`, `.hidden`.

- [ ] **Step 1: Rewrite `socials/registration.html`**

```html
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <title>{{ event.name }} Registration</title>
    <meta name="description" content="TCSC Social Event Registration" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <link rel="icon" href="{{ url_for('static', filename='favicon.ico') }}" type="image/x-icon">
    <link rel="stylesheet" href="{{ url_for('static', filename='css/normalize.css') }}" />
    <link rel="stylesheet" href="{{ url_for('static', filename='css/styles/main.css') }}" />
    <script src="https://js.stripe.com/v3/"></script>
    <script src="{{ url_for('static', filename='social_event.js') }}" defer></script>
  </head>
  <body>
    <div class="page">
      <header class="page-header">
        <img src="{{ url_for('static', filename='images/tcsc-logo.svg') }}" alt="TCSC Logo" class="page-header__logo">
      </header>

      <div class="page-content page-content--narrow">
        <div class="form-header payment-view">
          <div><span class="badge badge--social">Social Event</span></div>
          <h1 class="form-header__title" style="margin-top: 8px;">{{ event.name }}</h1>
          <div class="form-header__meta">
            <span>📍 {{ event.location }}</span>
            <span>📅 {{ event.formatted_date }}</span>
            <span>🕐 {{ event.formatted_time }}</span>
          </div>
        </div>

        <div class="single-price-display price-summary payment-view" data-event-id="{{ event.id }}">
          <span class="price-summary__label">Event Price</span>
          <span class="price-summary__amount price-amount">${{ "%.2f"|format(event.price/100) }}</span>
        </div>

        <div class="payment-view">
          <div class="form-field">
            <label class="form-field__label" for="name">Full Name</label>
            <input type="text" id="name" class="form-input" placeholder="Full Name" autocomplete="name">
          </div>
          <div class="form-field">
            <label class="form-field__label" for="email">Email Address</label>
            <input type="email" id="email" class="form-input" placeholder="Email Address" autocomplete="email">
          </div>
          <div class="form-field">
            <label class="form-field__label" for="card-element">Card Details</label>
            <div class="card-element-wrapper" id="card-element"></div>
            <div class="card-error" id="card-errors" role="alert"></div>
          </div>

          <button class="btn btn--full" id="submit">
            <div class="spinner hidden" id="spinner"></div>
            <span id="button-text">Pay — ${{ "%.2f"|format(event.price/100) }}</span>
          </button>
        </div>

        <div class="completed-view hidden">
          <div style="text-align: center; padding: 32px 0;">
            <h1>Registration Complete!</h1>
            <div class="notice notice--info" style="margin-top: 20px; text-align: left;">
              <p style="margin: 0 0 8px;">Your registration has been confirmed and your card has been charged.</p>
              <p style="margin: 0;">You will receive a confirmation email shortly.</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  </body>
</html>
```

- [ ] **Step 2: Verify social event registration page**

Open `http://localhost:5001/social/<any-social-slug>` (requires an active social event). Verify:
- Social Event badge shows in green
- Event name, location, date, time display
- Price summary bar renders
- Form fields styled correctly
- Button text shows "Pay — $XX.XX"
- No JS console errors

- [ ] **Step 3: Commit**

```bash
git add app/templates/socials/registration.html
git commit -m "feat: redesign social event registration template"
```

---

### Task 8: Season Registration Template

**Files:**
- Rewrite: `app/templates/season_register.html`

**Context:** Route at `app/routes/registration.py` passes `season` object. JS contract from `script.js`: `#registration-form[data-season-id][data-price-cents]`, `#email`, `#name`, `#card-element`, `#card-errors`, `#register-btn`, `#button-text`, `#button-spinner`, `.field-error`, `input[name="status"]`, all form field names (see spec JS Contract section). The localStorage persistence uses these exact field names.

- [ ] **Step 1: Rewrite `season_register.html`**

```html
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <title>TCSC Season Registration</title>
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <link rel="stylesheet" href="{{ url_for('static', filename='css/normalize.css') }}" />
    <link rel="stylesheet" href="{{ url_for('static', filename='css/styles/main.css') }}" />
  </head>
  <body>
    <div class="page">
      <header class="page-header">
        <img src="{{ url_for('static', filename='images/tcsc-logo.svg') }}" alt="TCSC Logo" class="page-header__logo">
      </header>

      <nav class="progress-bar">
        <div class="progress-bar__steps">
          <button class="progress-step progress-step--active" data-section="section-about">
            <span class="progress-step__number">1</span>
            <span class="progress-step__label">About You</span>
          </button>
          <div class="progress-bar__line"></div>
          <button class="progress-step" data-section="section-skiing">
            <span class="progress-step__number">2</span>
            <span class="progress-step__label">Skiing</span>
          </button>
          <div class="progress-bar__line"></div>
          <button class="progress-step" data-section="section-emergency">
            <span class="progress-step__number">3</span>
            <span class="progress-step__label">Emergency</span>
          </button>
          <div class="progress-bar__line"></div>
          <button class="progress-step" data-section="section-payment">
            <span class="progress-step__number">4</span>
            <span class="progress-step__label">Payment</span>
          </button>
        </div>
      </nav>

      <div class="page-content page-content--medium">
        {% with messages = get_flashed_messages(with_categories=true) %}
          {% if messages %}
            <div class="notice notice--error">
              {% for category, message in messages %}
                <p style="margin: 0;">{{ message }}</p>
              {% endfor %}
            </div>
          {% endif %}
        {% endwith %}

        <form id="registration-form" method="POST" data-season-id="{{ season.id }}" data-price-cents="{{ season.price_cents or 0 }}">

          <!-- Section 1: About You -->
          <div id="section-about" class="form-section">
            <h2 class="form-section__title">About You</h2>
            <p class="form-section__subtitle">Basic info and membership status</p>

            <div class="form-field">
              <label class="form-field__label" for="email">Email Address</label>
              <input class="form-input" type="email" id="email" name="email" placeholder="Email Address" autocomplete="email" required>
            </div>

            <div class="form-field">
              <div class="pill-group__label">Member Type</div>
              <div class="pill-group">
                <label class="pill">
                  <input type="radio" name="status" value="new" required>
                  New Member
                </label>
                <label class="pill">
                  <input type="radio" name="status" value="returning_former">
                  Returning / Former
                </label>
              </div>
            </div>

            <div class="form-row form-row--pair">
              <div class="form-field">
                <label class="form-field__label" for="firstName">First Name</label>
                <input class="form-input" type="text" id="firstName" name="firstName" placeholder="First Name" autocomplete="given-name" required>
              </div>
              <div class="form-field">
                <label class="form-field__label" for="lastName">Last Name</label>
                <input class="form-input" type="text" id="lastName" name="lastName" placeholder="Last Name" autocomplete="family-name" required>
              </div>
            </div>

            <div class="form-row form-row--pair">
              <div class="form-field">
                <label class="form-field__label" for="pronouns">Pronouns <span class="form-field__hint">(optional)</span></label>
                <input class="form-input" type="text" id="pronouns" name="pronouns" placeholder="Pronouns">
              </div>
              <div class="form-field">
                <label class="form-field__label" for="dob">Date of Birth</label>
                <input class="form-input" type="date" id="dob" name="dob" autocomplete="bday" required>
              </div>
            </div>

            <div class="form-row form-row--pair">
              <div class="form-field">
                <label class="form-field__label" for="phone">Phone Number</label>
                <input class="form-input" type="tel" id="phone" name="phone" placeholder="Phone Number" autocomplete="tel" required>
              </div>
              <div class="form-field">
                <label class="form-field__label" for="tshirtSize">T-Shirt Size</label>
                <select class="form-input" id="tshirtSize" name="tshirtSize" required>
                  <option value="">Choose Size</option>
                  <option value="XS">XS</option>
                  <option value="S">S</option>
                  <option value="M">M</option>
                  <option value="L">L</option>
                  <option value="XL">XL</option>
                  <option value="2XL">2XL</option>
                </select>
              </div>
            </div>
          </div>

          <hr class="form-divider">

          <!-- Section 2: Skiing Details -->
          <div id="section-skiing" class="form-section">
            <h2 class="form-section__title">Skiing Details</h2>
            <p class="form-section__subtitle">Tell us about your skiing background</p>

            <div class="form-field">
              <div class="pill-group__label">Preferred Technique</div>
              <div class="pill-group">
                <label class="pill">
                  <input type="radio" name="technique" value="classic" required>
                  Classic
                </label>
                <label class="pill">
                  <input type="radio" name="technique" value="skate">
                  Skate
                </label>
                <label class="pill">
                  <input type="radio" name="technique" value="no_preference">
                  No Preference
                </label>
              </div>
            </div>

            <div class="form-field">
              <div class="pill-group__label">Experience Level</div>
              <div class="pill-group">
                <label class="pill">
                  <input type="radio" name="experience" value="1-3" required>
                  Beginner <span class="pill__hint">1–3 yr</span>
                </label>
                <label class="pill">
                  <input type="radio" name="experience" value="3-7">
                  Intermediate <span class="pill__hint">3–7 yr</span>
                </label>
                <label class="pill">
                  <input type="radio" name="experience" value="7+">
                  Advanced <span class="pill__hint">7+ yr</span>
                </label>
              </div>
            </div>
          </div>

          <hr class="form-divider">

          <!-- Section 3: Emergency Contact -->
          <div id="section-emergency" class="form-section">
            <h2 class="form-section__title">Emergency Contact</h2>
            <p class="form-section__subtitle">Someone we can reach in case of emergency</p>

            <div class="form-row form-row--pair">
              <div class="form-field">
                <label class="form-field__label" for="emergencyName">Contact's Full Name</label>
                <input class="form-input" type="text" id="emergencyName" name="emergencyName" placeholder="Full Name" autocomplete="off" required>
              </div>
              <div class="form-field">
                <label class="form-field__label" for="emergencyRelation">Relationship</label>
                <input class="form-input" type="text" id="emergencyRelation" name="emergencyRelation" placeholder="Relationship" autocomplete="off" required>
              </div>
            </div>

            <div class="form-row form-row--pair">
              <div class="form-field">
                <label class="form-field__label" for="emergencyPhone">Phone Number</label>
                <input class="form-input" type="tel" id="emergencyPhone" name="emergencyPhone" placeholder="Phone Number" autocomplete="off" required>
              </div>
              <div class="form-field">
                <label class="form-field__label" for="emergencyEmail">Email Address</label>
                <input class="form-input" type="email" id="emergencyEmail" name="emergencyEmail" placeholder="Email Address" autocomplete="off" required>
              </div>
            </div>
          </div>

          <hr class="form-divider">

          <!-- Section 4: Payment -->
          <div id="section-payment" class="form-section">
            <h2 class="form-section__title">Payment</h2>
            <p class="form-section__subtitle">Secure payment via Stripe</p>

            {% if season.price_cents %}
            <div class="price-summary">
              <span class="price-summary__label">Season Membership</span>
              <span class="price-summary__amount">${{ '%.2f' % (season.price_cents / 100) }}</span>
            </div>
            {% endif %}

            <div class="form-field">
              <label class="form-field__label" for="name">Name on Card</label>
              <input class="form-input" type="text" id="name" name="name" placeholder="Full Name" autocomplete="cc-name" required>
            </div>

            <div class="form-field">
              <label class="form-field__label" for="card-element">Card Details</label>
              <div class="card-element-wrapper" id="card-element"></div>
              <div class="card-error" id="card-errors" role="alert"></div>
            </div>

            <div class="checkbox-group">
              <input type="checkbox" id="agreement" name="agreement" required>
              <label for="agreement">
                I agree to the <a href="https://docs.google.com/document/d/10gPfG-GSEXNCsFrcg4AeAmf0MQ-in0xdfWuk_RSJgxs/edit?usp=sharing" target="_blank" rel="noopener noreferrer">Assumption of Risk, Release of Liability, SMS Communication and Photography Release</a>
              </label>
            </div>
          </div>

          <button type="submit" class="btn btn--full" id="register-btn">
            <span id="button-text">Register & Pay{% if season.price_cents %} — ${{ '%.2f' % (season.price_cents / 100) }}{% endif %}</span>
            <span id="button-spinner" style="display: none;">
              <svg width="20" height="20" viewBox="0 0 20 20" class="spin">
                <circle cx="10" cy="10" r="8" stroke="currentColor" stroke-width="2" fill="none" stroke-dasharray="40" stroke-dashoffset="10"/>
              </svg>
              Processing...
            </span>
          </button>
        </form>
      </div>
    </div>
    <script src="https://js.stripe.com/v3/"></script>
    <script src="{{ url_for('static', filename='script.js') }}" defer></script>
    <script src="{{ url_for('static', filename='progress.js') }}" defer></script>
  </body>
</html>
```

- [ ] **Step 2: Verify season registration page**

Open `http://localhost:5001/seasons/<season_id>/register`. Verify:
- Progress bar sticky at top with 4 steps
- All form sections render with correct fields
- Pill selectors for member type, technique, experience work (click toggles selection)
- Side-by-side fields on desktop, stacked on mobile
- Stripe card element mounts into `#card-element`
- Email field triggers membership check on blur (check network tab)
- Agreement checkbox and link work
- localStorage persistence works (fill some fields, refresh, verify they're restored)
- Submit button shows price

- [ ] **Step 3: Commit**

```bash
git add app/templates/season_register.html
git commit -m "feat: redesign season registration with progress bar and pill selectors"
```

---

### Task 9: Progress Bar JavaScript

**Files:**
- Create: `app/static/progress.js`

- [ ] **Step 1: Write `progress.js`**

```javascript
document.addEventListener('DOMContentLoaded', function () {
  const steps = document.querySelectorAll('.progress-step');
  const lines = document.querySelectorAll('.progress-bar__line');
  const sections = [];

  steps.forEach(function (step) {
    var id = step.getAttribute('data-section');
    var el = document.getElementById(id);
    if (el) sections.push({ id: id, el: el, step: step });
  });

  if (sections.length === 0) return;

  function updateProgress(activeIndex) {
    steps.forEach(function (step, i) {
      step.classList.remove('progress-step--active', 'progress-step--completed');
      if (i < activeIndex) {
        step.classList.add('progress-step--completed');
        var num = step.querySelector('.progress-step__number');
        if (num) num.textContent = '✓';
      } else if (i === activeIndex) {
        step.classList.add('progress-step--active');
        var num = step.querySelector('.progress-step__number');
        if (num) num.textContent = String(i + 1);
      } else {
        var num = step.querySelector('.progress-step__number');
        if (num) num.textContent = String(i + 1);
      }
    });

    lines.forEach(function (line, i) {
      if (i < activeIndex) {
        line.classList.add('progress-bar__line--completed');
      } else {
        line.classList.remove('progress-bar__line--completed');
      }
    });
  }

  var observer = new IntersectionObserver(function (entries) {
    entries.forEach(function (entry) {
      if (entry.isIntersecting) {
        for (var i = 0; i < sections.length; i++) {
          if (sections[i].el === entry.target) {
            updateProgress(i);
            break;
          }
        }
      }
    });
  }, {
    rootMargin: '-20% 0px -60% 0px',
    threshold: 0
  });

  sections.forEach(function (s) { observer.observe(s.el); });

  steps.forEach(function (step) {
    step.addEventListener('click', function () {
      var id = step.getAttribute('data-section');
      var target = document.getElementById(id);
      if (target) {
        var offset = document.querySelector('.progress-bar').offsetHeight + 20;
        var top = target.getBoundingClientRect().top + window.pageYOffset - offset;
        window.scrollTo({ top: top, behavior: 'smooth' });
      }
    });
  });
});
```

- [ ] **Step 2: Verify progress bar behavior**

Open the season registration page and verify:
- Step 1 "About You" is active (navy) on load
- Scrolling down highlights successive steps
- Completed steps show checkmark
- Connecting lines fill in as steps complete
- Clicking a step smooth-scrolls to that section
- On mobile (< 480px), step labels are hidden, only numbers show

- [ ] **Step 3: Commit**

```bash
git add app/static/progress.js
git commit -m "feat: add progress bar scroll tracking for season registration"
```

---

### Task 10: Season Success + Season Detail Templates

**Files:**
- Rewrite: `app/templates/season_success.html`
- Rewrite: `app/templates/season_detail.html`

**Context:** `season_detail.html` uses `main.css` and old `sr-` classes — it will break after the CSS switchover and must be updated. Route passes `season`, `is_registration_open`, `now`.

- [ ] **Step 1: Rewrite `season_success.html`**

```html
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <title>Registration Successful – TCSC</title>
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <link rel="stylesheet" href="{{ url_for('static', filename='css/normalize.css') }}" />
    <link rel="stylesheet" href="{{ url_for('static', filename='css/styles/main.css') }}" />
  </head>
  <body>
    <div class="page">
      <header class="page-header">
        <img src="{{ url_for('static', filename='images/tcsc-logo.svg') }}" alt="TCSC Logo" class="page-header__logo">
      </header>

      <div class="page-content page-content--narrow">
        <div style="text-align: center; margin-bottom: 24px;">
          <h1>Thank you for registering!</h1>
          <p style="color: var(--text-muted);">Your registration for <strong>{{ season.name }}</strong> has been received.</p>
        </div>

        {% if payment_hold %}
          <div class="notice notice--info">
            <p style="margin: 0 0 8px;">A hold of <strong>{{ amount_display }}</strong> has been placed on your card. Your card will <strong>not</strong> be charged until your membership is confirmed.</p>
            <p style="margin: 0;">You'll receive a receipt email from Stripe once your membership is confirmed and the charge is processed.</p>
          </div>
          <div class="notice notice--warn" style="margin-top: 12px;">
            <strong>Tip:</strong> Save this page or take a screenshot for your records.
          </div>
        {% else %}
          <div class="notice notice--info">
            <p style="margin: 0 0 8px;">Your card has been charged <strong>{{ amount_display }}</strong>. Your membership for <strong>{{ season.name }}</strong> is confirmed!</p>
            <p style="margin: 0;">You'll receive a receipt from Stripe shortly at the email address you provided.</p>
          </div>
        {% endif %}

        <p style="color: var(--text-muted); font-size: 14px; margin-top: 20px;">
          If you have any questions, please contact <a href="mailto:contact@twincitiesskiclub.org">contact@twincitiesskiclub.org</a>.
        </p>

        <div style="text-align: center; margin-top: 24px;">
          <a href="/" class="btn btn--secondary">&larr; Back to Home</a>
        </div>
      </div>
    </div>
  </body>
</html>
```

- [ ] **Step 2: Rewrite `season_detail.html`**

```html
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <title>{{ season.name }} – TCSC Season Info</title>
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <link rel="stylesheet" href="{{ url_for('static', filename='css/normalize.css') }}" />
    <link rel="stylesheet" href="{{ url_for('static', filename='css/styles/main.css') }}" />
  </head>
  <body>
    <div class="page">
      <header class="page-header">
        <img src="{{ url_for('static', filename='images/tcsc-logo.svg') }}" alt="TCSC Logo" class="page-header__logo">
      </header>

      <div class="page-content page-content--medium">
        <div class="notice notice--info">
          <p style="margin: 0 0 4px;"><strong>Registration Opens:</strong></p>
          <ul style="margin: 0; padding-left: 20px;">
            {% if season.returning_start %}
              <li>Returning Members: {{ season.returning_start.strftime('%b %d, %Y %I:%M %p') }}</li>
            {% endif %}
            {% if season.new_start %}
              <li>New Members: {{ season.new_start.strftime('%b %d, %Y %I:%M %p') }}</li>
            {% endif %}
            {% if not season.returning_start and not season.new_start %}
              <li>Registration dates will be announced soon.</li>
            {% endif %}
          </ul>
        </div>

        <div class="card" style="margin-top: 20px;">
          <div class="card__header">
            <span class="card__title" style="font-size: 20px;">{{ season.name }}</span>
            {% if is_registration_open %}
              <span class="badge badge--open">Open</span>
            {% elif season.returning_start and season.returning_start > now %}
              <span class="badge badge--upcoming">Upcoming</span>
            {% elif season.new_start and season.new_start > now %}
              <span class="badge badge--upcoming">Upcoming</span>
            {% else %}
              <span class="badge badge--closed">Closed</span>
            {% endif %}
          </div>

          {% if season.description %}
            <p class="card__description">{{ season.description }}</p>
          {% endif %}

          <div class="card__meta">
            <span class="card__meta-item">📅 {{ season.start_date.strftime('%b %d, %Y') }} to {{ season.end_date.strftime('%b %d, %Y') }}</span>
            <span class="card__meta-item">👥 Registration Limit: {{ season.registration_limit if season.registration_limit else 'No limit' }}</span>
            {% if season.price_cents %}
              <span class="card__meta-item">💰 Price: ${{ '%.2f' % (season.price_cents / 100) }}</span>
            {% endif %}
          </div>

          {% if is_registration_open %}
            {% if season.returning_start and season.returning_end and season.returning_start <= now <= season.returning_end %}
              <span class="card__subtext">Returning member window closes {{ season.returning_end|central_time }}.</span>
            {% endif %}
            {% if season.new_start and season.new_end and season.new_start <= now <= season.new_end %}
              <span class="card__subtext">New member window closes {{ season.new_end|central_time }}.</span>
            {% endif %}
          {% elif season.returning_start and season.returning_start > now %}
            <span class="card__subtext">Registration opens for returning members on {{ season.returning_start|central_time }}.</span>
          {% elif season.new_start and season.new_start > now %}
            <span class="card__subtext">Registration opens for new members on {{ season.new_start|central_time }}.</span>
          {% endif %}

          <div class="card__footer">
            <span></span>
            {% if is_registration_open %}
              <a href="{{ url_for('registration.season_register', season_id=season.id) }}" class="btn btn--small">Register for this Season</a>
            {% else %}
              <button class="btn btn--small" disabled>Registration Closed</button>
            {% endif %}
          </div>
        </div>

        <div style="text-align: center; margin-top: 24px;">
          <a href="/" class="btn btn--secondary">&larr; Back to Home</a>
        </div>
      </div>
    </div>
  </body>
</html>
```

- [ ] **Step 3: Verify both pages**

- Open `http://localhost:5001/seasons/<id>` — verify season detail card renders with badge, metadata, register button
- Season success: can only be fully tested after a real registration, but visually verify the template renders without errors by temporarily visiting the route or checking for Jinja syntax errors in the logs

- [ ] **Step 4: Commit**

```bash
git add app/templates/season_success.html app/templates/season_detail.html
git commit -m "feat: redesign season detail and success pages"
```

---

### Task 11: Dryland Triathlon Template

**Files:**
- Rewrite: `app/templates/dryland-triathlon.html`

**Context:** Static info page. Route at `app/routes/main.py:44-46` renders with no context. External registration links (Google Forms). No Stripe/JS contract concerns.

- [ ] **Step 1: Rewrite `dryland-triathlon.html`**

```html
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <title>TCSC Dryland Triathlon</title>
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <link rel="stylesheet" href="{{ url_for('static', filename='css/normalize.css') }}" />
    <link rel="stylesheet" href="{{ url_for('static', filename='css/styles/main.css') }}" />
  </head>
  <body>
    <div class="page">
      <header class="page-header">
        <img src="{{ url_for('static', filename='images/tcsc-logo.svg') }}" alt="TCSC Logo" class="page-header__logo">
      </header>

      <div class="page-content page-content--medium">
        <div style="text-align: center; margin-bottom: 32px;">
          <h1 style="font-size: 28px; font-weight: 700;">Roll. Ride. Run.</h1>
          <div style="display: flex; justify-content: center; gap: 16px; font-size: 15px; color: var(--text-muted); flex-wrap: wrap; margin-top: 8px;">
            <span>📅 Saturday, October 25th, 2025</span>
            <span>📍 Carver Park Reserve, Parley Lake Area</span>
          </div>
        </div>

        <div class="form-section">
          <h2 class="form-section__title">About the Event</h2>
          <p style="color: var(--text-muted); line-height: 1.6; margin: 0 0 12px;">Join us for TCSC's pilot year of the Dryland Triathlon! This fun event combines three common off-season activities for Nordic skiers: rollerskiing, mountain biking, and trail running. Show off your off-season gains before winter arrives!</p>
          <p style="color: var(--text-muted); line-height: 1.6; margin: 0;">Compete individually or with two teammates. Each leg starts and ends in the Parley Lake lot where your team will have a designated transition zone.</p>
        </div>

        <hr class="form-divider">

        <div class="form-section">
          <h2 class="form-section__title">Distances & Schedule</h2>
          <div class="section-grid" style="margin-bottom: 16px;">
            <div class="card" style="cursor: default;">
              <span class="card__title">Long Course</span>
              <p class="card__description">18K roll · 17K ride · 11K run</p>
              <span class="card__meta-item">🕐 9:00 AM start</span>
            </div>
            <div class="card" style="cursor: default;">
              <span class="card__title">Short Course</span>
              <p class="card__description">9.5K roll · 9K ride · 6K run</p>
              <span class="card__meta-item">🕐 9:30 AM start</span>
            </div>
          </div>
          <p style="color: var(--text-muted); font-size: 14px;"><a href="https://docs.google.com/document/d/14DYvbi9gYWKBf5l3jUw5JZHBa_0G9GQvz3l3xZzE3ME/edit?usp=sharing" target="_blank" style="color: var(--text-primary); text-decoration: underline;">View Participant Guide</a> for event details, rules, and course maps</p>
        </div>

        <hr class="form-divider">

        <div class="form-section">
          <h2 class="form-section__title">Registration</h2>
          <div class="section-grid" style="margin-bottom: 12px;">
            <a href="https://bit.ly/drytri25solo" target="_blank" class="btn btn--full" style="text-decoration: none; flex-direction: column; gap: 4px;">
              <span style="font-size: 16px;">Individual</span>
              <span style="font-size: 20px; font-weight: 700;">$55</span>
            </a>
            <a href="https://bit.ly/drytri25team" target="_blank" class="btn btn--full" style="text-decoration: none; flex-direction: column; gap: 4px;">
              <span style="font-size: 16px;">Team</span>
              <span style="font-size: 20px; font-weight: 700;">$105</span>
            </a>
          </div>
          <p style="text-align: center; color: var(--text-muted); font-size: 14px; font-style: italic;">TCSC members receive a discount</p>
        </div>

        <hr class="form-divider">

        <div class="form-section">
          <h2 class="form-section__title">Team Finder</h2>
          <p style="color: var(--text-muted); line-height: 1.6; margin: 0;">Looking for teammates? Connect with other participants on the <a href="https://docs.google.com/spreadsheets/d/1h4gkY6P2khJ-ofArl5yBZdihDC98pv02BGN7OGEjWi4/edit?usp=sharing" target="_blank" style="color: var(--text-primary); text-decoration: underline;">Team Finder Spreadsheet</a></p>
        </div>

        <hr class="form-divider">

        <div class="form-section">
          <h2 class="form-section__title">About TCSC</h2>
          <p style="color: var(--text-muted); line-height: 1.6; margin: 0;">The Twin Cities Ski Club (TCSC) is a welcoming community of Nordic skiers offering training, trips, and fun events for skiers of all abilities. Come meet fellow skiers and join the community!</p>
        </div>

        <div style="text-align: center; margin-top: 24px;">
          <a href="/" class="btn btn--secondary">&larr; Back to Home</a>
        </div>
      </div>
    </div>
  </body>
</html>
```

- [ ] **Step 2: Verify triathlon page**

Open `http://localhost:5001/tri` and verify:
- Logo header renders
- Hero section (title, date, location) displays centered
- Course cards render side by side on desktop, stacked on mobile
- Registration buttons link to external Google Forms
- All section headings match the new typography
- Back button styled as secondary outlined button
- No Font Awesome icons (emoji only)

- [ ] **Step 3: Commit**

```bash
git add app/templates/dryland-triathlon.html
git commit -m "feat: redesign dryland triathlon page"
```

---

### Task 12: Final Verification + Cleanup

**Files:** None created — verification only.

- [ ] **Step 1: Run dev server and test all pages**

```bash
./scripts/dev.sh 5001
```

Test each page at these URLs:

| Page | URL | Check |
|------|-----|-------|
| Homepage | `http://localhost:5001/` | Section pills, cards, status badges, responsive grid |
| Season detail | `http://localhost:5001/seasons/<id>` | Card layout, badge, register button |
| Season register | `http://localhost:5001/seasons/<id>/register` | Progress bar, pill selectors, side-by-side fields, Stripe card mount, form submission, localStorage persistence |
| Trip register | `http://localhost:5001/<trip-slug>` | Price selectors, form fields, lottery notice, Stripe payment flow |
| Social register | `http://localhost:5001/social/<slug>` | Social badge, price bar, form fields, immediate charge flow |
| Triathlon | `http://localhost:5001/tri` | Course cards, registration buttons, section layout |

- [ ] **Step 2: Test mobile responsiveness**

Use browser dev tools to test at these widths:
- **375px** (iPhone SE): all fields stack, progress bar shows numbers only, cards stack to 1-column
- **640px** (breakpoint): verify side-by-side fields kick in, grid goes to 2-column
- **1024px** (desktop): full layout

- [ ] **Step 3: Verify no console errors**

On each page, open browser dev tools Console tab. Verify no JavaScript errors, especially:
- Stripe Elements mounting correctly
- No "element not found" errors from `script.js` or `social_event.js`
- Progress bar observer working without errors

- [ ] **Step 4: Verify old CSS files are gone**

```bash
ls app/static/css/styles/layout/ 2>/dev/null && echo "WARN: layout/ still exists" || echo "OK: layout/ removed"
ls app/static/css/styles/animations/ 2>/dev/null && echo "WARN: animations/ still exists" || echo "OK: animations/ removed"
ls app/static/css/styles/utils/ 2>/dev/null && echo "WARN: utils/ still exists" || echo "OK: utils/ removed"
ls app/static/css/styles/components/_header.css 2>/dev/null && echo "WARN: _header.css still exists" || echo "OK"
ls app/static/css/styles/components/_trips.css 2>/dev/null && echo "WARN: _trips.css still exists" || echo "OK"
ls app/static/css/styles/components/_registration.css 2>/dev/null && echo "WARN: _registration.css still exists" || echo "OK"
ls app/static/css/styles/components/_triathlon.css 2>/dev/null && echo "WARN: _triathlon.css still exists" || echo "OK"
```

- [ ] **Step 5: Final commit if any cleanup was needed**

```bash
git status
# If any cleanup changes:
git add -A
git commit -m "fix: final cleanup from registration UI redesign"
```
