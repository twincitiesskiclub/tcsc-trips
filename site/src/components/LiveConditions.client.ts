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

async function fetchAndRender(root: HTMLElement) {
  const url = root.dataset.apiUrl!;
  try {
    const r = await fetch(url, { cache: 'no-store' });
    if (!r.ok) throw new Error('Bad status');
    const data: Resp = await r.json();
    renderInto(root, data);
  } catch {
    renderFailure(root);
  }
}

function renderInto(root: HTMLElement, data: Resp) {
  data.locations.forEach((loc) => {
    const el = root.querySelector(`[data-location="${loc.id}"]`) as HTMLElement | null;
    if (!el) return;
    setText(el, '[data-name]', loc.name);
    setText(el, '[data-temp]', loc.temp_f == null ? '·' : `${loc.temp_f}°F`);
    setText(el, '[data-wax]', loc.wax_label ?? 'Conditions unavailable');
  });
  const stamp = root.querySelector('[data-updated]') as HTMLElement | null;
  if (stamp) {
    const date = new Date(data.updated_at);
    const mins = Math.max(0, Math.floor((Date.now() - date.getTime()) / 60000));
    stamp.textContent = data.error
      ? '● Conditions unavailable'
      : `● Live · updated ${mins} min ago`;
  }
}

function renderFailure(root: HTMLElement) {
  // Total fetch failure: make each cell read clearly, not four orphan middots.
  root.querySelectorAll<HTMLElement>('[data-location]').forEach((el) => {
    setText(el, '[data-wax]', 'Conditions unavailable');
  });
  const stamp = root.querySelector('[data-updated]') as HTMLElement | null;
  if (stamp) stamp.textContent = '● Conditions unavailable';
}

function setText(el: HTMLElement, sel: string, val: string) {
  const t = el.querySelector(sel) as HTMLElement | null;
  if (t) t.textContent = val;
}

export function init() {
  const roots = document.querySelectorAll<HTMLElement>('[data-live-conditions]');
  roots.forEach((root) => {
    // Idempotence guard: double-inclusion must not double-poll.
    if (root.dataset.lcInitialized === 'true') return;
    root.dataset.lcInitialized = 'true';

    let staleWhileHidden = false;
    fetchAndRender(root);
    setInterval(() => {
      // Skip refreshes while the tab is hidden to save NWS quota.
      if (document.hidden) {
        staleWhileHidden = true;
        return;
      }
      fetchAndRender(root);
    }, REFRESH_MS);
    document.addEventListener('visibilitychange', () => {
      if (!document.hidden && staleWhileHidden) {
        staleWhileHidden = false;
        fetchAndRender(root);
      }
    });
  });
}
