// The registration state rule, in one place.
//
// This module is imported by the Astro build AND shipped to the browser, on
// purpose. The site is a static build, so a state decided at build time is
// wrong the moment a window boundary passes; the browser re-derives it from
// timestamps baked into the HTML. Both callers must agree, so there is
// exactly one implementation and no Python twin.
export type RegistrationState = 'open' | 'coming_soon' | 'closed';

export interface RegistrationWindows {
  returning_start?: string | null;
  returning_end?: string | null;
  new_start?: string | null;
  new_end?: string | null;
}

interface ParsedWindow {
  start: number;
  end: number;
}

// A window counts only when BOTH ends parse, matching Season.is_open_for on
// the Python side, which returns False unless both columns are set.
function parseWindows(w: RegistrationWindows): ParsedWindow[] {
  const pairs: Array<[unknown, unknown]> = [
    [w.returning_start, w.returning_end],
    [w.new_start, w.new_end],
  ];
  const parsed: ParsedWindow[] = [];
  for (const [rawStart, rawEnd] of pairs) {
    if (typeof rawStart !== 'string' || typeof rawEnd !== 'string') continue;
    const start = Date.parse(rawStart);
    const end = Date.parse(rawEnd);
    if (Number.isNaN(start) || Number.isNaN(end)) continue;
    parsed.push({ start, end });
  }
  return parsed;
}

/** `now` is a millisecond epoch (Date.now()), so build and browser share it. */
export function deriveRegistrationState(
  w: RegistrationWindows,
  now: number,
): RegistrationState {
  const windows = parseWindows(w);
  if (windows.length === 0) return 'closed';
  if (windows.some((x) => now >= x.start && now <= x.end)) return 'open';
  // Covers the gap between the returning and new windows: nobody can submit
  // right now, but a window is still ahead, so "open" would be a lie.
  if (windows.some((x) => x.start > now)) return 'coming_soon';
  return 'closed';
}
