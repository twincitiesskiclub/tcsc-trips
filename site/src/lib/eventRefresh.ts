// Browser refresh for the Dry Tri band.
//
// The marketing site rebuilds only on a commit, so the baked band is only
// as fresh as the last deploy. On load this (1) re-renders from the baked
// JSON with the current time, so the button flips at the right minute even
// offline, then (2) fetches the API and re-renders from fresh data, so an
// admin edit on tcsc.ski shows up without a deploy. Any failure leaves what
// is already on the page.
import { renderEventBand } from './eventRender.ts';
import type { EventRecord } from './eventData.ts';

const FETCH_TIMEOUT_MS = 10_000;

function parseBaked(raw: string | null): EventRecord | null {
  try {
    return raw ? (JSON.parse(raw) as EventRecord | null) : null;
  } catch {
    return null;
  }
}

export async function refreshEventBands(
  root: ParentNode,
  fetchFn: typeof fetch,
  now: () => number,
): Promise<void> {
  const bands = Array.from(root.querySelectorAll<HTMLElement>('[data-event-band]'));
  await Promise.all(
    bands.map(async (band) => {
      const apiUrl = band.getAttribute('data-event-api') ?? '';
      const baked = parseBaked(band.getAttribute('data-event'));
      if (baked) band.innerHTML = renderEventBand(baked, now(), apiUrl);
      if (!apiUrl) return;
      try {
        const response = await fetchFn(apiUrl, { signal: AbortSignal.timeout(FETCH_TIMEOUT_MS) });
        if (!response.ok) return;
        const body = await response.json();
        if (!body || !('event' in body)) return;
        band.innerHTML = renderEventBand(body.event, now(), apiUrl);
        band.setAttribute('data-event-source', 'live');
      } catch {
        // Keep the baked band.
      }
    }),
  );
}
