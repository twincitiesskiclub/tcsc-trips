// admin_trips.js — Trips bespoke event-ledger UI
// Replaces Tabulator grid with a date-forward card list grouped into Upcoming/Past.
// Reads GET /admin/trips/data; mutations POST /admin/trips/{id}/delete.
(function () {
  'use strict';

  /* ---- module state ---- */
  var tripsData = [];
  var tripsFilterStatus = 'all';
  var tripsSearchQ = '';
  var tripsPastExpanded = false;
  var tripsPastLimit = 20;
  var tripsCurrentDrawer = null; // { close, id }
  var tripsLastFocused = null;

  /* ---- date helpers (Central, date-string based) ---- */
  function chicagoTodayYMD() {
    return new Intl.DateTimeFormat('en-CA', {
      timeZone: 'America/Chicago',
      year: 'numeric', month: '2-digit', day: '2-digit'
    }).format(new Date());
  }

  /* ---- price formatter (trips: falsy -> '-'; cents -> $N.NN) ---- */
  function formatPrice(cents) {
    if (!cents) return '-';
    return '$' + (cents / 100).toFixed(2);
  }

  /* ---- signup-window pill element ---- */
  function tripsSignupPill(signup_start, signup_end) {
    if (!signup_start && !signup_end) return null;
    var today = chicagoTodayYMD();
    var cls, label;
    if (signup_start && today < signup_start) {
      // Before open: "Opens MMM D"
      var d = new Date(signup_start + 'T12:00:00Z');
      var mon = d.toLocaleString('en-US', { month: 'short', timeZone: 'UTC' });
      var day = d.getUTCDate();
      cls = 'tl-signup opens';
      label = 'Opens ' + mon + ' ' + day;
    } else if (signup_end && today > signup_end) {
      cls = 'tl-signup closed';
      label = 'Signups closed';
    } else {
      cls = 'tl-signup open';
      label = 'Signups open';
    }
    return AdminUI.el('span', { class: cls }, [label]);
  }

  /* ---- capacity chip element ---- */
  function tripsCapChip(std, extra) {
    var stdVal = (std === null || std === undefined) ? null : std;
    var extVal = (extra === null || extra === undefined) ? null : extra;
    var label, ariaLabel;
    if (stdVal === null && extVal === null) {
      label = 'No capacity set';
      ariaLabel = 'Capacity: not set';
    } else {
      label = 'std ' + (stdVal || 0) + ' / extra ' + (extVal || 0);
      ariaLabel = 'Capacity: std ' + (stdVal || 0) + ', extra ' + (extVal || 0);
    }
    return AdminUI.el('span', { class: 'tl-cap', 'aria-label': ariaLabel }, [label]);
  }

  /* ---- status badge variant mapping ---- */
  function tripsStatusVariant(status) {
    if (status === 'active') return 'success';
    if (status === 'closed') return 'danger';
    return 'neutral'; // draft or unknown
  }

  /* ---- filter predicate ---- */
  function tripsMatchesFilters(trip) {
    if (tripsFilterStatus !== 'all' && trip.status !== tripsFilterStatus) return false;
    if (!tripsSearchQ) return true;
    var hay = ((trip.name || '') + ' ' + (trip.destination || '')).toLowerCase();
    return hay.includes(tripsSearchQ);
  }

  /* ---- group upcoming/past ---- */
  function tripsGroupUpcomingPast(rows) {
    var today = chicagoTodayYMD();
    var upcoming = [], past = [];
    rows.forEach(function (t) {
      var d = (t.start_date || '').slice(0, 10);
      if (d && d < today) {
        past.push(t);
      } else {
        upcoming.push(t);
      }
    });
    // Upcoming: soonest first; Past: most recent first
    upcoming.sort(function (a, b) {
      return (a.start_date || '') < (b.start_date || '') ? -1 : 1;
    });
    past.sort(function (a, b) {
      return (a.start_date || '') > (b.start_date || '') ? -1 : 1;
    });
    return { upcoming: upcoming, past: past };
  }

  /* ---- date block element ---- */
  function tripsDateBlock(isoDate, isPast) {
    var cls = 'tl-db';
    var mon = '', day = '';
    if (isoDate) {
      var today = chicagoTodayYMD();
      if (isoDate.slice(0, 10) === today) cls += ' is-today';
      var d = new Date(isoDate + 'T12:00:00Z');
      mon = d.toLocaleString('en-US', { month: 'short', timeZone: 'UTC' }).toUpperCase();
      day = String(d.getUTCDate());
    }
    return AdminUI.el('div', { class: cls }, [
      AdminUI.el('span', { class: 'mo' }, [mon]),
      AdminUI.el('span', { class: 'dn' }, [day])
    ]);
  }

  /* ---- render a single card ---- */
  function tripsRenderCard(trip, isPast) {
    var el = AdminUI.el;
    var esc = AdminUI.escapeHtml;

    // Price display
    var priceText;
    if (trip.price_low === trip.price_high) {
      priceText = formatPrice(trip.price_low);
    } else {
      priceText = formatPrice(trip.price_low) + ' – ' + formatPrice(trip.price_high);
    }

    // Meta line children
    var metaChildren = [];
    if (trip.destination) {
      metaChildren.push(AdminUI.el('span', null, [trip.destination]));
    }
    if (trip.date_range) {
      if (metaChildren.length) metaChildren.push(AdminUI.el('span', { class: 'sep', 'aria-hidden': 'true' }, ['·']));
      metaChildren.push(AdminUI.el('span', null, [trip.date_range]));
    }
    if (trip.price_low || trip.price_high) {
      if (metaChildren.length) metaChildren.push(AdminUI.el('span', { class: 'sep', 'aria-hidden': 'true' }, ['·']));
      metaChildren.push(AdminUI.el('span', { class: 'price' }, [priceText]));
    }
    // Capacity chip
    metaChildren.push(el('span', { class: 'sep', 'aria-hidden': 'true' }, ['·']));
    metaChildren.push(tripsCapChip(trip.capacity_standard, trip.capacity_extra));
    // Signup pill
    var pill = tripsSignupPill(trip.signup_start, trip.signup_end);
    if (pill) {
      metaChildren.push(el('span', { class: 'sep', 'aria-hidden': 'true' }, ['·']));
      metaChildren.push(pill);
    }

    var nameLink = el('a', {
      href: '/admin/trips/' + trip.id + '/edit',
      'aria-label': 'Edit ' + esc(trip.name),
      onclick: function (e) { e.stopPropagation(); }
    }, [trip.name || '']);

    var editBtn = el('a', {
      class: 'tl-edit',
      href: '/admin/trips/' + trip.id + '/edit',
      'aria-label': 'Edit ' + esc(trip.name),
      onclick: function (e) { e.stopPropagation(); }
    }, ['Edit']);

    var deleteBtn = el('button', {
      type: 'button',
      class: 'tl-delete',
      'aria-label': 'Delete ' + esc(trip.name),
      onclick: function (e) { e.stopPropagation(); tripsDelete(trip.id, trip.name); }
    }, ['Delete']);

    var badge = AdminUI.statusBadge(
      trip.status ? (trip.status.charAt(0).toUpperCase() + trip.status.slice(1)) : '',
      tripsStatusVariant(trip.status)
    );

    var cardAriaLabel = (trip.name || '') + ', ' +
      (trip.date_range || trip.start_date || '') + ', ' +
      (trip.status || '') + '. Press Enter to preview.';

    var card = el('div', {
      class: 'tl-card',
      tabindex: '0',
      role: 'button',
      'aria-label': cardAriaLabel,
      dataset: { id: String(trip.id) }
    }, [
      tripsDateBlock(trip.start_date, isPast),
      el('div', { class: 'tl-card-main' }, [
        nameLink,
        el('div', { class: 'tl-meta' }, metaChildren)
      ]),
      el('div', { class: 'tl-card-aside' }, [
        badge,
        el('div', { class: 'tl-actions' }, [editBtn, deleteBtn])
      ])
    ]);

    // Card body click: open drawer
    card.addEventListener('click', function () {
      tripsOpenDrawer(trip, card);
    });
    card.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        tripsOpenDrawer(trip, card);
      }
    });

    return card;
  }

  /* ---- render section header ---- */
  function tripsSecHeader(label, count) {
    return AdminUI.el('div', { class: 'tl-sec' }, [
      label,
      AdminUI.el('span', { class: 'tl-sec-rule' }, []),
      AdminUI.el('span', { class: 'tl-sec-count' }, [String(count)])
    ]);
  }

  /* ---- update count chip ---- */
  function tripsUpdateCount(n) {
    var chip = document.getElementById('trip-count');
    if (chip) chip.textContent = n === 1 ? '1 trip' : n + ' trips';
  }

  /* ---- main render ---- */
  function tripsRender() {
    var root = document.getElementById('trips-rows');
    if (!root) return;

    var filtered = tripsData.filter(tripsMatchesFilters);
    var groups = tripsGroupUpcomingPast(filtered);
    var upcoming = groups.upcoming;
    var past = groups.past;
    var total = filtered.length;

    tripsUpdateCount(total);

    // Clear
    while (root.firstChild) root.removeChild(root.firstChild);

    if (total === 0 && tripsData.length === 0) {
      var emptyEl = AdminUI.el('p', { class: 'tl-empty' }, [
        'No trips yet. ',
        AdminUI.el('a', { href: '/admin/trips/new' }, ['Create the first one.'])
      ]);
      root.appendChild(emptyEl);
      return;
    }

    if (total === 0) {
      root.appendChild(AdminUI.el('p', { class: 'tl-empty' }, ['No trips match your search.']));
      return;
    }

    // Upcoming section
    if (upcoming.length > 0) {
      root.appendChild(tripsSecHeader('Upcoming', upcoming.length));
      var upCards = AdminUI.el('div', { class: 'tl-cards' }, []);
      upcoming.forEach(function (t) { upCards.appendChild(tripsRenderCard(t, false)); });
      root.appendChild(upCards);
    }

    // Past section
    if (past.length > 0) {
      var toggleBtn = AdminUI.el('button', {
        type: 'button',
        class: 'tl-past-toggle',
        'aria-expanded': tripsPastExpanded ? 'true' : 'false',
        'aria-controls': 'tl-past-list'
      }, [
        AdminUI.el('span', { class: 'chev', 'aria-hidden': 'true' }, ['▸']),
        ' Past trips ',
        AdminUI.el('span', { class: 'tl-past-dim' }, ['— ' + past.length])
      ]);
      root.appendChild(toggleBtn);

      if (tripsPastExpanded) {
        var slice = past.slice(0, tripsPastLimit);
        var remaining = past.length - slice.length;
        var pastList = AdminUI.el('div', { class: 'tl-past-list tl-cards', id: 'tl-past-list' }, []);
        slice.forEach(function (t) { pastList.appendChild(tripsRenderCard(t, true)); });

        if (remaining > 0) {
          var loadBtn = AdminUI.el('button', {
            type: 'button',
            class: 'tl-loadmore',
            onclick: function () {
              tripsPastLimit += 20;
              tripsRender();
            }
          }, ['Load more (' + remaining + ')']);
          pastList.appendChild(loadBtn);
        }
        root.appendChild(pastList);
      }

      toggleBtn.addEventListener('click', function () {
        tripsPastExpanded = !tripsPastExpanded;
        tripsRender();
        // Keep toggle button focused
        var newToggle = root.querySelector('.tl-past-toggle');
        if (newToggle) newToggle.focus();
      });
    }
  }

  /* ---- drawer ---- */
  function tripsOpenDrawer(trip, cardEl) {
    tripsLastFocused = cardEl;

    // Mark card active
    document.querySelectorAll('#trips-rows .tl-card.is-active').forEach(function (c) {
      c.classList.remove('is-active');
    });
    if (cardEl) cardEl.classList.add('is-active');

    // Inert background
    var rowsEl = document.getElementById('trips-rows');
    var toolbarEl = document.querySelector('#trips-list .tl-toolbar');
    var headEl = document.querySelector('#trips-list .tl-head');
    if (rowsEl) rowsEl.inert = true;
    if (toolbarEl) toolbarEl.inert = true;
    if (headEl) headEl.inert = true;

    var esc = AdminUI.escapeHtml;

    // Build drawer body content
    var subLine = AdminUI.el('p', { class: 'tl-dw-sub' }, [
      (trip.destination || '') + (trip.date_range ? ' · ' + trip.date_range : '')
    ]);

    var kvRows = [
      { k: 'Destination', v: trip.destination || '-' },
      { k: 'Dates', v: trip.date_range || '-' }
    ];

    // Signup window
    var swText = '';
    if (trip.signup_start || trip.signup_end) {
      var today = chicagoTodayYMD();
      if (trip.signup_start && today < trip.signup_start) {
        var d = new Date(trip.signup_start + 'T12:00:00Z');
        var mon = d.toLocaleString('en-US', { month: 'short', timeZone: 'UTC' });
        swText = 'Opens ' + mon + ' ' + d.getUTCDate();
      } else if (trip.signup_end && today > trip.signup_end) {
        swText = 'Signups closed';
      } else {
        swText = 'Signups open';
      }
    }
    if (swText) kvRows.push({ k: 'Signups', v: swText });

    // Price
    var priceText;
    if (trip.price_low === trip.price_high) {
      priceText = formatPrice(trip.price_low);
    } else {
      priceText = formatPrice(trip.price_low) + ' – ' + formatPrice(trip.price_high);
    }
    kvRows.push({ k: 'Price', v: priceText });

    // Capacity
    var stdV = (trip.capacity_standard === null || trip.capacity_standard === undefined) ? 'not set' : trip.capacity_standard;
    var extV = (trip.capacity_extra === null || trip.capacity_extra === undefined) ? 'not set' : trip.capacity_extra;
    kvRows.push({ k: 'Std seats', v: String(stdV) });
    kvRows.push({ k: 'Extra seats', v: String(extV) });

    var contentDiv = AdminUI.el('div', null, []);
    contentDiv.appendChild(subLine);
    kvRows.forEach(function (row) {
      contentDiv.appendChild(
        AdminUI.el('div', { class: 'tl-kv' }, [
          AdminUI.el('span', { class: 'k' }, [row.k]),
          AdminUI.el('span', { class: 'v' }, [row.v])
        ])
      );
    });

    // Status badge row
    var badgeRow = AdminUI.el('div', { class: 'tl-kv' }, [
      AdminUI.el('span', { class: 'k' }, ['Status']),
      AdminUI.el('span', { class: 'v' }, [
        AdminUI.statusBadge(
          trip.status ? (trip.status.charAt(0).toUpperCase() + trip.status.slice(1)) : '',
          tripsStatusVariant(trip.status)
        )
      ])
    ]);
    contentDiv.appendChild(badgeRow);

    var drawer = AdminUI.drawer({ title: trip.name || 'Trip', content: contentDiv });
    tripsCurrentDrawer = { close: drawer.close, id: trip.id };

    // Footer actions (appended to drawer.body, sticky)
    var editA = AdminUI.el('a', {
      class: 'tl-dw-edit',
      href: '/admin/trips/' + trip.id + '/edit'
    }, ['Edit']);
    var deleteB = AdminUI.el('button', {
      type: 'button',
      class: 'tl-dw-delete',
      onclick: function () { tripsDelete(trip.id, trip.name); }
    }, ['Delete']);
    var footer = AdminUI.el('div', { class: 'tl-dwfooter' }, [editA, deleteB]);
    drawer.body.appendChild(footer);

    // On drawer close: restore inert + active state + focus
    var origClose = drawer.close;
    tripsCurrentDrawer.close = function () {
      origClose();
      if (rowsEl) rowsEl.inert = false;
      if (toolbarEl) toolbarEl.inert = false;
      if (headEl) headEl.inert = false;
      document.querySelectorAll('#trips-rows .tl-card.is-active').forEach(function (c) {
        c.classList.remove('is-active');
      });
      if (tripsLastFocused) {
        tripsLastFocused.focus();
        tripsLastFocused = null;
      }
      tripsCurrentDrawer = null;
    };

    // Patch the original close references inside drawer to also clean up
    // (Esc and scrim click use origClose; we need them to also run our cleanup)
    // We do this by overriding the drawer API close with our wrapped version.
    // The drawer internally calls origClose; by reassigning current.close the
    // drawer module itself won't call our wrapper, but Esc/scrim are wired to
    // origClose. So we listen for the panel removal via MutationObserver.
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
              document.querySelectorAll('#trips-rows .tl-card.is-active').forEach(function (c) {
                c.classList.remove('is-active');
              });
              if (tripsLastFocused) {
                tripsLastFocused.focus();
                tripsLastFocused = null;
              }
              tripsCurrentDrawer = null;
            }
          });
        });
      });
      obs.observe(document.body, { childList: true });
    }
  }

  /* ---- delete handler ---- */
  function tripsDelete(id, name) {
    if (!confirm('Delete trip "' + (name || '') + '"?\n\nThis cannot be undone.')) return;
    AdminUI.mutate('/admin/trips/' + id + '/delete').then(function () {
      if (window.showToast) showToast('Trip deleted', 'success');
      // Close drawer if it was showing this trip
      if (tripsCurrentDrawer && tripsCurrentDrawer.id === id) {
        tripsCurrentDrawer.close();
      }
      // Remove from data
      tripsData = tripsData.filter(function (t) { return t.id !== id; });
      tripsRender();
    }).catch(function () {
      // AdminUI.mutate already toasts the error
    });
  }

  /* ---- attach toolbar listeners ---- */
  function tripsAttachListeners() {
    var searchEl = document.getElementById('trips-search');
    if (searchEl) {
      searchEl.addEventListener('input', function (e) {
        tripsSearchQ = e.target.value.toLowerCase().trim();
        tripsRender();
      });
    }

    document.querySelectorAll('#trips-list .tl-pill').forEach(function (pill) {
      pill.addEventListener('click', function () {
        document.querySelectorAll('#trips-list .tl-pill').forEach(function (p) {
          p.setAttribute('aria-pressed', 'false');
        });
        pill.setAttribute('aria-pressed', 'true');
        tripsFilterStatus = pill.dataset.status || 'all';
        tripsRender();
      });
    });
  }

  /* ---- init ---- */
  AdminUI.onReady(function () {
    tripsAttachListeners();
    AdminUI.fetchJSON('/admin/trips/data').then(function (data) {
      tripsData = data.trips || [];
      tripsRender();
    }).catch(function () {
      if (window.showToast) showToast('Failed to load trips. Reload the page to retry.', 'error');
      var root = document.getElementById('trips-rows');
      if (root) {
        while (root.firstChild) root.removeChild(root.firstChild);
        root.appendChild(AdminUI.el('p', { class: 'tl-empty' }, ['Something went wrong. Try reloading.']));
      }
      tripsUpdateCount(0);
    });
  });
})();
