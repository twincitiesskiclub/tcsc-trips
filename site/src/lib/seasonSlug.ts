// The database stores season_type as 'fall/winter'; the content collection
// keys the same season as the file `fall-winter.yaml`. One character apart,
// and worth naming rather than inlining a .replace() at the call site.
export function seasonTypeToSlug(seasonType: string | null | undefined): string {
  if (!seasonType) return '';
  return seasonType.replace(/\//g, '-');
}
