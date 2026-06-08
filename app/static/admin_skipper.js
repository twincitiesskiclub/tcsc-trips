// app/static/admin_skipper.js
// Skipper Dashboard: pending proposals + decisions feed.
// Depends on AdminUI foundation (_core.js, drawer.js, status_badge.js, filter_bar.js,
// focus_trap.js, data.js) loaded before this script.

(function () {
'use strict';

// ---------------------------------------------------------------------------
// Shared state
// ---------------------------------------------------------------------------
var proposalsData = [];

// ---------------------------------------------------------------------------
// Page bootstrap
// ---------------------------------------------------------------------------
AdminUI.onReady(function () {
  sk_showLoadingState();
  loadProposals();
  loadConfig();
});

// ---------------------------------------------------------------------------
// Data fetch (single fetch for both pending cards and decisions feed)
// ---------------------------------------------------------------------------
function loadProposals() {
  AdminUI.fetchJSON('/admin/skipper/data')
    .then(function (data) {
      proposalsData = data.proposals || [];
      renderPendingProposals();
      sk_render();
    })
    .catch(function (err) {
      console.error('Error loading proposals:', err);
      sk_showError();
      if (window.showToast) showToast('Failed to load decisions', 'error');
    });
}

// ---------------------------------------------------------------------------
// Pending proposals (unchanged logic; HTML rendered directly)
// ---------------------------------------------------------------------------
function renderPendingProposals() {
  var container = document.getElementById('pending-proposals');
  var pending = proposalsData.filter(function (p) { return p.status === 'pending'; });

  if (pending.length === 0) {
    container.innerHTML =
      '<div class="py-10 text-center text-tcsc-gray-600 italic bg-gray-50 rounded-tcsc">No pending proposals</div>';
    return;
  }

  var html = '';
  for (var i = 0; i < pending.length; i++) {
    var proposal = pending[i];
    var practiceDate = new Date(proposal.practice_date).toLocaleString();
    var proposedDate = new Date(proposal.proposed_at).toLocaleString();
    var e = AdminUI.escapeHtml;

    html += '<div class="bg-white border border-gray-300 rounded-lg p-4 mb-3">' +
      '<div class="flex justify-between items-start mb-3">' +
        '<div>' +
          '<div class="font-semibold text-sm text-tcsc-navy">' + e(proposal.practice_location) + ' - ' + e(practiceDate) + '</div>' +
          '<div class="text-xs text-tcsc-gray-600">Proposed: ' + e(proposedDate) + '</div>' +
        '</div>' +
        '<span class="inline-block px-2 py-0.5 rounded-full text-xs font-semibold status-' + e(proposal.status) + '">' + e(proposal.status) + '</span>' +
      '</div>' +
      '<div class="p-3 bg-amber-50 border-l-[3px] border-amber-500 rounded mb-3">' +
        '<div class="font-semibold text-[11px] uppercase text-amber-800 mb-1">' + e(proposal.reason_type.replace(/_/g, ' ')) + '</div>' +
        '<div class="text-sm text-amber-900">' + e(proposal.reason_summary) + '</div>' +
      '</div>' +
      '<div class="tbl-actions justify-end">' +
        '<button class="tbl-btn tbl-btn-secondary" onclick="rejectProposal(' + proposal.id + ')">Reject</button>' +
        '<button class="tbl-btn tbl-btn-primary" onclick="approveProposal(' + proposal.id + ')">Approve Cancellation</button>' +
      '</div>' +
    '</div>';
  }

  container.innerHTML = html;
}

// ---------------------------------------------------------------------------
// Approve / Reject actions (unchanged)
// ---------------------------------------------------------------------------
function approveProposal(proposalId) {
  var notes = prompt('Optional decision notes:');
  if (notes === null) return;

  fetch('/admin/skipper/approve/' + proposalId, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ notes: notes })
  })
    .then(function (res) { return res.json(); })
    .then(function (result) {
      if (result.success) {
        showToast(result.message, 'success');
        loadProposals();
      } else {
        showToast(result.error || 'Failed to approve', 'error');
      }
    })
    .catch(function (err) {
      console.error('Error approving proposal:', err);
      showToast('Failed to approve proposal', 'error');
    });
}

