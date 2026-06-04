// admin_seasons.js
// Bespoke vertical lifecycle timeline for /admin/seasons.
// Requires AdminUI foundation (_core, status_badge, focus_trap, drawer, data).
// All stl* prefixed helpers; only AdminUI and showToast touched on window.

(function () {
  'use strict';

  // -----------------------------------------------------------------------
  // State
  // -----------------------------------------------------------------------
  var _seasons = [];
  var _activeCardEl = null;   // card element currently highlighted (drawer open)
  var _activeDrawer = null;   // { close } returned by AdminUI.drawer

  // -----------------------------------------------------------------------
  // Formatting helpers
  // -----------------------------------------------------------------------

  function stlFormatPrice(cents) {
    if (!cents) return '-';
    return '$' + (cents / 100).toFixed(2);
  }

  function stlCapitalize(s) {
    return s ? s.charAt(0).toUpperCase() + s.slice(1) : '';
  }

  // Parse a 'YYYY-MM-DD HH:MM' Central wall-clock string safely (Safari-safe).
  function stlParseWallClock(s) {
    if (!s) return null;
    var p = s.split(/[\- :]/);
    return new Date(+p[0], +p[1] - 1, +p[2], +(p[3] || 0), +(p[4] || 0));
  }

  // Parse 'YYYY-MM-DD' as a local date (avoids UTC midnight off-by-one).
  function stlParseDate(s) {
    if (!s) return null;
    var p = s.split('-');
    return new Date(+p[0], +p[1] - 1, +p[2]);
  }

  // stlComputeWindowState(startStr, endStr) -> 'upcoming'|'open'|'closed'|'none'
  // Input: Central wall-clock strings 'YYYY-MM-DD HH:MM' or null.
  function stlComputeWindowState(startStr, endStr) {
    if (!startStr && !endStr) return 'none';
    var now = new Date();
    var start = stlParseWallClock(startStr);
    var end = stlParseWallClock(endStr);
    if (start && now < start) return 'upcoming';
    if (end && now > end) return 'closed';
    return 'open';
  }

  // stlComputeSeasonStatus(season) -> { label, variant }
  function stlComputeSeasonStatus(season) {
    if (season.is_current) return { label: 'Current', variant: 'success' };
    var today = new Date();
    var start = stlParseDate(season.start_date);
    var end = stlParseDate(season.end_date);
    if (start && today < start) return { label: 'Upcoming', variant: 'info' };
    if (end && today > end) return { label: 'Past', variant: 'neutral' };
    // Check if any reg window is open
    var retState = stlComputeWindowState(season.returning_start, season.returning_end);
    var newState = stlComputeWindowState(season.new_start, season.new_end);
    if (retState === 'open' || newState === 'open') return { label: 'Reg Open', variant: 'success' };
    return { label: 'Active', variant: 'warning' };
  }

  // Format a date range for display. short=true -> 'Dec 2024 - Mar 2025'; false -> 'December 1, 2024 - March 15, 2025'
  function stlFormatDateRange(startStr, endStr, short) {
    if (!startStr && !endStr) return '—';
    var MONTHS_SHORT = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
    var MONTHS_LONG  = ['January','February','March','April','May','June','July','August','September','October','November','December'];
    function fmtDate(s, isShort) {
      if (!s) return '?';
      var p = s.split('-');
      var m = +p[1] - 1;
      var d = +p[2];
      var y = +p[0];
      if (isShort) return MONTHS_SHORT[m] + ' ' + y;
      return MONTHS_LONG[m] + ' ' + d + ', ' + y;
    }
    var s = startStr ? fmtDate(startStr, short) : '?';
    var e = endStr ? fmtDate(endStr, short) : '?';
    if (!startStr) return e;
    if (!endStr) return s;
    return s + ' - ' + e;
  }

  // Format a window datetime range for display (always verbose).
  function stlFormatWindowRange(startStr, endStr) {
    if (!startStr && !endStr) return '—';
    function fmtWall(s) {
      if (!s) return '?';
      var p = s.split(/[\- :]/);
      var MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
      var m = MONTHS[+p[1] - 1];
      var d = +p[2];
      var h = +p[3];
      var min = +p[4];
      var ampm = h >= 12 ? 'PM' : 'AM';
      var h12 = h % 12 || 12;
      var minStr = min === 0 ? ':00' : (':' + (min < 10 ? '0' : '') + min);
      return m + ' ' + d + ' at ' + h12 + minStr + ' ' + ampm;
    }
    var s = startStr ? fmtWall(startStr) : '?';
    var e = endStr ? fmtWall(endStr) : '?';
    if (!startStr) return e;
    if (!endStr) return s;
    return s + ' - ' + e;
  }

  // Badge for window state
  function stlWindowBadge(state) {
    var map = {
      open:     { label: 'Open',     variant: 'success' },
      upcoming: { label: 'Upcoming', variant: 'info'    },
      closed:   { label: 'Closed',   variant: 'neutral' }
    };
    var entry = map[state];
    if (!entry) return null;
    return AdminUI.statusBadge(entry.label, entry.variant);
  }

  // -----------------------------------------------------------------------
  // DOM helpers
  // -----------------------------------------------------------------------

  var el = AdminUI.el;

  function stlSetCount(n) {
    var el_ = document.getElementById('stl-count');
    if (el_) el_.textContent = n + ' season' + (n === 1 ? '' : 's');
  }

  function stlRemoveActiveCard() {
    if (_activeCardEl) {
      _activeCardEl.classList.remove('is-active');
      _activeCardEl = null;
    }
  }

  function stlMarkActiveCard(cardEl) {
    stlRemoveActiveCard();
    _activeCardEl = cardEl;
    cardEl.classList.add('is-active');
  }

  // -----------------------------------------------------------------------
  // Confirm dialog (bespoke, replaces window.confirm)
  // stlConfirm({ title, body, confirmLabel, danger }) -> Promise<bool>
  // -----------------------------------------------------------------------

  function stlConfirm(opts) {
    opts = opts || {};
    return new Promise(function (resolve) {
      var previousEl = document.activeElement;

      var scrim = el('div', { class: 'stl-modal-scrim' }, []);
      var dlg = el('div', {
        class: 'stl-modal-dlg',
        role: 'dialog',
        'aria-modal': 'true',
        'aria-labelledby': 'stl-confirm-title'
      }, [
        el('h3', { id: 'stl-confirm-title' }, [opts.title || 'Confirm']),
        el('p', {}, [opts.body || 'Are you sure?']),
        el('div', { class: 'stl-modal-actions' }, [
          el('button', {
            type: 'button',
            class: 'stl-btn stl-btn-ghost',
            onclick: function () { cleanup(); resolve(false); }
          }, ['Cancel']),
          el('button', {
            type: 'button',
            class: opts.danger ? 'stl-btn-confirm-danger' : 'stl-btn stl-btn-primary',
            id: 'stl-confirm-ok',
            onclick: function () { cleanup(); resolve(true); }
          }, [opts.confirmLabel || 'Confirm'])
        ])
      ]);

      function cleanup() {
        document.removeEventListener('keydown', onEsc);
        document.body.removeChild(scrim);
        document.body.removeChild(dlg);
        _confirmRelease();
        if (previousEl && typeof previousEl.focus === 'function') previousEl.focus();
      }

      function onEsc(e) {
        if (e.key === 'Escape') { cleanup(); resolve(false); }
      }

      document.body.appendChild(scrim);
      document.body.appendChild(dlg);
      document.addEventListener('keydown', onEsc);
      scrim.addEventListener('click', function () { cleanup(); resolve(false); });

      var _confirmRelease = AdminUI.trapFocus(dlg);
      // Initial focus on Cancel (safer default for destructive)
      var cancelBtn = dlg.querySelector('button');
      if (cancelBtn) cancelBtn.focus();
    });
  }

  // -----------------------------------------------------------------------
  // Late-link modal
  // -----------------------------------------------------------------------

  function stlLateLinkModal(season) {
    var scrim = el('div', { class: 'stl-modal-scrim' }, []);
    var dlg = el('div', {
      class: 'stl-modal-dlg',
      role: 'dialog',
      'aria-modal': 'true',
      'aria-labelledby': 'stl-ll-title'
    }, []);

    var _releaseLL = null;

    function open() {
      document.body.appendChild(scrim);
      document.body.appendChild(dlg);
      document.addEventListener('keydown', onEsc);
      scrim.addEventListener('click', closeLate);
      _releaseLL = AdminUI.trapFocus(dlg);
    }

    function closeLate() {
      document.removeEventListener('keydown', onEsc);
      if (document.body.contains(scrim)) document.body.removeChild(scrim);
      if (document.body.contains(dlg)) document.body.removeChild(dlg);
      if (_releaseLL) { _releaseLL(); _releaseLL = null; }
    }

    function onEsc(e) {
      if (e.key === 'Escape') closeLate();
    }

    function renderStep1() {
      dlg.innerHTML = '';
      var errSpan = el('span', { class: 'stl-input-err', id: 'stl-ll-err' }, ['Enter a valid email address']);
      var emailInput = el('input', {
        type: 'email',
        class: 'stl-input',
        placeholder: 'recipient@example.com',
        'aria-label': 'Recipient email address',
        id: 'stl-ll-email'
      }, []);
      var generateBtn = el('button', {
        type: 'button',
        class: 'stl-btn stl-btn-primary',
        id: 'stl-ll-gen',
        disabled: 'disabled'
      }, ['Generate']);

      // Enable Generate when '@' present
      emailInput.addEventListener('input', function () {
        if (emailInput.value.indexOf('@') !== -1) {
          generateBtn.removeAttribute('disabled');
        } else {
          generateBtn.setAttribute('disabled', 'disabled');
        }
        errSpan.classList.remove('shown');
      });

      generateBtn.addEventListener('click', function () {
        if (emailInput.value.indexOf('@') === -1) {
          errSpan.classList.add('shown');
          return;
        }
        generateBtn.setAttribute('disabled', 'disabled');
        generateBtn.textContent = 'Generating...';
        errSpan.classList.remove('shown');

        fetch('/admin/seasons/' + season.id + '/late-link', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
          body: JSON.stringify({ email: emailInput.value.trim() })
        })
        .then(function (res) { return res.json(); })
        .then(function (data) {
          if (!data.success) {
            if (window.showToast) showToast(data.error || 'Failed to generate link', 'error');
            generateBtn.removeAttribute('disabled');
            generateBtn.textContent = 'Generate';
            return;
          }
          if (_releaseLL) { _releaseLL(); _releaseLL = null; }
          renderStep2(data.url, data.email);
          _releaseLL = AdminUI.trapFocus(dlg);
        })
        .catch(function (err) {
          if (window.showToast) showToast('Error: ' + err.message, 'error');
          generateBtn.removeAttribute('disabled');
          generateBtn.textContent = 'Generate';
        });
      });

      var cancelBtn = el('button', {
        type: 'button',
        class: 'stl-btn stl-btn-ghost',
        onclick: closeLate
      }, ['Cancel']);

      dlg.appendChild(el('h3', { id: 'stl-ll-title' }, ['Generate Late Registration Link']));
      dlg.appendChild(el('div', { style: 'margin-top:14px' }, [
        el('label', { class: 'stl-field-lbl', for: 'stl-ll-email' }, ['Recipient email address']),
        emailInput,
        errSpan,
        el('p', { class: 'stl-field-note', style: 'margin-top:6px' }, ['Link expires 7 days after generation'])
      ]));
      dlg.appendChild(el('div', { class: 'stl-modal-actions' }, [cancelBtn, generateBtn]));

      // Focus the email input
      setTimeout(function () { emailInput.focus(); }, 50);
    }

    function renderStep2(url, recipientEmail) {
      dlg.innerHTML = '';

      var urlInput = el('input', {
        type: 'text',
        class: 'stl-input',
        readonly: 'readonly',
        value: url,
        'aria-label': 'Late registration link URL'
      }, []);

      var copyBtn = el('button', {
        type: 'button',
        class: 'stl-btn stl-btn-ghost',
        'aria-label': 'Copy link to clipboard'
      }, ['Copy']);

      copyBtn.addEventListener('click', function () {
        var announcer = document.getElementById('stl-copy-announce');
        function onCopied() {
          copyBtn.textContent = 'Copied!';
          copyBtn.setAttribute('disabled', 'disabled');
          if (announcer) announcer.textContent = 'Link copied';
          setTimeout(function () {
            copyBtn.textContent = 'Copy';
            copyBtn.removeAttribute('disabled');
            if (announcer) announcer.textContent = '';
          }, 2000);
        }
        if (navigator.clipboard && navigator.clipboard.writeText) {
          navigator.clipboard.writeText(url).then(onCopied).catch(function () {
            urlInput.select();
            document.execCommand('copy');
            onCopied();
          });
        } else {
          urlInput.select();
          document.execCommand('copy');
          onCopied();
        }
      });

      var doneBtn = el('button', {
        type: 'button',
        class: 'stl-btn stl-btn-primary',
        onclick: closeLate
      }, ['Done']);

      dlg.appendChild(el('h3', { id: 'stl-ll-title' }, ['Late Registration Link']));
      dlg.appendChild(el('div', { style: 'margin-top:14px' }, [
        el('label', { class: 'stl-field-lbl' }, ['Late registration link']),
        el('div', { class: 'stl-copy-row' }, [urlInput, copyBtn]),
        el('p', { class: 'stl-field-note', style: 'margin-top:6px' }, [
          'Sent to ' + AdminUI.escapeHtml(recipientEmail) + '. Link expires in 7 days - share via Slack or email.'
        ])
      ]));
      dlg.appendChild(el('div', { class: 'stl-modal-actions' }, [doneBtn]));

      // Focus the URL input
      setTimeout(function () { urlInput.focus(); }, 50);
    }

    renderStep1();
    open();
  }

  // -----------------------------------------------------------------------
  // Activate action
  // -----------------------------------------------------------------------

  function stlActivate(season) {
    var previousFocus = document.activeElement;
    stlConfirm({
      title: 'Activate season?',
      body: 'This will set this season as current, update all user statuses based on their registration records, and recalculate seasons_since_active counters. This action cannot be undone.',
      confirmLabel: 'Activate',
      danger: false
    }).then(function (confirmed) {
      if (!confirmed) return;

      // Disable the button that triggered this while loading
      if (previousFocus && previousFocus.tagName === 'BUTTON') {
        previousFocus.setAttribute('disabled', 'disabled');
        previousFocus.textContent = 'Activating...';
      }

      fetch('/admin/seasons/' + season.id + '/activate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
        body: JSON.stringify({})
      })
      .then(function (res) { return res.json(); })
      .then(function (data) {
        if (!data.success) {
          if (window.showToast) showToast(data.error || 'Failed to activate season', 'error');
          if (previousFocus && previousFocus.tagName === 'BUTTON') {
            previousFocus.removeAttribute('disabled');
            previousFocus.textContent = 'Activate';
          }
          return;
        }
        var msg = data.message;
        if (!msg && data.stats) {
          msg = 'Season activated. ' + data.stats.active + ' active, ' + data.stats.alumni + ' alumni, ' + data.stats.pending + ' pending.';
        }
        if (!msg) msg = 'Season activated';
        if (window.showToast) showToast(msg, 'success');

        // Close drawer if open
        if (_activeDrawer) { _activeDrawer.close(); _activeDrawer = null; }
        stlRemoveActiveCard();

        // Re-fetch and re-render in place
        AdminUI.fetchJSON('/admin/seasons/data')
          .then(function (d) { stlRender(d.seasons); })
          .catch(function () { location.reload(); });
      })
      .catch(function (err) {
        if (window.showToast) showToast('Error: ' + err.message, 'error');
        if (previousFocus && previousFocus.tagName === 'BUTTON') {
          previousFocus.removeAttribute('disabled');
          previousFocus.textContent = 'Activate';
        }
      });
    });
  }

  // -----------------------------------------------------------------------
  // Delete action
  // -----------------------------------------------------------------------

  function stlDelete(season, cardEl) {
    stlConfirm({
      title: 'Delete season?',
      body: 'This cannot be undone.',
      confirmLabel: 'Delete',
      danger: true
    }).then(function (confirmed) {
      if (!confirmed) return;

      AdminUI.mutate('/admin/seasons/' + season.id + '/delete-json', {})
        .then(function () {
          // Close drawer if open
          if (_activeDrawer) { _activeDrawer.close(); _activeDrawer = null; }
          stlRemoveActiveCard();

          // Remove card from DOM
          if (season.is_current) {
            var hero = document.getElementById('stl-hero');
            if (hero) hero.innerHTML = '';
          } else {
            // Find node by data-season-id
            var node = document.querySelector('#stl-list .stl-node[data-season-id="' + season.id + '"]');
            if (node) node.parentNode.removeChild(node);
          }

          // Decrement count
          var newCount = Math.max(0, _seasons.length - 1);
          _seasons = _seasons.filter(function (s) { return s.id !== season.id; });
          stlSetCount(_seasons.length);

          if (window.showToast) showToast('Season deleted', 'success');
        })
        .catch(function () {
          // mutate already toasted the error
        });
    });
  }

  // -----------------------------------------------------------------------
  // Preview drawer
  // -----------------------------------------------------------------------

  function stlBuildDrawerContent(season) {
    var retState = stlComputeWindowState(season.returning_start, season.returning_end);
    var newState = stlComputeWindowState(season.new_start, season.new_end);

    var metaChildren = [];
    if (season.is_current) metaChildren.push(AdminUI.statusBadge('Current', 'success'));
    metaChildren.push(el('span', { class: 'stl-pill' }, [stlCapitalize(season.season_type || '')]));
    if (season.year) metaChildren.push(el('span', { class: 'stl-year' }, [String(season.year)]));
    var meta = el('div', { class: 'stl-dw-meta' }, metaChildren);

    // Block 1: Identity
    var block1 = el('div', { class: 'stl-blk' }, [
      el('div', { class: 'stl-blk-h' }, ['Identity']),
      el('div', { class: 'stl-kv' }, [
        el('span', { class: 'k' }, ['Name']),
        el('span', { class: 'v' }, [season.name || '-'])
      ]),
      el('div', { class: 'stl-kv' }, [
        el('span', { class: 'k' }, ['Type']),
        el('span', { class: 'v' }, [stlCapitalize(season.season_type || '-')])
      ]),
      el('div', { class: 'stl-kv' }, [
        el('span', { class: 'k' }, ['Year']),
        el('span', { class: 'v' }, [season.year ? String(season.year) : '-'])
      ])
    ]);

    // Block 2: Season Dates
    var block2 = el('div', { class: 'stl-blk' }, [
      el('div', { class: 'stl-blk-h' }, ['Season Dates']),
      el('div', { class: 'stl-kv' }, [
        el('span', { class: 'k' }, ['Start']),
        el('span', { class: 'v' }, [season.start_date || '-'])
      ]),
      el('div', { class: 'stl-kv' }, [
        el('span', { class: 'k' }, ['End']),
        el('span', { class: 'v' }, [season.end_date || '-'])
      ])
    ]);

    // Block 3: Returning Members Window
    var retChildren = [el('div', { class: 'stl-blk-h' }, ['Returning Members Window'])];
    if (!season.returning_start && !season.returning_end) {
      retChildren.push(el('div', { class: 'stl-kv' }, [
        el('span', { class: 'k' }, ['Window']),
        el('span', { class: 'v' }, ['Not set'])
      ]));
    } else {
      var retKv = [
        el('span', { class: 'k' }, ['Window']),
        el('span', { class: 'v' }, [stlFormatWindowRange(season.returning_start, season.returning_end)])
      ];
      var retBadge = stlWindowBadge(retState);
      if (retBadge) retKv.push(retBadge);
      retChildren.push(el('div', { class: 'stl-kv' }, retKv));
    }
    var block3 = el('div', { class: 'stl-blk' }, retChildren);

    // Block 4: New Members Window
    var newChildren = [el('div', { class: 'stl-blk-h' }, ['New Members Window'])];
    if (!season.new_start && !season.new_end) {
      newChildren.push(el('div', { class: 'stl-kv' }, [
        el('span', { class: 'k' }, ['Window']),
        el('span', { class: 'v' }, ['Not set'])
      ]));
    } else {
      var newKv = [
        el('span', { class: 'k' }, ['Window']),
        el('span', { class: 'v' }, [stlFormatWindowRange(season.new_start, season.new_end)])
      ];
      var newBadge = stlWindowBadge(newState);
      if (newBadge) newKv.push(newBadge);
      newChildren.push(el('div', { class: 'stl-kv' }, newKv));
    }
    var block4 = el('div', { class: 'stl-blk' }, newChildren);

    // Block 5: Registration
    // TODO: member_count slot - pending /admin/seasons/data serializer addition (UserSeason count join)
    var block5 = el('div', { class: 'stl-blk' }, [
      el('div', { class: 'stl-blk-h' }, ['Registration']),
      el('div', { class: 'stl-kv' }, [
        el('span', { class: 'k' }, ['Price']),
        el('span', { class: 'v' }, [stlFormatPrice(season.price_cents)])
      ]),
      el('div', { class: 'stl-kv' }, [
        el('span', { class: 'k' }, ['Limit']),
        el('span', { class: 'v' }, [season.registration_limit ? String(season.registration_limit) : 'No limit'])
      ])
    ]);

    var blocks = [meta, block1, block2, block3, block4, block5];

    // Block 6: Description (only if non-empty)
    if (season.description && season.description.trim()) {
      blocks.push(el('div', { class: 'stl-blk' }, [
        el('div', { class: 'stl-blk-h' }, ['Description']),
        el('div', { class: 'stl-desc-box' }, [season.description])
      ]));
    }

    return el('div', {}, blocks);
  }

  function stlOpenPreview(season, cardEl) {
    stlMarkActiveCard(cardEl);

    var content = stlBuildDrawerContent(season);
    var drawer = AdminUI.drawer({ title: season.name, content: content });
    _activeDrawer = drawer;

    // Build footer actions and append to panel (outside scrollable body)
    var activateBtn = el('button', {
      type: 'button',
      class: 'stl-act stl-act-success',
      style: season.is_current ? 'display:none' : '',
      onclick: function () { stlActivate(season); }
    }, ['Activate']);

    var deleteBtn = el('button', {
      type: 'button',
      class: 'stl-act stl-act-danger',
      onclick: function () { stlDelete(season, cardEl); }
    }, ['Delete']);

    var footer = el('div', { class: 'stl-dw-footer' }, [
      el('a', {
        href: '/admin/seasons/' + season.id + '/edit',
        class: 'stl-act stl-act-primary'
      }, ['Edit']),
      el('a', {
        href: '/admin/seasons/' + season.id + '/export',
        class: 'stl-act stl-act-ghost',
        download: 'download'
      }, ['Export CSV']),
      el('button', {
        type: 'button',
        class: 'stl-act stl-act-ghost',
        onclick: function () { stlLateLinkModal(season); }
      }, ['Late Link']),
      activateBtn,
      deleteBtn
    ]);

    // Append footer to panel (sibling of body, not inside body)
    var panel = drawer.body.parentElement;
    if (panel) panel.appendChild(footer);

    // Programmatic close override: for stlActivate / stlDelete paths.
    var origClose = drawer.close;
    drawer.close = function () {
      origClose();
      stlRemoveActiveCard();
      _activeDrawer = null;
    };
    _activeDrawer = drawer;

    // The frozen drawer wires its x-button, Esc, and scrim directly to its
    // internal close function (not drawer.close), so the override above does
    // not fire on user-initiated close. Use a MutationObserver on document.body
    // to detect panel removal and clean up the active-card highlight on ALL
    // close paths without touching any frozen foundation file.
    if (panel && typeof MutationObserver !== 'undefined') {
      var _panelObserver = new MutationObserver(function (mutations) {
        for (var i = 0; i < mutations.length; i++) {
          var removed = mutations[i].removedNodes;
          for (var j = 0; j < removed.length; j++) {
            if (removed[j] === panel) {
              _panelObserver.disconnect();
              stlRemoveActiveCard();
              _activeDrawer = null;
              return;
            }
          }
        }
      });
      _panelObserver.observe(document.body, { childList: true });
    }
  }

  // -----------------------------------------------------------------------
  // Card builders
  // -----------------------------------------------------------------------

  // Build window row (compact, for cards)
  function stlCardWinRow(label, startStr, endStr) {
    var state = stlComputeWindowState(startStr, endStr);
    if (state === 'none') return null;
    var children = [
      el('span', { class: 'stl-card-win-lbl' }, [label]),
      el('span', { class: 'stl-card-win-dates' }, [stlFormatWindowRange(startStr, endStr)])
    ];
    var badge = stlWindowBadge(state);
    if (badge) children.push(badge);
    return el('div', { class: 'stl-card-win-row' }, children);
  }

  // Build the hero card (current season)
  function stlBuildHeroCard(season) {
    var retRow = stlCardWinRow('Returning', season.returning_start, season.returning_end);
    var newRow = stlCardWinRow('New Members', season.new_start, season.new_end);

    var idRowChildren = [
      el('span', { class: 'stl-season-name' }, [season.name]),
      el('span', { class: 'stl-pill' }, [stlCapitalize(season.season_type || '')]),
      el('span', { class: 'stl-year' }, [season.year ? String(season.year) : ''])
    ];
    idRowChildren.push(AdminUI.statusBadge('Current', 'success'));
    var idRow = el('div', { class: 'stl-id-row' }, idRowChildren);

    var dateRange = el('div', { class: 'stl-date-range' }, [
      stlFormatDateRange(season.start_date, season.end_date, false)
    ]);

    var winChildren = [];
    if (retRow) winChildren.push(retRow);
    if (newRow) winChildren.push(newRow);

    var leftCol = el('div', { class: 'stl-hero-left' }, [idRow, dateRange].concat(winChildren));

    var priceVal = el('div', { class: 'stl-stat-val' }, [stlFormatPrice(season.price_cents)]);
    var limitVal = el('div', { class: 'stl-stat-val' }, [
      season.registration_limit ? String(season.registration_limit) : '-'
    ]);
    var rightCol = el('div', { class: 'stl-hero-right' }, [
      el('div', { class: 'stl-stat-lbl' }, ['Price']),
      priceVal,
      el('div', { class: 'stl-stat-lbl' }, ['Registration Limit']),
      limitVal
      // member_count: pending /data serializer field
    ]);

    var innerRow = el('div', { class: 'stl-hero-inner' }, [leftCol, rightCol]);

    var actions = el('div', { class: 'stl-hero-actions' }, [
      el('a', {
        href: '/admin/seasons/' + season.id + '/edit',
        class: 'stl-btn stl-btn-primary'
      }, ['Edit']),
      el('a', {
        href: '/admin/seasons/' + season.id + '/export',
        class: 'stl-btn stl-btn-ghost',
        download: 'download'
      }, ['Export CSV']),
      el('button', {
        type: 'button',
        class: 'stl-btn stl-btn-ghost',
        onclick: function (e) {
          e.stopPropagation();
          stlOpenPreview(season, card);
        }
      }, ['View Details'])
    ]);

    var card = el('div', {
      class: 'stl-hero-card',
      'data-season-id': String(season.id),
      onclick: function (e) {
        // Only trigger if click not on a link/button
        if (e.target.tagName === 'A' || e.target.tagName === 'BUTTON') return;
        stlOpenPreview(season, card);
      }
    }, [innerRow, actions]);

    return card;
  }

  // Build a timeline node card (non-current seasons)
  function stlBuildNodeCard(season) {
    var status = stlComputeSeasonStatus(season);
    var retRow = stlCardWinRow('Returning', season.returning_start, season.returning_end);
    var newRow = stlCardWinRow('New Members', season.new_start, season.new_end);

    var topChildren = [
      el('span', { class: 'stl-card-name' }, [season.name]),
      el('span', { class: 'stl-pill' }, [stlCapitalize(season.season_type || '')]),
      el('span', { class: 'stl-card-year' }, [season.year ? String(season.year) : '']),
      el('span', { class: 'stl-card-range' }, [stlFormatDateRange(season.start_date, season.end_date, true)]),
      AdminUI.statusBadge(status.label, status.variant)
    ];

    var winChildren = [];
    if (retRow) winChildren.push(retRow);
    if (newRow) winChildren.push(newRow);

    var activateBtn = el('button', {
      type: 'button',
      class: 'stl-btn stl-btn-sm',
      style: 'color:#166534;border:1.5px solid #bbf7d0;background:#fff',
      onclick: function (e) {
        e.stopPropagation();
        stlActivate(season);
      }
    }, ['Activate']);

    var editLink = el('a', {
      href: '/admin/seasons/' + season.id + '/edit',
      class: 'stl-btn stl-btn-sm stl-btn-ghost',
      onclick: function (e) { e.stopPropagation(); }
    }, ['Edit']);

    var cardBody = el('div', {
      class: 'stl-card-body',
      role: 'button',
      tabindex: '0',
      'aria-label': AdminUI.escapeHtml(season.name) + ' - view season details',
      onclick: function () { stlOpenPreview(season, cardBody); },
      onkeydown: function (e) {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          stlOpenPreview(season, cardBody);
        }
      }
    }, [
      el('div', { class: 'stl-card-top' }, topChildren),
      el('div', { class: 'stl-card-wins' }, winChildren)
    ]);

    var actionsRow = el('div', { class: 'stl-card-actions' }, [editLink, activateBtn]);

    var dot = el('div', { class: 'stl-dot', 'aria-hidden': 'true' }, []);

    var node = el('div', {
      class: 'stl-node',
      'data-season-id': String(season.id)
    }, [dot, cardBody, actionsRow]);

    return node;
  }

  // -----------------------------------------------------------------------
  // Render
  // -----------------------------------------------------------------------

  function stlRender(seasons) {
    _seasons = seasons;
    stlSetCount(seasons.length);

    var heroSlot = document.getElementById('stl-hero');
    var listSlot = document.getElementById('stl-list');
    if (!heroSlot || !listSlot) return;

    heroSlot.innerHTML = '';
    listSlot.innerHTML = '';

    if (seasons.length === 0) {
      listSlot.appendChild(el('div', { class: 'stl-empty' }, [
        el('p', {}, ['No seasons yet.']),
        el('a', {
          href: '/admin/seasons/new',
          class: 'stl-btn stl-btn-primary',
          style: 'margin-top:12px;display:inline-flex'
        }, ['+ Create New Season'])
      ]));
      return;
    }

    // Split current vs non-current
    var current = null;
    var rest = [];
    seasons.forEach(function (s) {
      if (s.is_current) current = s;
      else rest.push(s);
    });

    if (current) {
      heroSlot.appendChild(stlBuildHeroCard(current));
    }

    rest.forEach(function (s) {
      listSlot.appendChild(stlBuildNodeCard(s));
    });
  }

  // -----------------------------------------------------------------------
  // Init
  // -----------------------------------------------------------------------

  function stlInit() {
    var listSlot = document.getElementById('stl-list');
    if (listSlot) listSlot.innerHTML = '<p class="stl-empty stl-loading">Loading seasons...</p>';

    AdminUI.fetchJSON('/admin/seasons/data')
      .then(function (data) {
        stlRender(data.seasons || []);
      })
      .catch(function (err) {
        console.error('stlInit: failed to load seasons', err);
        var listSlot = document.getElementById('stl-list');
        if (!listSlot) return;
        listSlot.innerHTML = '';
        listSlot.appendChild(el('div', { class: 'stl-error' }, [
          'Failed to load seasons. Reload to try again. ',
          el('button', {
            type: 'button',
            class: 'stl-btn stl-btn-ghost',
            style: 'margin-left:8px',
            onclick: stlInit
          }, ['Reload'])
        ]));
      });
  }

  AdminUI.onReady(stlInit);

})();
