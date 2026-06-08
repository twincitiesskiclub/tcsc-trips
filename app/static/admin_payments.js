// admin_payments.js - Finance Worktable
// Single IIFE; all helpers prefixed pay_.
// Depends on: AdminUI foundation (_core, status_badge, focus_trap, drawer, filter_bar, data),
//             showToast (toast.js) - all loaded before this file.
(function () {
  'use strict';

  // ---------------------------------------------------------------------------
  // Constants
  // ---------------------------------------------------------------------------
  var MONEY_HIDDEN = '—'; // em-dash glyph used only as a visual code constant (not prose)

  var SECTION_DEFS = [
    {
      key: 'action',
      title: 'Action Needed',
      slug: 'action-needed',
      match: function (p) { return p.display_status === 'pending' || p.display_status === 'processing'; },
      defaultExpanded: true
    },
    {
      key: 'captured',
      title: 'Captured',
      slug: 'captured',
      match: function (p) { return p.display_status === 'success'; },
      defaultExpanded: true
    },
    {
      key: 'closed',
      title: 'Closed',
      slug: 'closed',
      match: function (p) {
        return p.display_status === 'refunded' ||
          p.display_status === 'canceled' ||
          p.display_status === 'unknown';
      },
      defaultExpanded: false
    }
  ];

  var STATUS_BADGE_MAP = {
    success: { variant: 'success', label: 'Success' },
    pending: { variant: 'warning', label: 'Pending' },
    processing: { variant: 'warning', label: 'Processing' },
    refunded: { variant: 'info', label: 'Refunded' },
    canceled: { variant: 'neutral', label: 'Canceled' },
    unknown: { variant: 'neutral', label: 'Unknown' }
  };

  var TYPE_LABELS = {
    trip: 'Trip',
    season: 'Season',
    social_event: 'Social Event'
  };

  // ---------------------------------------------------------------------------
  // Module state
  // ---------------------------------------------------------------------------
  var state = {
    all: [],
    canViewAmounts: false,
    filters: { search: '', type: '', status: '', capturable: [] },
    selected: new Set(),
    // per-section expanded state (persists across re-renders)
    expanded: { action: true, captured: true, closed: false },
    // current filtered rows (cached for CSV export)
    currentFiltered: [],
    // open drawer reference
    openDrawer: null
  };

  // ---------------------------------------------------------------------------
  // Boot
  // ---------------------------------------------------------------------------
  AdminUI.onReady(function () {
    pay_buildShell();
    pay_load();
  });

  // ---------------------------------------------------------------------------
  // Shell build (page header + filter bar mount)
  // ---------------------------------------------------------------------------
  function pay_buildShell() {
    var root = document.getElementById('pay-root');
    if (!root) return;

    // Page header
    var h1 = AdminUI.el('h1', null, ['Payments']);
    var head = AdminUI.el('div', { class: 'pw-head' }, [h1]);
    root.appendChild(head);

    // Filter bar mount point
    var filterMount = AdminUI.el('div', { id: 'pw-filter-mount' }, []);
    root.appendChild(filterMount);

    // Content area
    var content = AdminUI.el('div', { id: 'pw-content' }, []);
    root.appendChild(content);

    // Spacer for bulk bar height
    var spacer = AdminUI.el('div', { class: 'pw-bulk-bar-spacer', id: 'pw-spacer' }, []);
    root.appendChild(spacer);

    // Export bar
    var exportSvg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    exportSvg.setAttribute('width', '13');
    exportSvg.setAttribute('height', '13');
    exportSvg.setAttribute('viewBox', '0 0 16 16');
    exportSvg.setAttribute('fill', 'none');
    exportSvg.setAttribute('aria-hidden', 'true');
    exportSvg.style.flexShrink = '0';
    var path1 = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    path1.setAttribute('d', 'M8 11L3 6h3V1h4v5h3L8 11Z');
    path1.setAttribute('fill', 'currentColor');
    var rect1 = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
    rect1.setAttribute('x', '2');
    rect1.setAttribute('y', '13');
    rect1.setAttribute('width', '12');
    rect1.setAttribute('height', '2');
    rect1.setAttribute('rx', '1');
    rect1.setAttribute('fill', 'currentColor');
    exportSvg.appendChild(path1);
    exportSvg.appendChild(rect1);
    var exportBtn = AdminUI.el('button', {
      type: 'button',
      class: 'admin-ui-export-btn',
      id: 'pw-export-csv',
      onclick: pay_exportCsv
    }, [exportSvg, 'Export CSV']);
    var exportBar = AdminUI.el('div', { class: 'admin-ui-export-bar' }, [exportBtn]);
    root.appendChild(exportBar);

    // Build filter bar
    AdminUI.filterBar(filterMount, {
      search: { placeholder: 'Search by name or email...' },
      selects: [
        {
          key: 'type',
          label: 'All Types',
          options: [
            { value: 'trip', label: 'Trip' },
            { value: 'season', label: 'Season' },
            { value: 'social_event', label: 'Social Event' }
          ]
        },
        {
          key: 'status',
          label: 'All Statuses',
          options: [
            { value: 'pending', label: 'Pending' },
            { value: 'processing', label: 'Processing' },
            { value: 'success', label: 'Captured' },
            { value: 'refunded', label: 'Refunded' },
            { value: 'canceled', label: 'Canceled' }
          ]
        }
      ],
      pills: [
        {
          key: 'capturable',
          label: 'Quick filters',
          multi: false,
          options: [{ value: 'capturable', label: 'Capturable only' }]
        }
      ]
    }, function (newState) {
      state.filters = newState;
      pay_render();
    });

    // Wire up bulk bar buttons
    var bulkBar = document.getElementById('pw-bulk-bar');
    var bulkAccept = document.getElementById('pw-bulk-accept');
    var bulkRefund = document.getElementById('pw-bulk-refund');
    var bulkClear = document.getElementById('pw-bulk-clear');

    if (bulkAccept) {
      bulkAccept.addEventListener('click', function () {
        if (bulkAccept.getAttribute('aria-disabled') === 'true') return;
        pay_confirm('capture');
      });
    }
    if (bulkRefund) {
      bulkRefund.addEventListener('click', function () {
        if (bulkRefund.getAttribute('aria-disabled') === 'true') return;
        pay_confirm('refund');
      });
    }
    if (bulkClear) {
      bulkClear.addEventListener('click', pay_clearSelection);
    }
  }

  // ---------------------------------------------------------------------------
  // Data load
  // ---------------------------------------------------------------------------
  function pay_load() {
    var content = document.getElementById('pw-content');
    if (content) {
      content.innerHTML = '';
      content.appendChild(AdminUI.el('p', { class: 'pw-loading' }, ['Loading payments...']));
    }

    AdminUI.fetchJSON('/admin/payments/data').then(function (data) {
      state.all = data.payments || [];
      state.canViewAmounts = !!data.can_view_amounts;
      pay_render();
    }).catch(function () {
      if (content) {
        content.innerHTML = '';
        content.appendChild(AdminUI.el('div', { class: 'pw-error' }, [
          'Could not load payments. Please refresh the page.'
        ]));
      }
      if (window.showToast) showToast('Failed to load payments', 'error');
    });
  }

  // ---------------------------------------------------------------------------
  // Filtering
  // ---------------------------------------------------------------------------
  function pay_applyFilters(rows) {
    var f = state.filters;
    var search = (f.search || '').toLowerCase().trim();
    var typeVal = f.type || '';
    var statusVal = f.status || '';
    var capturableOnly = Array.isArray(f.capturable) && f.capturable.indexOf('capturable') !== -1;

    return rows.filter(function (p) {
      if (search) {
        var name = (p.name || '').toLowerCase();
        var email = (p.email || '').toLowerCase();
        if (name.indexOf(search) === -1 && email.indexOf(search) === -1) return false;
      }
      if (typeVal && p.payment_type !== typeVal) return false;
      if (statusVal && p.display_status !== statusVal) return false;
      if (capturableOnly && p.status !== 'requires_capture') return false;
      return true;
    });
  }

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------
  function pay_render() {
    // Close any open drawer before rebuilding DOM
    if (state.openDrawer) {
      state.openDrawer.close();
      state.openDrawer = null;
    }

    var content = document.getElementById('pw-content');
    if (!content) return;
    content.innerHTML = '';

    var filtered = pay_applyFilters(state.all);
    state.currentFiltered = filtered;

    // Reconcile selection: remove ids no longer in filtered set
    var filteredIds = new Set(filtered.map(function (p) { return p.id; }));
    state.selected.forEach(function (id) {
      if (!filteredIds.has(id)) state.selected.delete(id);
    });

    var allEmpty = true;

    SECTION_DEFS.forEach(function (def) {
      var sectionRows = filtered.filter(def.match);
      if (sectionRows.length > 0) allEmpty = false;

      content.appendChild(pay_buildSection(def, sectionRows));
    });

    if (allEmpty && filtered.length === 0 && state.all.length > 0) {
      content.appendChild(AdminUI.el('p', { class: 'pw-empty' }, [
        'No payments match the current filters.'
      ]));
    }

    pay_updateBulkBar();
  }

  // ---------------------------------------------------------------------------
  // Section builder
  // ---------------------------------------------------------------------------
  function pay_buildSection(def, rows) {
    var isExpanded = state.expanded[def.key];
    var bodyId = 'pw-section-' + def.slug;

    // Compute subtotal for finance-authorized users
    var subtotal = null;
    if (state.canViewAmounts) {
      subtotal = rows.reduce(function (sum, p) {
        return sum + (p.amount != null ? p.amount : 0);
      }, 0);
    }

    // Section select-all checkbox
    var selectAllCb = AdminUI.el('input', {
      type: 'checkbox',
      class: 'pw-sec-selectall',
      'aria-label': 'Select all ' + def.title + ' payments'
    }, []);
    selectAllCb.addEventListener('click', function (e) {
      e.stopPropagation();
      pay_toggleSectionSelect(rows, selectAllCb);
    });

    // Header children
    var chevron = AdminUI.el('span', { class: 'pw-chevron', 'aria-hidden': 'true' }, ['▶']);
    var titleSpan = AdminUI.el('span', { class: 'pw-sec-title' }, [def.title]);
    var countSpan = AdminUI.el('span', { class: 'pw-sec-count' }, ['(' + rows.length + ')']);

    var headerChildren = [chevron, titleSpan, countSpan, selectAllCb];

    if (subtotal !== null) {
      headerChildren.push(AdminUI.el('span', { class: 'pw-sec-subtotal' }, [
        '$' + subtotal.toFixed(2)
      ]));
    }

    var headerBtn = AdminUI.el('button', {
      type: 'button',
      class: 'pw-sec-header',
      'aria-expanded': isExpanded ? 'true' : 'false',
      'aria-controls': bodyId
    }, headerChildren);

    var hr = AdminUI.el('hr', { class: 'pw-sec-hr' }, []);

    // Section body
    var bodyChildren = [];
    if (rows.length === 0) {
      bodyChildren.push(AdminUI.el('p', { class: 'pw-empty-section' }, ['No payments']));
    } else {
      var ul = AdminUI.el('ul', {
        class: 'pw-rows',
        role: 'list',
        'aria-label': def.title + ' payments'
      }, rows.map(function (p) { return pay_buildRow(p); }));
      bodyChildren.push(ul);
    }

    var body = AdminUI.el('div', {
      id: bodyId,
      role: 'region',
      'aria-label': def.title + ' payments'
    }, bodyChildren);

    if (!isExpanded) body.setAttribute('hidden', '');

    // Wire collapse toggle
    headerBtn.addEventListener('click', function () {
      var expanded = headerBtn.getAttribute('aria-expanded') === 'true';
      expanded = !expanded;
      state.expanded[def.key] = expanded;
      headerBtn.setAttribute('aria-expanded', expanded ? 'true' : 'false');
      if (expanded) {
        body.removeAttribute('hidden');
      } else {
        body.setAttribute('hidden', '');
      }
    });

    // Update section-select-all state
    pay_syncSectionSelectAll(selectAllCb, rows);

    return AdminUI.el('div', { class: 'pw-section' }, [headerBtn, hr, body]);
  }

  // ---------------------------------------------------------------------------
  // Ledger row builder
  // ---------------------------------------------------------------------------
  function pay_buildRow(p) {
    var isSelected = state.selected.has(p.id);

    // Checkbox
    var cb = AdminUI.el('input', {
      type: 'checkbox',
      'aria-label': 'Select payment for ' + AdminUI.escapeHtml(p.name)
    }, []);
    cb.checked = isSelected;
    cb.addEventListener('change', function (e) {
      e.stopPropagation();
      pay_toggleSelect(p.id, li);
    });
    var checkWrap = AdminUI.el('div', { class: 'pw-row-check' }, [cb]);

    // Status badge
    var badgeDef = STATUS_BADGE_MAP[p.display_status] || { variant: 'neutral', label: 'Unknown' };
    var badge = AdminUI.statusBadge(badgeDef.label, badgeDef.variant);

    // Type pill
    var typePill = AdminUI.el('span', {
      class: 'pw-type-pill pw-type-' + (p.payment_type || 'unknown')
    }, [TYPE_LABELS[p.payment_type] || (p.payment_type || 'Unknown')]);

    // Line 1: name + badge
    var line1 = AdminUI.el('div', { class: 'pw-row-line1' }, [
      AdminUI.el('span', { class: 'pw-row-name' }, [p.name || '']),
      badge
    ]);

    // Line 2: email . type pill . for_name . created_at
    var line2Children = [
      AdminUI.el('span', null, [p.email || '']),
      AdminUI.el('span', { class: 'pw-row-sep', 'aria-hidden': 'true' }, ['·']),
      typePill,
      AdminUI.el('span', { class: 'pw-row-sep', 'aria-hidden': 'true' }, ['·']),
      AdminUI.el('span', { class: 'pw-row-forname' }, [p.for_name || '']),
      AdminUI.el('span', { class: 'pw-row-sep', 'aria-hidden': 'true' }, ['·']),
      AdminUI.el('span', null, [p.created_at || ''])
    ];
    var line2 = AdminUI.el('div', { class: 'pw-row-line2' }, line2Children);

    var mainCol = AdminUI.el('div', { class: 'pw-row-main' }, [line1, line2]);

    // Amount (right-aligned)
    var amtText, amtClass;
    if (state.canViewAmounts && p.amount != null) {
      amtText = '$' + p.amount.toFixed(2);
      amtClass = 'pw-row-amount';
    } else {
      amtText = MONEY_HIDDEN;
      amtClass = 'pw-row-amount pw-amount-hidden';
    }
    var amountEl = AdminUI.el('div', { class: amtClass }, [amtText]);

    // Inline action buttons
    var canAcceptRow = p.status === 'requires_capture';
    var canRefundRow = p.status === 'requires_capture' || p.status === 'succeeded';

    var acceptBtn = AdminUI.el('button', {
      type: 'button',
      class: 'pw-row-act pw-row-act-accept'
    }, ['Accept']);
    if (!canAcceptRow) acceptBtn.setAttribute('disabled', '');
    acceptBtn.addEventListener('click', function (e) {
      e.stopPropagation();
      pay_capture(p.id);
    });

    var refundBtn = AdminUI.el('button', {
      type: 'button',
      class: 'pw-row-act pw-row-act-refund'
    }, ['Refund']);
    if (!canRefundRow) refundBtn.setAttribute('disabled', '');
    refundBtn.addEventListener('click', function (e) {
      e.stopPropagation();
      pay_refund(p.id);
    });

    var actions = AdminUI.el('div', { class: 'pw-row-actions' }, [acceptBtn, refundBtn]);

    // Row item
    var li = AdminUI.el('li', {
      class: 'pw-row-item' + (isSelected ? ' is-selected' : ''),
      tabindex: '0',
      role: 'row',
      dataset: { paymentId: String(p.id) }
    }, [checkWrap, mainCol, amountEl, actions]);

    // Row click -> open drawer (excluding controls)
    li.addEventListener('click', function (e) {
      if (e.target === cb || e.target === acceptBtn || e.target === refundBtn ||
        e.target.closest('.pw-row-check') || e.target.closest('.pw-row-actions')) {
        return;
      }
      pay_openDrawer(p);
    });

    // Keyboard: Enter -> drawer, Space -> toggle select
    // Guard: if focus is on the row checkbox or another interactive element,
    // let the native event handle it (avoids double-toggle on Space).
    li.addEventListener('keydown', function (e) {
      if (e.key === 'Enter') {
        if (e.target === cb || e.target.tagName === 'BUTTON' || e.target.tagName === 'INPUT') return;
        pay_openDrawer(p);
      } else if (e.key === ' ') {
        if (e.target === cb || e.target.tagName === 'BUTTON' || e.target.tagName === 'INPUT') return;
        e.preventDefault();
        pay_toggleSelect(p.id, li);
      }
    });

    return li;
  }

  // ---------------------------------------------------------------------------
  // Selection
  // ---------------------------------------------------------------------------
  function pay_toggleSelect(id, rowEl) {
    if (state.selected.has(id)) {
      state.selected.delete(id);
      if (rowEl) {
        rowEl.classList.remove('is-selected');
        var cb = rowEl.querySelector('input[type="checkbox"]');
        if (cb) cb.checked = false;
      }
    } else {
      state.selected.add(id);
      if (rowEl) {
        rowEl.classList.add('is-selected');
        var cb = rowEl.querySelector('input[type="checkbox"]');
        if (cb) cb.checked = true;
      }
    }
    pay_updateBulkBar();

    // Update section select-all states
    pay_syncAllSectionSelectAlls();
  }

  function pay_toggleSectionSelect(rows, sectionCb) {
    var ids = rows.map(function (p) { return p.id; });
    var allSelected = ids.every(function (id) { return state.selected.has(id); });

    if (allSelected) {
      // Deselect all in section
      ids.forEach(function (id) { state.selected.delete(id); });
    } else {
      // Select all in section
      ids.forEach(function (id) { state.selected.add(id); });
    }

    // Update row DOM - look up by data-payment-id to avoid collisions on same name
    var content = document.getElementById('pw-content');
    if (content) {
      rows.forEach(function (p) {
        var isNowSelected = state.selected.has(p.id);
        var rowEl = content.querySelector('.pw-row-item[data-payment-id="' + p.id + '"]');
        if (rowEl) {
          rowEl.classList.toggle('is-selected', isNowSelected);
          var cb2 = rowEl.querySelector('input[type="checkbox"]');
          if (cb2) cb2.checked = isNowSelected;
        }
      });
    }

    pay_updateBulkBar();
    pay_syncAllSectionSelectAlls();
  }

  function pay_syncSectionSelectAll(sectionCb, rows) {
    if (!sectionCb || !rows.length) return;
    var selectedCount = rows.filter(function (p) { return state.selected.has(p.id); }).length;
    if (selectedCount === 0) {
      sectionCb.checked = false;
      sectionCb.indeterminate = false;
    } else if (selectedCount === rows.length) {
      sectionCb.checked = true;
      sectionCb.indeterminate = false;
    } else {
      sectionCb.checked = false;
      sectionCb.indeterminate = true;
    }
  }

  function pay_syncAllSectionSelectAlls() {
    // Re-sync section select-all checkboxes based on current selection state
    var content = document.getElementById('pw-content');
    if (!content) return;
    var filtered = state.currentFiltered;
    SECTION_DEFS.forEach(function (def) {
      var sectionRows = filtered.filter(def.match);
      // Find the section's select-all checkbox
      var sectionEls = content.querySelectorAll('.pw-section');
      sectionEls.forEach(function (sEl) {
        var hdr = sEl.querySelector('.pw-sec-header');
        if (!hdr) return;
        var titleEl = hdr.querySelector('.pw-sec-title');
        if (!titleEl || titleEl.textContent !== def.title) return;
        var cb = hdr.querySelector('.pw-sec-selectall');
        if (cb) pay_syncSectionSelectAll(cb, sectionRows);
      });
    });
  }

  function pay_clearSelection() {
    state.selected.clear();
    var content = document.getElementById('pw-content');
    if (content) {
      content.querySelectorAll('.pw-row-item.is-selected').forEach(function (el) {
        el.classList.remove('is-selected');
        var cb = el.querySelector('input[type="checkbox"]');
        if (cb) cb.checked = false;
      });
    }
    pay_updateBulkBar();
    pay_syncAllSectionSelectAlls();
  }

  // ---------------------------------------------------------------------------
  // Bulk bar update
  // ---------------------------------------------------------------------------
  function pay_updateBulkBar() {
    var bulkBar = document.getElementById('pw-bulk-bar');
    var spacer = document.getElementById('pw-spacer');
    var countEl = document.getElementById('pw-bulk-count');
    var sumEl = document.getElementById('pw-bulk-sum');
    var acceptBtn = document.getElementById('pw-bulk-accept');
    var refundBtn = document.getElementById('pw-bulk-refund');

    if (!bulkBar) return;

    var selCount = state.selected.size;

    if (selCount === 0) {
      bulkBar.setAttribute('hidden', '');
      bulkBar.classList.remove('is-visible');
      if (spacer) {
        spacer.classList.remove('is-visible');
      }
      return;
    }

    bulkBar.removeAttribute('hidden');
    bulkBar.classList.add('is-visible');
    if (spacer) spacer.classList.add('is-visible');

    if (countEl) countEl.textContent = selCount + ' selected';

    // Compute eligibility
    var selectedPayments = state.all.filter(function (p) { return state.selected.has(p.id); });
    var canAccept = selectedPayments.some(function (p) { return p.status === 'requires_capture'; });
    var canRefund = selectedPayments.some(function (p) {
      return p.status === 'requires_capture' || p.status === 'succeeded';
    });

    // Live sum
    if (state.canViewAmounts && sumEl) {
      var sum = selectedPayments.reduce(function (acc, p) {
        return acc + (p.amount != null ? p.amount : 0);
      }, 0);
      sumEl.textContent = '$' + sum.toFixed(2);
      sumEl.removeAttribute('hidden');
    } else if (sumEl) {
      sumEl.setAttribute('hidden', '');
    }

    if (acceptBtn) {
      acceptBtn.setAttribute('aria-disabled', canAccept ? 'false' : 'true');
    }
    if (refundBtn) {
      refundBtn.setAttribute('aria-disabled', canRefund ? 'false' : 'true');
    }
  }

  // ---------------------------------------------------------------------------
  // Confirm modal
  // ---------------------------------------------------------------------------
  function pay_confirm(action) {
    var selectedPayments = state.all.filter(function (p) { return state.selected.has(p.id); });

    // Compute eligible
    var eligiblePayments;
    if (action === 'capture') {
      eligiblePayments = selectedPayments.filter(function (p) { return p.status === 'requires_capture'; });
    } else {
      eligiblePayments = selectedPayments.filter(function (p) {
        return p.status === 'requires_capture' || p.status === 'succeeded';
      });
    }

    var ineligibleCount = selectedPayments.length - eligiblePayments.length;
    var actionLabel = action === 'capture' ? 'Accept' : 'Refund';
    var eligibleIds = eligiblePayments.map(function (p) { return p.id; });

    // Modal title
    var titleText = actionLabel + ' ' + eligiblePayments.length + ' Payment' +
      (eligiblePayments.length !== 1 ? 's' : '');

    // Summary stat: count
    var statCount = AdminUI.el('div', { class: 'pw-modal-stat' }, [
      AdminUI.el('span', { class: 'pw-modal-stat-val' }, [String(eligiblePayments.length)]),
      AdminUI.el('span', { class: 'pw-modal-stat-lbl' }, ['Payments'])
    ]);

    var summaryChildren = [statCount];

    // Finance-gated total
    if (state.canViewAmounts) {
      var total = eligiblePayments.reduce(function (sum, p) {
        return sum + (p.amount != null ? p.amount : 0);
      }, 0);
      summaryChildren.push(AdminUI.el('div', { class: 'pw-modal-stat' }, [
        AdminUI.el('span', { class: 'pw-modal-stat-val' }, ['$' + total.toFixed(2)]),
        AdminUI.el('span', { class: 'pw-modal-stat-lbl' }, ['Total'])
      ]));
    }

    var summary = AdminUI.el('div', { class: 'pw-modal-summary' }, summaryChildren);

    // Ineligible warning
    var bodyChildren = [summary];
    if (ineligibleCount > 0) {
      bodyChildren.push(AdminUI.el('p', { class: 'pw-modal-warning' }, [
        String(ineligibleCount) + ' selected payment' +
          (ineligibleCount !== 1 ? 's are' : ' is') +
          ' not eligible for this action and will be skipped.'
      ]));
    }

    // Per-row breakdown
    var listItems = eligiblePayments.map(function (p) {
      var itemChildren = [AdminUI.el('span', null, [p.name || ''])];
      if (state.canViewAmounts && p.amount != null) {
        itemChildren.push(AdminUI.el('span', { class: 'pw-modal-item-amt' }, [
          '$' + p.amount.toFixed(2)
        ]));
      }
      return AdminUI.el('li', { class: 'pw-modal-item' }, itemChildren);
    });
    bodyChildren.push(AdminUI.el('ul', { class: 'pw-modal-list' }, listItems));

    // Footer buttons
    var cancelBtn = AdminUI.el('button', {
      type: 'button',
      class: 'pw-modal-cancel'
    }, ['Cancel']);

    var confirmBtn = AdminUI.el('button', {
      type: 'button',
      class: 'pw-modal-confirm ' + (action === 'capture' ? 'pw-modal-confirm-accept' : 'pw-modal-confirm-refund')
    }, [actionLabel]);

    var footer = AdminUI.el('div', { class: 'pw-modal-ft' }, [cancelBtn, confirmBtn]);

    // Modal structure
    var titleEl = AdminUI.el('h2', { class: 'pw-modal-title', id: 'pw-modal-title' }, [titleText]);
    var closeBtn = AdminUI.el('button', {
      type: 'button',
      class: 'pw-modal-x',
      'aria-label': 'Close'
    }, ['×']);

    var modalHd = AdminUI.el('div', { class: 'pw-modal-hd' }, [titleEl, closeBtn]);
    var modalBody = AdminUI.el('div', { class: 'pw-modal-body' }, bodyChildren);
    var modal = AdminUI.el('div', {
      class: 'pw-modal',
      role: 'dialog',
      'aria-modal': 'true',
      'aria-labelledby': 'pw-modal-title'
    }, [modalHd, modalBody, footer]);

    var scrim = AdminUI.el('div', { class: 'pw-modal-scrim' }, [modal]);
    document.body.appendChild(scrim);

    // Focus trap, initial focus on Cancel
    var releaseFocus = AdminUI.trapFocus(modal);
    cancelBtn.focus();

    // Store opener ref for focus restoration
    var opener = document.getElementById('pw-bulk-accept');
    if (action === 'refund') opener = document.getElementById('pw-bulk-refund');

    function closeModal() {
      releaseFocus();
      scrim.remove();
      if (opener && typeof opener.focus === 'function') opener.focus();
    }

    // Esc and scrim click close
    scrim.addEventListener('click', function (e) {
      if (e.target === scrim) closeModal();
    });
    function onEsc(e) {
      if (e.key === 'Escape') { document.removeEventListener('keydown', onEsc); closeModal(); }
    }
    document.addEventListener('keydown', onEsc);

    cancelBtn.addEventListener('click', function () {
      document.removeEventListener('keydown', onEsc);
      closeModal();
    });
    closeBtn.addEventListener('click', function () {
      document.removeEventListener('keydown', onEsc);
      closeModal();
    });

    // Confirm action
    confirmBtn.addEventListener('click', function () {
      confirmBtn.setAttribute('disabled', '');
      confirmBtn.textContent = 'Processing...';

      var bulkFn = action === 'capture' ? pay_bulkCapture : pay_bulkRefund;
      bulkFn(eligibleIds).then(function (result) {
        document.removeEventListener('keydown', onEsc);
        closeModal();
        if (result.failed === 0) {
          var verb = action === 'capture' ? 'Accepted' : 'Refunded';
          if (window.showToast) showToast(verb + ' ' + result.succeeded + ' payment(s)', 'success');
          pay_clearSelection();
        } else {
          var verb2 = action === 'capture' ? 'Accepted' : 'Refunded';
          if (window.showToast) {
            showToast(
              verb2 + ' ' + result.succeeded + ' of ' + (result.succeeded + result.failed) +
              ' payment(s). ' + result.failed + ' could not be processed.',
              'error'
            );
          }
          // Do NOT clear selection on partial failure - leave failed ones selected
        }
        pay_load();
      }).catch(function () {
        confirmBtn.removeAttribute('disabled');
        confirmBtn.textContent = actionLabel;
      });
    });
  }

  // ---------------------------------------------------------------------------
  // Mutation: single capture/refund
  // ---------------------------------------------------------------------------
  function pay_capture(id) {
    if (!window.confirm('Accept this payment?')) return;

    fetch('/admin/payments/' + id + '/capture', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' }
    }).then(function (res) {
      return res.json().then(function (data) {
        if (res.ok && data.status === 'success') {
          // Silently reload
        } else if (window.showToast) {
          showToast(data.error || 'Failed to accept payment', 'error');
        }
      });
    }).catch(function (err) {
      console.error('Capture error:', err);
    }).then(function () {
      // Always re-fetch in a finally-style path
      pay_load();
    });
  }

  function pay_refund(id) {
    if (!window.confirm('Refund this payment?')) return;

    fetch('/admin/payments/' + id + '/refund', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' }
    }).then(function (res) {
      return res.json().then(function (data) {
        if (res.ok && data.status === 'success') {
          // Silently reload
        } else if (window.showToast) {
          showToast(data.error || 'Failed to refund payment', 'error');
        }
      });
    }).catch(function (err) {
      console.error('Refund error:', err);
    }).then(function () {
      pay_load();
    });
  }

  // ---------------------------------------------------------------------------
  // Mutation: bulk
  // ---------------------------------------------------------------------------
  function pay_bulkCapture(ids) {
    return pay_bulkMutate('/admin/payments/bulk-capture', ids);
  }

  function pay_bulkRefund(ids) {
    return pay_bulkMutate('/admin/payments/bulk-refund', ids);
  }

  function pay_bulkMutate(endpoint, ids) {
    return fetch(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
      body: JSON.stringify({ payment_ids: ids })
    }).then(function (res) {
      return res.json().then(function (data) {
        if (!res.ok) {
          return Promise.reject(new Error(data.error || 'Request failed'));
        }
        // HTTP 200 even on partial failures; inspect results[]
        var results = data.results || [];
        var succeeded = results.filter(function (r) { return r.success; }).length;
        var failed = results.filter(function (r) { return !r.success; }).length;
        // If no results array, treat all as succeeded
        if (results.length === 0) {
          succeeded = ids.length;
          failed = 0;
        }
        return { succeeded: succeeded, failed: failed };
      });
    });
  }

  // ---------------------------------------------------------------------------
  // Preview drawer
  // ---------------------------------------------------------------------------
  function pay_openDrawer(p) {
    var badgeDef = STATUS_BADGE_MAP[p.display_status] || { variant: 'neutral', label: 'Unknown' };
    var canAccept = p.status === 'requires_capture';
    var canRefund = p.status === 'requires_capture' || p.status === 'succeeded';

    // Definition-list KV rows
    var kvRows = [
      pay_kvRow('Email', AdminUI.el('span', null, [p.email || ''])),
      pay_kvRow('Amount', pay_amountNode(p)),
      pay_kvRow('Type', AdminUI.el('span', { class: 'admin-ui-dw-pill' }, [
        TYPE_LABELS[p.payment_type] || (p.payment_type || '')
      ])),
      pay_kvRow('For', AdminUI.el('span', null, [p.for_name || ''])),
      pay_kvRow('Status', AdminUI.statusBadge(badgeDef.label, badgeDef.variant)),
      pay_kvRow('Created', AdminUI.el('span', null, [p.created_at || ''])),
      pay_kvRow('Intent ID', AdminUI.el('span', { class: 'admin-ui-dw-val--mono' }, [p.payment_intent_id || '']))
    ];

    var kvList = AdminUI.el('div', { class: 'admin-ui-dw' }, kvRows);

    // Action buttons in drawer
    var dwAcceptBtn = AdminUI.el('button', {
      type: 'button',
      class: 'admin-ui-dw-btn-primary'
    }, ['Accept']);
    if (!canAccept) dwAcceptBtn.setAttribute('disabled', '');

    var dwRefundBtn = AdminUI.el('button', {
      type: 'button',
      class: 'admin-ui-dw-btn-danger'
    }, ['Refund']);
    if (!canRefund) dwRefundBtn.setAttribute('disabled', '');

    var actRow = AdminUI.el('div', { class: 'admin-ui-dw-footer' }, [dwAcceptBtn, dwRefundBtn]);
    var content = AdminUI.el('div', null, [kvList]);
    content.appendChild(actRow);

    var drawerApi = AdminUI.drawer({ title: p.name || 'Payment', content: content });
    state.openDrawer = drawerApi;

    dwAcceptBtn.addEventListener('click', function () {
      drawerApi.close();
      state.openDrawer = null;
      pay_capture(p.id);
    });

    dwRefundBtn.addEventListener('click', function () {
      drawerApi.close();
      state.openDrawer = null;
      pay_refund(p.id);
    });
  }

  function pay_kvRow(label, valueNode) {
    return AdminUI.el('div', { class: 'admin-ui-dw-kv' }, [
      AdminUI.el('span', { class: 'admin-ui-dw-key' }, [label]),
      AdminUI.el('div', { class: 'admin-ui-dw-val' }, [valueNode])
    ]);
  }

  function pay_amountNode(p) {
    if (state.canViewAmounts && p.amount != null) {
      return AdminUI.el('span', null, ['$' + p.amount.toFixed(2)]);
    }
    return AdminUI.el('span', { class: 'pw-amount-hidden' }, [MONEY_HIDDEN]);
  }

  // ---------------------------------------------------------------------------
  // CSV export
  // ---------------------------------------------------------------------------
  function pay_exportCsv() {
    var rows = state.currentFiltered;
    var headers = ['Name', 'Email', 'Amount', 'For', 'Status', 'Type', 'Created'];
    var lines = [headers.map(csvQuote).join(',')];

    rows.forEach(function (p) {
      var amt = '';
      if (state.canViewAmounts && p.amount != null) {
        amt = '$' + p.amount.toFixed(2);
      }
      var line = [
        p.name || '',
        p.email || '',
        amt,
        p.for_name || '',
        p.display_status || '',
        TYPE_LABELS[p.payment_type] || (p.payment_type || ''),
        p.created_at || ''
      ].map(csvQuote).join(',');
      lines.push(line);
    });

    var csv = lines.join('\r\n');
    var blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    var url = URL.createObjectURL(blob);
    var a = document.createElement('a');
    a.href = url;
    a.download = 'tcsc_payments.csv';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  function csvQuote(val) {
    var s = String(val == null ? '' : val);
    if (s.indexOf('"') !== -1 || s.indexOf(',') !== -1 || s.indexOf('\n') !== -1) {
      return '"' + s.replace(/"/g, '""') + '"';
    }
    return '"' + s + '"';
  }

})();
