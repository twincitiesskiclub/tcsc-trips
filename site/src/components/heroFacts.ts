// Shared masthead fact shape: HeroInner renders it, InnerPageLayout passes it
// through, page frontmatters construct it. Lives in a .ts module (like
// imageWidths.ts) rather than a .astro frontmatter export by convention.
export interface Fact {
  value: string;
  label: string;
}
