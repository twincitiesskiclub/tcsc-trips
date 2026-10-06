// The Dry Tri event band, as an HTML string.
//
// One function serves both the Astro build (set:html) and the browser
// refresh (innerHTML), so the baked page and the refreshed page cannot
// drift. Every value from the API is escaped: admins type the description,
// location and entry names, and none of it is trusted markup.
import { deriveEventState, type EventState } from './eventState.ts';
import { FALLBACK_URL, registrationUrl, type EventRecord } from './eventData.ts';

const CENTRAL = 'America/Chicago';

export function escapeHtml(s: string): string {
  return String(s)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

function central(iso: string, options: Intl.DateTimeFormatOptions): string {
  return new Date(iso).toLocaleString('en-US', { ...options, timeZone: CENTRAL });
}

/** "Saturday, October 24" */
const longDay = (iso: string) => central(iso, { weekday: 'long', month: 'long', day: 'numeric' });
/** "9:00 AM", joined by a no-break space so AM never wraps onto its own line. */
const clock = (iso: string) => central(iso, { hour: 'numeric', minute: '2-digit' }).replace(/[\u202f ]/g, '\u00a0');
/** "Sat, Oct 24" */
export const raceDayShort = (iso: string) => central(iso, { weekday: 'short', month: 'short', day: 'numeric' });
/** "2026" */
export const raceYear = (iso: string) => central(iso, { year: 'numeric' });

export function formatPrice(cents: number): string {
  const dollars = cents / 100;
  return Number.isInteger(dollars) ? `$${dollars}` : `$${dollars.toFixed(2)}`;
}

/** Blank lines separate blocks; "- " lines become a list; other lines a paragraph. */
export function descriptionHtml(text: string): string {
  const out: string[] = [];
  let list: string[] = [];
  let para: string[] = [];
  const flushList = () => {
    if (list.length) out.push(`<ul>${list.map((item) => `<li>${escapeHtml(item)}</li>`).join('')}</ul>`);
    list = [];
  };
  const flushPara = () => {
    if (para.length) out.push(`<p>${para.map(escapeHtml).join('<br>')}</p>`);
    para = [];
  };
  for (const raw of (text ?? '').replace(/\r\n?/g, '\n').split('\n')) {
    const line = raw.trim();
    if (!line) {
      flushList();
      flushPara();
    } else if (line.startsWith('- ')) {
      flushPara();
      list.push(line.slice(2).trim());
    } else {
      flushList();
      para.push(line);
    }
  }
  flushList();
  flushPara();
  return out.join('');
}

const BUTTON =
  'inline-flex items-center px-5 py-3 rounded-md bg-navy text-mint font-semibold text-sm transition-colors duration-150 hover:bg-navy-deep active:bg-navy/90';
const LINK =
  'font-semibold text-navy underline underline-offset-4 decoration-ink/30 hover:decoration-mint-deep hover:text-mint-deep transition-colors';

function ctaHtml(event: EventRecord, state: EventState, apiUrl: string): string {
  switch (state) {
    case 'upcoming':
      return `<p class="font-semibold text-navy">Registration opens ${escapeHtml(longDay(event.signup_start))}</p>`;
    case 'open':
      return (
        `<a class="${BUTTON}" href="${escapeHtml(registrationUrl(event, apiUrl))}">Register</a>` +
        `<p class="mt-3 text-sm text-slate">Registration closes ${escapeHtml(longDay(event.signup_end))}.</p>`
      );
    case 'closed':
      return '<p class="font-semibold text-navy">Registration is closed. See you at the start.</p>';
    case 'past':
      return '';
  }
}

function safeHttpUrl(url: string | null): string | null {
  if (!url) return null;
  try {
    const parsed = new URL(url);
    return parsed.protocol === 'https:' || parsed.protocol === 'http:' ? parsed.toString() : null;
  } catch {
    return null;
  }
}

export function renderEventBand(event: EventRecord | null, now: number, apiUrl: string): string {
  if (!event) {
    return `<p class="text-lg text-ink">Dates, entries and registration: <a class="${LINK}" href="${FALLBACK_URL}">tcsc.ski/tri</a></p>`;
  }
  const state = deriveEventState(event, now);
  const entries = event.entries
    .map(
      (entry) =>
        `<div class="py-4 grid grid-cols-[1fr_auto] gap-x-6">` +
        `<div><div class="font-semibold text-navy">${escapeHtml(entry.name)}</div>` +
        (entry.description ? `<div class="text-sm text-ink/70 mt-0.5">${escapeHtml(entry.description)}</div>` : '') +
        `</div><div class="font-semibold text-navy tabular-nums" data-entry-price>${formatPrice(entry.price_cents)}</div></div>`,
    )
    .join('');
  const details = safeHttpUrl(event.details_url);
  return (
    `<div class="grid gap-10 md:grid-cols-2">` +
    `<div>` +
    `<p class="text-2xl font-semibold text-navy">${escapeHtml(longDay(event.event_date))} · ${escapeHtml(clock(event.event_date))}</p>` +
    `<p class="mt-1 text-ink/80">${escapeHtml(event.location)}</p>` +
    `<div class="mt-6 prose text-ink">${descriptionHtml(event.description)}</div>` +
    `</div>` +
    `<div>` +
    `<div class="divide-y divide-ink/10 border-y border-ink/10">${entries}</div>` +
    `<div class="mt-6" data-event-cta data-state="${state}">${ctaHtml(event, state, apiUrl)}</div>` +
    (details ? `<p class="mt-6 text-sm"><a class="${LINK}" data-event-details href="${escapeHtml(details)}">Full race details</a></p>` : '') +
    `</div>` +
    `</div>`
  );
}
