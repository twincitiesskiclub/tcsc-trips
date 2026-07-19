type ConditionsPayload = {
  error?: unknown;
  locations?: unknown;
};

export type ConditionsDisplayMode = 'off-season' | 'live' | 'unavailable';

export function conditionsDisplayMode(
  payload: unknown,
  at = new Date(),
): ConditionsDisplayMode {
  if (typeof payload === 'object' && payload !== null) {
    const { error, locations } = payload as ConditionsPayload;
    if (!error && Array.isArray(locations) && locations.length > 0) {
      return 'live';
    }
  }

  const month = at.getMonth() + 1;
  return month >= 4 && month <= 10 ? 'off-season' : 'unavailable';
}