function rejectProposal(proposalId) {
  var notes = prompt('Optional decision notes:');
  if (notes === null) return;

  fetch('/admin/skipper/reject/' + proposalId, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ notes: notes })
  })
    .then(function (res) { return res.json(); })
    .then(function (result) {
      if (result.success) {
        showToast(result.message, 'success');
        loadProposals();
      } else {
        showToast(result.error || 'Failed to reject', 'error');
      }
    })
    .catch(function (err) {
      console.error('Error rejecting proposal:', err);
      showToast('Failed to reject proposal', 'error');
    });
}

// ---------------------------------------------------------------------------
// Config (unchanged)
// ---------------------------------------------------------------------------
function loadConfig() {
  fetch('/admin/skipper/config')
    .then(function (res) { return res.json(); })
    .then(function (result) {
      if (result.success) renderConfig(result.config);
    })
    .catch(function (err) {
      console.error('Error loading config:', err);
    });
}

function renderConfig(config) {
  var container = document.getElementById('config-display');
  var thresholds = config.thresholds || {};
  var weatherThresholds = thresholds.weather || {};
  var leadThresholds = thresholds.lead || {};

  var html = '<h3 class="m-0 mb-3 text-sm text-tcsc-gray-600 font-medium">Weather Thresholds</h3>';
  html += '<div class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">';
  for (var key in weatherThresholds) {
    if (!Object.prototype.hasOwnProperty.call(weatherThresholds, key)) continue;
    var value = weatherThresholds[key];
    html += '<div class="p-3 bg-gray-50 border border-gray-200 rounded-tcsc">' +
      '<div class="text-[11px] font-semibold uppercase text-tcsc-gray-600 mb-1">' +
        AdminUI.escapeHtml(key.replace(/_/g, ' ')) +
      '</div>' +
      '<div class="text-sm font-semibold text-tcsc-navy">' + AdminUI.escapeHtml(String(value)) + '</div>' +
    '</div>';
  }
  html += '</div>';

  html += '<h3 class="mt-5 mb-3 text-sm text-tcsc-gray-600 font-medium">Lead Requirements</h3>';
  html += '<div class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">';
  for (var lkey in leadThresholds) {
    if (!Object.prototype.hasOwnProperty.call(leadThresholds, lkey)) continue;
    var lvalue = leadThresholds[lkey];
    var displayValue = typeof lvalue === 'boolean' ? (lvalue ? 'Yes' : 'No') : lvalue;
    html += '<div class="p-3 bg-gray-50 border border-gray-200 rounded-tcsc">' +
      '<div class="text-[11px] font-semibold uppercase text-tcsc-gray-600 mb-1">' +
        AdminUI.escapeHtml(lkey.replace(/_/g, ' ')) +
      '</div>' +
      '<div class="text-sm font-semibold text-tcsc-navy">' + AdminUI.escapeHtml(String(displayValue)) + '</div>' +
    '</div>';
  }
  html += '</div>';

  container.innerHTML = html;
}

function refreshConfig() {
  loadConfig();
  showToast('Configuration refreshed', 'success');
}

// ===========================================================================
// sk_ DECISIONS FEED
// ===========================================================================

// ---------------------------------------------------------------------------
// Filter state
// ---------------------------------------------------------------------------
var sk_filterState = { search: '', status: '', window: 'all' };

// ---------------------------------------------------------------------------
// Initialise filter bar (called once DOM is ready, wired in sk_initFeed)
// ---------------------------------------------------------------------------
function sk_initFeed() {
  var toolbar = document.getElementById('sk-toolbar');
  if (!toolbar) return;

  AdminUI.filterBar(toolbar, {
    search: { placeholder: 'Search location or reason...' },
    selects: [
      {
        key: 'status',
        label: 'All Status',
        options: [
          { value: 'approved', label: 'Approved' },
          { value: 'rejected', label: 'Rejected' },
          { value: 'expired', label: 'Expired / Auto-kept' }
        ]
      },
      {
        key: 'window',
        label: 'All time',
        options: [
          { value: '30d', label: 'Last 30 days' },
          { value: '7d', label: 'Last 7 days' }
        ]
      }
    ]
  }, function (state) {
    sk_filterState.search = state.search || '';
    sk_filterState.status = state.status || '';
    sk_filterState.window = state.window || 'all';
    sk_render();
  });
}

