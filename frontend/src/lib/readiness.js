// A recommendation, never a block: is the runner's current load low for the race?
// These minimums are our own rule of thumb (Daniels gives none per race), so they
// live here in one place. The Plan still starts from the current load (see
// STARTING POINT in app/agent/prompt.py).

export const RECOMMENDED_LOAD = {
  half_marathon: { weeklyKm: 25, longestRunKm: 12 },
  full_marathon: { weeklyKm: 40, longestRunKm: 18 },
}

// Returns the recommended load when either number is below it, else null.
export function loadAdvice(distance, weeklyKm, longestRunKm) {
  const rec = RECOMMENDED_LOAD[distance]
  if (!rec || !Number.isFinite(weeklyKm) || !Number.isFinite(longestRunKm)) return null
  return weeklyKm < rec.weeklyKm || longestRunKm < rec.longestRunKm ? rec : null
}
