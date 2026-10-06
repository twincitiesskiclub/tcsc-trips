// The Dry Tri page's registration state rule, in one place.
//
// Imported by the Astro build and shipped to the browser. The API sends
// timestamps only, so both callers derive the state here from the same
// inputs and cannot disagree. Mirrors registrationState.ts for seasons.
export type EventState = 'upcoming' | 'open' | 'closed' | 'past';

export interface EventTimes {
  event_date: string;
  signup_start: string;
  signup_end: string;
}

const CENTRAL = 'America/Chicago';

function centralParts(instant: number): { year: number; month: number; day: number; hour: number } {
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone: CENTRAL,
    year: 'numeric',
    month: 'numeric',
    day: 'numeric',
    hour: 'numeric',
    hourCycle: 'h23',
  }).formatToParts(new Date(instant));
  const get = (type: string) => Number(parts.find((p) => p.type === type)?.value);
  return { year: get('year'), month: get('month'), day: get('day'), hour: get('hour') };
}

/** First instant of the Central calendar day after the one holding `instant`. */
export function endOfCentralDay(instant: number): number {
  const { year, month, day } = centralParts(instant);
  // Central midnight is 05:00Z (CDT) or 06:00Z (CST). US DST changes at
  // 2 AM, so exactly one candidate lands on hour 0.
  for (const utcHour of [5, 6]) {
    const candidate = Date.UTC(year, month - 1, day + 1, utcHour);
    if (centralParts(candidate).hour === 0) return candidate;
  }
  throw new Error(`no Central midnight found after ${new Date(instant).toISOString()}`);
}

/** `now` is a millisecond epoch so build and browser share the signature. */
export function deriveEventState(t: EventTimes, now: number): EventState {
  const start = Date.parse(t.signup_start);
  const end = Date.parse(t.signup_end);
  const race = Date.parse(t.event_date);
  if ([start, end, race].some(Number.isNaN)) return 'closed';
  if (now >= endOfCentralDay(race)) return 'past';
  if (now < start) return 'upcoming';
  // Inclusive, matching events.py: signup_start <= now <= signup_end.
  if (now <= end) return 'open';
  return 'closed';
}