// ---------------------------------------------------------------------------
// Show loading placeholder (before first fetch resolves)
// ---------------------------------------------------------------------------
function sk_showLoadingState() {
  var empty = document.getElementById('sk-empty');
  if (empty) {
    empty.textContent = 'Loading...';
    empty.removeAttribute('hidden');
  }
  var feed = document.getElementById('sk-feed');
  if (feed) feed.innerHTML = '';
  sk_initFeed();
}

// ---------------------------------------------------------------------------
// Show error state
// ---------------------------------------------------------------------------
function sk_showError() {
  var empty = document.getElementById('sk-empty');
  if (empty) {
    empty.textContent = 'Could not load decisions';
    empty.removeAttribute('hidden');
  }
  var feed = document.getElementById('sk-feed');
  if (feed) feed.innerHTML = '';
}

// ---------------------------------------------------------------------------
// Main render: reads proposalsData, applies filters, groups, renders cards
// ---------------------------------------------------------------------------
function sk_render() {
  var feed = document.getElementById('sk-feed');
  var empty = document.getElementById('sk-empty');
  if (!feed || !empty) return;

  // Filter: exclude pending, apply search/status/window
  var decisions = proposalsData.filter(function (p) {
    return p.status !== 'pending' && sk_matchesFilters(p, sk_filterState);
  });

  // Sort newest first by the "effective date" (decided_at or proposed_at)
  decisions.sort(function (a, b) {
    var da = a.decided_at || a.proposed_at || '';
    var db = b.decided_at || b.proposed_at || '';
    return da < db ? 1 : da > db ? -1 : 0;
  });

  feed.innerHTML = '';

  if (decisions.length === 0) {
    empty.textContent = sk_filterState.search || sk_filterState.status || sk_filterState.window !== 'all'
      ? 'No matches'
      : 'No decisions recorded';
    empty.removeAttribute('hidden');
    return;
  }

  empty.setAttribute('hidden', '');

  // Group by relative-day rail
  var groups = sk_groupByDay(decisions);

  for (var g = 0; g < groups.length; g++) {
    var group = groups[g];

    // Day-rail header
    var rail = document.createElement('div');
    rail.className = 'sk-rail';
    var railLabel = document.createElement('span');
    railLabel.className = 'sk-rail__label';
    railLabel.textContent = group.label + ' (' + group.items.length + ')';
    var railLine = document.createElement('span');
    railLine.className = 'sk-rail__line';
    rail.appendChild(railLabel);
    rail.appendChild(railLine);
    feed.appendChild(rail);

    // Card list
    var ul = document.createElement('ul');
    ul.className = 'sk-card-list';
    ul.setAttribute('role', 'list');

    for (var c = 0; c < group.items.length; c++) {
      var p = group.items[c];
      var li = document.createElement('li');
      li.appendChild(sk_buildCard(p));
      ul.appendChild(li);
    }

    feed.appendChild(ul);
  }
}

