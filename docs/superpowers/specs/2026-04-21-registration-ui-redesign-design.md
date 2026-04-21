# Registration UI Redesign

Complete visual overhaul of the public-facing registration experience: homepage, trip registration, social event registration, and season membership form.

## Problem

The current registration UI was built on top of a Stripe payment sample template (`sr-` prefixed classes). It looks dated, disorganized, and "buggy" even though it functions correctly. The CSS has accumulated specificity cruft with `!important` overrides and fragmented styling across `_registration.css`, `_forms.css`, and `_trips.css`. Mobile experience is poor — pages just narrow without adapting layout.

For a flow that asks users for credit card information, the unpolished appearance undermines trust.

## Approach

Clean-slate rewrite of HTML templates and CSS, preserving the JS contract. The Stripe payment JS (`script.js`, `social_event.js`) relies on specific element IDs, a handful of CSS classes, and data attributes — not on the styling classes. Everything else can be replaced.

### JS Contract (must preserve)

**Element IDs:** `#card-element`, `#card-errors`, `#name`, `#email`, `#submit`, `#spinner`, `#button-text`, `#registration-form`, `#register-btn`, `#button-spinner`

**CSS classes used by JS:** `.payment-view`, `.completed-view`, `.hidden`, `.field-error`, `.price-option-container`

**Data attributes:** `data-event-id`, `data-season-id`, `data-price-cents`, `data-value` (on price option containers)

**Radio input names:** `price-choice`, `status`, `technique`, `experience`

**Form field names:** `email`, `firstName`, `lastName`, `pronouns`, `dob`, `phone`, `tshirtSize`, `emergencyName`, `emergencyRelation`, `emergencyPhone`, `emergencyEmail`, `name`, `agreement`

## Visual Direction

Balance of "Clean & Minimal" (Stripe/Linear feel — white space, subtle borders, refined type) and "Warm & Inviting" (rounded elements, approachable feel, community vibe).

### Design Tokens

| Token | Value | Usage |
|-------|-------|-------|
| Primary | `#1c2c44` | Headings, buttons, selected states |
| Mint | `#acf3c4` | Existing brand accent (social badge on homepage) |
| Background | `#f8fafb` | Page background |
| Card bg | `white` | Cards, inputs |
| Border | `#e5e7eb` | Card borders, input borders |
| Border thickness | `1.5px` | Inputs, selected cards |
| Text primary | `#1c2c44` | Headings, prices |
| Text secondary | `#475569` | Labels |
| Text muted | `#64748b` | Descriptions, metadata |
| Text faint | `#94a3b8` | Placeholders, subtext |
| Border radius (cards) | `12px` | Cards, price selectors |
| Border radius (inputs) | `10px` | Inputs, buttons, pills |
| Border radius (badges) | `12px` (small) / `20px` (section pills) | Status badges, section labels |
| Font stack | `-apple-system, BlinkMacSystemFont, sans-serif` | Same as current |

### Status Badge Colors

| Status | Background | Text |
|--------|-----------|------|
| Open | `#dcfce7` | `#166534` |
| Upcoming | `#dbeafe` | `#1e40af` |
| Closed | `#f1f5f9` | `#64748b` |

### Section Pill Colors (Homepage)

| Section | Background | Text |
|---------|-----------|------|
| Membership | `#1c2c44` | `white` |
| Trips | `#dbeafe` | `#1e40af` |
| Social Events | `#d1fae5` | `#065f46` |

## Page Designs

### 1. Homepage (`index.html`)

**Layout:** TCSC logo centered in a white header bar with bottom border. Below, content area with `max-width: 720px` centered on `#f8fafb` background.

**Sections:** Three sections, each rendered only if content exists: Membership, Trips, Social Events. Each section has a colored pill label and 36px vertical spacing between sections.

**Cards:** Consistent structure across all types:
- White background, `1px solid #e5e7eb` border, `12px` border radius
- `24px` padding, flexbox column with `12px` gap
- Title (17px, 600 weight, navy)
- Metadata lines (13px, `#64748b`, emoji prefixed: 📍 location, 📅 date, 🕐 time)
- Description (14px, `#64748b`, 1.5 line height)
- Bottom row pinned with `margin-top: auto`: price (17px, 700 weight) left, button right

**Season card specifics:** Status badge pill (Open/Upcoming/Closed) positioned top-right of title row. Registration window closing info as muted subtext (13px, `#94a3b8`).

**Social event card specifics:** No per-card badge needed since the section pill identifies the type.

**Trip/social grid:** 2-column CSS grid within each section, `16px` gap. Stacks to 1-column below `640px`.

**Season grid:** Single card (no grid needed, but use same card styling).

**Empty state:** If no trips and no social events exist, show nothing (no "coming soon" placeholder). The homepage just shows whatever sections have content.

### 2. Trip Registration (`trips/base_trip.html`)

**Layout:** Logo header (same as homepage). Content area `max-width: 420px` centered, `32px` padding.

