---
name: tailwind-migrate
description: Guide Tailwind CSS migration for TCSC Flask app. Use when converting pages to Tailwind, fixing CSS issues, or continuing the migration. Triggers on "tailwind", "migrate CSS", "style the page", or requests to work on public frontend UI.
---

# Tailwind Migration

Incremental migration of TCSC Trips from custom CSS to Tailwind CSS using Catalyst UI Kit patterns.

## Current Status

- **Admin UI**: Complete (minor CSS quirks remain)
- **Public Frontend**: Not started
- **Status tracking**: `docs/tailwind-migration/STATUS.md`

## Quick Reference

| Resource | Path |
|----------|------|
| Catalyst components | `~/env/catalyst-ui-kit/javascript/` |
| Catalyst demo app | `~/env/catalyst-ui-kit/demo/javascript/src/app/` |
| Component mappings | See [references/component-map.md](references/component-map.md) |
| Public frontend spec | See [references/public-frontend.md](references/public-frontend.md) |
| Migration status | `docs/tailwind-migration/STATUS.md` |

## Brand Colors

```javascript
// tailwind.config.js
'tcsc-navy': '#1c2c44',      // Primary
'tcsc-mint': '#acf3c4',      // Secondary/accent
'tcsc-gray': {
  50: 'rgba(28,44,68,0.03)',  // overlay
  100: 'rgba(28,44,68,0.15)', // border
  400: 'rgba(28,44,68,0.4)',  // light text
  600: 'rgba(28,44,68,0.7)',  // medium text
  800: 'rgba(28,44,68,0.9)',  // dark text
}
```

## Migration Workflow

### For Admin CSS Fixes

1. Identify the issue
2. Check [references/component-map.md](references/component-map.md) for Tailwind equivalents
3. Update classes in template
4. Test responsive behavior

### For Public Frontend Pages

1. Read [references/public-frontend.md](references/public-frontend.md) for design principles
2. Check `docs/tailwind-migration/STATUS.md` for current progress
3. Follow mobile-first approach
4. Update status after completing each page

## Key Patterns

### JSX to Jinja

```jsx
// Catalyst JSX
<div className="flex items-center gap-3">

// Jinja HTML
<div class="flex items-center gap-3">
```

- `className` → `class`
- `{children}` → `{% block content %}{% endblock %}`
- React state → Alpine.js (if needed)

### CSS Coexistence

Both systems load during migration:
```html
<link href="tailwind-output.css" rel="stylesheet">
<link href="styles/main.css" rel="stylesheet">
```
