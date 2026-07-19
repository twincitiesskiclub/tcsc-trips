// Lightbox controller for PhotoMosaic tiles.
//
// Lifecycle assumptions (mirrors MobileNavPanel): no ClientRouter / view
// transitions, at most one PhotoMosaic and one Lightbox per page. init() is
// guarded so double-inclusion cannot double-bind listeners.
//
// RESOLUTION CONTRACT: items are built from each tile's data-full /
// data-full-srcset attributes (full-resolution getImage() output computed
// server-side in PhotoMosaic.astro). NEVER read the tile <img>'s
// src/currentSrc here; that is the small grid-optimized variant, which is
// exactly the prior shipped bug (305px images stretched fullscreen).

import { lockPageScroll, unlockPageScroll } from '@/lib/pageScrollLock';

type Item = { full: string; fullSrcset: string; alt: string; caption: string };

let bound = false;

export function init() {
  if (bound) return;
  const mosaic = document.querySelector<HTMLElement>('[data-photo-mosaic]');
  const box = document.querySelector<HTMLElement>('[data-lightbox]');
  if (!mosaic || !box) return;

  const img = box.querySelector<HTMLImageElement>('[data-lightbox-img]');
  const captionEl = box.querySelector<HTMLElement>('[data-lightbox-caption]');
  const closeBtn = box.querySelector<HTMLButtonElement>('[data-lightbox-close]');
  const prevBtn = box.querySelector<HTMLButtonElement>('[data-lightbox-prev]');
  const nextBtn = box.querySelector<HTMLButtonElement>('[data-lightbox-next]');
  if (!img || !captionEl || !closeBtn || !prevBtn || !nextBtn) return;
  bound = true;

  const tiles = Array.from(mosaic.querySelectorAll<HTMLButtonElement>('button[data-full]'));
  const items: Item[] = tiles.map((t) => ({
    full: t.dataset.full ?? '',
    fullSrcset: t.dataset.fullSrcset ?? '',
    alt: t.dataset.alt ?? '',
    caption: t.dataset.caption ?? '',
  }));
  if (items.length === 0) return;

  let index = 0;
  let invoker: HTMLElement | null = null;
  const isOpen = () => !box.classList.contains('hidden');

  // Hard-cut rendering per spec: swap content immediately, no transitions.
  function render(i: number) {
    index = (i + items.length) % items.length; // wraparound both directions
    const item = items[index];
    // Clear the previous photo before assigning the next one: on slow
    // connections the old image would otherwise linger (with the new alt and
    // caption already swapped in) until the new bytes arrive.
    img!.removeAttribute('src');
    img!.removeAttribute('srcset');
    img!.alt = item.alt;
    if (item.fullSrcset) img!.setAttribute('srcset', item.fullSrcset);
    img!.setAttribute('sizes', '100vw');
    img!.src = item.full;
    // Caption line doubles as the aria-live announcement; the position
    // suffix means caption-less photos still announce navigation.
    const position = `Photo ${index + 1} of ${items.length}`;
    captionEl!.textContent = item.caption ? `${item.caption} · ${position}` : position;
    preloadNeighbors();
  }

  // Warm the browser cache for the adjacent photos so prev/next swaps do
  // not hard-cut to a blank frame on slow connections.
  function preloadNeighbors() {
    for (const offset of [-1, 1]) {
      const neighbor = items[(index + offset + items.length) % items.length];
      const pre = new Image();
      pre.sizes = '100vw';
      if (neighbor.fullSrcset) pre.srcset = neighbor.fullSrcset;
      pre.src = neighbor.full;
    }
  }

  function open(i: number, from: HTMLElement) {
    invoker = from; // restore focus here on close
    render(i);
    box!.classList.remove('hidden');
    box!.classList.add('flex');
    box!.setAttribute('aria-hidden', 'false');
    lockPageScroll();
    closeBtn!.focus();
  }

  function close() {
    box!.classList.add('hidden');
    box!.classList.remove('flex');
    box!.setAttribute('aria-hidden', 'true');
    unlockPageScroll();
    invoker?.focus({ preventScroll: true });
    invoker = null;
  }

  tiles.forEach((tile, i) => tile.addEventListener('click', () => open(i, tile)));
  closeBtn.addEventListener('click', close);
  prevBtn.addEventListener('click', () => render(index - 1));
  nextBtn.addEventListener('click', () => render(index + 1));

  // Keyboard shortcuts only while open.
  document.addEventListener('keydown', (e) => {
    if (!isOpen()) return;
    if (e.key === 'Escape') close();
    else if (e.key === 'ArrowLeft') {
      e.preventDefault(); // keep arrows from scrolling/moving focus
      render(index - 1);
    } else if (e.key === 'ArrowRight') {
      e.preventDefault();
      render(index + 1);
    }
  });

  // Wrap Tab focus inside the open lightbox (MobileNavPanel pattern).
  box.addEventListener('keydown', (e) => {
    if (e.key !== 'Tab') return;
    const focusables = box.querySelectorAll<HTMLElement>('button');
    const first = focusables[0];
    const last = focusables[focusables.length - 1];
    if (!first || !last) return;
    if (e.shiftKey && document.activeElement === first) {
      e.preventDefault();
      last.focus();
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault();
      first.focus();
    }
  });
}
