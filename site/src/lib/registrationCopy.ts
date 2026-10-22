// Registration copy, formatted in US Central.
//
// Timestamps arrive as UTC from the API; the club is in Minneapolis and every
// date a member reads is a Central date. Formatting in UTC would show the
// wrong DAY for any evening deadline, so the timezone is pinned explicitly
// rather than inherited from the build machine or the visitor.
import type { RegistrationState, RegistrationWindows } from './registrationState';

const CENTRAL = 'America/Chicago';
const ABILITY = 'You should be comfortable on skis. Racing is optional.';
const FALL_WINTER_REOPENS = 'Aug/Sep';
const SPRING_SUMMER_REOPENS = 'Apr/May';

const dayFormatter = new Intl.DateTimeFormat('en-US', {
  timeZone: CENTRAL,
  month: 'short',
  day: 'numeric',
});

export function formatDay(iso: string | null | undefined): string | null {
  if (typeof iso !== 'string') return null;
  const ms = Date.parse(iso);
  if (Number.isNaN(ms)) return null;
  return dayFormatter.format(new Date(ms));
}

function openingDays(w: RegistrationWindows) {
  return {
    returning: formatDay(w.returning_start),
    fresh: formatDay(w.new_start),
  };
}

/** "Returning members Aug 28 · new members Sep 3". Null when no dates. */
export function datesSentence(w: RegistrationWindows): string | null {
  const { returning, fresh } = openingDays(w);
  const parts: string[] = [];
  if (returning) parts.push(`Returning members ${returning}`);
  if (fresh) parts.push(returning ? `new members ${fresh}` : `New members ${fresh}`);
  return parts.length ? parts.join(' · ') : null;
}

/** The shared opening-date format for the hero and registration strip. */
export function datesLine(w: RegistrationWindows): string | null {
  return datesSentence(w);
}

export function newMembersLine(w: RegistrationWindows, now: number): string {
  if (typeof w.new_start !== 'string') return '';
  const freshStart = Date.parse(w.new_start);
  const fresh = formatDay(w.new_start);
  return fresh && !Number.isNaN(freshStart) && now < freshStart
    ? `New members ${fresh}`
    : '';
}

export function stripSubhead(state: RegistrationState, w: RegistrationWindows): string {
  if (state === 'open') return `Registration is open. ${ABILITY}`;
  if (state === 'closed') {
    return `Registration is closed. Fall/Winter reopens ${FALL_WINTER_REOPENS}, Spring/Summer ${SPRING_SUMMER_REOPENS}. ${ABILITY}`;
  }
  const dates = datesSentence(w);
  return dates ? `${dates}. ${ABILITY}` : `Registration opens soon. ${ABILITY}`;
}

/** Registration status for a season card, with dates only when still useful. */
export function cardNote(
  state: RegistrationState,
  year: number,
  w: RegistrationWindows,
): string | null {
  if (state === 'open') {
    const fresh = formatDay(w.new_start);
    const freshStart = typeof w.new_start === 'string' ? Date.parse(w.new_start) : Number.NaN;
    return fresh && !Number.isNaN(freshStart) && Date.now() < freshStart
      ? `Registration open · new members from ${fresh}`
      : 'Registration open';
  }
  if (state === 'closed') return `${year} registration closed`;

  const { returning, fresh } = openingDays(w);
  const parts: string[] = [];
  if (returning) parts.push(`returning members ${returning}`);
  if (fresh) parts.push(`new members ${fresh}`);
  return parts.length ? `${year} registration: ${parts.join(' · ')}` : null;
}
