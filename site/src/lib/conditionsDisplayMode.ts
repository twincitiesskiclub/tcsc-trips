type ConditionsPayload = {
  error?: unknown;
  locations?: unknown;
};

export type ConditionsDisplayMode = 'off-season' | 'live' | 'unavailable';

export function conditionsDisplayMode(
  payload: unknown,
  at = new Date(),
): ConditionsDisplayMode {
  const month = at.getMonth() + 1;
  if (month >= 4 && month <= 10) return 'off-season';

  if (typeof payload !== 'object' || payload === null) return 'unavailable';
  const { error, locations } = payload as ConditionsPayload;
  return !error && Array.isArray(locations) && locations.length > 0
    ? 'live'
    : 'unavailable';
}
