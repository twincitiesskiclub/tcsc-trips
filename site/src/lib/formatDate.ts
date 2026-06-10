// Date formatters for content-collection dates.
//
// WHY timeZone: 'UTC' (verified empirically): unquoted YAML dates
// (`date: 2026-12-12`) parse as UTC-midnight JS Dates through
// z.coerce.date(). Formatting in the build machine's local zone
// (US Central) shifts them back a day ("Friday, December 11" instead of
// "Saturday, December 12"), so every formatter here pins the zone to UTC.

/** "Saturday, December 12, 2026" */
export const longDate = (d: Date) =>
  d.toLocaleDateString('en-US', {
    weekday: 'long',
    month: 'long',
    day: 'numeric',
    year: 'numeric',
    timeZone: 'UTC',
  });

/** "Dec 12" */
export const shortDate = (d: Date) =>
  d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', timeZone: 'UTC' });
