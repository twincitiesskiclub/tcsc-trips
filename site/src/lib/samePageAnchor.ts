// Does this href point at a fragment of the page it is already on?
//
// Such a link never navigates: the browser only scrolls. Two places on the
// home page break on that, and both are easy to reintroduce, so the check
// lives here rather than being reasoned about twice.
//
//   1. The bottom CTA strip IS <section id="registration">. A CTA url of
//      `https://twincitiesskiclub.org/#registration` (what the `coming_soon`
//      state carries, so the hero and nav can scroll down to the strip) makes
//      the strip's own button a dead click.
//   2. The mobile menu is a fixed overlay over a scroll-locked body. A
//      same-page anchor click inside it never reloads, so nothing dismisses
//      the overlay and the click looks ignored.
//
// Authored urls come from Keystatic as absolute urls, so a self-link does not
// look like a bare '#registration' — it has to be resolved to be recognised.
export function isSamePageAnchor(
  href: string | null | undefined,
  pageHref: string,
): boolean {
  if (!href) return false;

  let link: URL;
  let page: URL;
  try {
    page = new URL(pageHref);
    link = new URL(href, page);
  } catch {
    return false;
  }

  if (!link.hash) return false;
  if (link.origin !== page.origin) return false;

  // Normalise an explicit index file away before comparing. Production builds
  // with TCSC_EDGE_CONFIG=true, which sets Astro's build.format to 'file' and
  // trailingSlash to 'never', so the home page's own url is /index.html while
  // the authored anchor is /#registration. Comparing those raw made this
  // return false in production only -- the guard silently stopped firing and
  // the CTA strip went back to linking at its own section.
  const path = (url: URL) => url.pathname.replace(/\/index\.html?$/i, '').replace(/\/+$/, '');
  return path(link) === path(page);
}