**Header:** Trip name (22px, 600 weight, centered) with metadata below (13px, `#64748b`, emoji prefixed, flex row centered).

**Price selection (multi-price trips):** Two card-style selectors side by side. Label "Select Price" above. Each card: `border-radius: 10px`, `14px` padding, centered. Label is "Lower Price" / "Higher Price" (12px, muted) with dollar amount below (18px, 700 weight). Selected card: navy background, white text, `1.5px` navy border. Unselected: white background, `1.5px` `#e5e7eb` border.

These cards still use `.price-option-container` with `data-value` and contain `input[name="price-choice"]` radios (visually hidden, toggled by card click) to preserve JS contract.

**Single price trips:** Summary bar — `#f8fafb` background, `1px` border, `10px` radius, flex row with label left and price right.

**Form fields:** Full Name and Email, each with label above (13px, 500 weight, `#475569`), input below (white, `1.5px` border, `10px` radius, `12px 14px` padding). `16px` gap between fields.

**Stripe card element:** Same input styling wrapper. Stripe mounts into `#card-element`.

**Lottery notice:** Warm yellow callout (`background: #fefce8`, `border: 1px solid #fde68a`, `10px` radius). Text in `#854d0e`. Replaces the current harsh red legal box.

**Submit button:** Full width, navy background, white text, `14px` padding, `10px` radius, 600 weight. Text: "Register — $XXX.XX" (shows selected price).

**Success view:** Same `.completed-view` / `.payment-view` toggle mechanism. Clean centered message with success heading and explanation text.

### 3. Social Event Registration (`socials/registration.html`)

**Layout:** Same as trip registration (`420px` max-width).

**Header:** Green "Social Event" pill badge above event name. Event name (22px, centered), metadata below (location, date, time).

**Price:** Summary bar (same as single-price trip).

**Form:** Name, Email, Card — same styling as trip form.

**No lottery notice** — social events charge immediately.

**Submit button:** "Pay — $XX.XX".

### 4. Season Registration (`season_register.html`)

**Layout:** Logo header. Content area `max-width: 560px` centered, `32px 24px` padding.

**Sticky progress bar:** Fixed below the header on scroll. White background, bottom border. 4 numbered steps connected by lines: "About You", "Skiing", "Emergency", "Payment".

Step indicator states:
- **Active (current section in viewport):** Navy circle with white number, navy label text (600 weight)
- **Completed:** Navy circle with white checkmark, navy label text
- **Upcoming:** `#e5e7eb` circle with `#94a3b8` number, `#94a3b8` label text

Clicking a step smooth-scrolls to that section. Active step updates based on scroll position (IntersectionObserver).

**Section structure:** Each section has:
- Heading (20px, 600 weight, navy)
- Subtitle (14px, `#94a3b8`)
- `24px` gap below subtitle before fields
- Thin `1px #e5e7eb` divider with `48px` margin before next section

**Section 1 — About You:**
- Email field (full width) with membership status feedback below (green checkmark + "Returning member found" or orange indicator)
- Member type: pill selectors ("New Member" / "Returning / Former") — visually styled pills wrapping hidden radio inputs `name="status"`
- First Name + Last Name (side by side)
- Pronouns + Date of Birth (side by side)
- Phone + T-Shirt Size (side by side, t-shirt as select dropdown)

**Section 2 — Skiing Details:**
- Preferred Technique: pill selectors (Classic / Skate / No Preference)
- Experience Level: pill selectors (Beginner 1–3 yr / Intermediate 3–7 yr / Advanced 7+ yr) with year range as smaller muted text within pill

**Section 3 — Emergency Contact:**
- Contact Name + Relationship (side by side)
- Phone + Email (side by side)

**Section 4 — Payment:**
- Price summary bar (same style as trip/social)
- Name on Card (full width)
- Card Details (Stripe element)
- Agreement: contained in a light box (`#fafafa` background, `1px` border, `10px` radius) with checkbox and link text
- Submit button: "Register & Pay — $XXX.XX"

**Side-by-side fields:** All paired fields use `display: flex; gap: 12px`. Below `640px`, stack to single column.

**Pill selectors:** Styled as clickable rounded buttons. Selected: navy background, white text, navy border. Unselected: `#f1f5f9` background, `#64748b` text, `#e5e7eb` border. Each pill wraps a hidden radio input to preserve form submission and JS contract.

**Form state persistence:** Existing localStorage mechanism continues to work — field `name` attributes are unchanged.

### 5. Season Success (`season_success.html`)

Light polish to match new design language. Same centered layout, same conditional content (payment hold vs immediate charge). Updated typography, spacing, and button styling to match.

## CSS Architecture

Replace the current fragmented CSS with a single clean file structure:

