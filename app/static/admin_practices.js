/* Practice list page: agenda render + preview drawer.
   Renders from GET /admin/practices/data; drawer lazy-loads RSVP + (gated) Skipper. */

let practicesData = [];
let locationsData = [];
let pastExpanded = false;
let pastLimit = 20;
let lastFocusedEl = null;
let currentDrawerId = null;

const STATUS_LABEL = {
  scheduled: 'Scheduled', confirmed: 'Confirmed', in_progress: 'In Progress',
  cancelled: 'Cancelled', completed: 'Completed'
};

document.addEventListener('DOMContentLoaded', async () => {
  // This file is also loaded on the practice create/edit form (for the
  // lead-candidates picker below), which has none of the list-page DOM.
  if (!document.getElementById('pl-list')) return;
  await Promise.all([loadPractices(), loadLocations()]);
  populateLocationFilter();
  attachEventListeners();
  render();
});

async function loadPractices() {
  try {
    const r = await fetch('/admin/practices/data');
    if (!r.ok) throw new Error('HTTP ' + r.status);
    practicesData = (await r.json()).practices || [];
  } catch (e) { console.error(e); showToast('Failed to load practices', 'error'); }
}

async function loadLocations() {
  try {
    const r = await fetch('/admin/practices/locations/data');
    if (!r.ok) throw new Error('HTTP ' + r.status);
    locationsData = (await r.json()).locations || [];
  } catch (e) { console.error(e); }
}

function populateLocationFilter() {
  const sel = document.getElementById('pl-location-filter');
  for (const loc of locationsData) {
    const o = document.createElement('option');
    o.value = loc.id;
    o.textContent = loc.spot ? `${loc.name} — ${loc.spot}` : loc.name;
    sel.appendChild(o);
  }
}

