// The state matrix as data. One entry per screenshot target.
//   build:        which builds/<name>/ to serve (open | soon | closed | populated)
//   conditions:   how the browser's /conditions fetch is answered: live | dryland | unavailable (aborted)
//   clock:        ISO time to freeze the browser clock at (only for the winter "unavailable" strip)
//   viewports:    subset of mobile | tablet | desktop (default mobile + desktop)
//   viewportOnly: capture the viewport, not the full page
//   actions:      { click: sel } | { waitFor: sel } | { scroll: y } | { wait: ms } | { hover: sel } | { press: key }
const OPEN = "open";

export const STATES = [
  // home, registration states (the CTA renders in nav, mobile panel, hero, and CTA strip)
  { id: "home-open", surface: "home", state: "open", build: "open", url: "/", conditions: "live" },
  { id: "home-soon", surface: "home", state: "soon", build: "soon", url: "/", conditions: "live" },
  { id: "home-closed", surface: "home", state: "closed", build: "closed", url: "/", conditions: "live" },
  // home, conditions strip states (registration open throughout)
  { id: "home-dryland", surface: "home", state: "dryland", build: OPEN, url: "/", conditions: "dryland" },
  { id: "home-unavailable", surface: "home", state: "unavailable", build: OPEN, url: "/", conditions: "unavailable",
    clock: "2027-01-15T18:00:00Z" }, // winter: an error payload renders "No report" instead of "Dryland season"
  { id: "home-birkie-hover", surface: "home", state: "birkie-hover", build: OPEN, url: "/", conditions: "live",
    viewports: ["desktop"], actions: [{ hover: "[data-birkie]" }, { wait: 300 }], viewportOnly: true },
  // home, content states
  { id: "home-wax-feed", surface: "home", state: "wax-feed", build: "populated", url: "/", conditions: "live",
    actions: [{ scrollIntoView: "section:has(a[href='/wax-room'])" }, { wait: 300 }], viewportOnly: true },
  { id: "home-hero", surface: "home", state: "hero", build: OPEN, url: "/", conditions: "live",
    viewports: ["mobile", "tablet", "desktop"], actions: [{ wait: 600 }], viewportOnly: true },
  { id: "home-mobile-nav", surface: "home", state: "mobile-nav", build: OPEN, url: "/", conditions: "live",
    viewports: ["mobile"], actions: [{ click: "button[aria-label='Open menu']" }, { wait: 400 }], viewportOnly: true },
  { id: "home-lightbox", surface: "home", state: "lightbox", build: OPEN, url: "/", conditions: "live",
    actions: [{ click: "[data-photo-mosaic] button" }, { waitFor: "[data-lightbox][aria-hidden='false']" }, { wait: 400 }], viewportOnly: true },
  { id: "home-mosaic-hover", surface: "home", state: "mosaic-hover", build: OPEN, url: "/", conditions: "live",
    viewports: ["desktop"], actions: [{ hover: "[data-photo-mosaic] button" }, { wait: 300 }], viewportOnly: true },
  // inner pages
  { id: "about", surface: "about", state: "open", build: OPEN, url: "/about", conditions: "live" },
  { id: "about-closed", surface: "about", state: "closed", build: "closed", url: "/about", conditions: "live" },
  { id: "community", surface: "community", state: "default", build: OPEN, url: "/community", conditions: "live" },
  { id: "racing", surface: "racing", state: "default", build: OPEN, url: "/racing", conditions: "live" },
  { id: "dry-tri", surface: "dry-tri", state: "default", build: OPEN, url: "/dry-tri", conditions: "live" },
  { id: "extra-training", surface: "extra-training-fun", state: "default", build: OPEN, url: "/extra-training-fun", conditions: "live" },
  { id: "coaches", surface: "coaches", state: "default", build: OPEN, url: "/coaches", conditions: "live" },
  { id: "sponsors", surface: "sponsors", state: "default", build: OPEN, url: "/sponsors", conditions: "live" },
  { id: "trips-empty", surface: "trips", state: "empty", build: OPEN, url: "/trips", conditions: "live" },
  { id: "trips-populated", surface: "trips", state: "populated", build: "populated", url: "/trips", conditions: "live" },
  { id: "wax-room-empty", surface: "wax-room", state: "empty", build: OPEN, url: "/wax-room", conditions: "live" },
  { id: "wax-room-populated", surface: "wax-room", state: "populated", build: "populated", url: "/wax-room", conditions: "live" },
  { id: "wax-entry", surface: "wax-entry", state: "default", build: "populated", url: "/wax-room/first-snow-wax", conditions: "live" },
  { id: "not-found", surface: "404", state: "default", build: OPEN, url: "/this-does-not-exist", conditions: "live" },
];
