// Re-derive the registration state in the browser.
//
// The site is a static build, so the state baked into the HTML is only true
// as of the last deploy. Rather than rebuild on a schedule or call an API on
// every page load, the CTA carries the real window timestamps and every
// state's copy; this picks the right variant for the CURRENT time. That makes
// the site correct at the exact minute registration opens, with no network.
//
// It holds no copy and formats no dates -- it only chooses among variants the
// build already rendered.
import { deriveRegistrationState } from '@/lib/registrationState';

type Variant = 'open' | 'coming_soon' | 'closed';

const ATTR: Record<Variant, { label: string; url: string }> = {
  open: { label: 'data-open-label', url: 'data-open-url' },
  coming_soon: { label: 'data-soon-label', url: 'data-soon-url' },
  closed: { label: 'data-closed-label', url: 'data-closed-url' },
};

function orNull(value: string | null): string | null {
  return value ? value : null;
}

for (const element of document.querySelectorAll<HTMLElement>('[data-registration]')) {
  const actual = deriveRegistrationState(
    {
      returning_start: orNull(element.getAttribute('data-returning-start')),
      returning_end: orNull(element.getAttribute('data-returning-end')),
      new_start: orNull(element.getAttribute('data-new-start')),
      new_end: orNull(element.getAttribute('data-new-end')),
    },
    Date.now(),
  );

  if (actual === element.getAttribute('data-state')) continue;

  const { label, url } = ATTR[actual];
  const nextLabel = element.getAttribute(label);
  const nextUrl = element.getAttribute(url);
  if (nextLabel) element.textContent = nextLabel;
  // hasAttribute rather than `instanceof HTMLAnchorElement`: the disabled
  // variant renders a <span> with no href, and an instanceof check would also
  // drag a DOM global into the jsdom test harness for no benefit.
  if (nextUrl && element.hasAttribute('href')) element.setAttribute('href', nextUrl);
  element.setAttribute('data-state', actual);
}
