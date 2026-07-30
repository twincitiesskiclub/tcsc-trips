// Registration copy, formatted in US Central.
//
// Timestamps arrive as UTC from the API; the club is in Minneapolis and every
// date a member reads is a Central date. Formatting in UTC would show the
// wrong DAY for any evening deadline, so the timezone is pinned explicitly
// rather than inherited from the build machine or the visitor.
import type { RegistrationState, RegistrationWindows } from './registrationState';

const CENTRAL = 'America/Chicago';
const ABILITY = 'Intermediate ability and up, no racing required.';

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

/** "Returning members Aug 28; new members Sep 3" — null when no dates. */
export function datesSentence(w: RegistrationWindows): string | null {
  const { returning, fresh } = openingDays(w);
  const parts: string[] = [];
  if (returning) parts.push(`Returning members ${returning}`);
  if (fresh) parts.push(returning ? `new members ${fresh}` : `New members ${fresh}`);
  return parts.length ? parts.join('; ') : null;
}

export function stripSubhead(state: RegistrationState, w: RegistrationWindows): string {
  if (state === 'open') return ABILITY;
  if (state === 'closed') return `Registration is closed. ${ABILITY}`;
  const dates = datesSentence(w);
  return dates ? `${dates}. ${ABILITY}` : `Registration opens soon. ${ABILITY}`;
}

/** "2026 registration: returning members Aug 28 · new members Sep 3" */
export function cardNote(year: number, w: RegistrationWindows): string | null {
  const { returning, fresh } = openingDays(w);
  const parts: string[] = [];
  if (returning) parts.push(`returning members ${returning}`);
  if (fresh) parts.push(`new members ${fresh}`);
  return parts.length ? `${year} registration: ${parts.join(' · ')}` : null;
}
