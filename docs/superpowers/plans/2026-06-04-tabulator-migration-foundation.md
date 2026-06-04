# Tabulator Migration — Foundation, Orchestration & Endgame Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and freeze the thin shared frontend foundation (WF-0) that every per-surface Tabulator-migration workflow stands on, define the procedure for launching the 8 surface workflows in parallel, and specify the hard-gated CDN-removal endgame (WF-9).

**Architecture:** A small `window.AdminUI` namespace of vanilla-JS primitives (no build step, IIFE modules loaded via `<script>` in `admin_base.html`, matching the repo's existing pattern of `js/toast.js` + global scripts) plus one scoped CSS partial. The primitives are consistency tools (status badge, filter bar, preview drawer, pill selectors, focus-trap, a tiny data layer), not a framework. They are committed and frozen before any surface workflow starts; surface workflows treat them as read-only.

**Tech Stack:** Vanilla ES5-compatible JS (IIFE, `window.AdminUI`), Tailwind tokens already compiled into `css/tailwind-output.css`, scoped CSS in `css/admin_ui.css`, existing global `showToast` from `js/toast.js`. Verification via a static browser harness (`console.assert`), consistent with the repo having no JS test runner.

**Companion spec:** `docs/superpowers/specs/2026-06-04-tabulator-migration-design.md`

---

## File Structure

Created by this plan:

- `app/static/js/admin/_core.js` — `AdminUI` namespace, `escapeHtml`, `el()` DOM builder, `onReady`
- `app/static/js/admin/status_badge.js` — `AdminUI.statusBadge(text, variant)`
- `app/static/js/admin/focus_trap.js` — `AdminUI.trapFocus(container)` → release fn
- `app/static/js/admin/drawer.js` — `AdminUI.drawer({title, content})` singleton right-side drawer
- `app/static/js/admin/filter_bar.js` — `AdminUI.filterBar(mount, config, onChange)`
- `app/static/js/admin/pills.js` — `AdminUI.pills(mount, items, opts)` → `{getSelected}`
- `app/static/js/admin/data.js` — `AdminUI.fetchJSON(url)`, `AdminUI.mutate(url, body)`
- `app/static/css/admin_ui.css` — scoped styles for all primitives (`.admin-ui-*`)
- `app/static/admin/foundation_harness.html` — browser verification harness

Modified by this plan:

- `app/templates/admin/admin_base.html` — load the foundation CSS + JS (WF-0); remove Tabulator CDN (WF-9)

Each primitive lives in its own focused file so a surface workflow can read exactly the one it needs.

---

## WF-0 — Shared Foundation

> **Build note (frozen 2026-06-04):** the code blocks below are the as-authored starting point.
> The frozen foundation files incorporate code-review refinements applied during the build (commit
> `86e9dfe`): the `el()` raw-HTML prop is named `unsafeHTML` (not `html`), `el()` warns-and-skips
> non-function `on*` props, the drawer exposes `content` (DOM node or safe text) vs `contentHTML`
> (opt-in raw HTML), and `focus_trap` uses `getClientRects().length`. **The committed files under
> `app/static/js/admin/` are the authoritative contract for surface workflows, not these blocks.**

### Task 1: Core namespace + DOM helpers

**Files:**
- Create: `app/static/js/admin/_core.js`

- [ ] **Step 1: Write the core module**

```javascript
// app/static/js/admin/_core.js
// AdminUI: thin shared frontend foundation for the admin panel.
// Loaded as a plain <script> (no build step). Each primitive registers onto window.AdminUI.
(function () {
  const AdminUI = window.AdminUI = window.AdminUI || {};

  // Escape a value for safe insertion as text/attribute content.
  AdminUI.escapeHtml = function (value) {
    if (value === null || value === undefined) return '';
    return String(value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  };

  // el('div', {class:'x', onclick: fn, dataset:{id:1}, html:'<b>x</b>'}, [child, ...])
  // - 'class' sets className; 'dataset' merges data-* attrs; 'html' sets innerHTML.
  // - keys starting with 'on' + a function become event listeners.
  // - any other non-null value becomes an attribute.
  // children may be DOM nodes or strings (inserted as text nodes).
  AdminUI.el = function (tag, props, children) {
    const node = document.createElement(tag);
    if (props) {
      Object.keys(props).forEach(function (key) {
        const val = props[key];
        if (key === 'class') node.className = val;
        else if (key === 'dataset') Object.assign(node.dataset, val);
        else if (key === 'html') node.innerHTML = val;
        else if (key.slice(0, 2) === 'on' && typeof val === 'function') {
          node.addEventListener(key.slice(2).toLowerCase(), val);
        } else if (val !== null && val !== undefined) {
          node.setAttribute(key, val);
        }
      });
    }
    (children || []).forEach(function (child) {
      if (child === null || child === undefined) return;
      node.appendChild(typeof child === 'string' ? document.createTextNode(child) : child);
    });
    return node;
  };

  // Run fn once the DOM is ready (now if already past loading).
  AdminUI.onReady = function (fn) {
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', fn);
    } else {
      fn();
    }
  };
})();
```

- [ ] **Step 2: Commit**

```bash
git add app/static/js/admin/_core.js
git commit -m "feat(admin-ui): core namespace + DOM helpers"
```

---

### Task 2: Status badge primitive

**Files:**
- Create: `app/static/js/admin/status_badge.js`

- [ ] **Step 1: Write the module**

```javascript
// app/static/js/admin/status_badge.js
// statusBadge(text, variant) -> <span> with a color dot + text (color + dot + text for a11y).
(function () {
  const AdminUI = window.AdminUI = window.AdminUI || {};

  // Logical variant -> Tailwind color pair (already compiled in tailwind-output.css).
  const VARIANTS = {
    success: 'bg-green-50 text-green-700',
    danger:  'bg-red-50 text-red-700',
    warning: 'bg-amber-50 text-amber-700',
    info:    'bg-blue-50 text-blue-700',
    neutral: 'bg-zinc-100 text-zinc-600'
  };

  AdminUI.statusBadge = function (text, variant) {
    const cls = VARIANTS[variant] || VARIANTS.neutral;
    return AdminUI.el('span', { class: 'admin-ui-badge ' + cls }, [
      AdminUI.el('span', { class: 'admin-ui-badge__dot', 'aria-hidden': 'true' }, []),
      String(text == null ? '' : text)
    ]);
  };
})();
```

- [ ] **Step 2: Commit**

```bash
git add app/static/js/admin/status_badge.js
git commit -m "feat(admin-ui): status badge primitive"
```

---

### Task 3: Focus-trap utility

**Files:**
- Create: `app/static/js/admin/focus_trap.js`

- [ ] **Step 1: Write the module**

```javascript
// app/static/js/admin/focus_trap.js
// trapFocus(container) -> release() : cycle Tab within container, restore focus on release.
(function () {
  const AdminUI = window.AdminUI = window.AdminUI || {};
  const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]), ' +
    'select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

  AdminUI.trapFocus = function (container) {
    const previouslyFocused = document.activeElement;

    function focusables() {
      return Array.prototype.slice.call(container.querySelectorAll(FOCUSABLE))
        .filter(function (el) { return el.offsetParent !== null; });
    }

    function onKeydown(e) {
      if (e.key !== 'Tab') return;
      const items = focusables();
      if (items.length === 0) { e.preventDefault(); return; }
      const first = items[0];
      const last = items[items.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault(); last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault(); first.focus();
      }
    }

    container.addEventListener('keydown', onKeydown);
    const initial = focusables()[0];
    if (initial) initial.focus();

    return function release() {
      container.removeEventListener('keydown', onKeydown);
      if (previouslyFocused && typeof previouslyFocused.focus === 'function') {
        previouslyFocused.focus();
      }
    };
  };
})();
```

- [ ] **Step 2: Commit**

```bash
git add app/static/js/admin/focus_trap.js
git commit -m "feat(admin-ui): focus-trap utility"
```

---

### Task 4: Preview drawer

**Files:**
- Create: `app/static/js/admin/drawer.js`

- [ ] **Step 1: Write the module**

```javascript
// app/static/js/admin/drawer.js
// drawer({ title, content }) -> { close, body }. Singleton: opening closes any open drawer.
// Right-side panel with inert scrim, focus-trap, Esc + scrim-click to close.
(function () {
  const AdminUI = window.AdminUI = window.AdminUI || {};
  let current = null;

  AdminUI.drawer = function (opts) {
    opts = opts || {};
    if (current) current.close();

    const scrim = AdminUI.el('div', { class: 'admin-ui-drawer-scrim' }, []);
    const panel = AdminUI.el('aside', {
      class: 'admin-ui-drawer', role: 'dialog', 'aria-modal': 'true',
      'aria-label': opts.title || 'Details'
    }, []);

    const body = AdminUI.el('div', { class: 'admin-ui-drawer__body' }, []);
    if (typeof opts.content === 'string') body.innerHTML = opts.content;
    else if (opts.content) body.appendChild(opts.content);

    const header = AdminUI.el('div', { class: 'admin-ui-drawer__header' }, [
      AdminUI.el('h2', { class: 'admin-ui-drawer__title' }, [opts.title || '']),
      AdminUI.el('button', {
        class: 'admin-ui-drawer__close', type: 'button',
        'aria-label': 'Close', onclick: close
      }, ['×'])
    ]);

    panel.appendChild(header);
    panel.appendChild(body);
    document.body.appendChild(scrim);
    document.body.appendChild(panel);
    document.body.classList.add('admin-ui-no-scroll');
    requestAnimationFrame(function () { panel.classList.add('is-open'); });

    const release = AdminUI.trapFocus(panel);
    scrim.addEventListener('click', close);
    function onEsc(e) { if (e.key === 'Escape') close(); }
    document.addEventListener('keydown', onEsc);

    function close() {
      if (current !== api) return;
      document.removeEventListener('keydown', onEsc);
      release();
      panel.remove();
      scrim.remove();
      document.body.classList.remove('admin-ui-no-scroll');
      current = null;
    }

    const api = { close: close, body: body };
    current = api;
    return api;
  };
})();
```

- [ ] **Step 2: Commit**

```bash
git add app/static/js/admin/drawer.js
git commit -m "feat(admin-ui): preview drawer primitive"
```

---

### Task 5: Filter bar

**Files:**
- Create: `app/static/js/admin/filter_bar.js`

- [ ] **Step 1: Write the module**

```javascript
// app/static/js/admin/filter_bar.js
// filterBar(mountEl, config, onChange) renders the shared filter UI and emits a state object.
// config = {
//   search:  { placeholder },                                    // optional
//   selects: [ { key, label, options:[{value,label}] } ],        // optional
//   pills:   [ { key, label, multi, options:[{value,label}] } ]  // optional
// }
// onChange(state): state = { search:'', <selectKey>:'', <pillKey>:[...] }
(function () {
  const AdminUI = window.AdminUI = window.AdminUI || {};

  AdminUI.filterBar = function (mountEl, config, onChange) {
    config = config || {};
    const state = { search: '' };
    const root = AdminUI.el('div', { class: 'admin-ui-filterbar' }, []);

    if (config.search) {
      const input = AdminUI.el('input', {
        type: 'search', class: 'admin-ui-filterbar__search',
        placeholder: config.search.placeholder || 'Search...',
        oninput: function () { state.search = input.value; emit(); }
      }, []);
      root.appendChild(input);
    }

    (config.selects || []).forEach(function (sel) {
      state[sel.key] = '';
      const node = AdminUI.el('select', {
        class: 'admin-ui-filterbar__select', 'aria-label': sel.label,
        onchange: function () { state[sel.key] = node.value; emit(); }
      }, [AdminUI.el('option', { value: '' }, [sel.label])].concat(
        sel.options.map(function (o) {
          return AdminUI.el('option', { value: o.value }, [o.label]);
        })
      ));
      root.appendChild(node);
    });

    (config.pills || []).forEach(function (group) {
      state[group.key] = [];
      const wrap = AdminUI.el('div', {
        class: 'admin-ui-filterbar__pills', role: 'group', 'aria-label': group.label
      }, []);
      group.options.forEach(function (o) {
        const btn = AdminUI.el('button', {
          type: 'button', class: 'admin-ui-pill', 'aria-pressed': 'false',
          onclick: function () { togglePill(group, o.value, btn); }
        }, [o.label]);
        wrap.appendChild(btn);
      });
      root.appendChild(wrap);
    });

    function togglePill(group, value, btn) {
      const arr = state[group.key];
      const idx = arr.indexOf(value);
      if (group.multi) {
        if (idx === -1) arr.push(value); else arr.splice(idx, 1);
      } else {
        state[group.key] = (idx === -1) ? [value] : [];
        Array.prototype.forEach.call(btn.parentNode.children, function (b) {
          b.classList.remove('is-active'); b.setAttribute('aria-pressed', 'false');
        });
      }
      const active = state[group.key].indexOf(value) !== -1;
      btn.classList.toggle('is-active', active);
      btn.setAttribute('aria-pressed', active ? 'true' : 'false');
      emit();
    }

    function emit() { onChange(Object.assign({}, state)); }

    mountEl.appendChild(root);
    return { state: state, emit: emit };
  };
})();
```

- [ ] **Step 2: Commit**

```bash
git add app/static/js/admin/filter_bar.js
git commit -m "feat(admin-ui): shared filter bar"
```

---

### Task 6: Form pill selector

**Files:**
- Create: `app/static/js/admin/pills.js`

- [ ] **Step 1: Write the module**

```javascript
// app/static/js/admin/pills.js
// pills(mountEl, items, opts) -> { getSelected }
// items = [{ id, label }]; opts = { multi:true, selected:[ids] }
// Selection is held in a Set and read at submit time (no hidden inputs).
(function () {
  const AdminUI = window.AdminUI = window.AdminUI || {};

  AdminUI.pills = function (mountEl, items, opts) {
    opts = opts || {};
    const multi = opts.multi !== false;
    const selected = new Set(opts.selected || []);

    // dataset values are strings; coerce back to number when the id was numeric.
    function coerce(v) {
      const asNum = Number(v);
      return (v !== '' && String(asNum) === v) ? asNum : v;
    }

    items.forEach(function (item) {
      const isOn = selected.has(item.id);
      const btn = AdminUI.el('button', {
        type: 'button',
        class: 'admin-ui-pill' + (isOn ? ' is-active' : ''),
        'aria-pressed': isOn ? 'true' : 'false',
        dataset: { id: item.id },
        onclick: function () {
          if (selected.has(item.id)) selected.delete(item.id);
          else { if (!multi) selected.clear(); selected.add(item.id); }
          syncAll();
        }
      }, [item.label]);
      mountEl.appendChild(btn);
    });

    function syncAll() {
      Array.prototype.forEach.call(mountEl.querySelectorAll('.admin-ui-pill'), function (btn) {
        const on = selected.has(coerce(btn.dataset.id));
        btn.classList.toggle('is-active', on);
        btn.setAttribute('aria-pressed', on ? 'true' : 'false');
      });
    }

    return { getSelected: function () { return Array.from(selected); } };
  };
})();
```

- [ ] **Step 2: Commit**

```bash
git add app/static/js/admin/pills.js
git commit -m "feat(admin-ui): form pill selector"
```

---

### Task 7: Data layer

**Files:**
- Create: `app/static/js/admin/data.js`

- [ ] **Step 1: Write the module**

```javascript
// app/static/js/admin/data.js
// fetchJSON(url): GET -> parsed JSON (rejects on non-2xx).
// mutate(url, body): POST JSON; toasts success/error via global showToast (js/toast.js).
(function () {
  const AdminUI = window.AdminUI = window.AdminUI || {};

  AdminUI.fetchJSON = function (url) {
    return fetch(url, { headers: { 'Accept': 'application/json' } })
      .then(function (res) {
        if (!res.ok) throw new Error('HTTP ' + res.status);
        return res.json();
      });
  };

  AdminUI.mutate = function (url, body) {
    return fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
      body: JSON.stringify(body || {})
    }).then(function (res) {
      return res.json().catch(function () { return {}; }).then(function (data) {
        if (!res.ok || data.success === false) {
          const msg = (data && (data.error || data.message)) ||
            ('Request failed (' + res.status + ')');
          if (window.showToast) showToast(msg, 'error');
          throw new Error(msg);
        }
        if (data.message && window.showToast) showToast(data.message, 'success');
        return data;
      });
    });
  };
})();
```

- [ ] **Step 2: Commit**

```bash
git add app/static/js/admin/data.js
git commit -m "feat(admin-ui): data fetch + mutate layer"
```

---

### Task 8: Scoped CSS partial

**Files:**
- Create: `app/static/css/admin_ui.css`

- [ ] **Step 1: Write the stylesheet**

```css
/* app/static/css/admin_ui.css
   Scoped styles for AdminUI foundation primitives. All selectors are .admin-ui-* . */

/* --- Status badge --- */
.admin-ui-badge {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 2px 10px; border-radius: 9999px;
  font-size: 12px; font-weight: 600; line-height: 1.4;
}
.admin-ui-badge__dot { width: 6px; height: 6px; border-radius: 50%; background: currentColor; }

/* --- Pills (filter + form) --- */
.admin-ui-pill {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 6px 12px; border-radius: 9999px;
  border: 1px solid #d4d4d8; background: #fff; color: #3f3f46;
  font-size: 13px; font-weight: 500; cursor: pointer;
}
.admin-ui-pill.is-active { background: #1c2c44; border-color: #1c2c44; color: #fff; }
.admin-ui-pill:focus-visible { outline: 2px solid #1c2c44; outline-offset: 2px; }

/* --- Filter bar --- */
.admin-ui-filterbar {
  display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin-bottom: 16px;
}
.admin-ui-filterbar__search, .admin-ui-filterbar__select {
  padding: 8px 12px; border: 1px solid #d4d4d8; border-radius: 8px; font-size: 14px;
}
.admin-ui-filterbar__search { flex: 1; min-width: 180px; }
.admin-ui-filterbar__pills { display: flex; flex-wrap: wrap; gap: 6px; }

/* --- Drawer --- */
.admin-ui-drawer-scrim { position: fixed; inset: 0; z-index: 60; background: rgba(0,0,0,0.3); }
.admin-ui-drawer {
  position: fixed; top: 0; right: 0; z-index: 61;
  height: 100vh; width: 420px; max-width: 100vw;
  background: #fff; box-shadow: -4px 0 24px rgba(0,0,0,0.12);
  display: flex; flex-direction: column;
  transform: translateX(100%); transition: transform .2s ease;
}
.admin-ui-drawer.is-open { transform: translateX(0); }
.admin-ui-drawer__header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 16px 20px; border-bottom: 1px solid #e4e4e7;
}
.admin-ui-drawer__title { font-size: 16px; font-weight: 600; margin: 0; }
.admin-ui-drawer__close {
  font-size: 22px; line-height: 1; background: none; border: 0;
  cursor: pointer; color: #71717a; padding: 4px 8px;
}
.admin-ui-drawer__close:focus-visible { outline: 2px solid #1c2c44; outline-offset: 2px; }
.admin-ui-drawer__body { padding: 20px; overflow-y: auto; flex: 1; }
.admin-ui-no-scroll { overflow: hidden; }

/* --- Sticky save bar (for bespoke edit pages) --- */
.admin-ui-sticky-bar {
  position: sticky; bottom: 0;
  display: flex; gap: 12px; justify-content: flex-end;
  padding: 12px 0; background: #fff; border-top: 1px solid #e4e4e7;
}

@media (max-width: 767px) {
  .admin-ui-drawer { width: 100vw; }
  .admin-ui-sticky-bar { padding-bottom: calc(12px + env(safe-area-inset-bottom)); }
}
```

- [ ] **Step 2: Commit**

```bash
git add app/static/css/admin_ui.css
git commit -m "feat(admin-ui): scoped CSS for foundation primitives"
```

---

### Task 9: Browser verification harness

**Files:**
- Create: `app/static/admin/foundation_harness.html`

- [ ] **Step 1: Write the harness page**

```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AdminUI foundation harness</title>
  <link rel="stylesheet" href="../css/admin_ui.css">
  <style> body { padding: 24px; font-family: system-ui, sans-serif; color: #1c2c44; } h2 { margin-top: 28px; } </style>
</head>
<body>
  <h1>AdminUI foundation harness</h1>
  <p>Open the browser console. Every check must log <strong>PASS</strong>; no assertion should fire.</p>

  <h2>Status badges</h2>
  <div id="badges"></div>

  <h2>Filter bar</h2>
  <div id="filter"></div>
  <pre id="filter-state">(interact with the filter bar; state prints here)</pre>

  <h2>Form pills</h2>
  <div id="pills"></div>

  <h2>Drawer</h2>
  <button id="open-drawer" class="admin-ui-pill" type="button">Open drawer</button>

  <script src="../js/admin/_core.js"></script>
  <script src="../js/admin/status_badge.js"></script>
  <script src="../js/admin/focus_trap.js"></script>
  <script src="../js/admin/drawer.js"></script>
  <script src="../js/admin/filter_bar.js"></script>
  <script src="../js/admin/pills.js"></script>
  <script src="../js/admin/data.js"></script>
  <script>
    function check(name, cond) {
      console.assert(cond, 'FAIL: ' + name);
      if (cond) console.log('PASS: ' + name);
    }

    // _core
    check('escapeHtml escapes', AdminUI.escapeHtml('<a>&"\'') === '&lt;a&gt;&amp;&quot;&#39;');
    check('el sets class', AdminUI.el('div', { class: 'x' }, ['hi']).className === 'x');
    check('el sets dataset', AdminUI.el('div', { dataset: { id: 5 } }, []).dataset.id === '5');

    // status badge
    var b = AdminUI.statusBadge('Active', 'success');
    document.getElementById('badges').append(
      AdminUI.statusBadge('Active', 'success'),
      AdminUI.statusBadge('Refunded', 'danger'),
      AdminUI.statusBadge('Pending', 'warning'),
      AdminUI.statusBadge('Unknown')
    );
    check('badge has dot', b.querySelector('.admin-ui-badge__dot') !== null);
    check('badge has text', b.textContent.indexOf('Active') !== -1);

    // filter bar
    var fb = AdminUI.filterBar(document.getElementById('filter'), {
      search: { placeholder: 'Search members...' },
      selects: [{ key: 'status', label: 'Status', options: [{ value: 'ACTIVE', label: 'Active' }] }],
      pills: [{ key: 'tier', label: 'Tier', multi: true,
                options: [{ value: 'a', label: 'A' }, { value: 'b', label: 'B' }] }]
    }, function (s) { document.getElementById('filter-state').textContent = JSON.stringify(s); });
    check('filter initial state shape', 'search' in fb.state && 'status' in fb.state && Array.isArray(fb.state.tier));

    // form pills
    var p = AdminUI.pills(document.getElementById('pills'),
      [{ id: 1, label: 'Coach' }, { id: 2, label: 'Lead' }], { multi: true, selected: [1] });
    check('pills preselected', p.getSelected().length === 1 && p.getSelected()[0] === 1);

    // data layer present
    check('fetchJSON defined', typeof AdminUI.fetchJSON === 'function');
    check('mutate defined', typeof AdminUI.mutate === 'function');

    // drawer (manual + assert)
    document.getElementById('open-drawer').addEventListener('click', function () {
      AdminUI.drawer({ title: 'Member detail',
        content: AdminUI.el('p', null, ['Drawer body. Esc or click the scrim to close.']) });
      check('drawer mounted', document.querySelector('.admin-ui-drawer') !== null);
    });

    console.log('Harness loaded. Click "Open drawer" to verify drawer + focus-trap manually.');
  </script>
</body>
</html>
```

- [ ] **Step 2: Start the dev server**

Run: `./scripts/dev.sh 5001`
Expected: Flask serves on `http://localhost:5001`.

- [ ] **Step 3: Open the harness and verify**

Open: `http://localhost:5001/static/admin/foundation_harness.html`
Expected in console: a row of `PASS:` lines, **zero** `FAIL:`/assertion errors. Visually: four status badges render with colored dots; the filter bar shows a search box, a Status select, and two Tier pills (clicking a pill toggles `is-active` and updates the printed state); two form pills with "Coach" preselected.

- [ ] **Step 4: Verify the drawer manually**

Click **Open drawer**. Expected: panel slides in from the right over a dim scrim; focus moves into the panel; Tab cycles inside it; Esc and scrim-click both close it and return focus to the button. Resize to ≤767px and confirm the drawer becomes full-width.

- [ ] **Step 5: Commit**

```bash
git add app/static/admin/foundation_harness.html
git commit -m "test(admin-ui): browser verification harness for foundation"
```

---

### Task 10: Wire the foundation into admin_base.html

**Files:**
- Modify: `app/templates/admin/admin_base.html` (CSS after line 10; JS after line 97)

- [ ] **Step 1: Add the foundation CSS link**

After the Tailwind stylesheet line (`app/templates/admin/admin_base.html:10`), add:

```html
    <!-- AdminUI foundation styles -->
    <link rel="stylesheet" href="{{ url_for('static', filename='css/admin_ui.css') }}">
```

- [ ] **Step 2: Add the foundation JS modules**

Immediately after the toast script (`app/templates/admin/admin_base.html:97`), add (order matters — `_core` first):

```html
    <!-- AdminUI foundation (load _core first) -->
    <script src="{{ url_for('static', filename='js/admin/_core.js') }}"></script>
    <script src="{{ url_for('static', filename='js/admin/status_badge.js') }}"></script>
    <script src="{{ url_for('static', filename='js/admin/focus_trap.js') }}"></script>
    <script src="{{ url_for('static', filename='js/admin/drawer.js') }}"></script>
    <script src="{{ url_for('static', filename='js/admin/filter_bar.js') }}"></script>
    <script src="{{ url_for('static', filename='js/admin/pills.js') }}"></script>
    <script src="{{ url_for('static', filename='js/admin/data.js') }}"></script>
```

- [ ] **Step 3: Verify no regression on a real admin page**

With the dev server running, open `http://localhost:5001/admin/users` (or any admin page). In the console run:
```javascript
typeof AdminUI.statusBadge === 'function' && typeof AdminUI.drawer === 'function'
```
Expected: `true`. Confirm the existing Tabulator grid still renders (foundation is purely additive at this point) and there are no console errors.

- [ ] **Step 4: Commit**

```bash
git add app/templates/admin/admin_base.html
git commit -m "feat(admin-ui): load foundation CSS + JS in admin base"
```

---

### Task 11: Freeze the foundation

- [ ] **Step 1: Confirm the foundation surface is complete**

Run: `git log --oneline -11`
Expected: commits for `_core`, status badge, focus-trap, drawer, filter bar, pills, data layer, CSS, harness, base-wiring.

- [ ] **Step 2: Tag the freeze point**

```bash
git tag admin-ui-foundation-frozen
```

The foundation is now read-only for surface workflows. Any required change comes back here, gets a new commit, and re-tags (`git tag -f admin-ui-foundation-frozen`).

---

## WF-1..8 — Surface Workflows (launched in parallel)

These are **not** implemented as tasks in this plan. Each surface is its own dynamic workflow that
runs its own `/brainstorming → spec → /writing-plans → implement → verify` cycle in an isolated git
worktree, consuming the frozen foundation. Launch them only **after Task 11**.

### Task 12: Launch the 8 surface workflows in parallel

- [ ] **Step 1: Confirm the freeze**

Run: `git tag --list admin-ui-foundation-frozen`
Expected: the tag exists. Do not proceed otherwise.

- [ ] **Step 2: For each surface, create an isolated worktree**

Use `superpowers:using-git-worktrees`. One worktree per surface so the 8 run without touching each
other's files. Surfaces and the files each one owns (disjoint, except the frozen foundation which is
read-only and `admin_base.html` which is reserved for WF-9):

