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
// With no season data the state is `closed`, which is the safe direction: its
// destination is tcsc.ski, which reads the database live and shows the real
// opening date regardless of what this static build believes. Falling back to
// `open` would send members at a form that may refuse them.
export async function getRegistrationCta(): Promise<RegistrationCta> {
  const home = await getEntry('home', 'home');
  const d = home?.data;
  const season = await fetchSeasonData();
  const windows: RegistrationWindows = season.primary ?? {};

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
    url_coming_soon: d?.cta_coming_soon_url ?? d?.cta_closed_url ?? 'https://tcsc.ski/',
    label_closed: d?.cta_closed_label ?? 'Register',
    url_closed: d?.cta_closed_url ?? 'https://tcsc.ski/',
  };
}