### Files to replace
- `_tokens.css` — replace entirely with new token values (no backward-compat needed since triathlon page is also being cut over)
- `_registration.css` — delete, replace with new
- `_forms.css` — delete, replace with new
- `_trips.css` — delete, replace with new
- `_buttons.css` — delete, replace with new
- `_layout.css` (in `layout/`) — delete, replace with new (currently defines `sr-root`/`sr-main`)
- `_header.css` — delete, replace with new (currently defines `sr-header`)
- `_states.css` — delete, replace with new (focus states, `.hidden`, error styles)
- `_animations.css` — delete, replace with new (spinner, form entry animations)
- `_media-queries.css` — delete (responsive styles will live in each component file)

- `_triathlon.css` — delete, restyle within new design system

### Files to keep unchanged
- `_reset.css` — basic box-sizing and body font, still needed

### New CSS structure
- `base/_tokens.css` — clean slate with new semantic tokens (`--color-primary`, `--color-mint`, `--bg-page`, `--bg-card`, `--border`, `--border-input`, `--radius-card`, `--radius-input`, `--text-primary`, `--text-secondary`, `--text-muted`, `--text-faint`, `--font-stack`)
- `components/_cards.css` — homepage cards (shared across season/trip/social)
- `components/_forms.css` — all form inputs, labels, pill selectors, field layout
- `components/_progress.css` — sticky progress bar component
- `components/_buttons.css` — button styles
- `components/_badges.css` — status badges and section pills
- `components/_layout.css` — page layout (header, content containers, grid)
- `components/_notices.css` — lottery notice, error display, membership status feedback
- `states/_states.css` — `.hidden`, focus states, `.field-error`, disabled states, spinner animation

### JS-coupled styles that must exist in the new CSS
- `.hidden { display: none }` — used by payment JS for view toggling
- `.field-error` — red border for validation errors on season form
- `.spinner` — loading animation for trip payment button (referenced by `#spinner` element)
- `.payment-view` / `.completed-view` — no inherent styles needed, just used as selectors by JS for `.hidden` toggling

### Key CSS principles
- No nesting beyond one level (`.form-field .label`, not `.registration-form .form-section .form-group label`)
- No `!important`
- BEM-lite naming: `.card`, `.card__title`, `.card__price` (not `.sr-root .sr-main .sr-header__title`)
- Mobile-first: base styles for mobile, `min-width: 640px` breakpoint for side-by-side fields and 2-column grid

### 6. Dryland Triathlon (`dryland-triathlon.html`)

Static info page with external registration links (Google Forms, not Stripe). Cut over to new design language.

**Layout:** Same logo header as all other pages. Content area `max-width: 560px` centered, `32px 24px` padding.

**Hero:** Event name "Roll. Ride. Run." as a heading (28px, 700 weight) centered, with date and location below (15px, `#64748b`). Contained in a light background section with subtle gradient (using `--bg-page` tones). Remove the Font Awesome dependency — this page was the last to reference it via the shared `sr-header`.

**Course cards:** Two side-by-side cards (same card styling as homepage — white, `1px` border, `12px` radius). Each shows course name (bold), distances, and start time. Stacks on mobile.

**Registration buttons:** Two side-by-side cards styled like the trip price selectors — navy background, white text, clickable. Show "Individual / $55" and "Team / $105". These link to external Google Forms.

**Sections:** Each section (About, Distances, Team Finder, About TCSC) uses the same heading style as season form sections (20px, 600 weight, navy) with body text below (15px, `#64748b`, 1.5 line height).

**Back link:** Styled as a secondary button (outlined or text-style) rather than the current full-width navy button.

**Participant guide link:** Styled as an inline text link, not a special callout box.

## main.css Import Manifest

The `main.css` file must be updated to import the new file structure:

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

Remove imports for deleted files: `_header.css`, `_trips.css`, `_registration.css`, `_animations.css`, `_media-queries.css`, old `_layout.css`.

## New JS: Progress Bar

Small new script for the season registration page only:

- Uses IntersectionObserver to detect which section is in the viewport
- Updates progress bar active/completed states
- Click handlers on steps for smooth scroll to section
- No changes to existing `script.js` or `social_event.js`

## Scope

### In scope
- Homepage (`index.html`)
- Trip registration (`trips/base_trip.html`)
- Social event registration (`socials/registration.html`)
- Season registration form (`season_register.html`)
- Season success page (`season_success.html`)
- Dryland triathlon page (`dryland-triathlon.html`)
- All CSS files under `css/styles/` (full replacement)
- New progress bar JS for season form

### Out of scope
- Admin pages
- Route handlers / backend logic
- Payment JS logic (`script.js`, `social_event.js`) — no changes beyond what's needed to match new class names for the ~5 JS-coupled classes
- Season detail page (`season_detail.html`) — only if it shares CSS that changes
- Individual trip template overrides (e.g., `birkie.html`) — they extend `base_trip.html` so they get the update automatically

## Mobile Behavior

- Below `640px`: side-by-side fields stack to single column, 2-column card grid becomes 1-column
- Homepage section pills and card structure unchanged on mobile
- Progress bar steps collapse to show only step numbers (hide labels) below `480px`
- Form padding reduces from `32px` to `20px` on mobile
- Inputs maintain `44px` minimum tap target height
