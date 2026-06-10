type LocResp = {
  id: string;
  name: string;
  temp_f: number | null;
  wind_chill_f: number | null;
  snow_conditions: string | null;
  wax_band: string | null;
  wax_label: string | null;
};
type BirkieResp = { status: string; word: string; detail: string };
type Resp = { updated_at: string; locations: LocResp[]; birkie?: BirkieResp; error?: string };

const REFRESH_MS = 5 * 60 * 1000;

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
    // Wind chill earns its spot only when it materially differs from air temp.
    const showFeels =
      loc.temp_f != null && loc.wind_chill_f != null && loc.temp_f - loc.wind_chill_f >= 3;
    setText(el, '[data-feels]', showFeels ? `feels ${Math.round(loc.wind_chill_f!)}°` : '');
    setText(el, '[data-wax]', loc.wax_label ?? 'No report');
    const chip = el.querySelector('[data-wax-chip]') as HTMLElement | null;
    if (chip) {
      if (loc.wax_band) {
        chip.dataset.band = loc.wax_band;
        chip.hidden = false;
      } else {
        chip.hidden = true;
      }
    }
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
  const birkie = root.querySelector('[data-birkie]') as HTMLElement | null;
  if (birkie) {
    setText(birkie, '[data-birkie-word]', data.birkie?.word ?? '·');
    setText(birkie, '[data-birkie-detail]', data.birkie?.detail ?? 'No report');
  }
  root.dataset.updatedAt = data.updated_at;
  root.dataset.filled = 'true';
  updateStamp(root);
}

function renderFailure(root: HTMLElement) {
  // Total failure: say it once in the stamp; cells go quiet ("No report")
  // instead of repeating the error four times. Off-season (April-October),
  // the strip talks like a member instead of erroring: no snow is not an
  // outage.
  const offSeason = new Date().getMonth() + 1 >= 4 && new Date().getMonth() + 1 <= 10;
  root.querySelectorAll<HTMLElement>('[data-location]').forEach((el) => {
    setText(el, '[data-wax]', offSeason ? 'Rollerski season' : 'No report');
    setText(el, '[data-feels]', '');
    const chip = el.querySelector('[data-wax-chip]') as HTMLElement | null;
    if (chip) chip.hidden = true;
  });
  const birkie = root.querySelector('[data-birkie]') as HTMLElement | null;
  if (birkie) {
    setText(birkie, '[data-birkie-word]', offSeason ? 'Early' : '·');
    setText(birkie, '[data-birkie-detail]', offSeason ? 'Snow talk starts in November' : 'No report');
  }
  delete root.dataset.updatedAt;
  const stamp = root.querySelector('[data-updated]') as HTMLElement | null;
  const stampText = offSeason
    ? '● Trail reports come back with the snow, usually around Thanksgiving'
    : '● Conditions unavailable';
  if (stamp && stamp.textContent !== stampText) {
    stamp.textContent = stampText;
  }
  root.dataset.filled = 'true';
}

function updateStamp(root: HTMLElement) {
  // Dateline form ("updated 7:02 AM"): an absolute time reads like a trail
  // report and never goes stale-looking between the 5-minute refreshes, so
  // no ticker is needed.
  const stamp = root.querySelector('[data-updated]') as HTMLElement | null;
  const iso = root.dataset.updatedAt;
  if (!stamp || !iso) return;
  const time = new Date(iso).toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' });
  const text = `● Live · updated ${time}`;
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
    // Entrance backstop: a slow first fetch must not hold the strip
    // invisible (the first-fill CSS keys on data-filled).
    setTimeout(() => {
      root.dataset.filled = 'true';
    }, 1200);
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
  }
}