/* ---------- date helpers (Central, date-string based) ---------- */
function ymd(iso) { return (iso || '').slice(0, 10); }
function chicagoTodayYMD() {
  return new Intl.DateTimeFormat('en-CA', { timeZone: 'America/Chicago',
    year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date());
}
function addDaysYMD(s, n) {
  const d = new Date(s + 'T12:00:00Z'); d.setUTCDate(d.getUTCDate() + n);
  return d.toISOString().slice(0, 10);
}

/* ---------- escaping ---------- */
function esc(s) {
  return String(s == null ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

/* ---------- filtering ---------- */
function personNames(p) {
  return [].concat(p.coaches || [], p.leads || [], p.assists || [])
    .map(x => (x.name || '').toLowerCase());
}
function matchesFilters(p) {
  const q = document.getElementById('pl-search').value.toLowerCase().trim();
  const status = document.getElementById('pl-status-filter').value;
  const loc = document.getElementById('pl-location-filter').value;
  if (status && p.status !== status) return false;
  if (loc && String(p.location_id) !== String(loc)) return false;
  if (!q) return true;
  const hay = [p.location_name || '', ...(p.activities || []), ...(p.practice_types || []),
    ...personNames(p)].join(' ').toLowerCase();
  return hay.includes(q);
}

/* ---------- rendering ---------- */
function render() {
  const root = document.getElementById('pl-list');
  const today = chicagoTodayYMD();
  const weekEnd = addDaysYMD(today, 7);
  const rows = practicesData.filter(matchesFilters);

  const todayL = [], weekL = [], laterL = [], pastL = [];
  for (const p of rows) {
    const d = ymd(p.date);
    if (d < today) pastL.push(p);
    else if (d === today) todayL.push(p);
    else if (d <= weekEnd) weekL.push(p);
    else laterL.push(p);
  }
  const byDateAsc = (a, b) => new Date(a.date) - new Date(b.date);
  todayL.sort(byDateAsc); weekL.sort(byDateAsc); laterL.sort(byDateAsc);
  pastL.sort((a, b) => new Date(b.date) - new Date(a.date));

  let html = '';
  html += section('Today', todayL, true);
  html += section('This week', weekL, false);
  html += section('Later', laterL, false);

  if (pastL.length) {
    html += `<button type="button" class="pl-past-toggle" id="pl-past-toggle" aria-expanded="${pastExpanded}">`
      + `<span class="chev" aria-hidden="true">▸</span> Past practices <span class="dim">— ${pastL.length}</span></button>`;
    if (pastExpanded) {
      const shown = pastL.slice(0, pastLimit);
      let pastHtml = dayGroups(shown, false);
      if (pastL.length > pastLimit) pastHtml += `<button type="button" class="pl-loadmore" id="pl-loadmore">Load more</button>`;
      html += `<div class="pl-past-list">${pastHtml}</div>`;
    }
  }

  if (!rows.length) html = '<p class="pl-empty">No practices match your filters.</p>';
  root.innerHTML = html;
}

function section(title, list, isToday) {
  if (!list.length) return '';
  return `<div class="pl-sec${isToday ? ' today' : ''}">${esc(title)}<span class="ln"></span>`
    + `<span class="ct">${list.length}</span></div>` + dayGroups(list, isToday);
}

function dayGroups(list, isToday) {
  // group consecutive items by their date (list already sorted)
  const groups = [];
  for (const p of list) {
    const key = ymd(p.date);
    const g = groups.length && groups[groups.length - 1].key === key ? groups[groups.length - 1] : null;
    if (g) g.items.push(p); else groups.push({ key, items: [p] });
  }
  return groups.map(g => {
    const d = new Date(g.items[0].date);
    const dow = d.toLocaleDateString([], { weekday: 'short' });
    const dn = d.toLocaleDateString([], { day: 'numeric' });
    const mo = d.toLocaleDateString([], { month: 'short' });
    const block = `<div class="pl-db${isToday ? ' is-today' : ''}"><span class="dow">${dow}</span>`
      + `<span class="dn">${dn}</span><span class="mo">${mo}</span></div>`;
    return `<div class="pl-day">${block}<div class="pl-rows">${g.items.map(p => rowHtml(p, isToday)).join('')}</div></div>`;
  }).join('');
}

function peopleLine(p) {
  const names = arr => (arr || [])
    .map(x => `<span class="pl-people-nm">${esc(x.name || 'Unknown')}${x.confirmed ? ' ✓' : ''}</span>`)
    .join(', ');
  const coaches = p.coaches || [], leads = p.leads || [];
  if (!coaches.length && !leads.length) return '<div class="pl-people warn">Needs leads</div>';
  const parts = [];
  if (coaches.length) parts.push(`<span class="pl-people-grp"><span class="pl-people-lbl">${coaches.length > 1 ? 'Coaches' : 'Coach'}</span> ${names(coaches)}</span>`);
  if (leads.length) parts.push(`<span class="pl-people-grp"><span class="pl-people-lbl">${leads.length > 1 ? 'Leads' : 'Lead'}</span> ${names(leads)}</span>`);
  return `<div class="pl-people">${parts.join('<span class="pl-people-sep" aria-hidden="true">·</span>')}</div>`;
}

function rowHtml(p, isToday) {
  const time = new Date(p.date).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
  const pills = [...(p.activities || []), ...(p.practice_types || [])]
    .map(n => `<span class="pl-pill">${esc(n)}</span>`).join('');
  let inds = '';
  if (p.has_social) inds += '<span class="pl-ind"><span aria-hidden="true">🍺</span> Social</span>';
  if (p.is_dark_practice) inds += '<span class="pl-ind"><span aria-hidden="true">🔦</span> Dark</span>';
  const st = p.status || 'scheduled';
  const status = `<span class="pl-status is-${esc(st)}">${esc(STATUS_LABEL[st] || st)}</span>`;
  const flag = isToday ? '<span class="pl-today-flag">Today</span>' : '';
  // A draft looks like any other practice in this list but no member can see
  // it, so it is badged on the row itself — a director reading the week needs
  // to know which of these are actually live without cross-checking anything.
  const missing = (p.missing_details || []);
  const draftBadge = p.is_draft
    ? `<span class="pl-draft">Draft${missing.length ? ` · needs ${esc(missing.join(', '))}` : ''}</span>`
    : '';
  return `<button type="button" class="pl-row${isToday ? ' today' : ''}${p.is_draft ? ' pl-row-draft' : ''}" data-id="${p.id}" `
    + `aria-label="${esc(p.location_name || 'Practice')} ${esc(time)}, ${esc(STATUS_LABEL[st] || st)}${p.is_draft ? ', draft, not visible to members' : ''}">`
    + `<div class="pl-row-main"><div class="pl-row-top"><span class="pl-loc">${esc(p.location_name || 'No Location')}</span>`
    + `<span class="pl-time">${esc(time)}</span>${flag}</div>`
    + `<div class="pl-meta">${pills}${inds}</div>`
    + peopleLine(p)
    + `</div>`
    + `<div class="pl-row-aside">${status}${draftBadge}</div></button>`;
}

/* ---------- drafts → published ----------

   Blocks are normally published from the availability poll that collected
   leads for them (POST /admin/availability/polls/<id>/publish), which is the
   batch a director actually thinks in. There is no week-level or list-level
   publish here on purpose: the Sunday evening flow already puts the coming
   week in front of members with nobody clicking anything.

   What lives here is the single-practice escape hatch, in the drawer. A draft
   whose block never got a poll has no other route to being published, and an
   unpublishable practice is the exact failure this whole feature exists to
   prevent. */

function draftPublishHtml(p) {
  if (!p.is_draft) return '';
  const missing = (p.missing_details || []);
  if (missing.length) {
    return `<div class="pl-draft-note">Draft — members can't see this yet; `
      + `needs ${esc(missing.join(', '))}.</div>`;
  }
  return `<div class="pl-draft-note">Draft — members can't see this yet. `
    + `Normally published with its availability block.`
    + `<button type="button" class="pl-act pl-act-ghost" id="pl-publish-one" `
    + `style="margin-top:9px">Publish this practice</button></div>`;
}

async function publishOnePractice(id) {
  const btn = document.getElementById('pl-publish-one');
  if (btn) { btn.disabled = true; btn.textContent = 'Publishing…'; }

  try {
    const r = await fetch('/admin/practices/publish', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ practice_ids: [id] }),
    });
    const body = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(body.error || ('HTTP ' + r.status));

    if ((body.published || []).length) {
      showToast('Practice published — members can see it now', 'success');
    } else {
      const skipped = (body.skipped || [])[0];
      showToast(
        skipped ? `Still needs ${skipped.missing.join(', ')}`
                : 'Practice was already published',
        skipped ? 'warning' : 'info');
    }

    await loadPractices();
    render();
    const fresh = findPractice(id);
    if (fresh && currentDrawerId === id) populateDrawer(fresh);
  } catch (e) {
    console.error(e);
    showToast(e.message || 'Failed to publish practice', 'error');
    if (btn) { btn.disabled = false; btn.textContent = 'Publish this practice'; }
  }
}