| Workflow | Owns (touch only these) |
|----------|-------------------------|
| WF-1 Members | `app/templates/admin/users.html`, `app/static/admin_users.js` |
| WF-2 Payments | `app/templates/admin/payments.html`, `app/static/admin_payments.js` |
| WF-3 Events | `app/templates/admin/trips.html`, `app/static/admin_trips.js`, `app/templates/admin/social_events.html`, `app/static/admin_social_events.js` |
| WF-4 Seasons | `app/templates/admin/seasons.html`, `app/static/admin_seasons.js` |
| WF-5 Roles | `app/templates/admin/roles.html` |
| WF-6 Practices config | `app/templates/admin/practices/config.html` |
| WF-7 Slack Sync | `app/templates/admin/slack_sync.html`, `app/static/admin_slack.js` |
| WF-8 Skipper | `app/templates/admin/skipper.html` |

- [ ] **Step 3: Seed each workflow with its charter, then start all 8 at once**

For each surface, fill the charter template from the design doc
(`docs/superpowers/specs/2026-06-04-tabulator-migration-design.md`, Section 8) with that surface's
row from Section 6 (Parity / UX hypothesis / Feature seeds / Edit approach / Files owned), and start
the workflow. The charter instructs the workflow to honor the migration canon (Section 3), reuse the
frozen foundation without modifying it, report foundation gaps back instead of patching, and treat
the surface as done only when parity is verified, lightweight feature seeds have landed, and mobile
is checked at 767px.