// ---------------------------------------------------------------------------
// Build a single decision card (button element)
// ---------------------------------------------------------------------------
function sk_buildCard(p) {
  var e = AdminUI.escapeHtml;

  var card = document.createElement('button');
  card.type = 'button';
  card.className = 'sk-card';
  card.setAttribute('aria-label', e(p.practice_location) + ', ' + sk_fmtDate(p.practice_date, 'short') + ' - ' + sk_statusLabel(p.status));
  card.addEventListener('click', function () { sk_openDrawer(p); });

  // Row 1: header line
  var header = document.createElement('div');
  header.className = 'sk-card__header';

  var locDate = document.createElement('div');
  locDate.className = 'sk-card__loc-date';

  var locSpan = document.createElement('span');
  locSpan.className = 'sk-card__loc';
  locSpan.textContent = p.practice_location;

  var sepSpan = document.createElement('span');
  sepSpan.className = 'sk-card__sep';
  sepSpan.textContent = '·'; // middot

  var dateSpan = document.createElement('span');
  dateSpan.className = 'sk-card__date';
  dateSpan.textContent = sk_fmtDate(p.practice_date, 'short');

  locDate.appendChild(locSpan);
  locDate.appendChild(sepSpan);
  locDate.appendChild(dateSpan);

  var statusBadge = document.createElement('span');
  statusBadge.className = 'sk-status is-' + e(p.status);

  var dot = document.createElement('span');
  dot.className = 'sk-status__dot';
  dot.setAttribute('aria-hidden', 'true');
  statusBadge.appendChild(dot);
  statusBadge.appendChild(document.createTextNode(sk_statusLabel(p.status)));

  header.appendChild(locDate);
  header.appendChild(statusBadge);

  // Row 2: chip + summary
  var body = document.createElement('div');
  body.className = 'sk-card__body';

  var chip = document.createElement('span');
  chip.className = 'sk-chip';
  chip.textContent = sk_formatReasonType(p.reason_type);
  body.appendChild(chip);

  var summary = document.createElement('span');
  summary.className = 'sk-card__summary';
  summary.textContent = p.reason_summary;
  body.appendChild(summary);

  // Row 3: footer meta
  var footer = document.createElement('div');
  footer.className = 'sk-footer';
  footer.textContent = sk_footerText(p);

  card.appendChild(header);
  card.appendChild(body);
  card.appendChild(footer);

  return card;
}

