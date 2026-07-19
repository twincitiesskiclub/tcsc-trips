// Shared viewport lock for fullscreen UI. `overflow: hidden` on body alone is
// not reliable in mobile Safari, so pin the body at the current scroll offset
// and lock the root as well. Exact inline values are restored on close.
type ScrollSnapshot = {
  scrollY: number;
  rootOverflow: string;
  bodyOverflow: string;
  bodyPosition: string;
  bodyTop: string;
  bodyLeft: string;
  bodyRight: string;
  bodyWidth: string;
  bodyPaddingRight: string;
};

let depth = 0;
let snapshot: ScrollSnapshot | null = null;

export function lockPageScroll() {
  depth += 1;
  if (depth > 1) return;

  const root = document.documentElement;
  const body = document.body;
  const scrollY = window.scrollY;
  const scrollbarWidth = Math.max(0, window.innerWidth - root.clientWidth);

  snapshot = {
    scrollY,
    rootOverflow: root.style.overflow,
    bodyOverflow: body.style.overflow,
    bodyPosition: body.style.position,
    bodyTop: body.style.top,
    bodyLeft: body.style.left,
    bodyRight: body.style.right,
    bodyWidth: body.style.width,
    bodyPaddingRight: body.style.paddingRight,
  };

  root.style.overflow = 'hidden';
  body.style.overflow = 'hidden';
  body.style.position = 'fixed';
  body.style.top = `-${scrollY}px`;
  body.style.left = '0';
  body.style.right = '0';
  body.style.width = '100%';
  if (scrollbarWidth > 0) body.style.paddingRight = `${scrollbarWidth}px`;
}

export function unlockPageScroll() {
  if (depth === 0) return;
  depth -= 1;
  if (depth > 0 || !snapshot) return;

  const root = document.documentElement;
  const body = document.body;
  const previous = snapshot;
  snapshot = null;

  root.style.overflow = previous.rootOverflow;
  body.style.overflow = previous.bodyOverflow;
  body.style.position = previous.bodyPosition;
  body.style.top = previous.bodyTop;
  body.style.left = previous.bodyLeft;
  body.style.right = previous.bodyRight;
  body.style.width = previous.bodyWidth;
  body.style.paddingRight = previous.bodyPaddingRight;
  window.scrollTo(0, previous.scrollY);
}