**Autonomous operation (required):** the charter template's AUTONOMY block makes every workflow
non-interactive from the moment it starts. Each `/brainstorming` cycle self-answers its clarifying
questions from the practices reference + its charter + existing codebase conventions, records any
residual assumption under an "Assumptions" heading in its own spec, and proceeds without prompting
the user. The only sanctioned stop is a hard technical blocker, which halts that one surface only.
This means all 8 can be launched together and run to completion unattended.

- [ ] **Step 4: Track completion**

A surface workflow is complete when its parity checklist passes, its branch is merged to the
integration branch, and its grid no longer instantiates Tabulator. Record each as it lands; WF-9 is
gated on all 8.

---

## WF-9 — Endgame (hard-gated on all 8 surfaces complete)

### Task 13: Remove Tabulator entirely

**Files:**
- Modify: `app/templates/admin/admin_base.html` (remove lines 7-8 CSS, lines 98-99 JS)

- [ ] **Step 1: Verify zero Tabulator instantiations remain**

Run: `grep -rn "new Tabulator" app/static app/templates`
Expected: **no output**. If anything prints, the owning surface workflow is not done — stop.

- [ ] **Step 2: Remove the Tabulator CDN includes**

In `app/templates/admin/admin_base.html`, delete the CSS include and its comment (currently lines 7-8):

