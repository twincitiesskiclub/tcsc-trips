import { getEntry } from 'astro:content';

export interface RegistrationCta {
  state: 'open' | 'coming_soon' | 'closed';
  label_open: string;
  url_open?: string;
  label_coming_soon: string;
  url_coming_soon?: string;
  label_closed: string;
  url_closed?: string;
}

// Resolves the registration CTA from the `home` singleton once, for every
// consumer (Nav now; home page composition later). The fallback labels below
// mirror the zod `.default()` values on the `home` collection in
// src/content.config.ts; they only apply when the singleton file is missing
// entirely (zod fills them whenever the entry exists). Keep the two in sync
// so the copy stays single-sourced.
export async function getRegistrationCta(): Promise<RegistrationCta> {
  const home = await getEntry('home', 'home');
  const d = home?.data;
  return {
    state: d?.registration_state ?? 'closed',
    label_open: d?.cta_open_label ?? 'Register for the season →',
    url_open: d?.cta_open_url ?? 'https://tcsc.ski',
    label_coming_soon: d?.cta_coming_soon_label ?? 'Get on the list',
    url_coming_soon: d?.cta_coming_soon_url,
    label_closed: d?.cta_closed_label ?? 'Register',
    url_closed: d?.cta_closed_url ?? 'https://tcsc.ski',
  };
}