/* ---------- events ---------- */
function attachEventListeners() {
  document.getElementById('pl-search').addEventListener('input', render);
  document.getElementById('pl-status-filter').addEventListener('change', render);
  document.getElementById('pl-location-filter').addEventListener('change', render);

  document.getElementById('pl-list').addEventListener('click', (e) => {
    const row = e.target.closest('.pl-row');
    if (row) { openDrawer(parseInt(row.dataset.id), row); return; }
    if (e.target.closest('#pl-past-toggle')) { pastExpanded = !pastExpanded; pastLimit = 20; render(); return; }
    if (e.target.closest('#pl-loadmore')) { pastLimit += 20; render(); return; }
  });

  document.getElementById('pl-close').addEventListener('click', closeDrawer);
  document.getElementById('pl-scrim').addEventListener('click', closeDrawer);
  document.getElementById('pl-cancel-btn').addEventListener('click', () => { if (currentDrawerId) openCancelModal(currentDrawerId); });
  document.getElementById('pl-delete-btn').addEventListener('click', () => { if (currentDrawerId) deletePractice(currentDrawerId); });
  document.getElementById('pl-poll-btn').addEventListener('click', openAvailabilityPoll);

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      if (!document.getElementById('pl-drawer').classList.contains('hidden')) { closeDrawer(); return; }
      closeCancelModal();
    }
    if (e.key === 'Tab' && !document.getElementById('pl-drawer').classList.contains('hidden')) trapTab(e);
  });
}

/* ---------- drawer ---------- */
function findPractice(id) { return practicesData.find(p => p.id === id); }

function openDrawer(id, triggerEl) {
  const p = findPractice(id);
  if (!p) return;
  currentDrawerId = id;
  lastFocusedEl = triggerEl || document.activeElement;

  document.querySelectorAll('.pl-row.is-active').forEach(r => r.classList.remove('is-active'));
  if (triggerEl) triggerEl.classList.add('is-active');

  populateDrawer(p);

  const scrim = document.getElementById('pl-scrim'), drawer = document.getElementById('pl-drawer');
  scrim.classList.remove('hidden');
  drawer.classList.remove('hidden');
  drawer.removeAttribute('hidden');
  ['.pl-head', '.pl-toolbar'].forEach(s => { const el = document.querySelector(s); if (el) el.inert = true; });
  document.getElementById('pl-list').inert = true;
  document.getElementById('pl-close').focus();

  loadDrawerRSVPs(id);
}