// ---------------------------------------------------------------------------
// Open the detail drawer for a proposal
// ---------------------------------------------------------------------------
function sk_openDrawer(p) {
  var e = AdminUI.escapeHtml;

  // Build content HTML with all server values escaped
  var html = '';

  // Status badge (rendered as first element in body)
  var statusLabel = p.status === 'expired' ? 'Auto-kept (expired)'
    : p.status === 'approved' ? 'Approved'
    : p.status === 'rejected' ? 'Rejected'
    : e(p.status);
  var statusVariant = p.status === 'approved' ? 'success'
    : p.status === 'rejected' ? 'neutral'
    : 'warning'; // expired
  // We'll append the badge DOM node after, since contentHTML is a string

  // Section 1: Decision
  html += '<div class="sk-blk">';
  html += '<div class="sk-blk-h">Decision</div>';
  html += '<div class="sk-kv">';
  html += '<div class="sk-kv-row">' +
    '<span class="sk-kv-label">Practice</span>' +
    '<span class="sk-kv-value">' + e(sk_fmtDate(p.practice_date, 'long')) + ' &mdash; ' + e(p.practice_location) + '</span>' +
  '</div>';
  html += '<div class="sk-kv-row">' +
    '<span class="sk-kv-label">Decided by</span>' +
    '<span class="sk-kv-value">' + (p.decided_by ? e(p.decided_by) : '&mdash;') + '</span>' +
  '</div>';

  var decidedAtText;
  if (p.decided_at) {
    decidedAtText = e(sk_fmtDate(p.decided_at, 'time'));
  } else if (p.expires_at) {
    decidedAtText = 'Auto-kept (timeout) &middot; expired ' + e(sk_fmtDate(p.expires_at, 'time'));
  } else {
    decidedAtText = '&mdash;';
  }
  html += '<div class="sk-kv-row">' +
    '<span class="sk-kv-label">Decided at</span>' +
    '<span class="sk-kv-value">' + decidedAtText + '</span>' +
  '</div>';
  html += '<div class="sk-kv-row">' +
    '<span class="sk-kv-label">Reason</span>' +
    '<span class="sk-kv-value"><span class="sk-chip sk-chip--lg">' + e(sk_formatReasonType(p.reason_type)) + '</span></span>' +
  '</div>';
  html += '</div>'; // sk-kv
  html += '</div>'; // sk-blk

  // Section 2: Reason summary
  html += '<div class="sk-blk">';
  html += '<div class="sk-blk-h">Reason Summary</div>';
  html += '<div class="sk-wblk">' + e(p.reason_summary) + '</div>';
  html += '</div>';

  // Section 3: Decision notes (only if present)
  if (p.decision_notes && p.decision_notes.trim()) {
    html += '<div class="sk-blk">';
    html += '<div class="sk-blk-h">Decision Notes</div>';
    html += '<div class="sk-wblk">' + e(p.decision_notes) + '</div>';
    html += '</div>';
  }

  // Section 4: Threshold violations
  var evalData = p.evaluation_data;
  if (evalData && evalData.violations && evalData.violations.length > 0) {
    html += '<div class="sk-blk">';
    html += '<div class="sk-blk-h">Threshold Violations</div>';
    html += '<div class="sk-violations">';
    for (var v = 0; v < evalData.violations.length; v++) {
      var viol = evalData.violations[v];
      var violVariant = viol.severity === 'critical' ? 'danger' : 'warning';
      var violLabel = viol.severity === 'critical' ? 'Critical' : 'Warning';
      html += '<div class="sk-viol-row">' +
        '<span class="admin-ui-badge ' + (violVariant === 'danger' ? 'bg-red-50 text-red-700' : 'bg-amber-50 text-amber-700') + '">' +
          '<span class="admin-ui-badge__dot" aria-hidden="true"></span>' + e(violLabel) +
        '</span>' +
        '<span class="sk-viol-msg">' + e(viol.message) + '</span>' +
      '</div>';
    }
    html += '</div>'; // sk-violations
    html += '</div>'; // sk-blk
  }

  // Section 5: Weather snapshot
  if (evalData && evalData.weather) {
    var w = evalData.weather;
    html += '<div class="sk-blk sk-snap">';
    html += '<div class="sk-blk-h">Weather at Evaluation</div>';
    html += '<div class="sk-snap-grid">';
    if (w.temperature_f != null) {
      html += '<div class="sk-kv-row"><span class="sk-kv-label">Temperature</span><span class="sk-kv-value">' + e(String(w.temperature_f)) + '°F</span></div>';
    }
    if (w.feels_like_f != null) {
      html += '<div class="sk-kv-row"><span class="sk-kv-label">Feels like</span><span class="sk-kv-value">' + e(String(w.feels_like_f)) + '°F</span></div>';
    }
    if (w.wind_speed_mph != null) {
      html += '<div class="sk-kv-row"><span class="sk-kv-label">Wind</span><span class="sk-kv-value">' + e(String(w.wind_speed_mph)) + ' mph</span></div>';
    }
    if (w.precipitation_chance != null) {
      html += '<div class="sk-kv-row"><span class="sk-kv-label">Precip chance</span><span class="sk-kv-value">' + e(String(w.precipitation_chance)) + '%</span></div>';
    }
    if (w.conditions_summary) {
      html += '<div class="sk-kv-row sk-kv-row--full"><span class="sk-kv-label">Conditions</span><span class="sk-kv-value">' + e(w.conditions_summary) + '</span></div>';
    }
    if (w.has_lightning_threat) {
      html += '<div class="sk-kv-row"><span class="sk-kv-label">Lightning threat</span><span class="sk-kv-value sk-kv-value--warn">Yes - cancel threshold</span></div>';
    }
    html += '</div>'; // sk-snap-grid
    html += '</div>'; // sk-blk sk-snap
  } else if (!evalData) {
    html += '<div class="sk-blk"><p class="sk-no-data">No snapshot recorded</p></div>';
  }

  // Section 6: Trail conditions
  if (evalData && evalData.trail_conditions) {
    var tc = evalData.trail_conditions;
    html += '<div class="sk-blk sk-snap">';
    html += '<div class="sk-blk-h">Trail Conditions at Evaluation</div>';
    html += '<div class="sk-snap-grid">';
    if (tc.location) {
      html += '<div class="sk-kv-row"><span class="sk-kv-label">Location</span><span class="sk-kv-value">' + e(tc.location) + '</span></div>';
    }
    if (tc.trails_open != null) {
      html += '<div class="sk-kv-row"><span class="sk-kv-label">Trails open</span><span class="sk-kv-value">' + (tc.trails_open ? 'Yes' : 'No') + '</span></div>';
    }
    if (tc.ski_quality) {
      html += '<div class="sk-kv-row"><span class="sk-kv-label">Ski quality</span><span class="sk-kv-value">' + e(tc.ski_quality) + '</span></div>';
    }
    if (tc.groomed != null) {
      html += '<div class="sk-kv-row"><span class="sk-kv-label">Groomed</span><span class="sk-kv-value">' + (tc.groomed ? 'Yes' : 'No') + '</span></div>';
    }
    if (tc.groomed_for) {
      html += '<div class="sk-kv-row"><span class="sk-kv-label">Groomed for</span><span class="sk-kv-value">' + e(tc.groomed_for) + '</span></div>';
    }
    html += '</div>'; // sk-snap-grid
    html += '</div>'; // sk-blk sk-snap
  }

  // Section 7: Actions footer
  html += '<div class="sk-drawer-acts">' +
    '<a href="/admin/practices/' + parseInt(p.practice_id, 10) + '" class="sk-btn-primary">View practice</a>' +
  '</div>';

  // Open drawer
  var drawerApi = AdminUI.drawer({
    title: p.practice_location,
    contentHTML: html
  });

  // Insert status badge below the title in the drawer header
  var panel = drawerApi.body.closest('.admin-ui-drawer');
  if (panel) {
    var drawerHeader = panel.querySelector('.admin-ui-drawer__header');
    var titleEl = drawerHeader && drawerHeader.querySelector('.admin-ui-drawer__title');
    if (titleEl) {
      var badge = AdminUI.statusBadge(statusLabel, statusVariant);
      badge.style.marginTop = '4px';
      badge.style.display = 'inline-flex';
      titleEl.style.flexDirection = 'column';
      titleEl.style.alignItems = 'flex-start';
      titleEl.appendChild(badge);
    }
  }
}

