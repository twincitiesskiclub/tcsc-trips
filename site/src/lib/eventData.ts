// Build-time fetch of the current Dry Tri from tcsc.ski.
//
// Never fails the build: an unreachable API yields { source: 'fallback' },
// the page renders its generic line pointing at tcsc.ski/tri, and the band
// carries data-event-source="fallback" so the cause is visible in the HTML.
import type { EventTimes } from './eventState.ts';

export interface EventEntry {
  name: string;
  description: string;
  price_cents: number;
}

export interface EventRecord extends EventTimes {
  slug: string;
  name: string;
  location: string;
  description: string;
  registration_path: string;
  details_url: string | null;
  entries: EventEntry[];
}

export interface EventData {
  source: 'api' | 'fallback';
  event: EventRecord | null;
}

export const FALLBACK_URL = 'https://tcsc.ski/tri';
const FETCH_TIMEOUT_MS = 10_000;

export function eventApiUrl(): string {
  // Optional chaining: plain `node --test` has no import.meta.env.
  return import.meta.env?.PUBLIC_EVENT_API_URL ?? 'https://tcsc.ski/api/events/dry-tri';
}

export function registrationUrl(event: Pick<EventRecord, 'registration_path'>, apiUrl: string = eventApiUrl()): string {
  if (!event.registration_path) return FALLBACK_URL;
  return new URL(event.registration_path, apiUrl).toString();
}

export async function fetchEventData(url: string = eventApiUrl()): Promise<EventData> {
  try {
    const response = await fetch(url, { signal: AbortSignal.timeout(FETCH_TIMEOUT_MS) });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const body = await response.json();
    return { source: 'api', event: body?.event ?? null };
  } catch (error) {
    console.warn(`[event] ${url} unreachable (${error}). The Dry Tri band will use its fallback line.`);
    return { source: 'fallback', event: null };
  }
}