function closeDrawer() {
  const scrim = document.getElementById('pl-scrim'), drawer = document.getElementById('pl-drawer');
  scrim.classList.add('hidden');
  drawer.classList.add('hidden');
  drawer.setAttribute('hidden', '');
  document.querySelectorAll('.pl-row.is-active').forEach(r => r.classList.remove('is-active'));
  ['.pl-head', '.pl-toolbar'].forEach(s => { const el = document.querySelector(s); if (el) el.inert = false; });
  const plList = document.getElementById('pl-list'); if (plList) plList.inert = false;
  if (lastFocusedEl && document.contains(lastFocusedEl)) lastFocusedEl.focus();
  currentDrawerId = null;
}

function populateDrawer(p) {
  const d = new Date(p.date);
  document.getElementById('pl-dw-title').textContent = p.location_name || 'No Location';
  document.getElementById('pl-dw-sub').textContent =
    d.toLocaleString([], { weekday: 'long', month: 'long', day: 'numeric', hour: 'numeric', minute: '2-digit' });

  const st = p.status || 'scheduled';
  let badges = `<span class="pl-status is-${esc(st)}">${esc(STATUS_LABEL[st] || st)}</span>`;
  if (p.is_dark_practice) badges += '<span class="pl-pill"><span aria-hidden="true">🔦</span>&nbsp;Dark</span>';
  badges += '<span id="pl-skipper-slot" aria-live="polite"></span>';
  document.getElementById('pl-badges').innerHTML = badges;

  document.getElementById('pl-dwbody').innerHTML = draftPublishHtml(p) + drawerBody(p);

  const publishOne = document.getElementById('pl-publish-one');
  if (publishOne) {
    publishOne.addEventListener('click', () => publishOnePractice(p.id));
  }

  const edit = document.getElementById('pl-edit');
  edit.setAttribute('href', '/admin/practices/' + p.id);

  // Skipper gated to today/tomorrow
  const today = chicagoTodayYMD();
  const isSoon = ymd(p.date) === today || ymd(p.date) === addDaysYMD(today, 1);
  const slot = document.getElementById('pl-skipper-slot');
  if (isSoon) {
    slot.innerHTML = `<button type="button" class="pl-skipper-btn" id="pl-skipper-btn">Load Skipper evaluation</button>`;
    document.getElementById('pl-skipper-btn').addEventListener('click', () => loadDrawerEvaluation(p.id));
  } else {
    slot.innerHTML = '';
  }
}

function drawerBody(p) {
  const social = p.social_location_name ? esc(p.social_location_name) : 'None';
  const wo = (label, text, main) => {
    const t = (text && text.trim()) ? esc(text) : '—';
    return `<div class="pl-wblk${main ? ' main' : ''}"><div class="wl">${label}</div><div class="wt">${t}</div></div>`;
  };
  const pills = [...(p.activities || []), ...(p.practice_types || [])]
    .map(n => `<span class="pl-pill">${esc(n)}</span>`).join('') || '<span class="pl-muted">None</span>';
  const people = [].concat(
    (p.coaches || []).map(x => ['Coach', x]),
    (p.leads || []).map(x => ['Lead', x]),
    (p.assists || []).map(x => ['Assist', x])
  );
  const peopleHtml = people.length ? people.map(([role, x]) =>
    `<div class="pl-person"><span class="role">${role}</span><span class="pn">${esc(x.name || 'Unknown')}</span>`
    + `<span class="pl-conf ${x.confirmed ? 'yes' : 'no'}">${x.confirmed ? 'Confirmed' : 'Pending'}</span></div>`
  ).join('') : '<span class="pl-muted">No one assigned</span>';

  return `
    <div class="pl-blk"><div class="pl-blk-h">When &amp; Where</div>
      <div class="pl-kv"><span class="k">Location</span><span class="v">${esc(p.location_name || 'No Location')}</span></div>
      <div class="pl-kv"><span class="k">Social</span><span class="v">${social}</span></div>
    </div>
    <div class="pl-blk"><div class="pl-blk-h">Activity &amp; Type</div><div class="pl-pills">${pills}</div></div>
    <div class="pl-blk"><div class="pl-blk-h">Workout Plan</div>
      ${wo('Workout', p.workout_description, true)}
      ${wo('Notes / Logistics', p.logistics_notes, false)}
    </div>
    <div class="pl-blk"><div class="pl-blk-h">Coaches · Leads · Assists</div>${peopleHtml}</div>
    <div class="pl-blk"><div class="pl-blk-h">RSVPs</div>
      <div id="pl-rsvp" aria-live="polite"><span class="pl-muted">Loading…</span></div>
    </div>`;
}