// ---------------------------------------------------------------------------
// Filter matching
// ---------------------------------------------------------------------------
function sk_matchesFilters(p, state) {
  // Status filter
  if (state.status && p.status !== state.status) return false;

  // Date window filter - compare against decided_at or proposed_at
  if (state.window && state.window !== 'all') {
    var refDate = p.decided_at || p.proposed_at;
    if (refDate) {
      var d = new Date(refDate);
      var now = new Date();
      var days = state.window === '7d' ? 7 : 30;
      var cutoff = new Date(now.getTime() - days * 24 * 60 * 60 * 1000);
      if (d < cutoff) return false;
    }
  }

  // Search filter (location + reason_summary)
  if (state.search) {
    var q = state.search.toLowerCase();
    var loc = (p.practice_location || '').toLowerCase();
    var rsn = (p.reason_summary || '').toLowerCase();
    if (loc.indexOf(q) === -1 && rsn.indexOf(q) === -1) return false;
  }

  return true;
}

// ---------------------------------------------------------------------------
// Group decisions by relative-day rail
// ---------------------------------------------------------------------------
function sk_groupByDay(decisions) {
  var groups = [];
  var groupMap = {};
  var keyOrder = [];

  for (var i = 0; i < decisions.length; i++) {
    var p = decisions[i];
    var ref = p.decided_at || p.proposed_at;
    var key = sk_relativeDay(ref);
    if (!groupMap[key]) {
      groupMap[key] = { label: key, items: [] };
      keyOrder.push(key);
    }
    groupMap[key].items.push(p);
  }

  for (var j = 0; j < keyOrder.length; j++) {
    groups.push(groupMap[keyOrder[j]]);
  }

  return groups;
}

