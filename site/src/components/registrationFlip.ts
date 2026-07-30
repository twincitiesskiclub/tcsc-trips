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

const SUBHEAD_ATTR: Record<Variant, string> = {
  open: 'data-open-subhead',
  coming_soon: 'data-soon-subhead',
  closed: 'data-closed-subhead',
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
  // A variant with no url must not inherit the previous state's href: that
  // would leave the CTA showing one state's label while linking to another
  // state's destination. Dropping the attribute matches how the build renders
  // a url-less variant (CtaForState emits a plain <span>).
  if (element.hasAttribute('href')) {
    if (nextUrl) element.setAttribute('href', nextUrl);
    else element.removeAttribute('href');
  }
  element.setAttribute('data-state', actual);

  // The CTA strip's subhead lives beside its CTA, not inside it, so it can't
  // be found by descending from `element` -- climb to the shared section and
  // look there. Other `[data-registration]` elements (hero, nav, mobile menu)
  // have no such sibling, so this is a no-op for them.
  const subhead = element.closest('section')?.querySelector<HTMLElement>('[data-registration-subhead]');
  if (subhead) {
    const nextSubhead = subhead.getAttribute(SUBHEAD_ATTR[actual]);
    if (nextSubhead) subhead.textContent = nextSubhead;
  }
}
