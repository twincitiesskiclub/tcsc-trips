import {
  conditionsDisplayMode,
  type ConditionsDisplayMode,
} from '@/lib/conditionsDisplayMode';

type LocResp = {
  id: string;
  name: string;
  temp_f: number | null;
  wind_chill_f: number | null;
  snow_conditions: string | null;
  wax_band: string | null;
  wax_label: string | null;
  source_url: string | null;
  report_date: string | null;
  groomed_for: string | null;
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
    renderQuiet(root, conditionsDisplayMode(null));
  }
}

function renderInto(root: HTMLElement, data: Resp) {
  const mode = conditionsDisplayMode(data);
  if (mode !== 'live') {
    renderQuiet(root, mode);
    return;
  }
  // Restore venue cells that were hidden during off-season, and remove any
  // injected dryland label so the grid layout comes back cleanly.
  root.querySelectorAll<HTMLElement>('[data-location]').forEach((el) => {
    el.hidden = false;
    // Inline display is the actual hide mechanism (the compact cells carry a
    // `flex` class that out-specifies the UA [hidden] rule).
    el.style.removeProperty('display');
  });
  root.querySelector('[data-dryland-label]')?.remove();
  // The groomed line rides below the wax line and is prominent-only (the
  // compact variant keeps one line per venue); the stamp only exists there.
  const isCompact = !root.querySelector('[data-updated]');
  const announcements: string[] = [];
  data.locations.forEach((loc) => {
    const el = root.querySelector(`[data-location="${loc.id}"]`) as HTMLElement | null;
    if (!el) return;
    setName(el, loc.name ?? '·', loc.source_url);
    if (!isCompact) setGroomed(el, loc.groomed_for, loc.report_date);
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
      announcements.push(`${loc.name} wax recommendation changed: ${loc.wax_label}`);
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

function renderQuiet(root: HTMLElement, mode: ConditionsDisplayMode) {
  // Unavailable conditions say it once in the stamp; cells go quiet ("No
  // report") instead of repeating the error four times. Off-season
  // (April-October), healthy payloads and failures share this dryland path:
  // no snow is not an outage.
  const offSeason = mode === 'off-season';
  root.querySelectorAll<HTMLElement>('[data-location]').forEach((el) => {
    // Clear temp so the server-rendered middot placeholder does not dangle.
    setText(el, '[data-temp]', '');
    setText(el, '[data-wax]', offSeason ? 'Dryland season' : 'No report');
    setText(el, '[data-feels]', '');
    // Drop any report link or groomed line a prior winter fetch left behind:
    // an outage should not keep advertising a stale report.
    const nameEl = el.querySelector('[data-name]') as HTMLElement | null;
    const link = nameEl?.querySelector('a[data-source-link]');
    if (nameEl && link) nameEl.textContent = link.textContent;
    el.querySelector('[data-groomed]')?.remove();
    const chip = el.querySelector('[data-wax-chip]') as HTMLElement | null;
    if (chip) chip.hidden = true;
    // Off-season: hide the four venue cells entirely; the stamp already
    // carries the message for the prominent variant, and the compact variant
    // will show one "Dryland season" label instead of four. Inline display,
    // not the hidden attribute: the compact cells' `flex` class would
    // out-specify the UA [hidden] rule.
    if (offSeason) {
      el.hidden = true;
      el.style.display = 'none';
    }
  });
  // Off-season: put a single "Dryland season" statement where the venue cells
  // were, so a phone visitor gets a member's read instead of a bare fever
  // number or an empty strip. Compact (inner) pages show it at all widths in
  // place of the venue lines; the prominent (home) strip shows it on mobile
  // only, where the fever cell is now md+, and keeps the fever reading on
  // desktop. Distinguish compact (no [data-updated] stamp) from prominent.
  const isCompact = !root.querySelector('[data-updated]');
  const birkie = root.querySelector('[data-birkie]') as HTMLElement | null;
  if (offSeason && birkie && !root.querySelector('[data-dryland-label]')) {
    const label = document.createElement('span');
    label.dataset.drylandLabel = '';
    label.textContent = 'Dryland season';
    label.className = isCompact
      ? 'flex items-baseline gap-1.5 text-paper/70'
      : 'md:hidden col-span-2 text-paper/70';
    birkie.parentElement?.insertBefore(label, birkie);
  }
  // Fever scale matches app/conditions/birkie.py: 98.6 means summer.
  if (birkie) {
    setText(birkie, '[data-birkie-word]', offSeason ? '98.6°' : '');
    setText(birkie, '[data-birkie-detail]', offSeason ? 'No fever yet. Birkie talk starts in November.' : 'No report');
  }
  delete root.dataset.updatedAt;
  const stamp = root.querySelector('[data-updated]') as HTMLElement | null;
  const stampText = offSeason
    ? '● Trail reports come back with the snow'
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

// Venue name: a quiet link to the SkinnySkI report when the payload carries
// one, plain text otherwise (exactly the server-rendered default). Ledger link
// treatment, opens in a new tab.
function setName(el: HTMLElement, name: string, sourceUrl: string | null) {
  const target = el.querySelector('[data-name]') as HTMLElement | null;
  if (!target) return;
  if (sourceUrl) {
    let a = target.querySelector('a[data-source-link]') as HTMLAnchorElement | null;
    if (!a) {
      a = document.createElement('a');
      a.dataset.sourceLink = '';
      a.target = '_blank';
      a.rel = 'noopener';
      a.className = 'underline underline-offset-4 decoration-mint/40 hover:decoration-mint';
      target.replaceChildren(a);
    }
    a.href = sourceUrl;
    if (a.textContent !== name) a.textContent = name;
  } else if (target.querySelector('a[data-source-link]') || target.textContent !== name) {
    target.textContent = name;
  }
}

// Groomed-as-of line injected below the wax line (prominent variant only);
// nothing renders when the report is not groomed, so dryland is unchanged.
function setGroomed(el: HTMLElement, groomedFor: string | null, reportDate: string | null) {
  const text = groomedLine(groomedFor, reportDate);
  let line = el.querySelector('[data-groomed]') as HTMLElement | null;
  if (!text) {
    line?.remove();
    return;
  }
  if (!line) {
    line = document.createElement('div');
    line.dataset.groomed = '';
    line.className = 'text-[11px] text-paper/50 mt-0.5';
    el.appendChild(line);
  }
  if (line.textContent !== text) line.textContent = text;
}

function groomedLine(groomedFor: string | null, reportDate: string | null): string {
  if (!groomedFor) return '';
  const label =
    groomedFor === 'skate' ? 'Groomed skate' :
    groomedFor === 'classic' ? 'Groomed classic' :
    'Groomed';
  const date = formatShortDate(reportDate);
  return date ? `${label} · ${date}` : label;
}

// 'YYYY-MM-DD' to short month + day, no year ('2026-02-08' -> 'Feb 8').
// Parsed as a local date (not the Date string parser, which reads bare ISO
// dates as UTC and can shift the day across US time zones).
function formatShortDate(iso: string | null): string {
  if (!iso) return '';
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso);
  if (!m) return '';
  const d = new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]));
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

function initBirkieFever(root: HTMLElement) {
  // Easter egg with a quiet ♪ invitation: the Birkie cell plays the club's
  // Birkie Fever song. Audio is created on first click only (6MB mp3, the
  // universally decodable codec; never part of page load); the note turns
  // coral while playing.
  const btn = root.querySelector<HTMLButtonElement>('button[data-birkie]');
  const src = btn?.dataset.birkieAudio;
  if (!btn || !src) return;
  const note = btn.querySelector<HTMLElement>('[data-fever-note]');
  let audio: HTMLAudioElement | null = null;
  const setPlaying = (playing: boolean) => {
    btn.setAttribute('aria-pressed', String(playing));
    if (note) {
      note.classList.toggle('text-coral', playing);
      note.classList.toggle('text-mint/50', !playing);
    }
  };
  btn.addEventListener('click', () => {
    if (!audio) {
      audio = new Audio(src);
      audio.addEventListener('ended', () => setPlaying(false));
      audio.addEventListener('error', () => setPlaying(false));
    }
    if (audio.paused) {
      void audio.play().then(() => setPlaying(true)).catch(() => setPlaying(false));
    } else {
      audio.pause();
      setPlaying(false);
    }
  });
}

export function init() {
  document.querySelectorAll<HTMLElement>('[data-live-conditions]').forEach((root) => {
    // Idempotence guard: double-inclusion must not double-poll.
    if (root.dataset.lcInitialized === 'true') return;
    root.dataset.lcInitialized = 'true';
    roots.push(root);
    initBirkieFever(root);

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
