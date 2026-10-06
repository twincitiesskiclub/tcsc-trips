(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  if (root) root.AdminAnalytics = api;
  if (root && root.document) {
    root.document.addEventListener('DOMContentLoaded', function () {
      api.init(root.document, root.vegaEmbed);
    }, {once: true});
  }
})(typeof window !== 'undefined' ? window : globalThis, function () {
  'use strict';

  const renders = new WeakMap();
  const initialized = new WeakSet();
  const fallback = 'This chart could not be drawn. The table below has the same numbers.';

  function embedChart(el, vegaEmbed) {
    const state = renders.get(el) || {pending: Promise.resolve(), result: null};
    renders.set(el, state);
    // Serialize renders so a slow initial embed cannot overwrite a resized chart.
    state.pending = state.pending.then(async function () {
      try {
        if (state.result) state.result.finalize();
        state.result = null;
        const script = el.ownerDocument.getElementById(el.dataset.specId);
        const spec = JSON.parse(script.textContent);
        spec.width = Math.max(1, el.clientWidth - 8);
        el.textContent = '';
        state.result = await vegaEmbed(el, spec, {renderer: 'svg', actions: false, ast: true});
      } catch (_) {
        el.textContent = fallback;
      }
    });
    return state.pending;
  }

  function embedAll(root, vegaEmbed) {
    return Promise.all(Array.from(root.querySelectorAll('.analytics-chart'), el => embedChart(el, vegaEmbed)));
  }

  function watchResize(root, vegaEmbed) {
    const doc = root.ownerDocument || root;
    const Observer = doc.defaultView.ResizeObserver;
    if (!Observer) return null;
    const widths = new WeakMap();
    const timers = new WeakMap();
    const observer = new Observer(function (entries) {
      entries.forEach(function (entry) {
        const el = entry.target;
        clearTimeout(timers.get(el));
        if (Math.abs(el.clientWidth - widths.get(el)) <= 8) return;
        timers.set(el, setTimeout(function () {
          widths.set(el, el.clientWidth);
          embedChart(el, vegaEmbed);
        }, 150));
      });
    });
    root.querySelectorAll('.analytics-chart').forEach(function (el) {
      widths.set(el, el.clientWidth);
      observer.observe(el);
    });
    return observer;
  }

  function sortTable(table, colIndex) {
    const headers = table.querySelectorAll('thead th');
    const header = headers[colIndex];
    const ascending = header.getAttribute('aria-sort') !== 'ascending';
    headers.forEach(th => th.setAttribute('aria-sort', 'none'));
    header.setAttribute('aria-sort', ascending ? 'ascending' : 'descending');
    const collator = new Intl.Collator(undefined, {numeric: true, sensitivity: 'base'});
    const text = row => (row.cells[colIndex]?.textContent || '').trim();
    const numeric = value => value !== '' && Number.isFinite(Number(value.replace(/,/g, '')));
    Array.from(table.tBodies).forEach(function (body) {
      const rows = Array.from(body.rows);
      rows.sort(function (a, b) {
        const left = text(a), right = text(b);
        const comparison = numeric(left) && numeric(right)
          ? Number(left.replace(/,/g, '')) - Number(right.replace(/,/g, ''))
          : collator.compare(left, right);
        return ascending ? comparison : -comparison;
      });
      rows.forEach(row => body.appendChild(row));
    });
  }

  function init(root, vegaEmbed) {
    if (initialized.has(root)) return;
    initialized.add(root);
    root.querySelectorAll('.analytics-table').forEach(function (table) {
      table.querySelectorAll('thead th').forEach(function (th, index) {
        th.tabIndex = 0;
        th.setAttribute('aria-sort', 'none');
        th.setAttribute('title', 'Sort by ' + th.textContent.trim());
        th.addEventListener('click', () => sortTable(table, index));
        th.addEventListener('keydown', function (event) {
          if (event.key === 'Enter') {
            event.preventDefault();
            sortTable(table, index);
          }
        });
      });
    });
    if (vegaEmbed) {
      embedAll(root, vegaEmbed);
      watchResize(root, vegaEmbed);
    }
  }

  return {embedAll, watchResize, sortTable, init};
});
