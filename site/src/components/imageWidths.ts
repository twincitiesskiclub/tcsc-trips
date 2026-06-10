// Responsive width presets for astro:assets <Image>/<Picture> `widths`.
//
// LESSON (do not re-learn it): never pre-filter these against the source
// image's intrinsic width. Astro's image service already clamps every
// requested width to the intrinsic width AND appends the intrinsic width
// itself as a srcset candidate; a pre-filter strips that appended full-res
// candidate (e.g. a 1600px source would cap at 1280w and stretch on wide
// screens). Pass the preset straight through.
export const FULL_BLEED = [768, 1280, 1920, 2560]; // 100vw heroes
export const CARD = [400, 800, 1200]; // grid cards / split panels
export const THUMB = [200, 400, 600]; // avatars / small thumbnails
export const MOSAIC = [400, 800, 1200, 1600]; // PhotoMosaic tiles (2-col spans reach ~700px CSS, so 1600 covers 2x DPR)
export const LIGHTBOX = [1024, 1600, 2048]; // fullscreen lightbox viewer (object-contain, up to ~100vw)