```html
    <!-- Tabulator CSS (load first so our overrides take precedence) -->
    <link href="https://unpkg.com/tabulator-tables@5.5.2/dist/css/tabulator.min.css" rel="stylesheet">
```

and the JS include and its comment (currently lines 98-99):

```html
    <!-- Tabulator JS -->
    <script type="text/javascript" src="https://unpkg.com/tabulator-tables@5.5.2/dist/js/tabulator.min.js"></script>
```

- [ ] **Step 3: Purge leftover Tabulator CSS hooks**

Run: `grep -rn "tabulator" app/static app/templates`
Expected: **no output**. Remove any remaining `.tabulator-*` style rules, and the `tabulator-data` /
`tabulator-config` container classes from any template still carrying them, until the grep is clean.

- [ ] **Step 4: Smoke-test every admin page**

With the dev server running, load each migrated page and confirm it renders with no console errors,
on desktop and at a ≤767px viewport:
`/admin/users`, `/admin/payments`, `/admin/trips`, `/admin/social-events`, `/admin/seasons`,
`/admin/roles`, `/admin/practices/config`, `/admin/slack`, `/admin/skipper`.

- [ ] **Step 5: Commit**

```bash
git add app/templates/admin/admin_base.html
git commit -m "chore(admin): remove Tabulator dependency (migration complete)"
```

---

## Self-Review Notes

- **Spec coverage:** WF-0 foundation (spec §4) → Tasks 1-11; canon (spec §3) is embedded in the
  charter handoff (Task 12 Step 3); surface charters (spec §6) → Task 12; parallel execution model
  (spec §5.1) → Tasks 11-12; endgame (spec §7) → Task 13. The 8 surface implementations are
  intentionally deferred to their own dynamic workflows per the user's directive, so they are
  orchestrated (Task 12), not coded, here.
- **Placeholder scan:** the `<...>` in the charter template (Task 12 Step 3) is an intentional
  fill-from-spec instruction, not an unfinished step; every JS/CSS step carries complete code.
- **Type consistency:** primitive signatures are stable across the plan — `AdminUI.statusBadge`,
  `AdminUI.drawer`, `AdminUI.filterBar`, `AdminUI.pills`, `AdminUI.fetchJSON`, `AdminUI.mutate`,
  `AdminUI.trapFocus`, `AdminUI.el`, `AdminUI.escapeHtml`, `AdminUI.onReady` — and the harness +
  base wiring reference exactly those names and the same file paths.
