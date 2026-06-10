type LocResp = {
  id: string;
  name: string;
  temp_f: number | null;
  wind_chill_f: number | null;
  snow_conditions: string | null;
  wax_band: string | null;
  wax_label: string | null;
};
type Resp = { updated_at: string; locations: LocResp[]; error?: string };

const REFRESH_MS = 5 * 60 * 1000;
const STAMP_TICK_MS = 60 * 1000;

const roots: HTMLElement[] = [];
let staleWhileHidden = false;
let documentTimersAttached = false;

async function fetchAndRender(root: HTMLElement) {
  const url = root.dataset.apiUrl!;
  try {
    // Default cache mode on purpose: the endpoint sends Cache-Control:
    // public, max-age=300, so per-page-nav fetches hit the browser cache.
    const r = await fetch(url);
    if (!r.ok) throw new Error('Bad status');
    const data: Resp = await r.json();
    renderInto(root, data);
  } catch {
    renderFailure(root);
  }
}

function renderInto(root: HTMLElement, data: Resp) {
  // Flask's defensive error body is {updated_at: null, locations: [], error}.
  if (data.error || !Array.isArray(data.locations) || data.locations.length === 0) {
    return renderFailure(root);
  }
  const announcements: string[] = [];
  data.locations.forEach((loc) => {
    const el = root.querySelector(`[data-location="${loc.id}"]`) as HTMLElement | null;
    if (!el) return;
    setText(el, '[data-name]', loc.name ?? '·');
    setText(el, '[data-temp]', loc.temp_f == null ? '·' : `${loc.temp_f}°F`);
    setText(el, '[data-wax]', loc.wax_label ?? 'Conditions unavailable');
    // Announce only material wax transitions: a previously rendered,
    // non-placeholder band changing to a different band.
    const prevBand = el.dataset.waxBand;
    if (prevBand && loc.wax_band && loc.wax_band !== prevBand && loc.wax_label) {
      announcements.push(`${loc.name} wax changed to ${loc.wax_label}`);
    }
    el.dataset.waxBand = loc.wax_band ?? '';
  });
  if (announcements.length > 0) {
    const announcer = root.querySelector('[data-announcer]') as HTMLElement | null;
    if (announcer) announcer.textContent = announcements.join('; ');
  }
  root.dataset.updatedAt = data.updated_at;
  updateStamp(root);
}

function renderFailure(root: HTMLElement) {
  // Total failure: make each cell read clearly, not four orphan middots.
  root.querySelectorAll<HTMLElement>('[data-location]').forEach((el) => {
    setText(el, '[data-wax]', 'Conditions unavailable');
  });
  delete root.dataset.updatedAt;
  const stamp = root.querySelector('[data-updated]') as HTMLElement | null;
  if (stamp && stamp.textContent !== '● Conditions unavailable') {
    stamp.textContent = '● Conditions unavailable';
  }
}

function updateStamp(root: HTMLElement) {
  const stamp = root.querySelector('[data-updated]') as HTMLElement | null;
  const iso = root.dataset.updatedAt;
  if (!stamp || !iso) return;
  const mins = Math.max(0, Math.floor((Date.now() - new Date(iso).getTime()) / 60000));
  const text = `● Live · updated ${mins} min ago`;
  if (stamp.textContent !== text) stamp.textContent = text;
}

function setText(el: HTMLElement, sel: string, val: string) {
  const t = el.querySelector(sel) as HTMLElement | null;
  if (t && t.textContent !== val) t.textContent = val;
}

export function init() {
  document.querySelectorAll<HTMLElement>('[data-live-conditions]').forEach((root) => {
    // Idempotence guard: double-inclusion must not double-poll.
    if (root.dataset.lcInitialized === 'true') return;
    root.dataset.lcInitialized = 'true';
    roots.push(root);

    fetchAndRender(root);
    setInterval(() => {
      // Skip refreshes while the tab is hidden to save NWS quota.
      if (document.hidden) {
        staleWhileHidden = true;
        return;
      }
      fetchAndRender(root);
    }, REFRESH_MS);
  });

  if (!documentTimersAttached && roots.length > 0) {
    documentTimersAttached = true;
    document.addEventListener('visibilitychange', () => {
      if (!document.hidden && staleWhileHidden) {
        staleWhileHidden = false;
        roots.forEach((root) => fetchAndRender(root));
      }
    });
    // Honest stamp: recompute "updated N min ago" between data refreshes.
    // Kept out of any live region so the ticker is never announced.
    setInterval(() => roots.forEach((root) => updateStamp(root)), STAMP_TICK_MS);
  }
}