// ---------------------------------------------------------------------------
// Relative day label for a given ISO timestamp (Central time)
// ---------------------------------------------------------------------------
function sk_relativeDay(isoString) {
  if (!isoString) return 'Earlier';

  var d = new Date(isoString);
  var nowCentral = new Date(new Date().toLocaleString('en-US', { timeZone: 'America/Chicago' }));
  var dCentral = new Date(d.toLocaleString('en-US', { timeZone: 'America/Chicago' }));

  // Compare by date parts only
  function ymd(date) {
    return [date.getFullYear(), date.getMonth(), date.getDate()];
  }

  var todayParts = ymd(nowCentral);
  var dParts = ymd(dCentral);

  if (todayParts[0] === dParts[0] && todayParts[1] === dParts[1] && todayParts[2] === dParts[2]) {
    return 'Today';
  }

  var yesterday = new Date(nowCentral);
  yesterday.setDate(yesterday.getDate() - 1);
  var yestParts = ymd(yesterday);
  if (yestParts[0] === dParts[0] && yestParts[1] === dParts[1] && yestParts[2] === dParts[2]) {
    return 'Yesterday';
  }

  // This week: Mon-Sun of the current week
  var nowDay = nowCentral.getDay(); // 0=Sun, 1=Mon, ..., 6=Sat
  var daysSinceMon = (nowDay + 6) % 7; // days since Monday
  var weekStart = new Date(nowCentral);
  weekStart.setDate(weekStart.getDate() - daysSinceMon);
  weekStart.setHours(0, 0, 0, 0);

  if (dCentral >= weekStart) {
    return 'This Week';
  }

  // Month/year label
  return dCentral.toLocaleString('en-US', {
    timeZone: 'America/Chicago',
    month: 'long',
    year: 'numeric'
  });
}

// ---------------------------------------------------------------------------
// Date formatting (Central time)
// ---------------------------------------------------------------------------
function sk_fmtDate(isoString, mode) {
  if (!isoString) return '';
  var d = new Date(isoString);

  if (mode === 'short') {
    // e.g. "Jun 2"
    return d.toLocaleString('en-US', {
      timeZone: 'America/Chicago',
      month: 'short',
      day: 'numeric'
    });
  } else if (mode === 'long') {
    // e.g. "Monday, June 2, 2026"
    return d.toLocaleString('en-US', {
      timeZone: 'America/Chicago',
      weekday: 'long',
      month: 'long',
      day: 'numeric',
      year: 'numeric'
    });
  } else if (mode === 'time') {
    // e.g. "Jun 2 at 3:41 PM"
    var datePart = d.toLocaleString('en-US', {
      timeZone: 'America/Chicago',
      month: 'short',
      day: 'numeric'
    });
    var timePart = d.toLocaleString('en-US', {
      timeZone: 'America/Chicago',
      hour: 'numeric',
      minute: '2-digit',
      hour12: true
    });
    return datePart + ' at ' + timePart;
  }
  return d.toLocaleString('en-US', { timeZone: 'America/Chicago' });
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function sk_statusLabel(status) {
  if (status === 'approved') return 'Approved';
  if (status === 'rejected') return 'Rejected';
  if (status === 'expired') return 'Auto-kept';
  return status || '';
}

function sk_formatReasonType(rt) {
  if (!rt) return '';
  return rt.replace(/_/g, ' ').replace(/\b\w/g, function (c) { return c.toUpperCase(); });
}

function sk_footerText(p) {
  if (p.decided_at && p.decided_by) {
    return 'Decided by ' + p.decided_by + ' · ' + sk_fmtDate(p.decided_at, 'time');
  } else if (p.decided_at) {
    return 'Decided · ' + sk_fmtDate(p.decided_at, 'time');
  } else if (p.expires_at) {
    return 'Auto-kept · expired ' + sk_fmtDate(p.expires_at, 'time');
  }
  return 'No decision recorded';
}

// ---------------------------------------------------------------------------
// Expose entry points needed by inline HTML handlers
// ---------------------------------------------------------------------------
window.approveProposal = approveProposal;
window.rejectProposal = rejectProposal;
window.refreshConfig = refreshConfig;

})();
