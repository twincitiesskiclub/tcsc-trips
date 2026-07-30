// Build-time season fetch.
//
// This runs during `astro build`, once, and its result is baked into static
// HTML. It must NEVER fail the build: a marketing deploy blocked because the
// Flask app happened to be restarting is a worse outcome than a page that
// declines to name a date. The fallback is therefore pessimistic AND
// self-announcing -- see the data-season-source stamp in BaseLayout.
import type { RegistrationWindows } from './registrationState';

export interface SeasonRecord extends RegistrationWindows {
  name?: string;
  season_type?: string;
  year?: number;
  price_cents?: number | null;
}

export interface SeasonData {
  source: 'api' | 'fallback';
  generated_at: string | null;
  primary: SeasonRecord | null;
  by_type: Record<string, SeasonRecord>;
}

const FETCH_TIMEOUT_MS = 10_000;

const FALLBACK: SeasonData = Object.freeze({
  source: 'fallback',
  generated_at: null,
  primary: null,
  by_type: {},
});

export function seasonApiUrl(): string {
  // Optional chaining: this module is also loaded by plain `node --test`,
  // where import.meta.env does not exist.
  return import.meta.env?.PUBLIC_SEASON_API_URL ?? 'https://tcsc.ski/api/season';
}

// Keyed by url so one build issues one request, while tests stay isolated by
// pointing at distinct ephemeral ports.
const inFlight = new Map<string, Promise<SeasonData>>();

async function load(url: string): Promise<SeasonData> {
  try {
    const response = await fetch(url, { signal: AbortSignal.timeout(FETCH_TIMEOUT_MS) });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const body = await response.json();
    return {
      source: 'api',
      generated_at: body?.generated_at ?? null,
      primary: body?.primary ?? null,
      by_type: body?.by_type ?? {},
    };
  } catch (error) {
    console.warn(
      `[season] ${url} unreachable (${error}). Falling back to committed copy; ` +
        'the built pages will report data-season-source="fallback".',
    );
    return FALLBACK;
  }
}

export function fetchSeasonData(url: string = seasonApiUrl()): Promise<SeasonData> {
  let pending = inFlight.get(url);
  if (!pending) {
    pending = load(url);
    inFlight.set(url, pending);
  }
  return pending;
}