async function loadDrawerRSVPs(id) {
  try {
    const { summary } = await fetch(`/admin/practices/${id}/rsvps`).then(r => r.json());
    const el = document.getElementById('pl-rsvp');
    if (!el || currentDrawerId !== id) return;
    el.innerHTML = `<div class="pl-rsvp">`
      + `<div class="pl-rcell"><span class="n">${summary.going}</span><span class="l">Going</span></div>`
      + `<div class="pl-rcell"><span class="n">${summary.maybe}</span><span class="l">Maybe</span></div>`
      + `<div class="pl-rcell"><span class="n">${summary.not_going}</span><span class="l">Out</span></div></div>`;
  } catch (e) {
    const el = document.getElementById('pl-rsvp');
    if (el) el.innerHTML = '<span class="pl-muted">Could not load RSVPs</span>';
  }
}

async function loadDrawerEvaluation(id) {
  const btn = document.getElementById('pl-skipper-btn');
  if (btn) btn.textContent = 'Checking…';
  try {
    const data = await fetch(`/admin/practices/${id}/evaluation`).then(r => r.json());
    const slot = document.getElementById('pl-skipper-slot');
    if (!slot || currentDrawerId !== id) return;
    if (!data.success) { slot.innerHTML = `<span class="pl-muted">${esc(data.error || 'No evaluation')}</span>`; return; }
    const ev = data.evaluation;
    slot.innerHTML = `<span class="pl-go ${ev.is_go ? '' : 'nogo'}">${ev.is_go ? 'GO' : 'NO-GO'} `
      + `· ${Math.round((ev.confidence || 0) * 100)}%</span>`;
  } catch (e) {
    const slot = document.getElementById('pl-skipper-slot');
    if (slot) slot.innerHTML = '<span class="pl-muted">Check failed</span>';
  }
}

function trapTab(e) {
  const drawer = document.getElementById('pl-drawer');
  const f = drawer.querySelectorAll('a[href], button:not([disabled]), input, select, textarea, [tabindex]:not([tabindex="-1"])');
  if (!f.length) return;
  const first = f[0], last = f[f.length - 1];
  if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
  else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
}

/* ---------- cancel modal + delete (kept) ---------- */
let currentCancelPracticeId = null;

function openCancelModal(id) {
  currentCancelPracticeId = id;
  document.getElementById('cancel-reason').value = '';
  document.getElementById('cancel-modal').style.display = 'flex';
}
function closeCancelModal() {
  document.getElementById('cancel-modal').style.display = 'none';
  currentCancelPracticeId = null;
}
async function confirmCancel() {
  const reason = document.getElementById('cancel-reason').value.trim();
  if (!reason) { showToast('Please provide a cancellation reason', 'error'); return; }
  try {
    const result = await fetch(`/admin/practices/${currentCancelPracticeId}/cancel`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ reason })
    }).then(r => r.json());
    if (result.success) {
      showToast(result.message, 'success');
      closeCancelModal(); closeDrawer();
      await loadPractices(); render();
    } else { showToast(result.error || 'Failed to cancel practice', 'error'); }
  } catch (e) { showToast('Failed to cancel practice', 'error'); }
}
async function deletePractice(id) {
  if (!confirm('Are you sure you want to delete this practice? This cannot be undone.')) return;
  try {
    const result = await fetch(`/admin/practices/${id}/delete`, { method: 'POST' }).then(r => r.json());
    if (result.success) {
      showToast(result.message, 'success');
      closeDrawer();
      await loadPractices(); render();
    } else { showToast(result.error || 'Failed to delete practice', 'error'); }
  } catch (e) { showToast('Failed to delete practice', 'error'); }
}

/* ---------- lead availability poll trigger ---------- */
// Friendly names for the only two channels a poll can ever target -- see
// app/practices/availability.py's _target_channel(). Falls back to the raw
// id below for anything unrecognized rather than guessing a name.
const AVAILABILITY_CHANNEL_NAMES = {
  'C02J4DGCFL2': '#coord-practices-leads-assists (the live, 64-member channel)',
  'C0B3Y71PG92': '#collab-asset-mgmt-practices (shadow test channel)',
};

