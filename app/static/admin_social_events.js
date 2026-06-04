// admin_social_events.js — Social Events bespoke event-ledger UI
// Replaces Tabulator grid with a date-forward card list grouped into Upcoming/Past.
// Reads GET /admin/social-events/data; mutations POST /admin/social-events/{id}/delete.
//
// NOTE: event_date is a pre-formatted 'Month D, YYYY' display string (e.g. 'June 4, 2026').
// This format is reliably parseable in all modern JS engines via new Date().
// If parsing yields NaN, the event is treated as upcoming (fail open).
(function () {
  'use strict';

  /* ---- module state ---- */
  var sevData = [];
  var sevFilterStatus = 'all';
  var sevSearchQ = '';
  var sevPastExpanded = false;
  var sevPastLimit = 20;
  var sevCurrentDrawer = null; // { close, id }
  var sevLastFocused = null;

  /* ---- date helpers (Central, date-string based) ---- */
  function chicagoTodayYMD() {
    return new Intl.DateTimeFormat('en-CA', {
      timeZone: 'America/Chicago',
      year: 'numeric', month: '2-digit', day: '2-digit'
    }).format(new Date());
  }

  // Parse 'Month D, YYYY' -> 'YYYY-MM-DD' for comparison.
  // Returns null if unparseable (fail open: treat as upcoming).
  function sevParseEventDate(displayDate) {
    if (!displayDate) return null;
    // new Date('January 15, 2026') is reliably parsed in V8, JavaScriptCore, SpiderMonkey.
    var d = new Date(displayDate);
    if (isNaN(d.getTime())) return null;
    // Build YYYY-MM-DD from local Date parts to avoid UTC offset issues.
    // Since the display string has no time, getMonth/getDate are local-time.
    var y = d.getFullYear();
    var m = String(d.getMonth() + 1).padStart(2, '0');
    var day = String(d.getDate()).padStart(2, '0');
    return y + '-' + m + '-' + day;
  }

  /* ---- price formatter (social events: 0/null -> 'Free'; cents -> $N.NN) ---- */
  function sevFormatPrice(cents) {
    if (!cents) return 'Free';
    return '$' + (cents / 100).toFixed(2);
  }

  /* ---- signup-window pill element ---- */
  function sevSignupPill(signup_start, signup_end) {
    if (!signup_start && !signup_end) return null;
    var today = chicagoTodayYMD();
    var cls, label;
    if (signup_start && today < signup_start) {
      var d = new Date(signup_start + 'T12:00:00Z');
      var mon = d.toLocaleString('en-US', { month: 'short', timeZone: 'UTC' });
      var dayN = d.getUTCDate();
      cls = 'sl-signup opens';
      label = 'Opens ' + mon + ' ' + dayN;
    } else if (signup_end && today > signup_end) {
      cls = 'sl-signup closed';
      label = 'Signups closed';
    } else {
      cls = 'sl-signup open';
      label = 'Signups open';
    }
    return AdminUI.el('span', { class: cls }, [label]);
  }

  /* ---- capacity chip element ---- */
  function sevCapChip(max_participants) {
    var label, ariaLabel;
    if (max_participants === null || max_participants === undefined) {
      label = 'No limit';
      ariaLabel = 'Capacity: no limit';
    } else {
      label = max_participants + ' seats';
      ariaLabel = 'Capacity: ' + max_participants + ' seats';
    }
    return AdminUI.el('span', { class: 'sl-cap', 'aria-label': ariaLabel }, [label]);
  }

  /* ---- status badge variant mapping ---- */
  function sevStatusVariant(status) {
    if (status === 'active') return 'success';
    if (status === 'closed') return 'danger';
    return 'neutral'; // draft or unknown
  }

  /* ---- filter predicate ---- */
  function sevMatchesFilters(evt) {
    if (sevFilterStatus !== 'all' && evt.status !== sevFilterStatus) return false;
    if (!sevSearchQ) return true;
    var hay = ((evt.name || '') + ' ' + (evt.location || '')).toLowerCase();
    return hay.includes(sevSearchQ);
  }

  /* ---- group upcoming/past ---- */
  function sevGroupUpcomingPast(rows) {
    var today = chicagoTodayYMD();
    var upcoming = [], past = [];
    rows.forEach(function (evt) {
      var ymd = sevParseEventDate(evt.event_date);
      if (ymd && ymd < today) {
        past.push(evt);
      } else {
        // Fail open: null parse or >= today -> upcoming
        upcoming.push(evt);
      }
    });
    // Upcoming: soonest first; Past: most recent first
    upcoming.sort(function (a, b) {
      var da = sevParseEventDate(a.event_date) || '';
      var db = sevParseEventDate(b.event_date) || '';
      return da < db ? -1 : da > db ? 1 : 0;
    });
    past.sort(function (a, b) {
      var da = sevParseEventDate(a.event_date) || '';
      var db = sevParseEventDate(b.event_date) || '';
      return da > db ? -1 : da < db ? 1 : 0;
    });
    return { upcoming: upcoming, past: past };
  }

  /* ---- date block element from 'Month D, YYYY' string ---- */
  function sevDateBlock(displayDate) {
    var cls = 'sl-db';
    var mon = '', dayStr = '';
    if (displayDate) {
      var ymd = sevParseEventDate(displayDate);
      if (ymd) {
        var today = chicagoTodayYMD();
        if (ymd === today) cls += ' is-today';
        var d = new Date(displayDate);
        mon = d.toLocaleString('en-US', { month: 'short' }).toUpperCase();
        dayStr = String(d.getDate());
      }
    }
    return AdminUI.el('div', { class: cls }, [
      AdminUI.el('span', { class: 'mo' }, [mon]),
      AdminUI.el('span', { class: 'dn' }, [dayStr])
    ]);
  }

  /* ---- render a single card ---- */
  function sevRenderCard(evt, isPast) {
    var el = AdminUI.el;
    var esc = AdminUI.escapeHtml;

    var priceText = sevFormatPrice(evt.price);
    var dateTimeText = evt.event_date || '';
    if (evt.event_time) dateTimeText += ' at ' + evt.event_time;

    // Meta line children
    var metaChildren = [];
    if (evt.location) {
      metaChildren.push(el('span', null, [evt.location]));
    }
    if (dateTimeText) {
      if (metaChildren.length) metaChildren.push(el('span', { class: 'sep', 'aria-hidden': 'true' }, ['·']));
      metaChildren.push(el('span', null, [dateTimeText]));
    }
    metaChildren.push(el('span', { class: 'sep', 'aria-hidden': 'true' }, ['·']));
    metaChildren.push(el('span', { class: 'price' }, [priceText]));
    metaChildren.push(el('span', { class: 'sep', 'aria-hidden': 'true' }, ['·']));
    metaChildren.push(sevCapChip(evt.max_participants));
    var pill = sevSignupPill(evt.signup_start, evt.signup_end);
    if (pill) {
      metaChildren.push(el('span', { class: 'sep', 'aria-hidden': 'true' }, ['·']));
      metaChildren.push(pill);
    }

    var nameLink = el('a', {
      href: '/admin/social-events/' + evt.id + '/edit',
      'aria-label': 'Edit ' + esc(evt.name),
      onclick: function (e) { e.stopPropagation(); }
    }, [evt.name || '']);

    var editBtn = el('a', {
      class: 'sl-edit',
      href: '/admin/social-events/' + evt.id + '/edit',
      'aria-label': 'Edit ' + esc(evt.name),
      onclick: function (e) { e.stopPropagation(); }
    }, ['Edit']);

    var deleteBtn = el('button', {
      type: 'button',
      class: 'sl-delete',
      'aria-label': 'Delete ' + esc(evt.name),
      onclick: function (e) { e.stopPropagation(); sevDelete(evt.id, evt.name); }
    }, ['Delete']);

    var badge = AdminUI.statusBadge(
      evt.status ? (evt.status.charAt(0).toUpperCase() + evt.status.slice(1)) : '',
      sevStatusVariant(evt.status)
    );

    var cardAriaLabel = (evt.name || '') + ', ' +
      (evt.event_date || '') + ', ' +
      (evt.status || '') + '. Press Enter to preview.';

    var card = el('div', {
      class: 'sl-card',
      tabindex: '0',
      role: 'button',
      'aria-label': cardAriaLabel,
      dataset: { id: String(evt.id) }
    }, [
      sevDateBlock(evt.event_date),
      el('div', { class: 'sl-card-main' }, [
        nameLink,
        el('div', { class: 'sl-meta' }, metaChildren)
      ]),
      el('div', { class: 'sl-card-aside' }, [
        badge,
        el('div', { class: 'sl-actions' }, [editBtn, deleteBtn])
      ])
    ]);

    card.addEventListener('click', function () {
      sevOpenDrawer(evt, card);
    });
    card.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        sevOpenDrawer(evt, card);
      }
    });

    return card;
  }

  /* ---- render section header ---- */
  function sevSecHeader(label, count) {
    return AdminUI.el('div', { class: 'sl-sec' }, [
      label,
      AdminUI.el('span', { class: 'sl-sec-rule' }, []),
      AdminUI.el('span', { class: 'sl-sec-count' }, [String(count)])
    ]);
  }

  /* ---- update count chip ---- */
  function sevUpdateCount(n) {
    var chip = document.getElementById('sev-count');
    if (chip) chip.textContent = n === 1 ? '1 event' : n + ' events';
  }

  /* ---- main render ---- */
  function sevRender() {
    var root = document.getElementById('sev-rows');
    if (!root) return;

    var filtered = sevData.filter(sevMatchesFilters);
    var groups = sevGroupUpcomingPast(filtered);
    var upcoming = groups.upcoming;
    var past = groups.past;
    var total = filtered.length;

    sevUpdateCount(total);

    while (root.firstChild) root.removeChild(root.firstChild);

    if (total === 0 && sevData.length === 0) {
      root.appendChild(AdminUI.el('p', { class: 'sl-empty' }, ['No social events yet.']));
      return;
    }

    if (total === 0) {
      root.appendChild(AdminUI.el('p', { class: 'sl-empty' }, ['No events match your search.']));
      return;
    }

    if (upcoming.length > 0) {
      root.appendChild(sevSecHeader('Upcoming', upcoming.length));
      var upCards = AdminUI.el('div', { class: 'sl-cards' }, []);
      upcoming.forEach(function (evt) { upCards.appendChild(sevRenderCard(evt, false)); });
      root.appendChild(upCards);
    }

    if (past.length > 0) {
      var toggleBtn = AdminUI.el('button', {
        type: 'button',
        class: 'sl-past-toggle',
        'aria-expanded': sevPastExpanded ? 'true' : 'false',
        'aria-controls': 'sl-past-list'
      }, [
        AdminUI.el('span', { class: 'chev', 'aria-hidden': 'true' }, ['▸']),
        ' Past events ',
        AdminUI.el('span', { class: 'sl-past-dim' }, ['— ' + past.length])
      ]);
      root.appendChild(toggleBtn);

      if (sevPastExpanded) {
        var slice = past.slice(0, sevPastLimit);
        var remaining = past.length - slice.length;
        var pastList = AdminUI.el('div', { class: 'sl-past-list sl-cards', id: 'sl-past-list' }, []);
        slice.forEach(function (evt) { pastList.appendChild(sevRenderCard(evt, true)); });

        if (remaining > 0) {
          var loadBtn = AdminUI.el('button', {
            type: 'button',
            class: 'sl-loadmore',
            onclick: function () {
              sevPastLimit += 20;
              sevRender();
            }
          }, ['Load more (' + remaining + ')']);
          pastList.appendChild(loadBtn);
        }
        root.appendChild(pastList);
      }

      toggleBtn.addEventListener('click', function () {
        sevPastExpanded = !sevPastExpanded;
        sevRender();
        var newToggle = root.querySelector('.sl-past-toggle');
        if (newToggle) newToggle.focus();
      });
    }
  }

  /* ---- drawer ---- */
  function sevOpenDrawer(evt, cardEl) {
    sevLastFocused = cardEl;

    document.querySelectorAll('#sev-rows .sl-card.is-active').forEach(function (c) {
      c.classList.remove('is-active');
    });
    if (cardEl) cardEl.classList.add('is-active');

    var rowsEl = document.getElementById('sev-rows');
    var toolbarEl = document.querySelector('#sev-list .sl-toolbar');
    var headEl = document.querySelector('#sev-list .sl-head');
    if (rowsEl) rowsEl.inert = true;
    if (toolbarEl) toolbarEl.inert = true;
    if (headEl) headEl.inert = true;

    var esc = AdminUI.escapeHtml;
    var dateTimeText = evt.event_date || '';
    if (evt.event_time) dateTimeText += ' at ' + evt.event_time;

    var subLine = AdminUI.el('p', { class: 'sl-dw-sub' }, [
      (evt.location || '') + (dateTimeText ? ' · ' + dateTimeText : '')
    ]);

    var kvRows = [
      { k: 'Location', v: evt.location || '-' },
      { k: 'Date', v: evt.event_date || '-' },
      { k: 'Time', v: evt.event_time || '-' }
    ];

    var swText = '';
    if (evt.signup_start || evt.signup_end) {
      var today = chicagoTodayYMD();
      if (evt.signup_start && today < evt.signup_start) {
        var d = new Date(evt.signup_start + 'T12:00:00Z');
        var mon = d.toLocaleString('en-US', { month: 'short', timeZone: 'UTC' });
        swText = 'Opens ' + mon + ' ' + d.getUTCDate();
      } else if (evt.signup_end && today > evt.signup_end) {
        swText = 'Signups closed';
      } else {
        swText = 'Signups open';
      }
    }
    if (swText) kvRows.push({ k: 'Signups', v: swText });

    kvRows.push({ k: 'Price', v: sevFormatPrice(evt.price) });
    kvRows.push({
      k: 'Max participants',
      v: evt.max_participants !== null && evt.max_participants !== undefined
        ? String(evt.max_participants)
        : 'No limit'
    });

    var contentDiv = AdminUI.el('div', null, []);
    contentDiv.appendChild(subLine);
    kvRows.forEach(function (row) {
      contentDiv.appendChild(
        AdminUI.el('div', { class: 'sl-kv' }, [
          AdminUI.el('span', { class: 'k' }, [row.k]),
          AdminUI.el('span', { class: 'v' }, [row.v])
        ])
      );
    });

    var badgeRow = AdminUI.el('div', { class: 'sl-kv' }, [
      AdminUI.el('span', { class: 'k' }, ['Status']),
      AdminUI.el('span', { class: 'v' }, [
        AdminUI.statusBadge(
          evt.status ? (evt.status.charAt(0).toUpperCase() + evt.status.slice(1)) : '',
          sevStatusVariant(evt.status)
        )
      ])
    ]);
    contentDiv.appendChild(badgeRow);

    var drawer = AdminUI.drawer({ title: evt.name || 'Event', content: contentDiv });
    sevCurrentDrawer = { close: drawer.close, id: evt.id };

    var editA = AdminUI.el('a', {
      class: 'sl-dw-edit',
      href: '/admin/social-events/' + evt.id + '/edit'
    }, ['Edit']);
    var deleteB = AdminUI.el('button', {
      type: 'button',
      class: 'sl-dw-delete',
      onclick: function () { sevDelete(evt.id, evt.name); }
    }, ['Delete']);
    var footer = AdminUI.el('div', { class: 'sl-dwfooter' }, [editA, deleteB]);
    drawer.body.appendChild(footer);

    // Watch for drawer panel removal (Esc / scrim close) to restore state
    var panelEl = document.querySelector('.admin-ui-drawer');
    if (panelEl) {
      var obs = new MutationObserver(function (mutations) {
        mutations.forEach(function (m) {
          m.removedNodes.forEach(function (n) {
            if (n === panelEl) {
              obs.disconnect();
              if (rowsEl) rowsEl.inert = false;
              if (toolbarEl) toolbarEl.inert = false;
              if (headEl) headEl.inert = false;
              document.querySelectorAll('#sev-rows .sl-card.is-active').forEach(function (c) {
                c.classList.remove('is-active');
              });
              if (sevLastFocused) {
                sevLastFocused.focus();
                sevLastFocused = null;
              }
              sevCurrentDrawer = null;
            }
          });
        });
      });
      obs.observe(document.body, { childList: true });
    }

    var origClose = drawer.close;
    sevCurrentDrawer.close = function () {
      origClose();
      if (rowsEl) rowsEl.inert = false;
      if (toolbarEl) toolbarEl.inert = false;
      if (headEl) headEl.inert = false;
      document.querySelectorAll('#sev-rows .sl-card.is-active').forEach(function (c) {
        c.classList.remove('is-active');
      });
      if (sevLastFocused) {
        sevLastFocused.focus();
        sevLastFocused = null;
      }
      sevCurrentDrawer = null;
    };
  }

  /* ---- delete handler ---- */
  function sevDelete(id, name) {
    if (!confirm('Delete event "' + (name || '') + '"?\n\nThis cannot be undone.')) return;
    AdminUI.mutate('/admin/social-events/' + id + '/delete').then(function () {
      if (window.showToast) showToast('Event deleted', 'success');
      if (sevCurrentDrawer && sevCurrentDrawer.id === id) {
        sevCurrentDrawer.close();
      }
      sevData = sevData.filter(function (e) { return e.id !== id; });
      sevRender();
    }).catch(function () {
      // AdminUI.mutate already toasts the error
    });
  }

  /* ---- attach toolbar listeners ---- */
  function sevAttachListeners() {
    var searchEl = document.getElementById('events-search');
    if (searchEl) {
      searchEl.addEventListener('input', function (e) {
        sevSearchQ = e.target.value.toLowerCase().trim();
        sevRender();
      });
    }

    document.querySelectorAll('#sev-list .sl-pill').forEach(function (pill) {
      pill.addEventListener('click', function () {
        document.querySelectorAll('#sev-list .sl-pill').forEach(function (p) {
          p.setAttribute('aria-pressed', 'false');
        });
        pill.setAttribute('aria-pressed', 'true');
        sevFilterStatus = pill.dataset.status || 'all';
        sevRender();
      });
    });
  }

  /* ---- init ---- */
  AdminUI.onReady(function () {
    sevAttachListeners();
    AdminUI.fetchJSON('/admin/social-events/data').then(function (data) {
      sevData = data.events || [];
      sevRender();
    }).catch(function () {
      if (window.showToast) showToast('Failed to load events. Reload the page to retry.', 'error');
      var root = document.getElementById('sev-rows');
      if (root) {
        while (root.firstChild) root.removeChild(root.firstChild);
        root.appendChild(AdminUI.el('p', { class: 'sl-empty' }, ['Something went wrong. Try reloading.']));
      }
      sevUpdateCount(0);
    });
  });
})();
