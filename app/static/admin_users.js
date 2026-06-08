// admin_users.js - Member Roster
// Replaces Tabulator with a bespoke, purpose-built roster view.
// Touches ONLY: app/templates/admin/users.html + app/static/admin_users.js
// All server strings rendered via AdminUI.el (never unsafeHTML for user data).

(function () {
  'use strict';

  // ===== Module state =====
  var usersData = [];      // raw from /admin/users/data, season_status mutated per view
  var allSeasons = [];
  var allTags = [];
  var currentSeason = null;
  var currentView = 'all';
  var selectedSeasonId = null;
  var mr_effectiveSeasonName = null;

  // Filter state flags for saved-chip tracking
  var activeChip = null;   // 'active-members' | 'unlinked-slack' | 'no-roles' | null
  var extraPredicate = null; // fn(user)->bool extra filter for chips that have no select equivalent

  var mr_state = { filtered: [] };

  // Select-mode state
  var mr_selectMode = false;
  var mr_selection = new Set();

  // Drawer return-focus
  var mr_drawerReturnFocus = null;
  var mr_activeDrawerUserId = null;
  var mr_drawerApi = null;

  // Edit/tag modal return-focus
  var mr_editReturnFocus = null;
  var mr_editUserId = null;
  var mr_tagUserId = null;
  var mr_tagBulkMode = false;

  // Default fallbacks
  var DEFAULT_EMOJI = String.fromCodePoint(0x1F3F7);  // label emoji
  var DEFAULT_GRADIENT = 'linear-gradient(135deg, #868e96 0%, #adb5bd 100%)';

  // Avatar palette (6 tcsc-navy-adjacent tones)
  var AVATAR_COLORS = ['#1c2c44','#2d4263','#3a5f8a','#29476b','#1e3a5f','#243654'];

  // Tag category grouping (carry over from original)
  var TAG_CATEGORIES = {
    'Leadership': ['PRESIDENT','VICE_PRESIDENT','TREASURER','SECRETARY','AUDITOR','BOARD_MEMBER','FRIEND_OF_BOARD'],
    'Coaching': ['HEAD_COACH','ASSISTANT_COACH','PRACTICES_DIRECTOR','PRACTICES_LEAD','WAX_MANAGER'],
    'Activities': ['TRIP_LEAD','ADVENTURES','SOCIAL','SOCIAL_COMMITTEE','MARKETING','APPAREL']
  };

  // ===== Helpers =====

  function mr_avatarColor(userId) {
    return AVATAR_COLORS[userId % AVATAR_COLORS.length];
  }

  function mr_initials(user) {
    var f = (user.first_name || '').trim();
    var l = (user.last_name || '').trim();
    return ((f[0] || '') + (l[0] || '')).toUpperCase() || '?';
  }

  // Status badge variants
  function mr_statusVariant(status) {
    var map = { ACTIVE: 'success', PENDING: 'warning', ALUMNI: 'info', DROPPED: 'danger' };
    return map[status] || 'neutral';
  }

  function mr_statusText(status) {
    var map = { ACTIVE: 'Active', PENDING: 'Pending', ALUMNI: 'Alumni', DROPPED: 'Dropped' };
    return map[status] || status || '';
  }

  function mr_seasonVariant(ss) {
    var map = {
      ACTIVE: 'success',
      PENDING_LOTTERY: 'warning',
      DROPPED_LOTTERY: 'neutral',
      DROPPED_VOLUNTARY: 'neutral',
      DROPPED_CAUSE: 'danger'
    };
    return map[ss] || 'neutral';
  }

  function mr_seasonText(ss) {
    var map = {
      ACTIVE: 'Active',
      PENDING_LOTTERY: 'Lottery',
      DROPPED_LOTTERY: 'Dropped (Lottery)',
      DROPPED_VOLUNTARY: 'Dropped',
      DROPPED_CAUSE: 'Dropped (Cause)'
    };
    return map[ss] || 'Not Registered';
  }

  function mr_seasonTextShort(ss) {
    var map = { ACTIVE: 'Active', PENDING_LOTTERY: 'Lottery', DROPPED_LOTTERY: 'Dropped', DROPPED_VOLUNTARY: 'Dropped', DROPPED_CAUSE: 'Dropped' };
    return map[ss] || '';
  }

  function mr_formatCurrency(val) {
    // total_paid is already DOLLARS from the backend (already divided by 100)
    return '$' + Number(val || 0).toFixed(2);
  }

  function mr_formatDate(iso) {
    if (!iso) return null;
    try {
      var d = new Date(iso);
      if (isNaN(d.getTime())) return null;
      return d.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric', timeZone: 'America/Chicago' });
    } catch (e) {
      return null;
    }
  }

  var el = AdminUI.el;

  function mr_updateCount() {
    var n = mr_state.filtered.length;
    var txt = n + ' ' + (n === 1 ? 'member' : 'members');
    var el2 = document.getElementById('mr-count');
    if (el2) el2.textContent = txt;
  }

  // ===== Global view + filter pipeline =====

  function mr_applyGlobalView() {
    var seasonIdToUse = null;
    var title = 'Members';

    if (currentView === 'current' && currentSeason) {
      seasonIdToUse = currentSeason.id;
      title = currentSeason.name + ' Members';
    } else if (currentView === 'season' && selectedSeasonId) {
      seasonIdToUse = selectedSeasonId;
      var s = allSeasons.find(function (ss) { return ss.id === selectedSeasonId; });
      title = (s ? s.name : 'Season') + ' Members';
    } else if (currentView === 'alumni') {
      title = 'Alumni Members';
    } else if (currentView === 'waitlist') {
      title = 'Waitlist Members';
    } else {
      title = 'All Members';
    }

    var vt = document.getElementById('view-title');
    if (vt) vt.textContent = title;

    // Recompute season_status for each user from the seasons map.
    // user.seasons uses STRING keys after JSON.parse (Python dict -> JSON).
    var effId = seasonIdToUse !== null ? seasonIdToUse : (currentSeason ? currentSeason.id : null);
    var _es = (effId !== null) ? allSeasons.find(function(s){return s.id === effId;}) : null;
    mr_effectiveSeasonName = _es ? _es.name : null;
    usersData.forEach(function (user) {
      if (effId !== null && user.seasons) {
        user.season_status = user.seasons[String(effId)] || '';
      }
      // If no season context, preserve the original season_status from the API
    });
  }

  function mr_applyFilters() {
    var searchVal = (document.getElementById('mr-search').value || '').toLowerCase();
    var statusVal = document.getElementById('mr-status-filter').value;
    var seasonVal = document.getElementById('mr-season-filter').value;

    // Get selected roles from popover
    var selectedRoles = mr_getSelectedRoles();

    var filtered = usersData.filter(function (user) {
      // Global view filter
      if (currentView === 'alumni') {
        if (user.status !== 'ALUMNI') return false;
      } else if (currentView === 'waitlist') {
        var statuses = Object.values(user.seasons || {});
        var hasLottery = statuses.some(function (s) { return s === 'PENDING_LOTTERY' || s === 'DROPPED_LOTTERY'; });
        var hasActive = statuses.some(function (s) { return s === 'ACTIVE'; });
        if (!hasLottery || hasActive) return false;
      } else if (currentView === 'current' && currentSeason) {
        var cs = user.seasons && user.seasons[String(currentSeason.id)];
        if (!cs || cs === 'DROPPED_LOTTERY' || cs === 'DROPPED_VOLUNTARY' || cs === 'DROPPED_CAUSE') return false;
      } else if (currentView === 'season' && selectedSeasonId) {
        if (!user.seasons || !user.seasons[String(selectedSeasonId)]) return false;
      }

      // Text search
      if (searchVal) {
        var haystack = [
          (user.full_name || '').toLowerCase(),
          (user.email || '').toLowerCase(),
          (user.phone || '').toLowerCase(),
          (user.slack_uid || '').toLowerCase()
        ].join(' ');
        if (haystack.indexOf(searchVal) === -1) return false;
      }

      // Status filter
      if (statusVal && user.status !== statusVal) return false;

      // Season status filter
      if (seasonVal) {
        if (seasonVal === 'registered') {
          if (!user.season_status) return false;
        } else if (seasonVal === 'not_registered') {
          if (user.season_status) return false;
        } else {
          if (user.season_status !== seasonVal) return false;
        }
      }

      // Role filter (OR: user must have at least one selected role)
      if (selectedRoles.length > 0) {
        var userTagNames = (user.tags || []).map(function (t) { return t.name; });
        if (!selectedRoles.some(function (r) { return userTagNames.indexOf(r) !== -1; })) return false;
      }

      // Extra predicate (from saved-filter chips without select equivalent)
      if (extraPredicate && !extraPredicate(user)) return false;

      return true;
    });

    mr_state.filtered = filtered;
    mr_render(filtered);
    mr_updateCount();
  }

  // ===== Row builder =====

  function mr_buildRow(user) {
    // Avatar chip
    var avatarEl = el('div', {
      class: 'mr-avatar',
      'aria-hidden': 'true',
      style: 'background:' + mr_avatarColor(user.id)
    }, [mr_initials(user)]);

    // Name link
    var nameLink = el('a', {
      href: '/admin/users/' + user.id,
      class: 'mr-name',
      onclick: function (e) { e.stopPropagation(); }
    }, [user.full_name || '']);

    // Copy email button (hover, pointer devices)
    var copyEmailBtn = el('button', {
      type: 'button',
      class: 'mr-copy-email-btn',
      'aria-label': 'Copy ' + user.email,
      onclick: function (e) {
        e.stopPropagation();
        mr_copyToClipboard(user.email, 'Email copied');
      }
    }, ['Copy']);

    // Email + copy
    var emailSpan = el('span', { class: 'mr-email' }, [user.email || '']);
    var nameRow = el('div', { class: 'mr-name-row' }, [nameLink, emailSpan, copyEmailBtn]);

    // Role strip
    var roleChildren = [];
    if (user.tags && user.tags.length > 0) {
      user.tags.forEach(function (tag) {
        var emoji = tag.emoji || DEFAULT_EMOJI;
        var chip = el('span', {
          class: 'mr-role-emoji',
          role: 'img',
          'aria-label': tag.display_name || tag.name,
          'data-tooltip': tag.display_name || tag.name
        }, [emoji]);
        roleChildren.push(chip);
      });
    } else {
      roleChildren.push(el('span', { class: 'mr-no-roles' }, ['No roles']));
    }
    var rolesEl = el('div', { class: 'mr-roles', 'aria-label': 'Roles' }, roleChildren);

    // Primary zone
    var primaryEl = el('div', { class: 'mr-primary' }, [nameRow, rolesEl]);

    // Grouped status cell: member-status badge + season sub-line
    var statusBadge = AdminUI.statusBadge(mr_statusText(user.status), mr_statusVariant(user.status));
    statusBadge.setAttribute('aria-label', 'Member status: ' + mr_statusText(user.status));

    var subText = user.season_status
      ? ((mr_effectiveSeasonName ? mr_effectiveSeasonName + ' · ' : '') + mr_seasonTextShort(user.season_status))
      : 'Not registered';
    var seasonSubEl = el('span', {
      class: 'mr-status-sub',
      'aria-label': user.season_status
        ? ('Season: ' + (mr_effectiveSeasonName ? mr_effectiveSeasonName + ', ' : '') + mr_seasonTextShort(user.season_status))
        : 'Not registered in current season'
    }, [subText]);

    var statusCellEl = el('div', { class: 'mr-status-cell' }, [statusBadge, seasonSubEl]);

    // Select checkbox + edit button (actions zone)
    var selectCb = el('input', {
      type: 'checkbox',
      class: 'mr-select-cb',
      'aria-label': 'Select ' + user.full_name,
      onclick: function (e) {
        e.stopPropagation();
        mr_toggleSelect(user.id);
      }
    }, []);
    // Pre-check if already selected
    if (mr_selection.has(user.id)) selectCb.checked = true;

    var editBtn = el('button', {
      type: 'button',
      class: 'mr-edit-btn',
      'aria-label': 'Edit ' + user.full_name,
      onclick: function (e) {
        e.stopPropagation();
        mr_openEditModal(user.id, e.currentTarget);
      }
    }, ['Edit']);

    var actionsEl = el('div', { class: 'mr-actions' }, [selectCb, editBtn]);

    // Row element
    var row = el('div', {
      class: 'mr-row' + (mr_activeDrawerUserId === user.id ? ' is-active' : ''),
      role: 'listitem',
      tabindex: '0',
      dataset: { userId: String(user.id) },
      onclick: function (e) {
        if (e.target.closest('a, button')) return;
        if (mr_selectMode) {
          mr_toggleSelect(user.id);
          selectCb.checked = mr_selection.has(user.id);
        } else {
          mr_openDrawer(user, row);
        }
      },
      onkeydown: function (e) {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          if (!mr_selectMode) mr_openDrawer(user, row);
        }
      }
    }, [avatarEl, primaryEl, statusCellEl, actionsEl]);

    return row;
  }

  // ===== Render =====

  function mr_render(filtered) {
    var roster = document.getElementById('member-roster');
    var emptyState = document.getElementById('mr-empty-state');
    if (!roster) return;

    // Clear
    roster.innerHTML = '';
    roster.setAttribute('aria-busy', 'false');

    if (filtered.length === 0) {
      roster.setAttribute('aria-hidden', 'true');
      if (emptyState) emptyState.style.display = '';
      return;
    }

    roster.setAttribute('aria-hidden', 'false');
    if (emptyState) emptyState.style.display = 'none';

    // Ensure we have the select-mode class set on the roster list
    var listEl = document.getElementById('member-roster-list');
    if (!listEl) {
      listEl = el('div', { id: 'member-roster-list' }, []);
      roster.appendChild(listEl);
    } else {
      listEl.innerHTML = '';
    }

    // Apply select-mode class
    if (mr_selectMode) {
      listEl.classList.add('mr-select-mode');
    } else {
      listEl.classList.remove('mr-select-mode');
    }

    filtered.forEach(function (user) {
      listEl.appendChild(mr_buildRow(user));
    });
  }

  // Re-render a single row in place (post-tag-save)
  function mr_renderRow(user) {
    var listEl = document.getElementById('member-roster-list');
    if (!listEl) return;
    var existing = listEl.querySelector('[data-user-id="' + user.id + '"]');
    if (!existing) return;
    var newRow = mr_buildRow(user);
    existing.replaceWith(newRow);
  }

  // ===== Drawer =====

  function mr_buildDrawerContent(user) {
    var content = el('div', { class: 'mr-dw-content' }, []);

    function kv(label, valueNode) {
      var vEl;
      if (typeof valueNode === 'string' || valueNode === null || valueNode === undefined) {
        var text = valueNode;
        if (!text) {
          vEl = el('span', { class: 'mr-v mr-v--empty' }, ['-']);
        } else {
          vEl = el('span', { class: 'mr-v' }, [text]);
        }
      } else {
        // DOM node
        vEl = el('span', { class: 'mr-v' }, []);
        vEl.appendChild(valueNode);
      }
      return el('div', { class: 'mr-kv' }, [
        el('span', { class: 'mr-k' }, [label]),
        vEl
      ]);
    }

    // Block helper
    function block(title, rows, extra) {
      var hrow = el('div', { class: 'mr-dw-blk-hrow' }, [
        el('h3', { class: 'mr-dw-blk-h' }, [title])
      ]);
      if (extra) hrow.appendChild(extra);
      var blk = el('section', { class: 'mr-dw-blk' }, [hrow]);
      rows.forEach(function (r) { blk.appendChild(r); });
      return blk;
    }

    // Contact block
    var emailRowNode = el('span', { class: 'mr-v mr-email-row' }, [
      el('span', {}, [user.email || '']),
      el('button', {
        type: 'button',
        class: 'mr-copy-btn',
        'aria-label': 'Copy email address',
        onclick: function () { mr_copyToClipboard(user.email, 'Email copied'); }
      }, ['Copy'])
    ]);
    content.appendChild(block('Contact', [
      el('div', { class: 'mr-kv' }, [
        el('span', { class: 'mr-k' }, ['Email']),
        emailRowNode
      ]),
      kv('Phone', user.phone || null),
      kv('Slack ID', user.slack_uid || null)
    ]));
    content.appendChild(el('hr', { class: 'mr-dw-sep' }, []));

    // Membership block
    var statusNode = AdminUI.statusBadge(mr_statusText(user.status), mr_statusVariant(user.status));
    var ssNode = AdminUI.statusBadge(mr_seasonText(user.season_status), mr_seasonVariant(user.season_status));
    content.appendChild(block('Membership', [
      el('div', { class: 'mr-kv' }, [el('span', { class: 'mr-k' }, ['Status']), el('span', { class: 'mr-v' }, [statusNode])]),
      el('div', { class: 'mr-kv' }, [el('span', { class: 'mr-k' }, ['Season']), el('span', { class: 'mr-v' }, [ssNode])]),
      kv('Type', user.is_returning ? 'Returning' : 'New'),
      kv('Trips', String(user.trip_count !== undefined ? user.trip_count : 0)),
      kv('Total Paid', mr_formatCurrency(user.total_paid)),
      kv('Member since', mr_formatDate(user.created_at))
    ]));
    content.appendChild(el('hr', { class: 'mr-dw-sep' }, []));

    // Skiing block
    content.appendChild(block('Skiing', [
      kv('Technique', user.preferred_technique || null),
      kv('Experience', user.ski_experience || null),
      kv('T-shirt', user.tshirt_size || null),
      kv('Pronouns', user.pronouns || null),
      kv('Date of birth', mr_formatDate(user.date_of_birth))
    ]));
    content.appendChild(el('hr', { class: 'mr-dw-sep' }, []));

    // Emergency contact block
    var ecn = user.emergency_contact_name;
    var ecp = user.emergency_contact_phone;
    var ece = user.emergency_contact_email;
    var ecr = user.emergency_contact_relation;
    var ecRows;
    if (!ecn && !ecp && !ece && !ecr) {
      ecRows = [el('p', { class: 'mr-v--empty', style: 'font-size:13.5px;color:#94a3b8' }, ['No emergency contact on file'])];
    } else {
      ecRows = [
        kv('Name', ecn || null),
        kv('Phone', ecp || null),
        kv('Email', ece || null),
        kv('Relation', ecr || null)
      ];
    }
    content.appendChild(block('Emergency', ecRows));
    content.appendChild(el('hr', { class: 'mr-dw-sep' }, []));

    // Roles block
    var assignRolesBtn = el('button', {
      type: 'button',
      class: 'mr-drawer-action-sm',
      onclick: function () {
        if (mr_drawerApi) mr_drawerApi.close();
        mr_openTagModal(user.id, null, false);
      }
    }, ['Assign roles']);

    var tagChildren = [];
    if (user.tags && user.tags.length > 0) {
      user.tags.forEach(function (tag) {
        var chip = el('span', {
          class: 'mr-tag-chip',
          style: 'background:' + (tag.gradient || DEFAULT_GRADIENT)
        }, [(tag.emoji || '') + ' ' + (tag.display_name || tag.name || '')]);
        tagChildren.push(chip);
      });
    } else {
      tagChildren.push(el('span', { class: 'mr-no-roles-note' }, ['No roles assigned']));
    }
    var rolesBodyEl = el('div', { style: 'display:flex;flex-wrap:wrap;gap:4px' }, tagChildren);

    var rolesBlk = el('section', { class: 'mr-dw-blk' }, [
      el('div', { class: 'mr-dw-blk-hrow' }, [
        el('h3', { class: 'mr-dw-blk-h' }, ['Roles']),
        assignRolesBtn
      ]),
      rolesBodyEl
    ]);
    content.appendChild(rolesBlk);
    content.appendChild(el('hr', { class: 'mr-dw-sep' }, []));

    // Activity block
    var seasonCount = Object.keys(user.seasons || {}).length;
    content.appendChild(block('Activity', [
      kv('Seasons registered', String(seasonCount))
    ]));

    return content;
  }

  function mr_openDrawer(user, rowEl) {
    // Mark active row
    document.querySelectorAll('#member-roster-list .mr-row.is-active').forEach(function (r) {
      r.classList.remove('is-active');
    });
    if (rowEl) rowEl.classList.add('is-active');
    mr_activeDrawerUserId = user.id;
    mr_drawerReturnFocus = rowEl || document.activeElement;

    var content = mr_buildDrawerContent(user);

    // Footer: Edit + View full profile
    var footer = el('div', { class: 'mr-dw-footer' }, [
      el('button', {
        type: 'button',
        class: 'mr-act-primary',
        onclick: function () { if (mr_drawerApi) mr_drawerApi.close(); mr_openEditModal(user.id, null); }
      }, ['Edit']),
      el('a', {
        href: '/admin/users/' + user.id,
        class: 'mr-act-ghost',
        onclick: function () { if (mr_drawerApi) mr_drawerApi.close(); }
      }, ['View full profile'])
    ]);
    content.appendChild(footer);

    var api = AdminUI.drawer({ title: user.full_name, content: content });

    // Run cleanup on every close path (X, scrim, Esc, or programmatic api.close).
    // The foundation removes the panel from document.body on close; observe that removal.
    var drawerPanel = api.body && api.body.closest('.admin-ui-drawer');
    var drawerObserver = null;
    function mr_drawerCleanup() {
      if (drawerObserver) { drawerObserver.disconnect(); drawerObserver = null; }
      document.querySelectorAll('#member-roster-list .mr-row.is-active').forEach(function (r) {
        r.classList.remove('is-active');
      });
      mr_activeDrawerUserId = null;
      mr_drawerApi = null;
      if (mr_drawerReturnFocus && typeof mr_drawerReturnFocus.focus === 'function') {
        mr_drawerReturnFocus.focus();
        mr_drawerReturnFocus = null;
      }
    }
    if (drawerPanel) {
      drawerObserver = new MutationObserver(function () {
        if (!document.body.contains(drawerPanel)) {
          mr_drawerCleanup();
        }
      });
      drawerObserver.observe(document.body, { childList: true });
    }

    // Also wrap api.close so programmatic callers trigger cleanup synchronously
    var origClose = api.close;
    api.close = function () {
      origClose();
      mr_drawerCleanup();
    };

    mr_drawerApi = api;
  }

  // ===== Role popover =====

  function mr_getSelectedRoles() {
    var btns = document.querySelectorAll('#mr-role-grid .mr-role-toggle[aria-pressed="true"]');
    return Array.from(btns).map(function (b) { return b.dataset.role; });
  }

  function mr_updateRoleFilterLabel() {
    var selected = mr_getSelectedRoles();
    var labelEl = document.getElementById('mr-role-label');
    var btn = document.getElementById('mr-role-btn');
    if (!labelEl || !btn) return;

    if (selected.length === 0) {
      labelEl.textContent = 'Roles';
      btn.classList.remove('has-selection');
    } else {
      // Show up to 4 emojis
      var emojis = selected.slice(0, 4).map(function (name) {
        var tag = allTags.find(function (t) { return t.name === name; });
        return tag ? (tag.emoji || DEFAULT_EMOJI) : DEFAULT_EMOJI;
      }).join('');
      var extra = selected.length > 4
        ? '<span class="mr-role-count">+' + (selected.length - 4) + '</span>'
        : '';
      labelEl.innerHTML = AdminUI.escapeHtml(emojis) + extra;
      btn.classList.add('has-selection');
    }
  }

  function mr_populateRoleGrid() {
    var grid = document.getElementById('mr-role-grid');
    if (!grid || allTags.length === 0) return;
    grid.innerHTML = '';
    allTags.forEach(function (tag) {
      var emoji = tag.emoji || DEFAULT_EMOJI;
      var btn = el('button', {
        type: 'button',
        class: 'mr-role-toggle',
        'aria-pressed': 'false',
        'aria-label': tag.display_name || tag.name,
        'data-tooltip': tag.display_name || tag.name,
        dataset: { role: tag.name },
        onclick: function () {
          var pressed = btn.getAttribute('aria-pressed') === 'true';
          btn.setAttribute('aria-pressed', pressed ? 'false' : 'true');
          mr_applyFilters();
          mr_updateRoleFilterLabel();
        }
      }, [emoji]);
      grid.appendChild(btn);
    });
  }

  function mr_clearAllRoles() {
    document.querySelectorAll('#mr-role-grid .mr-role-toggle').forEach(function (b) {
      b.setAttribute('aria-pressed', 'false');
    });
    mr_applyFilters();
    mr_updateRoleFilterLabel();
  }

  // ===== Edit modal =====

  function mr_openEditModal(userId, returnFocusEl) {
    var user = usersData.find(function (u) { return u.id === userId; });
    if (!user) return;

    mr_editUserId = userId;
    mr_editReturnFocus = returnFocusEl || document.activeElement;

    // Title
    var titleEl = document.getElementById('mr-edit-modal-title');
    if (titleEl) titleEl.textContent = 'Edit: ' + user.full_name;

    // Form action
    var form = document.getElementById('mr-edit-form');
    if (form) form.action = '/admin/users/' + userId + '/edit';

    // View details link
    var vdLink = document.getElementById('mr-edit-view-link');
    if (vdLink) vdLink.href = '/admin/users/' + userId;

    // Email field
    var emailEl = document.getElementById('mr-edit-email');
    if (emailEl) emailEl.value = user.email || '';

    // Status badge (read-only)
    var statusBadgeEl = document.getElementById('mr-edit-status-badge');
    if (statusBadgeEl) {
      statusBadgeEl.innerHTML = '';
      statusBadgeEl.appendChild(AdminUI.statusBadge(mr_statusText(user.status), mr_statusVariant(user.status)));
    }

    // Tags inline checkboxes
    var tagsContainer = document.getElementById('mr-edit-tags');
    if (tagsContainer) {
      tagsContainer.innerHTML = '';
      var userTagIds = new Set((user.tags || []).map(function (t) { return t.id; }));
      allTags.forEach(function (tag) {
        var cb = el('input', {
          type: 'checkbox',
          name: 'tag_ids',
          value: String(tag.id)
        }, []);
        if (userTagIds.has(tag.id)) cb.checked = true;
        var badge = el('span', {
          class: 'mr-tag-badge-sm',
          style: 'background:' + (tag.gradient || DEFAULT_GRADIENT)
        }, [tag.display_name || tag.name]);
        var lbl = el('label', { class: 'mr-edit-tag-item' }, [cb, badge]);
        tagsContainer.appendChild(lbl);
      });
    }

    // Show modal
    var modal = document.getElementById('mr-edit-modal');
    if (modal) {
      modal.removeAttribute('hidden');
      requestAnimationFrame(function () {
        var firstInput = document.getElementById('mr-edit-email');
        if (firstInput) firstInput.focus();
      });
    }
  }

  function mr_closeEditModal() {
    var modal = document.getElementById('mr-edit-modal');
    if (modal) modal.setAttribute('hidden', '');
    mr_editUserId = null;
    if (mr_editReturnFocus && typeof mr_editReturnFocus.focus === 'function') {
      mr_editReturnFocus.focus();
    }
    mr_editReturnFocus = null;
  }

  // ===== Tag-assign modal =====

  function mr_buildTagCheckboxes(preCheckedIds, bulkMode) {
    var container = document.getElementById('mr-tag-checkboxes');
    if (!container) return;
    container.innerHTML = '';

    var userTagIdSet = new Set(preCheckedIds || []);
    var categorized = Object.keys(TAG_CATEGORIES);
    var categorizedNames = categorized.reduce(function (acc, c) { return acc.concat(TAG_CATEGORIES[c]); }, []);

    function buildCategory(label, tags) {
      if (tags.length === 0) return;
      var catDiv = el('div', { class: 'mr-tag-category' }, [
        el('div', { class: 'mr-tag-cat-label' }, [label]),
        el('div', { class: 'mr-tag-cat-items' }, tags.map(function (tag) {
          var cb = el('input', { type: 'checkbox', value: String(tag.id) }, []);
          if (!bulkMode && userTagIdSet.has(tag.id)) cb.checked = true;
          var badge = el('span', {
            class: 'mr-tag-badge-sm',
            style: 'background:' + (tag.gradient || DEFAULT_GRADIENT)
          }, [tag.display_name || tag.name]);
          return el('label', { class: 'mr-tag-cb-item' }, [cb, badge]);
        }))
      ]);
      container.appendChild(catDiv);
    }

    categorized.forEach(function (cat) {
      var catTags = allTags.filter(function (t) { return TAG_CATEGORIES[cat].indexOf(t.name) !== -1; });
      buildCategory(cat, catTags);
    });

    var otherTags = allTags.filter(function (t) { return categorizedNames.indexOf(t.name) === -1; });
    buildCategory('Other', otherTags);
  }

  function mr_openTagModal(userId, returnFocusEl, bulkMode) {
    mr_tagBulkMode = !!bulkMode;
    mr_tagUserId = bulkMode ? null : userId;
    mr_editReturnFocus = returnFocusEl || document.activeElement;

    var modal = document.getElementById('mr-tag-modal');
    var titleEl = document.getElementById('mr-tag-modal-title');
    var bulkNote = document.getElementById('mr-tag-bulk-note');

    if (bulkMode) {
      var n = mr_selection.size;
      if (titleEl) titleEl.textContent = 'Add Roles to ' + n + ' Members';
      if (bulkNote) {
        bulkNote.textContent = 'Adds selected roles to each member\'s existing roles. Does not remove any current roles.';
        bulkNote.style.display = '';
      }
      mr_buildTagCheckboxes([], true);
    } else {
      var user = usersData.find(function (u) { return u.id === userId; });
      if (!user) return;
      if (titleEl) titleEl.textContent = 'Assign Tags: ' + user.full_name;
      if (bulkNote) bulkNote.style.display = 'none';
      var preChecked = (user.tags || []).map(function (t) { return t.id; });
      mr_buildTagCheckboxes(preChecked, false);
    }

    if (modal) {
      modal.removeAttribute('hidden');
      requestAnimationFrame(function () {
        var firstCb = modal.querySelector('input[type="checkbox"]');
        if (firstCb) firstCb.focus();
      });
    }
  }

  function mr_closeTagModal() {
    var modal = document.getElementById('mr-tag-modal');
    if (modal) modal.setAttribute('hidden', '');
    mr_tagUserId = null;
    mr_tagBulkMode = false;
    if (mr_editReturnFocus && typeof mr_editReturnFocus.focus === 'function') {
      mr_editReturnFocus.focus();
    }
    mr_editReturnFocus = null;
  }

  async function mr_saveTagModal() {
    var checkboxes = document.querySelectorAll('#mr-tag-checkboxes input[type="checkbox"]:checked');
    var selectedIds = Array.from(checkboxes).map(function (cb) { return parseInt(cb.value, 10); });

    if (mr_tagBulkMode) {
      // ADD-ONLY bulk mode
      var userIds = Array.from(mr_selection);
      var n = userIds.length;
      if (n === 0) { mr_closeTagModal(); return; }

      if (window.showToast) showToast('Updating roles...', 'info');

      var successCount = 0;
      for (var i = 0; i < userIds.length; i++) {
        var uid = userIds[i];
        var user = usersData.find(function (u) { return u.id === uid; });
        if (!user) continue;
        // Merge: existing + newly selected
        var existingIds = (user.tags || []).map(function (t) { return t.id; });
        var mergedIds = Array.from(new Set(existingIds.concat(selectedIds)));
        try {
          var result = await AdminUI.mutate('/admin/users/' + uid + '/tags', { tag_ids: mergedIds });
          user.tags = result.tags || user.tags;
          successCount++;
        } catch (e) {
          console.error('Tag update failed for user', uid, e);
        }
      }

      if (window.showToast) showToast('Roles updated for ' + successCount + ' of ' + n + ' members', 'success');
      // Re-render all affected rows
      mr_applyFilters();
      mr_exitSelectMode();
      mr_closeTagModal();
    } else {
      // Single-user replace-all mode
      var userId = mr_tagUserId;
      if (!userId) return;
      try {
        var res = await AdminUI.mutate('/admin/users/' + userId + '/tags', { tag_ids: selectedIds });
        if (window.showToast) showToast('Roles updated', 'success');
        var u = usersData.find(function (x) { return x.id === userId; });
        if (u && res.tags) u.tags = res.tags;
        mr_renderRow(u);
        mr_applyFilters();
        mr_closeTagModal();
      } catch (e) {
        // AdminUI.mutate already showed an error toast
      }
    }
  }

  // ===== Select mode =====

  function mr_toggleSelect(userId) {
    if (mr_selection.has(userId)) {
      mr_selection.delete(userId);
    } else {
      mr_selection.add(userId);
    }
    mr_updateBulkBar();
  }

  function mr_updateBulkBar() {
    var n = mr_selection.size;
    var countEl = document.getElementById('mr-bulk-count');
    if (countEl) countEl.textContent = n + ' selected';

    var assignBtn = document.getElementById('mr-bulk-assign');
    var copyBtn = document.getElementById('mr-bulk-copy');
    var disabled = n === 0;
    [assignBtn, copyBtn].forEach(function (btn) {
      if (!btn) return;
      btn.disabled = disabled;
      btn.setAttribute('aria-disabled', String(disabled));
    });
  }

  function mr_exitSelectMode() {
    mr_selectMode = false;
    mr_selection.clear();
    var toggle = document.getElementById('mr-select-toggle');
    if (toggle) { toggle.textContent = 'Select'; toggle.classList.remove('is-active'); }
    var bar = document.getElementById('mr-bulk-bar');
    if (bar) bar.classList.remove('show');
    // Re-render to hide checkboxes
    mr_render(mr_state.filtered);
  }

  // ===== Saved-filter chips =====

  function mr_applyChip(chipName) {
    // Clear all chip state first
    document.querySelectorAll('.mr-qf-chip').forEach(function (c) {
      c.setAttribute('aria-pressed', 'false');
      c.classList.remove('mr-qf-chip--on');
    });
    extraPredicate = null;

    if (activeChip === chipName) {
      // Toggle off - reset all filter controls that the chip had set
      activeChip = null;
      mr_setPillActive('all');
      currentView = 'all';
      // Reset status filter if chip had set it
      var statusFilterEl = document.getElementById('mr-status-filter');
      if (statusFilterEl) statusFilterEl.value = '';
      mr_applyGlobalView();
      mr_applyFilters();
      return;
    }

    activeChip = chipName;
    var chip = document.querySelector('.mr-qf-chip[data-chip="' + chipName + '"]');
    if (chip) { chip.setAttribute('aria-pressed', 'true'); chip.classList.add('mr-qf-chip--on'); }

    if (chipName === 'active-members') {
      mr_setPillActive('current');
      currentView = 'current';
      document.getElementById('mr-status-filter').value = 'ACTIVE';
      extraPredicate = null;
    } else if (chipName === 'unlinked-slack') {
      mr_setPillActive('all');
      currentView = 'all';
      extraPredicate = function (u) { return !u.slack_uid; };
    } else if (chipName === 'no-roles') {
      mr_setPillActive('all');
      currentView = 'all';
      extraPredicate = function (u) { return !u.tags || u.tags.length === 0; };
    }

    mr_applyGlobalView();
    mr_applyFilters();
  }

  function mr_setPillActive(view) {
    document.querySelectorAll('.mr-pill').forEach(function (p) {
      var isActive = p.dataset.view === view;
      p.setAttribute('aria-pressed', String(isActive));
      p.classList.toggle('is-active', isActive);
    });
    // Clear season select
    var seasonSel = document.getElementById('mr-season-select');
    if (seasonSel) seasonSel.value = '';
    selectedSeasonId = null;
  }

  // ===== CSV export =====

  function mr_exportCsv() {
    var rows = mr_state.filtered;
    var headers = [
      'Name', 'Email', 'Status', 'Season Status', 'Type', 'Trips', 'Total Paid',
      'Phone', 'Slack UID', 'Pronouns', 'DOB', 'Technique', 'T-Shirt', 'Experience',
      'Emergency Name', 'Emergency Phone', 'Emergency Email', 'Emergency Relation', 'Roles'
    ];

    function csvCell(val) {
      var s = val === null || val === undefined ? '' : String(val);
      if (s.indexOf(',') !== -1 || s.indexOf('"') !== -1 || s.indexOf('\n') !== -1) {
        return '"' + s.replace(/"/g, '""') + '"';
      }
      return s;
    }

    var lines = [headers.map(csvCell).join(',')];
    rows.forEach(function (user) {
      var roleNames = (user.tags || []).map(function (t) { return t.display_name || t.name; }).join('; ');
      var line = [
        user.full_name,
        user.email,
        user.status,
        user.season_status || '',
        user.is_returning ? 'Returning' : 'New',
        user.trip_count !== undefined ? user.trip_count : 0,
        Number(user.total_paid || 0).toFixed(2),
        user.phone || '',
        user.slack_uid || '',
        user.pronouns || '',
        user.date_of_birth || '',
        user.preferred_technique || '',
        user.tshirt_size || '',
        user.ski_experience || '',
        user.emergency_contact_name || '',
        user.emergency_contact_phone || '',
        user.emergency_contact_email || '',
        user.emergency_contact_relation || '',
        roleNames
      ].map(csvCell).join(',');
      lines.push(line);
    });

    var blob = new Blob([lines.join('\r\n')], { type: 'text/csv' });
    var url = URL.createObjectURL(blob);
    var a = document.createElement('a');
    a.href = url;
    a.download = 'tcsc_members.csv';
    a.click();
    URL.revokeObjectURL(url);
  }

  // ===== Clipboard helper =====

  function mr_copyToClipboard(text, toastMsg) {
    if (!text) return;
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(function () {
        if (window.showToast) showToast(toastMsg || 'Copied', 'success');
      }).catch(function () {
        if (window.showToast) showToast('Copy failed', 'error');
      });
    } else {
      if (window.showToast) showToast('Copy not supported in this browser', 'error');
    }
  }

  // ===== Edit form submit handler =====

  function mr_attachEditFormSubmit() {
    var form = document.getElementById('mr-edit-form');
    if (!form) return;
    form.addEventListener('submit', async function (e) {
      e.preventDefault();
      if (!mr_editUserId) { form.submit(); return; }

      var checkboxes = form.querySelectorAll('input[name="tag_ids"]:checked');
      var tagIds = Array.from(checkboxes).map(function (cb) { return parseInt(cb.value, 10); });

      try {
        var result = await AdminUI.mutate('/admin/users/' + mr_editUserId + '/tags', { tag_ids: tagIds });
        if (window.showToast) showToast('Roles updated', 'success');
        var user = usersData.find(function (u) { return u.id === mr_editUserId; });
        if (user && result.tags) user.tags = result.tags;
      } catch (e2) {
        // AdminUI.mutate already showed an error toast; do NOT proceed with form submit
        return;
      }

      // Disable checkboxes to prevent re-submission
      checkboxes.forEach(function (cb) { cb.disabled = true; });
      form.submit();
    });
  }

  // ===== Populate season dropdown =====

  function mr_populateSeasonDropdown() {
    var sel = document.getElementById('mr-season-select');
    if (!sel) return;
    allSeasons.forEach(function (season) {
      var opt = document.createElement('option');
      opt.value = String(season.id);
      opt.textContent = season.name;
      sel.appendChild(opt);
    });
  }

  // ===== Init =====

  AdminUI.onReady(function () {
    // Wire edit modal close handlers
    var editCloseBtn = document.getElementById('mr-edit-close');
    var editCancelBtn = document.getElementById('mr-edit-cancel');
    [editCloseBtn, editCancelBtn].forEach(function (btn) {
      if (btn) btn.addEventListener('click', mr_closeEditModal);
    });

    // Wire tag modal close handlers
    var tagCloseBtn = document.getElementById('mr-tag-close');
    var tagCancelBtn = document.getElementById('mr-tag-cancel');
    [tagCloseBtn, tagCancelBtn].forEach(function (btn) {
      if (btn) btn.addEventListener('click', mr_closeTagModal);
    });

    // Wire tag modal save
    var tagSaveBtn = document.getElementById('mr-tag-save');
    if (tagSaveBtn) tagSaveBtn.addEventListener('click', mr_saveTagModal);

    // Edit form submit
    mr_attachEditFormSubmit();

    // Esc key closes modals (drawer handled by foundation)
    document.addEventListener('keydown', function (e) {
      if (e.key !== 'Escape') return;
      var editModal = document.getElementById('mr-edit-modal');
      if (editModal && !editModal.hasAttribute('hidden')) {
        mr_closeEditModal();
        return;
      }
      var tagModal = document.getElementById('mr-tag-modal');
      if (tagModal && !tagModal.hasAttribute('hidden')) {
        mr_closeTagModal();
        return;
      }
    });

    // Role popover toggle
    var roleBtn = document.getElementById('mr-role-btn');
    var roleMenu = document.getElementById('mr-role-menu');
    if (roleBtn && roleMenu) {
      roleBtn.addEventListener('click', function (e) {
        e.stopPropagation();
        var isOpen = roleMenu.classList.toggle('show');
        roleBtn.setAttribute('aria-expanded', String(isOpen));
        if (isOpen) {
          var first = roleMenu.querySelector('.mr-role-toggle');
          if (first) requestAnimationFrame(function () { first.focus(); });
        }
      });

      // Close popover on outside click
      document.addEventListener('click', function (e) {
        var dropdown = document.getElementById('mr-role-dropdown');
        if (dropdown && !dropdown.contains(e.target)) {
          roleMenu.classList.remove('show');
          roleBtn.setAttribute('aria-expanded', 'false');
        }
      });

      // Esc closes popover
      roleMenu.addEventListener('keydown', function (e) {
        if (e.key === 'Escape') {
          roleMenu.classList.remove('show');
          roleBtn.setAttribute('aria-expanded', 'false');
          roleBtn.focus();
        }
      });
    }

    // Role clear all
    var roleClear = document.getElementById('mr-role-clear');
    if (roleClear) roleClear.addEventListener('click', mr_clearAllRoles);

    // View pills
    document.querySelectorAll('.mr-pill').forEach(function (btn) {
      btn.addEventListener('click', function () {
        mr_setPillActive(btn.dataset.view);
        currentView = btn.dataset.view;
        selectedSeasonId = null;
        activeChip = null;
        document.querySelectorAll('.mr-qf-chip').forEach(function (c) {
          c.setAttribute('aria-pressed', 'false');
          c.classList.remove('mr-qf-chip--on');
        });
        extraPredicate = null;
        mr_applyGlobalView();
        mr_applyFilters();
      });
    });

    // Season select
    var seasonSel = document.getElementById('mr-season-select');
    if (seasonSel) {
      seasonSel.addEventListener('change', function () {
        var val = seasonSel.value;
        if (val) {
          document.querySelectorAll('.mr-pill').forEach(function (p) {
            p.setAttribute('aria-pressed', 'false');
            p.classList.remove('is-active');
          });
          selectedSeasonId = parseInt(val, 10);
          currentView = 'season';
          activeChip = null;
          document.querySelectorAll('.mr-qf-chip').forEach(function (c) {
            c.setAttribute('aria-pressed', 'false');
            c.classList.remove('mr-qf-chip--on');
          });
          extraPredicate = null;
          mr_applyGlobalView();
          mr_applyFilters();
        }
      });
    }

    // Status + season-status filters
    var statusFilter = document.getElementById('mr-status-filter');
    var seasonFilter = document.getElementById('mr-season-filter');
    [statusFilter, seasonFilter].forEach(function (sel) {
      if (sel) sel.addEventListener('change', function () {
        activeChip = null;
        document.querySelectorAll('.mr-qf-chip').forEach(function (c) {
          c.setAttribute('aria-pressed', 'false');
          c.classList.remove('mr-qf-chip--on');
        });
        extraPredicate = null;
        mr_applyFilters();
      });
    });

    // Search
    var searchEl = document.getElementById('mr-search');
    if (searchEl) searchEl.addEventListener('input', mr_applyFilters);

    // Quick-filter chips
    document.querySelectorAll('.mr-qf-chip').forEach(function (chip) {
      chip.addEventListener('click', function () {
        mr_applyChip(chip.dataset.chip);
      });
    });

    // Select mode toggle
    var selectToggle = document.getElementById('mr-select-toggle');
    if (selectToggle) {
      selectToggle.addEventListener('click', function () {
        if (mr_selectMode) {
          mr_exitSelectMode();
        } else {
          mr_selectMode = true;
          selectToggle.textContent = 'Done';
          selectToggle.classList.add('is-active');
          var bar = document.getElementById('mr-bulk-bar');
          if (bar) bar.classList.add('show');
          mr_updateBulkBar();
          mr_render(mr_state.filtered);
        }
      });
    }

    // Bulk bar actions
    var bulkAssign = document.getElementById('mr-bulk-assign');
    if (bulkAssign) {
      bulkAssign.addEventListener('click', function () {
        if (mr_selection.size === 0) return;
        mr_openTagModal(null, bulkAssign, true);
      });
    }

    var bulkCopy = document.getElementById('mr-bulk-copy');
    if (bulkCopy) {
      bulkCopy.addEventListener('click', function () {
        var emails = Array.from(mr_selection).map(function (uid) {
          var u = usersData.find(function (x) { return x.id === uid; });
          return u ? u.email : null;
        }).filter(Boolean);
        mr_copyToClipboard(emails.join(', '), emails.length + ' emails copied');
      });
    }

    var bulkClear = document.getElementById('mr-bulk-clear');
    if (bulkClear) {
      bulkClear.addEventListener('click', function () {
        mr_selection.clear();
        mr_updateBulkBar();
        // Uncheck all visible checkboxes
        document.querySelectorAll('.mr-select-cb').forEach(function (cb) { cb.checked = false; });
      });
    }

    // CSV export
    var exportBtn = document.getElementById('mr-export-csv');
    if (exportBtn) exportBtn.addEventListener('click', mr_exportCsv);

    // Load data
    AdminUI.fetchJSON('/admin/users/data').then(function (data) {
      usersData = data.users || [];
      allSeasons = data.seasons || [];
      allTags = data.tags || [];
      currentSeason = data.current_season || null;

      // Sort alphabetically by last_name, then first_name
      usersData.sort(function (a, b) {
        var ka = ((a.last_name || '') + (a.first_name || '')).toLowerCase();
        var kb = ((b.last_name || '') + (b.first_name || '')).toLowerCase();
        return ka < kb ? -1 : ka > kb ? 1 : 0;
      });

      // Populate season dropdown
      mr_populateSeasonDropdown();

      // Populate role grid
      mr_populateRoleGrid();

      // Initial view (all members, current-season context)
      mr_applyGlobalView();
      mr_applyFilters();

    }).catch(function (err) {
      console.error('Failed to load members:', err);
      var roster = document.getElementById('member-roster');
      if (roster) {
        roster.innerHTML = '';
        roster.setAttribute('aria-busy', 'false');
        var errMsg = el('p', { class: 'mr-error' }, ['Failed to load members. ']);
        var retryBtn = el('button', {
          type: 'button',
          class: 'mr-retry',
          onclick: function () { location.reload(); }
        }, ['Try again']);
        errMsg.appendChild(retryBtn);
        roster.appendChild(errMsg);
      }
    });
  });

})();
