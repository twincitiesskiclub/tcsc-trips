// admin_slack.js -- Slack User Sync surface.
// All module-level identifiers are prefixed ssync to prevent global leakage.
// Uses AdminUI.* foundation primitives (loaded before this file).

(function () {
  'use strict';

  // ─── Module state ────────────────────────────────────────────────────────────
  var ssyncState = {
    segment: 'attention',
    search: '',
    users: [],          // {id, email, first_name, last_name, full_name, status, slack_matched, slack_uid, slack_display_name}
    unmatchedSlack: [], // {id, slack_uid, email, display_name, full_name}
    unmatchedDb: [],    // {id, email, first_name, last_name, full_name, status}
    status: null,       // {total_slack_users, total_db_users, matched_users, unmatched_slack_users, unmatched_db_users}
    channelStatus: null // {config, credentials, scheduler}
  };

  // Track currently open popover element for singleton management
  var ssyncOpenPopover = null;
  // Track the currently open inline picker wrap for singleton management
  var ssyncOpenPicker = null;
  // Track the row whose drawer is currently open (for is-active rail)
  var ssyncActiveRow = null;

  // ─── Initials chip palette ───────────────────────────────────────────────────
  var CHIP_PALETTE = [
    { from: '#1c2c44', to: '#2d4a6a' },
    { from: '#1e40af', to: '#3b82f6' },
    { from: '#5b21b6', to: '#8b5cf6' },
    { from: '#0f766e', to: '#14b8a6' },
    { from: '#92400e', to: '#f59e0b' },
    { from: '#9d174d', to: '#ec4899' }
  ];

  function ssyncChipColor(name) {
    if (!name) return CHIP_PALETTE[0];
    var hash = 0;
    for (var i = 0; i < name.length; i++) { hash += name.charCodeAt(i); }
    return CHIP_PALETTE[hash % CHIP_PALETTE.length];
  }

  function ssyncInitials(name) {
    if (!name) return '?';
    var parts = name.trim().split(/\s+/);
    if (parts.length === 1) return parts[0][0].toUpperCase();
    return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
  }

  function ssyncChip(name, isSlack) {
    var chipEl;
    if (isSlack) {
      chipEl = AdminUI.el('div', {
        class: 'ss-row-chip',
        style: 'background:#4A154B',
        'aria-hidden': 'true'
      }, [name && name[0] ? name[0].toUpperCase() : 'S']);
    } else {
      var pal = ssyncChipColor(name);
      chipEl = AdminUI.el('div', {
        class: 'ss-row-chip',
        style: 'background:linear-gradient(135deg,' + pal.from + ',' + pal.to + ')',
        'aria-hidden': 'true'
      }, [ssyncInitials(name)]);
    }
    return chipEl;
  }

  // ─── Status badge variant helpers ────────────────────────────────────────────
  function ssyncStatusVariant(status) {
    return { ACTIVE: 'success', PENDING: 'warning', ALUMNI: 'neutral', DROPPED: 'danger' }[status] || 'neutral';
  }

  // ─── Suggested match engine ───────────────────────────────────────────────────
  // Returns {candidate, confidence:'confident'|'strong'|'weak'|'none', reason}
  function ssyncSuggestMatch(dbUser, slackPool) {
    if (!slackPool || slackPool.length === 0) {
      return { candidate: null, confidence: 'none', reason: 'No Slack accounts available' };
    }
    var dbEmail = (dbUser.email || '').toLowerCase().trim();
    var dbName = (dbUser.full_name || '').toLowerCase().trim();

    // 1. Exact email match (confident)
    for (var i = 0; i < slackPool.length; i++) {
      var s = slackPool[i];
      if (dbEmail && s.email && s.email.toLowerCase().trim() === dbEmail) {
        return { candidate: s, confidence: 'confident', reason: 'Email match: ' + s.email };
      }
    }

    // 2. Normalized full-name equality (strong)
    if (dbName) {
      for (var j = 0; j < slackPool.length; j++) {
        var s2 = slackPool[j];
        var slackName = (s2.full_name || s2.display_name || '').toLowerCase().trim();
        if (slackName && slackName === dbName) {
          return { candidate: s2, confidence: 'strong', reason: 'Name match: ' + (s2.full_name || s2.display_name) };
        }
      }
    }

    // 3. Token/startsWith overlap (weak)
    if (dbName) {
      var dbTokens = dbName.split(/\s+/);
      var best = null, bestScore = 0;
      for (var k = 0; k < slackPool.length; k++) {
        var s3 = slackPool[k];
        var sn = (s3.full_name || s3.display_name || '').toLowerCase();
        if (!sn) continue;
        var snTokens = sn.split(/\s+/);
        var matches = 0;
        dbTokens.forEach(function (t) {
          if (snTokens.some(function (st) { return st.startsWith(t) || t.startsWith(st); })) matches++;
        });
        var score = matches / Math.max(dbTokens.length, snTokens.length);
        if (score > bestScore) { bestScore = score; best = s3; }
      }
      if (best && bestScore >= 0.5) {
        return { candidate: best, confidence: 'weak', reason: 'Partial name overlap' };
      }
    }

    return { candidate: null, confidence: 'none', reason: 'No match found' };
  }

  // Symmetric: for a Slack user, find best DB match
  function ssyncSuggestMatchSlack(slackUser, dbPool) {
    if (!dbPool || dbPool.length === 0) {
      return { candidate: null, confidence: 'none', reason: 'No DB users available' };
    }
    var slackEmail = (slackUser.email || '').toLowerCase().trim();
    var slackName = (slackUser.full_name || slackUser.display_name || '').toLowerCase().trim();

    for (var i = 0; i < dbPool.length; i++) {
      var d = dbPool[i];
      if (slackEmail && d.email && d.email.toLowerCase().trim() === slackEmail) {
        return { candidate: d, confidence: 'confident', reason: 'Email match: ' + d.email };
      }
    }
    if (slackName) {
      for (var j = 0; j < dbPool.length; j++) {
        var d2 = dbPool[j];
        var dn = (d2.full_name || '').toLowerCase().trim();
        if (dn && dn === slackName) {
          return { candidate: d2, confidence: 'strong', reason: 'Name match: ' + d2.full_name };
        }
      }
    }
    if (slackName) {
      var sTokens = slackName.split(/\s+/);
      var best = null, bestScore = 0;
      for (var k = 0; k < dbPool.length; k++) {
        var d3 = dbPool[k];
        var dname = (d3.full_name || '').toLowerCase();
        if (!dname) continue;
        var dTokens = dname.split(/\s+/);
        var matches = 0;
        sTokens.forEach(function (t) {
          if (dTokens.some(function (dt) { return dt.startsWith(t) || t.startsWith(dt); })) matches++;
        });
        var score = matches / Math.max(sTokens.length, dTokens.length);
        if (score > bestScore) { bestScore = score; best = d3; }
      }
      if (best && bestScore >= 0.5) {
        return { candidate: best, confidence: 'weak', reason: 'Partial name overlap' };
      }
    }
    return { candidate: null, confidence: 'none', reason: 'No match found' };
  }

  // ─── Load all data ────────────────────────────────────────────────────────────
  function ssyncLoadAll() {
    return Promise.all([
      AdminUI.fetchJSON('/admin/slack/status').then(function (d) { ssyncState.status = d; }).catch(function (e) {
        console.error('status load failed', e);
        if (window.showToast) showToast('Failed to load sync status', 'error');
      }),
      AdminUI.fetchJSON('/admin/slack/users').then(function (d) { ssyncState.users = d.users || []; }).catch(function (e) {
        console.error('users load failed', e);
        if (window.showToast) showToast('Failed to load users', 'error');
      }),
      AdminUI.fetchJSON('/admin/slack/unmatched').then(function (d) {
        ssyncState.unmatchedSlack = d.unmatched_slack_users || [];
        ssyncState.unmatchedDb = d.unmatched_db_users || [];
      }).catch(function (e) {
        console.error('unmatched load failed', e);
        if (window.showToast) showToast('Failed to load unmatched users', 'error');
      }),
      AdminUI.fetchJSON('/admin/channel-sync/status').then(function (d) { ssyncState.channelStatus = d; }).catch(function (e) {
        console.error('channel-sync status load failed', e);
      })
    ]).then(function () {
      ssyncRenderStatline();
      ssyncUpdateTabCounts();
      ssyncRenderList();
    });
  }

  // ─── Statline (replaces stats ribbon + channel card) ─────────────────────────
  // Renders a quiet inline line of sync numbers and a channel-sync chip.
  // Numbers are informational only -- not clickable filters.
  function ssyncRenderStatline() {
    var el = document.getElementById('ssync-statline');
    if (!el) return;
    el.innerHTML = '';

    var s = ssyncState.status;
    var cs = ssyncState.channelStatus;

    if (!s) {
      el.appendChild(AdminUI.el('span', { class: 'ss-skel-stat' }, []));
      el.appendChild(AdminUI.el('span', { class: 'ss-skel-stat' }, []));
      return;
    }

    // Narrative numbers (text nodes, never innerHTML)
    el.appendChild(document.createTextNode(String(s.matched_users) + ' matched'));
    el.appendChild(AdminUI.el('span', { class: 'ss-statline-dot', 'aria-hidden': 'true' }, ['·']));
    el.appendChild(document.createTextNode(String(s.unmatched_db_users) + ' DB users need Slack'));
    el.appendChild(AdminUI.el('span', { class: 'ss-statline-dot', 'aria-hidden': 'true' }, ['·']));
    el.appendChild(document.createTextNode(String(s.unmatched_slack_users) + ' Slack accounts unclaimed'));
    el.appendChild(AdminUI.el('span', { class: 'ss-statline-dot', 'aria-hidden': 'true' }, ['·']));
    el.appendChild(document.createTextNode(String(s.total_slack_users) + ' Slack / ' + String(s.total_db_users) + ' DB total'));

    // Spacer pushes channel chip right
    el.appendChild(AdminUI.el('span', { class: 'ss-statline-spacer' }, []));

    // Channel-sync inline chip
    var credsOk = cs && cs.credentials && cs.credentials.valid;
    var schedulerOk = cs && cs.scheduler && cs.scheduler.running;
    var chipLabel, chipVariant;
    if (!cs) {
      chipLabel = 'Channel Sync'; chipVariant = 'neutral';
    } else if (credsOk && schedulerOk) {
      chipLabel = 'Channel Sync: Ready'; chipVariant = 'success';
    } else if (credsOk) {
      chipLabel = 'Channel Sync: Idle'; chipVariant = 'warning';
    } else {
      chipLabel = 'Channel Sync: Config needed'; chipVariant = 'danger';
    }

    var channelChip = AdminUI.el('a', {
      href: '/admin/channel-sync',
      class: 'ss-status-chip',
      'aria-label': chipLabel + ' - go to channel sync dashboard'
    }, []);
    channelChip.appendChild(AdminUI.statusBadge(chipLabel, chipVariant));
    el.appendChild(channelChip);
  }

  // ─── Segment / tab switching ──────────────────────────────────────────────────
  function ssyncSetSegment(key, _tabBtn) {
    ssyncState.segment = key;
    ssyncState.search = '';
    var searchEl = document.getElementById('ssync-search');
    if (searchEl) searchEl.value = '';

    // Update pill is-active + aria-selected
    ['attention', 'all_db', 'unclaimed_slack'].forEach(function (k) {
      var tab = document.getElementById('ssync-tab-' + k);
      if (tab) {
        tab.setAttribute('aria-selected', k === key ? 'true' : 'false');
        if (k === key) {
          tab.classList.add('is-active');
        } else {
          tab.classList.remove('is-active');
        }
      }
    });

    // Update tabpanel aria-labelledby
    var list = document.getElementById('ssync-list');
    if (list) list.setAttribute('aria-labelledby', 'ssync-tab-' + key);

    ssyncRenderList();
  }

  function ssyncUpdateTabCounts() {
    var attentionCount = ssyncState.unmatchedDb.length + ssyncState.unmatchedSlack.length;
    var allDbCount = ssyncState.users.length;
    var unclaimedCount = ssyncState.unmatchedSlack.length;

    var ac = document.getElementById('ssync-tab-attention-count');
    var dc = document.getElementById('ssync-tab-all_db-count');
    var uc = document.getElementById('ssync-tab-unclaimed_slack-count');

    if (ac) ac.textContent = '(' + attentionCount + ')';
    if (dc) dc.textContent = '(' + allDbCount + ')';
    if (uc) uc.textContent = '(' + unclaimedCount + ')';
  }

  function ssyncOnSearch(val) {
    ssyncState.search = val;
    ssyncRenderList();
  }

  function ssyncFilterBySearch(arr, q) {
    if (!q) return arr;
    var lq = q.toLowerCase();
    return arr.filter(function (u) {
      var name = (u.full_name || u.display_name || '').toLowerCase();
      var email = (u.email || '').toLowerCase();
      return name.includes(lq) || email.includes(lq);
    });
  }

  // Update the live visible-count in the toolbar
  function ssyncUpdateVisibleCount(n) {
    var el = document.getElementById('ssync-visible-count');
    if (el) el.textContent = n + ' item' + (n === 1 ? '' : 's');
    var announce = document.getElementById('ssync-count-announce');
    if (announce) announce.textContent = n + ' item' + (n === 1 ? '' : 's');
  }

  // ─── is-active rail management ────────────────────────────────────────────────
  function ssyncSetActiveRow(rowEl) {
    if (ssyncActiveRow && ssyncActiveRow !== rowEl) {
      ssyncActiveRow.classList.remove('is-active');
    }
    ssyncActiveRow = rowEl;
    if (rowEl) rowEl.classList.add('is-active');
  }

  function ssyncClearActiveRow() {
    if (ssyncActiveRow) {
      ssyncActiveRow.classList.remove('is-active');
      ssyncActiveRow = null;
    }
  }

  // ─── Render list ──────────────────────────────────────────────────────────────
  function ssyncRenderList() {
    var listEl = document.getElementById('ssync-list');
    if (!listEl) return;
    listEl.innerHTML = '';
    var q = ssyncState.search;

    if (ssyncState.segment === 'attention') {
      ssyncRenderAttentionList(listEl, q);
    } else if (ssyncState.segment === 'all_db') {
      ssyncRenderAllDbList(listEl, q);
    } else {
      ssyncRenderUnclaimedSlackList(listEl, q);
    }
  }

  // ─── Attention view ───────────────────────────────────────────────────────────
  function ssyncRenderAttentionList(listEl, q) {
    var dbUsers = ssyncFilterBySearch(ssyncState.unmatchedDb, q);
    var slackUsers = ssyncFilterBySearch(ssyncState.unmatchedSlack, q);

    if (dbUsers.length === 0 && slackUsers.length === 0 && !q) {
      listEl.appendChild(AdminUI.el('div', { class: 'ss-empty' }, [
        AdminUI.el('div', { class: 'ss-empty-icon' }, ['✓']),
        AdminUI.el('div', { class: 'ss-empty-title' }, ['All users are linked']),
        AdminUI.el('div', { class: 'ss-empty-sub' }, ['DB users and Slack accounts are fully matched.'])
      ]));
      ssyncUpdateVisibleCount(0);
      return;
    }

    if (dbUsers.length === 0 && slackUsers.length === 0) {
      listEl.appendChild(AdminUI.el('div', { class: 'ss-empty' }, ['No results for "' + q + '"']));
      ssyncUpdateVisibleCount(0);
      return;
    }

    // Sort: confident > strong > weak/none, then alphabetical
    var dbWithMatch = dbUsers.map(function (u) {
      var match = ssyncSuggestMatch(u, ssyncState.unmatchedSlack);
      return { user: u, match: match };
    });

    var confident = dbWithMatch.filter(function (x) { return x.match.confidence === 'confident'; });
    var strong = dbWithMatch.filter(function (x) { return x.match.confidence === 'strong'; });
    var weakNone = dbWithMatch.filter(function (x) { return x.match.confidence !== 'confident' && x.match.confidence !== 'strong'; });

    function sortByName(a, b) {
      return (a.user.full_name || '').localeCompare(b.user.full_name || '');
    }
    confident.sort(sortByName);
    strong.sort(sortByName);
    weakNone.sort(sortByName);

    var orderedDb = confident.concat(strong).concat(weakNone);

    orderedDb.forEach(function (item) {
      listEl.appendChild(ssyncBuildRow(item.user, 'attention-db', item.match));
    });

    // Unclaimed Slack rows
    var sortedSlack = slackUsers.slice().sort(function (a, b) {
      return (a.full_name || a.display_name || '').localeCompare(b.full_name || b.display_name || '');
    });
    sortedSlack.forEach(function (u) {
      listEl.appendChild(ssyncBuildRow(u, 'slack', null));
    });

    ssyncUpdateVisibleCount(dbUsers.length + slackUsers.length);
  }

  // ─── All DB users view ────────────────────────────────────────────────────────
  function ssyncRenderAllDbList(listEl, q) {
    var users = ssyncFilterBySearch(ssyncState.users, q);

    if (users.length === 0) {
      listEl.appendChild(AdminUI.el('div', { class: 'ss-empty' }, [
        q ? 'No users match "' + q + '"' : 'No users found'
      ]));
      ssyncUpdateVisibleCount(0);
      return;
    }

    users.forEach(function (user) {
      var kind = user.slack_matched ? 'all-db-linked' : 'all-db-unlinked';
      listEl.appendChild(ssyncBuildRow(user, kind, null));
    });

    ssyncUpdateVisibleCount(users.length);
  }

  // ─── Unclaimed Slack view ─────────────────────────────────────────────────────
  function ssyncRenderUnclaimedSlackList(listEl, q) {
    var users = ssyncFilterBySearch(ssyncState.unmatchedSlack, q);

    // Bulk import button at top (when not searching)
    if (!q && ssyncState.unmatchedSlack.length > 0) {
      var bulkWrap = AdminUI.el('div', { style: 'margin-bottom:8px' }, []);
      var bulkBtn = AdminUI.el('button', {
        type: 'button',
        class: 'ss-bulk-import-btn'
      }, ['Import all unclaimed (' + ssyncState.unmatchedSlack.length + ')']);
      bulkBtn.addEventListener('click', function () {
        ssyncShowBulkConfirm(bulkWrap, bulkBtn);
      });
      bulkWrap.appendChild(bulkBtn);
      bulkWrap.appendChild(AdminUI.el('div', { class: 'ss-bulk-import-note' }, [
        'Creates each as ALUMNI with a legacy season.'
      ]));
      listEl.appendChild(bulkWrap);
    }

    if (users.length === 0) {
      listEl.appendChild(AdminUI.el('div', { class: 'ss-empty' }, [
        q ? 'No unclaimed Slack accounts match "' + q + '"' : 'No unclaimed Slack accounts'
      ]));
      ssyncUpdateVisibleCount(0);
      return;
    }

    var sorted = users.slice().sort(function (a, b) {
      return (a.full_name || a.display_name || '').localeCompare(b.full_name || b.display_name || '');
    });

    sorted.forEach(function (u) {
      listEl.appendChild(ssyncBuildRow(u, 'slack', null));
    });

    ssyncUpdateVisibleCount(sorted.length);
  }

  // ─── UNIFIED ROW BUILDER ──────────────────────────────────────────────────────
  // Single .ss-row geometry for ALL three views.
  // kind: 'attention-db' | 'all-db-linked' | 'all-db-unlinked' | 'slack'
  function ssyncBuildRow(record, kind, match) {
    var isSlack = (kind === 'slack');
    var name = isSlack
      ? (record.display_name || record.full_name || record.slack_uid || '?')
      : (record.full_name || (record.first_name + ' ' + (record.last_name || '')) || record.email || '?');

    var chip = ssyncChip(name, isSlack);

    // Primary column
    var metaEls = [];

    if (isSlack) {
      // email
      if (record.email) metaEls.push(AdminUI.el('span', {}, [record.email]));
      // uid in monospace
      if (record.slack_uid) {
        metaEls.push(AdminUI.el('span', { class: 'ss-row-uid' }, [record.slack_uid]));
      }
    } else {
      // email
      if (record.email) metaEls.push(AdminUI.el('span', {}, [record.email]));
      // status badge
      metaEls.push(AdminUI.statusBadge(record.status, ssyncStatusVariant(record.status)));
      // linked badge for all-db view
      if (kind === 'all-db-linked' || kind === 'all-db-unlinked') {
        metaEls.push(record.slack_matched
          ? AdminUI.statusBadge('Linked', 'success')
          : AdminUI.statusBadge('Not linked', 'neutral'));
      }
      // Slack display name if linked
      if (record.slack_display_name) {
        metaEls.push(AdminUI.el('span', { class: 'ss-row-uid' }, ['@' + record.slack_display_name]));
      }
    }

    var mainEl = AdminUI.el('div', { class: 'ss-row-main' }, [
      AdminUI.el('div', { class: 'ss-row-name' }, [name]),
      AdminUI.el('div', { class: 'ss-row-meta' }, metaEls)
    ]);

    // Actions column (varies by kind)
    var actionsEl = AdminUI.el('div', { class: 'ss-row-actions' }, []);
    actionsEl.addEventListener('click', function (e) { e.stopPropagation(); });

    ssyncBuildRowActions(actionsEl, record, kind, match, name);

    // aria-label
    var ariaLabel;
    if (isSlack) {
      ariaLabel = name + ', ' + (record.email || '') + ', unclaimed Slack account';
    } else {
      var linkedState = record.slack_matched ? 'linked' : 'not linked';
      ariaLabel = name + ', ' + (record.email || '') + ', ' + record.status + ', ' + linkedState;
    }

    // NOTE: row is a <button> with interactive descendants (invalid nesting, pre-existing). Follow-up: convert to <div role="button" tabindex="0"> so actions/picker are valid siblings.
    var row = AdminUI.el('button', {
      type: 'button',
      class: 'ss-row',
      'aria-label': ariaLabel
    }, [chip, mainEl, actionsEl]);

    // Drawer open on row body click (not on action controls)
    row.addEventListener('click', function (e) {
      if (e.target === row || e.target === mainEl || e.target.closest('.ss-row-main')) {
        ssyncSetActiveRow(row);
        if (isSlack) {
          ssyncOpenDrawer({ type: 'slack', user: record }, row);
        } else {
          var m = match || ssyncSuggestMatch(record, ssyncState.unmatchedSlack);
          ssyncOpenDrawer({ type: 'db', user: record, match: m }, row);
        }
      }
    });

    return row;
  }

  // Helper: open a picker inside pickerWrap, replacing the trigger element.
  // Closes any other open picker or popover first.
  // Returns the picker element so callers can focus its input.
  function ssyncActivatePickerInWrap(pickerWrap, trigger, direction, record, match, pool, onLink, onRestore) {
    // Close any other open picker first
    if (ssyncOpenPicker && ssyncOpenPicker !== pickerWrap) {
      ssyncCollapsePicker(ssyncOpenPicker);
    }
    // Close any open popover
    if (ssyncOpenPopover) {
      var oldPop = ssyncOpenPopover.querySelector('.ss-popover');
      if (oldPop) ssyncOpenPopover.removeChild(oldPop);
      ssyncOpenPopover = null;
    }
    var picker = ssyncLinkPicker(direction, record, match, pool, onLink);
    // Store restore callback so collapse can put trigger back (or rebuild actions)
    picker._trigger = trigger;
    picker._onRestore = onRestore || null;
    picker._pickerWrap = pickerWrap;
    if (trigger && trigger.parentNode === pickerWrap) pickerWrap.removeChild(trigger);
    pickerWrap.appendChild(picker);
    ssyncOpenPicker = pickerWrap;

    // Esc collapses picker and returns focus to trigger
    function onPickerEsc(e) {
      if (e.key === 'Escape') {
        ssyncCollapsePicker(pickerWrap);
        document.removeEventListener('keydown', onPickerEsc);
      }
    }
    // Outside-click collapses picker
    function onPickerOutside(e) {
      if (!pickerWrap.contains(e.target)) {
        ssyncCollapsePicker(pickerWrap);
        document.removeEventListener('click', onPickerOutside);
        document.removeEventListener('keydown', onPickerEsc);
      }
    }
    picker._onEsc = onPickerEsc;
    picker._onOutside = onPickerOutside;
    document.addEventListener('keydown', onPickerEsc);
    setTimeout(function () { document.addEventListener('click', onPickerOutside); }, 0);

    return picker;
  }

  // Collapse the open picker inside pickerWrap and restore its trigger.
  // If no trigger but an onRestore callback was provided, invoke it instead
  // so the row's actions column is rebuilt rather than left bare.
  function ssyncCollapsePicker(pickerWrap) {
    var picker = pickerWrap.querySelector('.ss-picker');
    if (!picker) return;
    var trigger = picker._trigger;
    var onRestore = picker._onRestore;
    if (picker._onEsc) document.removeEventListener('keydown', picker._onEsc);
    if (picker._onOutside) document.removeEventListener('click', picker._onOutside);
    pickerWrap.removeChild(picker);
    if (trigger) {
      pickerWrap.appendChild(trigger);
      trigger.focus();
    } else if (onRestore) {
      onRestore();
    }
    if (ssyncOpenPicker === pickerWrap) ssyncOpenPicker = null;
  }

  // Build the actions column content based on kind
  function ssyncBuildRowActions(actionsEl, record, kind, match, name) {
    if (kind === 'all-db-linked') {
      // Linked: one ghost Unlink button, no overflow
      var unlinkBtn = AdminUI.el('button', {
        type: 'button',
        class: 'ss-act-ghost',
        'aria-label': 'Unlink ' + name + ' from Slack'
      }, ['Unlink']);
      unlinkBtn.addEventListener('click', function (e) {
        e.stopPropagation();
        ssyncUnlink(record.id, name, record.slack_display_name);
      });
      actionsEl.appendChild(unlinkBtn);

    } else if (kind === 'all-db-unlinked') {
      // Unlinked DB: primary Link trigger (opens picker on demand) + overflow with Delete
      var pickerWrap = AdminUI.el('div', { style: 'position:relative' }, []);
      var linkTrigger = AdminUI.el('button', {
        type: 'button',
        class: 'ss-act-primary',
        'aria-label': 'Link ' + name + ' to Slack'
      }, ['Link']);
      linkTrigger.addEventListener('click', function (e) {
        e.stopPropagation();
        var existing = pickerWrap.querySelector('.ss-picker');
        if (existing) { ssyncCollapsePicker(pickerWrap); return; }
        var m = ssyncSuggestMatch(record, ssyncState.unmatchedSlack);
        var picker = ssyncActivatePickerInWrap(pickerWrap, linkTrigger, 'db', record, m, ssyncState.unmatchedSlack, function (slackId) {
          ssyncLink(record.id, slackId);
        });
        var inp = picker.querySelector('.ss-picker-input');
        if (inp) inp.focus();
      });
      pickerWrap.appendChild(linkTrigger);
      actionsEl.appendChild(pickerWrap);

      var overflowWrapU = AdminUI.el('div', { class: 'ss-overflow-wrap' }, []);
      var overflowBtnU = AdminUI.el('button', {
        type: 'button',
        class: 'ss-overflow-btn',
        'aria-label': 'More actions for ' + name
      }, ['…']);
      overflowBtnU.addEventListener('click', function (e) {
        e.stopPropagation();
        ssyncTogglePopover(overflowWrapU, [
          { label: 'Delete user', danger: true, action: function () { ssyncDelete(record.id); } }
        ]);
      });
      overflowWrapU.appendChild(overflowBtnU);
      actionsEl.appendChild(overflowWrapU);

    } else if (kind === 'attention-db') {
      // Attention DB: confident = one-click fast path + overflow; weak/none = Link opens picker + overflow
      if (match && match.confidence === 'confident' && match.candidate) {
        var slackDisplayName = match.candidate.display_name || match.candidate.full_name || match.candidate.slack_uid || 'Slack user';
        var slackEmail = match.candidate.email || '';
        var warnTitle = 'Links to @' + slackDisplayName + ' via email match' + (slackEmail ? ' (' + slackEmail + ')' : '');
        var linkBtn = AdminUI.el('button', {
          type: 'button',
          class: 'ss-act-primary',
          title: warnTitle,
          'aria-describedby': 'ssync-link-warn-' + record.id
        }, ['Link']);
        linkBtn.addEventListener('click', function (e) {
          e.stopPropagation();
          ssyncLink(record.id, match.candidate.id);
        });

        var warnSpan = AdminUI.el('span', {
          id: 'ssync-link-warn-' + record.id,
          class: 'ss-sr-only'
        }, ['Links to @' + slackDisplayName + ' via email match. Note: DB email will be updated to ' + slackEmail]);
        actionsEl.appendChild(linkBtn);
        actionsEl.appendChild(warnSpan);

        // Overflow: link via picker, open details, delete
        var overflowWrapC = AdminUI.el('div', { class: 'ss-overflow-wrap' }, []);
        var overflowBtnC = AdminUI.el('button', {
          type: 'button',
          class: 'ss-overflow-btn',
          'aria-label': 'More actions for ' + name
        }, ['…']);
        overflowBtnC.addEventListener('click', function (e) {
          e.stopPropagation();
          ssyncTogglePopover(overflowWrapC, [
            {
              label: 'Link via picker', danger: false, action: function () {
                // Replace actions content with an on-demand picker (no Delete inline)
                actionsEl.innerHTML = '';
                var pickerWrap2 = AdminUI.el('div', { style: 'position:relative' }, []);
                actionsEl.appendChild(pickerWrap2);
                var picker2 = ssyncActivatePickerInWrap(pickerWrap2, null, 'db', record, match, ssyncState.unmatchedSlack, function (slackId) {
                  ssyncLink(record.id, slackId);
                }, function () {
                  // Restore: rebuild the row's normal actions
                  actionsEl.innerHTML = '';
                  ssyncBuildRowActions(actionsEl, record, 'attention-db', match, name);
                });
                var inp2 = picker2.querySelector('.ss-picker-input');
                if (inp2) inp2.focus();
              }
            },
            {
              label: 'Open details', danger: false, action: function () {
                ssyncOpenDrawer({ type: 'db', user: record, match: match }, null);
              }
            },
            { label: 'Delete user', danger: true, action: function () { ssyncDelete(record.id); } }
          ]);
        });
        overflowWrapC.appendChild(overflowBtnC);
        actionsEl.appendChild(overflowWrapC);

      } else {
        // No confident match: primary Link trigger opens picker on demand + overflow with Delete
        var m2 = match || { candidate: null, confidence: 'none', reason: '' };
        var pickerWrapW = AdminUI.el('div', { style: 'position:relative' }, []);
        var linkTriggerW = AdminUI.el('button', {
          type: 'button',
          class: 'ss-act-primary',
          'aria-label': 'Link ' + name + ' to Slack'
        }, ['Link']);
        linkTriggerW.addEventListener('click', function (e) {
          e.stopPropagation();
          var existing = pickerWrapW.querySelector('.ss-picker');
          if (existing) { ssyncCollapsePicker(pickerWrapW); return; }
          var picker = ssyncActivatePickerInWrap(pickerWrapW, linkTriggerW, 'db', record, m2, ssyncState.unmatchedSlack, function (slackId) {
            ssyncLink(record.id, slackId);
          });
          var inp = picker.querySelector('.ss-picker-input');
          if (inp) inp.focus();
        });
        pickerWrapW.appendChild(linkTriggerW);
        actionsEl.appendChild(pickerWrapW);

        var overflowWrapW = AdminUI.el('div', { class: 'ss-overflow-wrap' }, []);
        var overflowBtnW = AdminUI.el('button', {
          type: 'button',
          class: 'ss-overflow-btn',
          'aria-label': 'More actions for ' + name
        }, ['…']);
        overflowBtnW.addEventListener('click', function (e) {
          e.stopPropagation();
          ssyncTogglePopover(overflowWrapW, [
            { label: 'Delete user', danger: true, action: function () { ssyncDelete(record.id); } }
          ]);
        });
        overflowWrapW.appendChild(overflowBtnW);
        actionsEl.appendChild(overflowWrapW);
      }

    } else if (kind === 'slack') {
      // Unclaimed Slack: primary Import + overflow with "Link to DB user" (picker on demand)
      // No Delete -- no delete-slack-user endpoint exists
      var importZone = AdminUI.el('div', {}, []);
      var importBtn = AdminUI.el('button', {
        type: 'button',
        class: 'ss-act-primary',
        'aria-label': 'Import ' + name + ' as ALUMNI member'
      }, ['Import']);
      importBtn.addEventListener('click', function (e) {
        e.stopPropagation();
        ssyncShowImportConfirm(importZone, importBtn, record);
      });
      importZone.appendChild(importBtn);
      actionsEl.appendChild(importZone);

      var overflowWrapS = AdminUI.el('div', { class: 'ss-overflow-wrap' }, []);
      var overflowBtnS = AdminUI.el('button', {
        type: 'button',
        class: 'ss-overflow-btn',
        'aria-label': 'More actions for ' + name
      }, ['…']);
      overflowBtnS.addEventListener('click', function (e) {
        e.stopPropagation();
        ssyncTogglePopover(overflowWrapS, [
          {
            label: 'Link to DB user', danger: false, action: function () {
              // Inject picker below the importZone (inside actionsEl, not the button)
              var existingPicker = actionsEl.querySelector('.ss-picker-wrap-s');
              if (existingPicker) { existingPicker.parentNode.removeChild(existingPicker); return; }
              var pickerWrapS = AdminUI.el('div', { class: 'ss-picker-wrap-s', style: 'position:relative' }, []);
              actionsEl.appendChild(pickerWrapS);
              var slackMatch = ssyncSuggestMatchSlack(record, ssyncState.unmatchedDb);
              var pickerS = ssyncActivatePickerInWrap(pickerWrapS, null, 'slack', record, slackMatch, ssyncState.unmatchedDb, function (dbId) {
                ssyncLink(dbId, record.id);
              }, function () {
                // Restore: drop the stray wrapper (Import + overflow remain)
                if (pickerWrapS.parentNode) pickerWrapS.parentNode.removeChild(pickerWrapS);
              });
              var inpS = pickerS.querySelector('.ss-picker-input');
              if (inpS) inpS.focus();
            }
          }
        ]);
      });
      overflowWrapS.appendChild(overflowBtnS);
      actionsEl.appendChild(overflowWrapS);
    }
  }

  // ─── Import confirm ───────────────────────────────────────────────────────────
  function ssyncShowImportConfirm(zone, importBtn, slackUser) {
    var name = slackUser.display_name || slackUser.full_name || slackUser.slack_uid || '?';
    importBtn.style.display = 'none';

    var confirmZone = AdminUI.el('div', { class: 'ss-inline-confirm', role: 'alert' }, [
      AdminUI.el('div', { class: 'ss-inline-confirm-msg' }, [
        'Import ' + name + ' (' + (slackUser.email || 'no email') + ') as ALUMNI member with a legacy season?'
      ])
    ]);
    var confirmActions = AdminUI.el('div', { class: 'ss-inline-confirm-actions' }, []);

    var confirmBtn = AdminUI.el('button', { type: 'button', class: 'ss-act-confirm' }, ['Confirm']);
    confirmBtn.addEventListener('click', function (e) {
      e.stopPropagation();
      confirmBtn.disabled = true;
      confirmBtn.textContent = 'Importing...';
      ssyncImport(slackUser.id);
    });
    var cancelBtn = AdminUI.el('button', { type: 'button', class: 'ss-act-cancel' }, ['Cancel']);
    cancelBtn.addEventListener('click', function (e) {
      e.stopPropagation();
      zone.removeChild(confirmZone);
      importBtn.style.display = '';
      importBtn.focus();
    });

    confirmActions.appendChild(confirmBtn);
    confirmActions.appendChild(cancelBtn);
    confirmZone.appendChild(confirmActions);
    zone.appendChild(confirmZone);
    confirmBtn.focus();
  }

  // ─── Bulk import ──────────────────────────────────────────────────────────────
  function ssyncShowBulkConfirm(bulkWrap, bulkBtn) {
    bulkBtn.style.display = 'none';
    var n = ssyncState.unmatchedSlack.length;
    var confirmEl = AdminUI.el('div', { class: 'ss-bulk-confirm', role: 'alert' }, [
      AdminUI.el('div', {}, [
        'Import all ' + n + ' unclaimed Slack accounts as ALUMNI members? This will process them one at a time.'
      ])
    ]);
    var confirmActions = AdminUI.el('div', { class: 'ss-bulk-confirm-actions' }, []);
    var confirmBtn = AdminUI.el('button', { type: 'button', class: 'ss-act-confirm' }, ['Confirm import']);
    confirmBtn.addEventListener('click', function () {
      confirmBtn.disabled = true;
      confirmBtn.textContent = 'Importing...';
      ssyncBulkImport(confirmEl, confirmActions);
    });
    var cancelBtn = AdminUI.el('button', { type: 'button', class: 'ss-act-cancel' }, ['Cancel']);
    cancelBtn.addEventListener('click', function () {
      bulkWrap.removeChild(confirmEl);
      bulkBtn.style.display = '';
      bulkBtn.focus();
    });
    confirmActions.appendChild(confirmBtn);
    confirmActions.appendChild(cancelBtn);
    confirmEl.appendChild(confirmActions);
    bulkWrap.appendChild(confirmEl);
    confirmBtn.focus();
  }

  // ─── Inline link picker ───────────────────────────────────────────────────────
  // direction: 'db' (picking from Slack pool) | 'slack' (picking from DB pool)
  function ssyncLinkPicker(direction, fromUser, match, pool, onLink) {
    var uid = direction + '-' + (fromUser.id || Math.random());
    var listId = 'ssync-picker-list-' + uid;

    var wrapper = AdminUI.el('div', { class: 'ss-picker' }, []);

    // Determine preselected text
    var preselected = '';
    if (match && match.candidate && (match.confidence === 'confident' || match.confidence === 'strong')) {
      preselected = direction === 'db'
        ? (match.candidate.display_name || match.candidate.full_name || match.candidate.slack_uid || '')
        : (match.candidate.full_name || match.candidate.email || '');
    }

    var input = AdminUI.el('input', {
      type: 'text',
      class: 'ss-picker-input',
      'aria-label': direction === 'db' ? 'Search Slack user to link' : 'Search DB user to link',
      'aria-controls': listId,
      'aria-expanded': 'false',
      'aria-autocomplete': 'list',
      placeholder: direction === 'db' ? 'Search Slack user...' : 'Search DB user...',
      value: preselected
    }, []);

    var dropdown = AdminUI.el('div', {
      class: 'ss-picker-dropdown',
      id: listId,
      role: 'listbox',
      'aria-label': 'Matching users'
    }, []);

    wrapper.appendChild(input);
    wrapper.appendChild(dropdown);

    var selectedId = null;
    var selectedName = '';
    var selectedEmail = '';
    var highlightedIndex = -1;

    function getOptions(q) {
      var ql = (q || '').toLowerCase();
      return pool.filter(function (u) {
        var name = (u.full_name || u.display_name || '').toLowerCase();
        var email = (u.email || '').toLowerCase();
        return !ql || name.includes(ql) || email.includes(ql);
      });
    }

    function renderDropdown(q) {
      dropdown.innerHTML = '';
      var options = getOptions(q);

      if (options.length === 0) {
        dropdown.appendChild(AdminUI.el('div', { class: 'ss-picker-empty' }, ['No matches']));
        return;
      }

      options.forEach(function (u, idx) {
        var isMatch = match && match.candidate && match.candidate.id === u.id;
        var optName = u.full_name || u.display_name || u.slack_uid || '';
        var email = u.email || '';

        var nameEl = AdminUI.el('div', { class: 'ss-picker-option-name' }, [optName]);
        if (isMatch && match.confidence !== 'none') {
          var badgeText = match.confidence === 'confident' ? 'email match' : 'name match';
          nameEl.appendChild(AdminUI.el('span', { class: 'ss-picker-suggestion-badge' }, [badgeText]));
        }

        var optEl = AdminUI.el('div', {
          id: listId + '-opt-' + idx,
          class: 'ss-picker-option',
          role: 'option',
          'aria-selected': 'false',
          dataset: { id: String(u.id), name: optName, email: email, idx: String(idx) }
        }, [nameEl, AdminUI.el('div', { class: 'ss-picker-option-email' }, [email])]);

        optEl.addEventListener('click', function () {
          selectOption(u.id, optName, email);
        });

        dropdown.appendChild(optEl);
      });
    }

    function selectOption(id, optName, email) {
      selectedId = id;
      selectedName = optName;
      selectedEmail = email;
      input.value = optName;
      closeDropdown();
      showConfirmRow();
    }

    var confirmRow = null;

    function showConfirmRow() {
      removeConfirmRow();
      var fromEmail = fromUser.email || '';
      var emailsDiffer = selectedEmail && fromEmail && selectedEmail.toLowerCase() !== fromEmail.toLowerCase();

      confirmRow = AdminUI.el('div', { class: 'ss-picker-confirm' }, []);
      var row = AdminUI.el('div', { class: 'ss-picker-confirm-row' }, []);

      var confirmBtn = AdminUI.el('button', {
        type: 'button',
        class: 'ss-picker-confirm-btn'
      }, ['Link ' + selectedName]);

      confirmBtn.addEventListener('click', function (e) {
        e.stopPropagation();
        onLink(selectedId);
      });
      row.appendChild(confirmBtn);

      confirmRow.appendChild(row);

      if (emailsDiffer) {
        var warnMsg = 'Note: DB email will be updated to ' + selectedEmail;
        var warnEl = AdminUI.el('div', { class: 'ss-picker-email-warn', role: 'alert' }, [warnMsg]);
        confirmRow.appendChild(warnEl);
      }

      wrapper.appendChild(confirmRow);
    }

    function removeConfirmRow() {
      if (confirmRow && confirmRow.parentNode) {
        confirmRow.parentNode.removeChild(confirmRow);
        confirmRow = null;
      }
    }

    // Outside-click handler -- attached on open, removed on close to avoid accumulation
    function onDocClickOutside(e) {
      if (!wrapper.contains(e.target)) {
        closeDropdown();
      }
    }

    function openDropdown() {
      renderDropdown(input.value);
      dropdown.classList.add('is-open');
      input.setAttribute('aria-expanded', 'true');
      highlightedIndex = -1;
      // Bind once per open; setTimeout defers past the current click that triggered focus
      setTimeout(function () {
        document.addEventListener('click', onDocClickOutside);
      }, 0);
    }

    function closeDropdown() {
      dropdown.classList.remove('is-open');
      input.setAttribute('aria-expanded', 'false');
      document.removeEventListener('click', onDocClickOutside);
    }

    // Events
    input.addEventListener('focus', function () { openDropdown(); });
    input.addEventListener('input', function () {
      selectedId = null;
      removeConfirmRow();
      openDropdown();
    });

    input.addEventListener('keydown', function (e) {
      var opts = dropdown.querySelectorAll('.ss-picker-option');
      if (e.key === 'Escape') { closeDropdown(); }
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        highlightedIndex = Math.min(highlightedIndex + 1, opts.length - 1);
        updateHighlight(opts);
      }
      if (e.key === 'ArrowUp') {
        e.preventDefault();
        highlightedIndex = Math.max(highlightedIndex - 1, 0);
        updateHighlight(opts);
      }
      if (e.key === 'Enter' && highlightedIndex >= 0 && opts[highlightedIndex]) {
        e.preventDefault();
        var opt = opts[highlightedIndex];
        selectOption(parseInt(opt.dataset.id), opt.dataset.name, opt.dataset.email);
      }
    });

    function updateHighlight(opts) {
      Array.prototype.forEach.call(opts, function (o, i) {
        o.setAttribute('aria-selected', i === highlightedIndex ? 'true' : 'false');
        if (i === highlightedIndex) {
          input.setAttribute('aria-activedescendant', o.id || '');
        }
      });
    }

    return wrapper;
  }

  // ─── Overflow popover ─────────────────────────────────────────────────────────
  // items: Array of {label:string, danger:boolean, action:function}
  function ssyncTogglePopover(wrapEl, items) {
    // Close any other open popover
    if (ssyncOpenPopover && ssyncOpenPopover !== wrapEl) {
      var old = ssyncOpenPopover.querySelector('.ss-popover');
      if (old) ssyncOpenPopover.removeChild(old);
      ssyncOpenPopover = null;
    }

    var existing = wrapEl.querySelector('.ss-popover');
    if (existing) {
      wrapEl.removeChild(existing);
      ssyncOpenPopover = null;
      return;
    }

    // Close any open picker when opening a popover
    if (ssyncOpenPicker) {
      ssyncCollapsePicker(ssyncOpenPicker);
    }

    var popover = AdminUI.el('div', { class: 'ss-popover', role: 'menu' }, []);

    items.forEach(function (item, idx) {
      var cls = 'ss-popover-item' + (item.danger ? ' ss-popover-item-danger' : '');
      var menuItem = AdminUI.el('button', { type: 'button', class: cls, role: 'menuitem' }, [item.label]);
      menuItem.addEventListener('click', function () {
        if (wrapEl.contains(popover)) wrapEl.removeChild(popover);
        ssyncOpenPopover = null;
        if (item.action) item.action();
      });
      popover.appendChild(menuItem);
    });

    wrapEl.appendChild(popover);
    ssyncOpenPopover = wrapEl;
    var firstItem = popover.querySelector('.ss-popover-item');
    if (firstItem) firstItem.focus();

    // Close on Esc or outside click
    function onKey(e) {
      if (e.key === 'Escape') {
        if (wrapEl.contains(popover)) wrapEl.removeChild(popover);
        ssyncOpenPopover = null;
        document.removeEventListener('keydown', onKey);
      }
    }
    function onDoc(e) {
      if (!wrapEl.contains(e.target)) {
        if (wrapEl.contains(popover)) wrapEl.removeChild(popover);
        ssyncOpenPopover = null;
        document.removeEventListener('click', onDoc);
      }
    }
    document.addEventListener('keydown', onKey);
    setTimeout(function () { document.addEventListener('click', onDoc); }, 0);
  }

  // ─── Drawer ───────────────────────────────────────────────────────────────────
  // originRow: the .ss-row element that was clicked (for is-active rail), or null
  function ssyncOpenDrawer(opts, originRow) {
    var record = opts.user;
    var type = opts.type;
    var match = opts.match || null;

    // Set active rail on the originating row
    ssyncSetActiveRow(originRow);

    var title = record.full_name || record.display_name || record.email || '?';
    var content = AdminUI.el('div', { class: 'admin-ui-dw' }, []);

    // DB section
    if (type === 'db') {
      var dbSection = AdminUI.el('div', { class: 'admin-ui-dw-section' }, [
        AdminUI.el('div', { class: 'admin-ui-dw-section-title' }, ['DB record'])
      ]);
      [
        ['ID', String(record.id || '')],
        ['Email', record.email || ''],
        ['Status', record.status || '']
      ].forEach(function (kv) {
        dbSection.appendChild(AdminUI.el('div', { class: 'admin-ui-dw-kv' }, [
          AdminUI.el('div', { class: 'admin-ui-dw-key' }, [kv[0]]),
          AdminUI.el('div', { class: kv[1] ? 'admin-ui-dw-val' : 'admin-ui-dw-val admin-ui-dw-val--empty' }, [kv[1] || 'none'])
        ]));
      });
      // Slack info if linked
      if (record.slack_matched) {
        dbSection.appendChild(AdminUI.el('div', { class: 'admin-ui-dw-kv' }, [
          AdminUI.el('div', { class: 'admin-ui-dw-key' }, ['Slack UID']),
          AdminUI.el('div', { class: record.slack_uid ? 'admin-ui-dw-val' : 'admin-ui-dw-val admin-ui-dw-val--empty' }, [record.slack_uid || 'none'])
        ]));
        dbSection.appendChild(AdminUI.el('div', { class: 'admin-ui-dw-kv' }, [
          AdminUI.el('div', { class: 'admin-ui-dw-key' }, ['Slack name']),
          AdminUI.el('div', { class: record.slack_display_name ? 'admin-ui-dw-val' : 'admin-ui-dw-val admin-ui-dw-val--empty' }, [record.slack_display_name || 'none'])
        ]));
      }
      content.appendChild(dbSection);
    }

    // Slack section
    if (type === 'slack') {
      var slackSection = AdminUI.el('div', { class: 'admin-ui-dw-section' }, [
        AdminUI.el('div', { class: 'admin-ui-dw-section-title' }, ['Slack record'])
      ]);
      [
        ['Slack UID', record.slack_uid || ''],
        ['Email', record.email || ''],
        ['Display name', record.display_name || ''],
        ['Full name', record.full_name || '']
      ].forEach(function (kv) {
        slackSection.appendChild(AdminUI.el('div', { class: 'admin-ui-dw-kv' }, [
          AdminUI.el('div', { class: 'admin-ui-dw-key' }, [kv[0]]),
          AdminUI.el('div', { class: kv[1] ? 'admin-ui-dw-val' : 'admin-ui-dw-val admin-ui-dw-val--empty' }, [kv[1] || 'none'])
        ]));
      });
      content.appendChild(slackSection);
    }

    // Match analysis (for unlinked DB users)
    if (type === 'db' && !record.slack_matched && match) {
      var matchSection = AdminUI.el('div', { class: 'admin-ui-dw-section' }, [
        AdminUI.el('div', { class: 'admin-ui-dw-section-title' }, ['Match analysis'])
      ]);
      var confVariants = { confident: 'success', strong: 'info', weak: 'warning', none: 'neutral' };
      matchSection.appendChild(AdminUI.el('div', { class: 'admin-ui-dw-kv' }, [
        AdminUI.el('div', { class: 'admin-ui-dw-key' }, ['Confidence']),
        AdminUI.statusBadge(match.confidence, confVariants[match.confidence] || 'neutral')
      ]));
      matchSection.appendChild(AdminUI.el('div', { class: 'admin-ui-dw-kv' }, [
        AdminUI.el('div', { class: 'admin-ui-dw-key' }, ['Reason']),
        AdminUI.el('div', { class: 'admin-ui-dw-val' }, [match.reason || ''])
      ]));
      if (match.candidate) {
        var cname = match.candidate.display_name || match.candidate.full_name || match.candidate.slack_uid || '';
        matchSection.appendChild(AdminUI.el('div', { class: 'admin-ui-dw-kv' }, [
          AdminUI.el('div', { class: 'admin-ui-dw-key' }, ['Candidate']),
          AdminUI.el('div', { class: 'admin-ui-dw-val' }, [cname + ' (' + (match.candidate.email || '') + ')'])
        ]));
      } else {
        matchSection.appendChild(AdminUI.el('div', { class: 'admin-ui-dw-kv' }, [
          AdminUI.el('div', { class: 'admin-ui-dw-key' }, ['Candidate']),
          AdminUI.el('div', { class: 'admin-ui-dw-val admin-ui-dw-val--empty' }, ['No candidate found'])
        ]));
      }
      content.appendChild(matchSection);
    }

    // Also suggest match for Slack-type drawer
    if (type === 'slack') {
      var slackMatch = ssyncSuggestMatchSlack(record, ssyncState.unmatchedDb);
      var matchSection2 = AdminUI.el('div', { class: 'admin-ui-dw-section' }, [
        AdminUI.el('div', { class: 'admin-ui-dw-section-title' }, ['Match analysis'])
      ]);
      var confVariants2 = { confident: 'success', strong: 'info', weak: 'warning', none: 'neutral' };
      matchSection2.appendChild(AdminUI.el('div', { class: 'admin-ui-dw-kv' }, [
        AdminUI.el('div', { class: 'admin-ui-dw-key' }, ['Confidence']),
        AdminUI.statusBadge(slackMatch.confidence, confVariants2[slackMatch.confidence] || 'neutral')
      ]));
      matchSection2.appendChild(AdminUI.el('div', { class: 'admin-ui-dw-kv' }, [
        AdminUI.el('div', { class: 'admin-ui-dw-key' }, ['Reason']),
        AdminUI.el('div', { class: 'admin-ui-dw-val' }, [slackMatch.reason || ''])
      ]));
      if (slackMatch.candidate) {
        matchSection2.appendChild(AdminUI.el('div', { class: 'admin-ui-dw-kv' }, [
          AdminUI.el('div', { class: 'admin-ui-dw-key' }, ['Candidate']),
          AdminUI.el('div', { class: 'admin-ui-dw-val' }, [slackMatch.candidate.full_name + ' (' + (slackMatch.candidate.email || '') + ')'])
        ]));
      }
      content.appendChild(matchSection2);
    }

    // Actions zone (footer -- mounted inside content before AdminUI.drawer so position:sticky works)
    var actionsZone = AdminUI.el('div', { class: 'admin-ui-dw-footer' }, []);

    function renderActionsZone() {
      actionsZone.innerHTML = '';

      if (type === 'db' && record.slack_matched) {
        // Unlink button
        var unlinkBtn = AdminUI.el('button', { type: 'button', class: 'admin-ui-dw-btn-ghost' }, ['Unlink from Slack']);
        unlinkBtn.addEventListener('click', function () { showUnlinkConfirm(); });
        actionsZone.appendChild(unlinkBtn);

      } else if (type === 'db' && !record.slack_matched) {
        // Link via picker
        var dwMatch = match || ssyncSuggestMatch(record, ssyncState.unmatchedSlack);
        var dwPicker = ssyncLinkPicker('db', record, dwMatch, ssyncState.unmatchedSlack, function (slackId) {
          ssyncLink(record.id, slackId);
        });
        actionsZone.appendChild(dwPicker);

        // Email overwrite warning if candidate exists
        if (dwMatch && dwMatch.candidate && dwMatch.candidate.email) {
          var fromEmail = record.email || '';
          var toEmail = dwMatch.candidate.email || '';
          if (toEmail.toLowerCase() !== fromEmail.toLowerCase()) {
            actionsZone.appendChild(AdminUI.el('div', { class: 'ss-dw-email-warn' }, [
              'Note: DB email will be updated to ' + toEmail
            ]));
          }
        }

        var deleteBtn = AdminUI.el('button', {
          type: 'button',
          class: 'admin-ui-dw-btn-danger'
        }, ['Delete user']);
        deleteBtn.addEventListener('click', function () { showDeleteConfirm(); });
        actionsZone.appendChild(deleteBtn);

      } else if (type === 'slack') {
        // Import button
        var importBtn = AdminUI.el('button', { type: 'button', class: 'admin-ui-dw-btn-primary' }, ['Import as member']);
        importBtn.addEventListener('click', function () { showImportConfirmDw(); });
        actionsZone.appendChild(importBtn);

        // Link to DB user
        var slackMatch2 = ssyncSuggestMatchSlack(record, ssyncState.unmatchedDb);
        var dwPickerSlack = ssyncLinkPicker('slack', record, slackMatch2, ssyncState.unmatchedDb, function (dbId) {
          ssyncLink(dbId, record.id);
        });
        actionsZone.appendChild(dwPickerSlack);
      }
    }

    function showUnlinkConfirm() {
      actionsZone.innerHTML = '';
      var slackName = record.slack_display_name || record.slack_uid || 'Slack';
      var confirmZone = AdminUI.el('div', { class: 'ss-dw-confirm-zone', role: 'alert' }, [
        AdminUI.el('div', { class: 'ss-dw-confirm-msg' }, [
          'Unlink ' + (record.full_name || '') + ' from @' + slackName + '? Their DB email will not revert.'
        ])
      ]);
      var confirmActions = AdminUI.el('div', { class: 'ss-dw-confirm-actions' }, []);
      var yesBtn = AdminUI.el('button', { type: 'button', class: 'admin-ui-dw-btn-danger' }, ['Confirm unlink']);
      yesBtn.addEventListener('click', function () { ssyncUnlinkById(record.id); });
      var noBtn = AdminUI.el('button', { type: 'button', class: 'admin-ui-dw-btn-ghost' }, ['Cancel']);
      noBtn.addEventListener('click', function () { renderActionsZone(); noBtn.focus(); });
      confirmActions.appendChild(yesBtn);
      confirmActions.appendChild(noBtn);
      confirmZone.appendChild(confirmActions);
      actionsZone.appendChild(confirmZone);
      yesBtn.focus();
    }

    function showDeleteConfirm() {
      actionsZone.innerHTML = '';
      var name = record.full_name || record.email || String(record.id);
      var confirmZone = AdminUI.el('div', { class: 'ss-dw-confirm-zone', role: 'alert' }, [
        AdminUI.el('div', { class: 'ss-dw-confirm-msg' }, [
          'Permanently delete ' + name + ' (' + (record.email || '') + ')? This removes UserSeason records. Associated payments will be preserved with no user attached.'
        ])
      ]);
      var confirmActions = AdminUI.el('div', { class: 'ss-dw-confirm-actions' }, []);
      var yesBtn = AdminUI.el('button', { type: 'button', class: 'admin-ui-dw-btn-danger' }, ['Confirm delete']);
      yesBtn.addEventListener('click', function () { ssyncDeleteById(record.id); });
      var noBtn = AdminUI.el('button', { type: 'button', class: 'admin-ui-dw-btn-ghost' }, ['Cancel']);
      noBtn.addEventListener('click', function () { renderActionsZone(); noBtn.focus(); });
      confirmActions.appendChild(yesBtn);
      confirmActions.appendChild(noBtn);
      confirmZone.appendChild(confirmActions);
      actionsZone.appendChild(confirmZone);
      yesBtn.focus();
    }

    function showImportConfirmDw() {
      actionsZone.innerHTML = '';
      var name = record.display_name || record.full_name || record.slack_uid || '?';
      var confirmZone = AdminUI.el('div', { class: 'ss-dw-confirm-zone', role: 'alert' }, [
        AdminUI.el('div', { class: 'ss-dw-confirm-msg' }, [
          'Import ' + name + ' (' + (record.email || 'no email') + ') as an ALUMNI member with a legacy season?'
        ])
      ]);
      var confirmActions = AdminUI.el('div', { class: 'ss-dw-confirm-actions' }, []);
      var yesBtn = AdminUI.el('button', { type: 'button', class: 'admin-ui-dw-btn-primary' }, ['Confirm import']);
      yesBtn.addEventListener('click', function () { ssyncImport(record.id); });
      var noBtn = AdminUI.el('button', { type: 'button', class: 'admin-ui-dw-btn-ghost' }, ['Cancel']);
      noBtn.addEventListener('click', function () { renderActionsZone(); noBtn.focus(); });
      confirmActions.appendChild(yesBtn);
      confirmActions.appendChild(noBtn);
      confirmZone.appendChild(confirmActions);
      actionsZone.appendChild(confirmZone);
      yesBtn.focus();
    }

    renderActionsZone();
    content.appendChild(actionsZone);

    AdminUI.drawer({
      title: title,
      content: content,
      onClose: function () { ssyncClearActiveRow(); }
    });
  }

  // ─── Overflow unlink from a row (uses drawer confirm) ────────────────────────
  function ssyncUnlink(userId, userName, slackName) {
    var user = ssyncState.users.find(function (u) { return u.id === userId; });
    if (user) {
      ssyncOpenDrawer({ type: 'db', user: user, match: null }, null);
    } else {
      ssyncUnlinkById(userId);
    }
  }

  // ─── Mutation wrappers ────────────────────────────────────────────────────────
  function ssyncLink(userId, slackUserId) {
    AdminUI.mutate('/admin/slack/link', { user_id: userId, slack_user_id: slackUserId })
      .then(function () {
        if (window.showToast) showToast('Linked successfully', 'success');
        return ssyncLoadAll();
      })
      .catch(function (e) {
        if (window.showToast) showToast('Failed to link: ' + e.message, 'error');
      });
  }

  function ssyncUnlinkById(userId) {
    AdminUI.mutate('/admin/slack/unlink', { user_id: userId })
      .then(function () {
        if (window.showToast) showToast('Unlinked successfully', 'success');
        return ssyncLoadAll();
      })
      .catch(function (e) {
        if (window.showToast) showToast('Failed to unlink: ' + e.message, 'error');
      });
  }

  function ssyncDelete(userId) {
    var user = ssyncState.users.find(function (u) { return u.id === userId; })
      || ssyncState.unmatchedDb.find(function (u) { return u.id === userId; });
    if (user) {
      ssyncOpenDrawer({ type: 'db', user: user, match: null }, null);
    } else {
      ssyncDeleteById(userId);
    }
  }

  function ssyncDeleteById(userId) {
    AdminUI.mutate('/admin/slack/delete-user', { user_id: userId })
      .then(function () {
        return ssyncLoadAll();
      })
      .catch(function (e) {
        if (window.showToast) showToast('Failed to delete: ' + e.message, 'error');
      });
  }

  function ssyncImport(slackUserId) {
    AdminUI.mutate('/admin/slack/import', { slack_user_id: slackUserId })
      .then(function () {
        return ssyncLoadAll();
      })
      .catch(function (e) {
        if (window.showToast) showToast('Failed to import: ' + e.message, 'error');
      });
  }

  // ─── Bulk import ──────────────────────────────────────────────────────────────
  function ssyncBulkImport(confirmEl, confirmActions) {
    var items = ssyncState.unmatchedSlack.slice();
    var total = items.length;
    var succeeded = 0;
    var errors = [];
    var i = 0;

    function processNext() {
      if (i >= items.length) {
        var summaryMsg = 'Imported ' + succeeded + ' of ' + total + '.';
        if (errors.length > 0) summaryMsg += ' ' + errors.length + ' error(s): ' + errors.join(', ');
        if (window.showToast) showToast(summaryMsg, errors.length > 0 ? 'info' : 'success');
        ssyncLoadAll();
        return;
      }

      var item = items[i];
      i++;
      if (window.showToast) showToast('Importing ' + i + ' of ' + total + '...', 'info');

      fetch('/admin/slack/import', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
        body: JSON.stringify({ slack_user_id: item.id })
      }).then(function (res) {
        return res.json().then(function (d) {
          if (!res.ok || d.error) {
            errors.push((item.display_name || item.full_name || String(item.id)) + ': ' + (d.error || 'error'));
          } else {
            succeeded++;
          }
          processNext();
        });
      }).catch(function (e) {
        errors.push((item.display_name || item.full_name || String(item.id)) + ': ' + e.message);
        processNext();
      });
    }

    processNext();
  }

  // ─── Sync from Slack ──────────────────────────────────────────────────────────
  function ssyncRunPull() {
    var btn = document.getElementById('ssync-pull-btn');
    btn.classList.add('ss-loading');
    btn.setAttribute('aria-busy', 'true');

    fetch('/admin/slack/sync', { method: 'POST' })
      .then(function (res) { return res.json(); })
      .then(function (data) {
        if (data.error) {
          if (window.showToast) showToast('Sync error: ' + data.error, 'error');
        } else if (data.errors && data.errors.length > 0) {
          if (window.showToast) showToast('Sync done with ' + data.errors.length + ' error(s)', 'info');
        } else {
          var parts = [];
          if (data.slack_users_created > 0) parts.push(data.slack_users_created + ' created');
          if (data.slack_users_updated > 0) parts.push(data.slack_users_updated + ' updated');
          if (data.users_matched > 0) parts.push(data.users_matched + ' matched');
          var msg = parts.length > 0 ? parts.join(', ') : 'No changes';
          if (window.showToast) showToast(msg, 'success');
        }
        return ssyncLoadAll();
      })
      .catch(function (e) {
        if (window.showToast) showToast('Sync failed: ' + e.message, 'error');
      })
      .finally(function () {
        btn.classList.remove('ss-loading');
        btn.setAttribute('aria-busy', 'false');
      });
  }

  // ─── Sync to Slack (batched push) ─────────────────────────────────────────────
  function ssyncRunProfilePush() {
    var btn = document.getElementById('ssync-push-btn');
    var progressSpan = btn.querySelector('.ss-btn-progress');
    btn.classList.add('ss-loading');
    btn.setAttribute('aria-busy', 'true');

    var totalUpdated = 0;
    var totalSkipped = 0;
    var totalErrors = [];
    var offset = 0;
    var totalUsers = 0;
    var batchSize = 10;

    function doNextBatch() {
      var progress = totalUsers > 0 ? offset + '/' + totalUsers : '...';
      progressSpan.textContent = 'Syncing ' + progress;

      fetch('/admin/slack/sync-profiles', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ batch_size: batchSize, offset: offset })
      })
        .then(function (res) {
          if (!res.ok) throw new Error('HTTP ' + res.status);
          return res.json();
        })
        .then(function (data) {
          if (data.error) throw new Error(data.error);

          if (data.total && totalUsers === 0) totalUsers = data.total;

          totalUpdated += data.users_updated || 0;
          totalSkipped += data.users_skipped || 0;
          if (data.errors) totalErrors = totalErrors.concat(data.errors);

          if (data.remaining === 0) {
            if (totalErrors.length > 0) {
              if (window.showToast) showToast('Sync done with ' + totalErrors.length + ' error(s). Updated: ' + totalUpdated, 'info');
            } else {
              if (window.showToast) showToast('Updated ' + totalUpdated + ' profile(s)', 'success');
            }
            btn.classList.remove('ss-loading');
            btn.setAttribute('aria-busy', 'false');
            progressSpan.textContent = 'Syncing...';
            ssyncLoadAll();
          } else {
            offset += batchSize;
            doNextBatch();
          }
        })
        .catch(function (e) {
          if (window.showToast) showToast('Profile sync failed: ' + e.message, 'error');
          btn.classList.remove('ss-loading');
          btn.setAttribute('aria-busy', 'false');
          progressSpan.textContent = 'Syncing...';
        });
    }

    doNextBatch();
  }

  // ─── Send Message modal ───────────────────────────────────────────────────────
  function ssyncMessageOpen() {
    var modal = document.getElementById('ssync-message-modal');
    var container = document.getElementById('ssync-user-checkboxes');
    container.innerHTML = '';

    var linkedUsers = ssyncState.users
      .filter(function (u) { return u.slack_matched; })
      .sort(function (a, b) { return (a.full_name || '').localeCompare(b.full_name || ''); });

    if (linkedUsers.length === 0) {
      container.appendChild(AdminUI.el('p', { style: 'margin:8px 0;color:#94a3b8;font-size:13px' }, [
        'No linked users - sync and link first.'
      ]));
      document.getElementById('ssync-send-btn').disabled = true;
    } else {
      document.getElementById('ssync-send-btn').disabled = false;
      linkedUsers.forEach(function (user) {
        var lbl = AdminUI.el('label', { class: 'ss-recipient-item' }, []);
        var cb = AdminUI.el('input', {
          type: 'checkbox',
          class: 'ssync-user-checkbox',
          value: String(user.id),
          dataset: { name: user.full_name || '' }
        }, []);
        cb.addEventListener('change', ssyncMessageUpdateCount);
        lbl.appendChild(cb);
        lbl.appendChild(AdminUI.el('span', { class: 'ss-recipient-name' }, [user.full_name || '']));
        lbl.appendChild(AdminUI.el('span', { class: 'ss-recipient-email' }, [user.email || '']));
        container.appendChild(lbl);
      });
    }

    // Setup search
    var searchInput = document.getElementById('ssync-user-search');
    searchInput.value = '';
    searchInput.oninput = function () {
      var q = this.value.toLowerCase();
      container.querySelectorAll('.ss-recipient-item').forEach(function (item) {
        var cb = item.querySelector('.ssync-user-checkbox');
        var name = (cb ? cb.dataset.name || '' : '').toLowerCase();
        var email = item.textContent.toLowerCase();
        item.style.display = (!q || name.includes(q) || email.includes(q)) ? '' : 'none';
      });
    };

    // Reset
    document.getElementById('ssync-message-text').value = '';
    var indvRadio = document.querySelector('input[name="ssync-message-mode"][value="individual"]');
    if (indvRadio) indvRadio.checked = true;

    ssyncMessageUpdateCount();
    modal.style.display = 'flex';
    AdminUI.trapFocus(modal);

    // Esc closes
    function onEsc(e) {
      if (e.key === 'Escape') {
        ssyncMessageClose();
        document.removeEventListener('keydown', onEsc);
      }
    }
    document.addEventListener('keydown', onEsc);
  }

  function ssyncMessageClose() {
    document.getElementById('ssync-message-modal').style.display = 'none';
  }

  function ssyncMessageSelectAll() {
    document.querySelectorAll('.ssync-user-checkbox').forEach(function (cb) {
      var item = cb.closest('.ss-recipient-item');
      if (!item || item.style.display !== 'none') cb.checked = true;
    });
    ssyncMessageUpdateCount();
  }

  function ssyncMessageDeselectAll() {
    document.querySelectorAll('.ssync-user-checkbox').forEach(function (cb) { cb.checked = false; });
    ssyncMessageUpdateCount();
  }

  function ssyncMessageUpdateCount() {
    var count = document.querySelectorAll('.ssync-user-checkbox:checked').length;
    var el = document.getElementById('ssync-selected-count');
    if (el) el.textContent = String(count);
  }

  function ssyncMessageSend() {
    var selectedCbs = document.querySelectorAll('.ssync-user-checkbox:checked');
    var userIds = Array.prototype.map.call(selectedCbs, function (cb) { return parseInt(cb.value); });
    var message = (document.getElementById('ssync-message-text').value || '').trim();
    var modeEl = document.querySelector('input[name="ssync-message-mode"]:checked');
    var mode = modeEl ? modeEl.value : 'individual';

    if (userIds.length === 0) {
      if (window.showToast) showToast('Please select at least one recipient', 'error');
      return;
    }
    if (!message) {
      if (window.showToast) showToast('Please enter a message', 'error');
      return;
    }

    var sendBtn = document.getElementById('ssync-send-btn');
    sendBtn.disabled = true;
    sendBtn.textContent = 'Sending...';

    fetch('/admin/slack/send-message', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_ids: userIds, message: message, mode: mode })
    })
      .then(function (res) { return res.json(); })
      .then(function (data) {
        if (data.success) {
          if (window.showToast) showToast('Message sent to ' + data.sent + ' user(s)', 'success');
          ssyncMessageClose();
        } else {
          var errMsg = data.errors && data.errors.length > 0 ? data.errors.join('; ') : 'Some messages failed';
          if (window.showToast) showToast('Sent: ' + data.sent + ', Failed: ' + data.failed + '. ' + errMsg, 'error');
        }
      })
      .catch(function (e) {
        if (window.showToast) showToast('Failed to send: ' + e.message, 'error');
      })
      .finally(function () {
        sendBtn.disabled = false;
        sendBtn.textContent = 'Send Message';
      });
  }

  // ─── Arrow key navigation in pill tablist ────────────────────────────────────
  function ssyncInitTablistKeys() {
    var tablist = document.getElementById('ssync-tablist');
    if (!tablist) return;
    tablist.addEventListener('keydown', function (e) {
      var tabs = Array.prototype.slice.call(tablist.querySelectorAll('[role=tab]'));
      var idx = tabs.indexOf(document.activeElement);
      if (idx < 0) return;
      if (e.key === 'ArrowRight') {
        e.preventDefault();
        tabs[(idx + 1) % tabs.length].focus();
      }
      if (e.key === 'ArrowLeft') {
        e.preventDefault();
        tabs[(idx - 1 + tabs.length) % tabs.length].focus();
      }
    });
  }

  // ─── Boot ─────────────────────────────────────────────────────────────────────
  AdminUI.onReady(function () {
    ssyncInitTablistKeys();
    ssyncLoadAll();
  });

  // Expose to global for inline onclick handlers in HTML
  window.ssyncRunPull = ssyncRunPull;
  window.ssyncRunProfilePush = ssyncRunProfilePush;
  window.ssyncMessageOpen = ssyncMessageOpen;
  window.ssyncMessageClose = ssyncMessageClose;
  window.ssyncMessageSelectAll = ssyncMessageSelectAll;
  window.ssyncMessageDeselectAll = ssyncMessageDeselectAll;
  window.ssyncMessageUpdateCount = ssyncMessageUpdateCount;
  window.ssyncMessageSend = ssyncMessageSend;
  window.ssyncSetSegment = ssyncSetSegment;
  window.ssyncOnSearch = ssyncOnSearch;

})();
