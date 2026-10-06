import { getEntry } from 'astro:content';

import { fetchSeasonData } from '@/lib/seasonData';
import {
  deriveRegistrationState,
  type RegistrationState,
  type RegistrationWindows,
} from '@/lib/registrationState';

export interface RegistrationCta {
  /** Derived from the database windows, never authored. */
  state: RegistrationState;
  windows: RegistrationWindows;
  source: 'api' | 'fallback';
  generated_at: string | null;
  label_open: string;
  url_open?: string;
  label_coming_soon: string;
  url_coming_soon?: string;
  label_closed: string;
  url_closed?: string;
}

// Resolves the registration CTA for every consumer (nav, mobile menu, hero,
// strip). Labels and urls stay editorial in Keystatic; the STATE and the dates
// come from the app database, because a human toggle is exactly what used to
// drift out of sync with reality.
//
// With no season data the state is `closed`, which is the safe direction.
// Falling back to `open` would send members at a form that may refuse them.
// A fallback build doesn't really know the state, though, so its closed CTA
// goes to tcsc.ski rather than the /join interest list: registration may be
// open, and the app reads the database live and shows either the Register
// button or its own interest form.
export async function getRegistrationCta(): Promise<RegistrationCta> {
  const home = await getEntry('home', 'home');
  const d = home?.data;
  const season = await fetchSeasonData();
  const windows: RegistrationWindows = season.primary ?? {};
  const unknown = season.source === 'fallback';

  return {
    state: deriveRegistrationState(windows, Date.now()),
    windows,
    source: season.source,
    generated_at: season.generated_at,
    label_open: d?.cta_open_label ?? 'Register for the season',
    url_open: d?.cta_open_url ?? 'https://tcsc.ski/',
    label_coming_soon: d?.cta_coming_soon_label ?? 'Get on the list',
    // Falls back like every other variant: a url-less coming_soon means
    // CtaForState renders a dead <span> and, before this fix, the flip could
    // not restore a clickable <a> once the state changed away from it.
    url_coming_soon: d?.cta_coming_soon_url ?? d?.cta_closed_url ?? '/join',
    label_closed: unknown ? 'How to register' : (d?.cta_closed_label ?? 'Registration'),
    url_closed: unknown ? 'https://tcsc.ski/' : (d?.cta_closed_url ?? '/join'),
  };
}