function describeAvailabilityChannel(channelId, isShadow) {
  const known = AVAILABILITY_CHANNEL_NAMES[channelId];
  if (known) return known;
  return isShadow ? `${channelId} (shadow)` : `${channelId} (live)`;
}

async function openAvailabilityPoll() {
  const startsOn = document.getElementById('pl-poll-start').value;
  const endsOn = document.getElementById('pl-poll-end').value;
  if (!startsOn || !endsOn) { showToast('Pick a start and end date for the poll', 'error'); return; }

  const btn = document.getElementById('pl-poll-btn');
  btn.disabled = true;
  try {
    // Step 1: build the DRAFT poll. build_poll() refuses (400) if any
    // practice in range is missing location/type/time -- that error names
    // exactly which practice needs what, so it's shown verbatim, not
    // replaced with a generic message. This step only writes a DRAFT row;
    // nothing is posted to Slack yet.
    const createResult = await fetch('/admin/availability/polls/create', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ starts_on: startsOn, ends_on: endsOn }),
    }).then(r => r.json());
    if (!createResult.success) {
      showToast(createResult.error || 'Failed to create poll', 'error');
      return;
    }

    // Confirm before the one step that actually posts to Slack, naming the
    // resolved target channel explicitly -- a one-click "Open Availability
    // Poll" button with no confirmation is how a shadow-mode misconfig
    // reaches all 64 real members instead of the 5-person test channel.
    const channelLabel = describeAvailabilityChannel(createResult.channel_id, createResult.is_shadow);
    const proceed = confirm(
      `This will post the availability poll to ${channelLabel}. Continue?`
    );
    if (!proceed) {
      showToast('Poll created as a draft; not posted to Slack', 'success');
      return;
    }

    // Step 2: open it -- posts to Slack and seeds reactions. Refuses (400)
    // if any custom letter emoji is missing from the workspace; that error
    // names the missing emoji verbatim too.
    const openResult = await fetch(`/admin/availability/polls/${createResult.poll_id}/open`, {
      method: 'POST',
    }).then(r => r.json());
    if (!openResult.success) {
      showToast(openResult.error || 'Failed to open poll', 'error');
      return;
    }

    showToast(`Availability poll posted to ${channelLabel}`, 'success');
  } catch (e) {
    showToast('Failed to open availability poll', 'error');
  } finally {
    btn.disabled = false;
  }
}

/* ---------- lead candidates picker (practice create/edit form) ---------- */
async function loadLeadCandidates(practiceId) {
  const response = await fetch(`/admin/practices/${practiceId}/lead-candidates`);
  if (!response.ok) {
    showToast('Could not load lead availability', 'error');
    return null;
  }
  return response.json();
}

function leadCandidateLabel(candidate) {
  const parts = [];
  if (candidate.available) {
    parts.push('available');
  } else if (candidate.responded) {
    parts.push('unavailable');
  } else {
    parts.push('no response');
  }
  parts.push(`led ${candidate.led_in_block} this block`);
  parts.push(`${candidate.led_last_90d} in 90d`);
  const warning = candidate.stale ? ' ⚠ answered before this practice changed' : '';
  return `${candidate.name} · ${parts.join(' · ')}${warning}`;
}

function renderLeadPicker(container, payload) {
  const assigned = new Set(payload.assigned || []);
  container.innerHTML = '';

  const capacity = document.createElement('div');
  capacity.className = 'lead-capacity';
  capacity.textContent =
    `Leads (needs ${payload.leads_needed}, assigned ${assigned.size})`;
  container.appendChild(capacity);

  // Ordering comes from the server: available and least-loaded first.
  // Every candidate stays selectable — assignment is a human judgment call.
  payload.candidates.forEach((candidate) => {
    const row = document.createElement('label');
    row.className = 'lead-option';
    // Available / unavailable / no-response are visually distinct states —
    // they mean different things to the person assigning leads.
    if (candidate.available) {
      row.classList.add('available');
    } else if (candidate.responded) {
      row.classList.add('unavailable');
    } else {
      row.classList.add('no-response');
    }
    if (candidate.stale) row.classList.add('stale');

    const box = document.createElement('input');
    box.type = 'checkbox';
    box.name = 'lead_ids';
    box.value = candidate.user_id;
    box.checked = assigned.has(candidate.user_id);

    const text = document.createElement('span');
    text.textContent = leadCandidateLabel(candidate);

    row.appendChild(box);
    row.appendChild(text);
    container.appendChild(row);
  });
}
