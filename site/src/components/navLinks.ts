import { getEntry } from 'astro:content';

export interface NavLink {
  label: string;
  href: string;
}

// Fallback links for when the `nav` content singleton hasn't been authored
// yet. Once src/content/nav.yaml exists, its top_links win (see getNavLinks).
export const navLinks: NavLink[] = [
  { label: 'About', href: '/about' },
  { label: 'Community', href: '/community' },
  { label: 'Racing', href: '/racing' },
  { label: 'Coaches', href: '/coaches' },
  { label: 'Wax Room', href: '/wax-room' },
  { label: 'Sponsors', href: '/sponsors' },
];

/**
 * Active-state test for nav links: true when `pathname` is the link target
 * or any deeper path within its section (/wax-room/xyz highlights Wax Room).
 * Generated `.html` filenames and trailing slashes are normalized to the
 * public extensionless form. Shared by Nav and MobileNavPanel.
 */
export function isActiveLink(href: string, pathname: string): boolean {
  const norm = (p: string) => {
    let normalized = p === '/index.html' ? '/' : p.replace(/\.html$/, '');
    if (normalized !== '/' && normalized.endsWith('/')) normalized = normalized.slice(0, -1);
    return normalized;
  };
  const target = norm(href);
  const current = norm(pathname);
  return current === target || current.startsWith(target + '/');
}

/**
 * Top-level nav links from the `nav` singleton, falling back to the constant
 * when the singleton is missing or empty. Used by Nav, MobileNavPanel, Footer.
 */
export async function getNavLinks(): Promise<NavLink[]> {
  const nav = await getEntry('nav', 'nav');
  const links = nav?.data.top_links;
  return links && links.length > 0 ? links : navLinks;
}
