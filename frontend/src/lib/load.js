// The runner's current load: total distance in a typical week and the longest
// recent run. Limits mirror app/models/goal.py.

export const MAX_WEEKLY_KM = 250
export const MAX_LONGEST_RUN_KM = 60

// Returns an i18n key for what is wrong, or null when both numbers are usable.
export function loadError(weeklyKm, longestRunKm) {
  const w = Number(weeklyKm)
  const l = Number(longestRunKm)
  if (weeklyKm === '' || longestRunKm === '' || !Number.isFinite(w) || !Number.isFinite(l)) return 'goal.loadRequired'
  if (w < 0 || w > MAX_WEEKLY_KM || l < 0 || l > MAX_LONGEST_RUN_KM) return 'goal.loadRange'
  if (l > w) return 'goal.loadLongest'
  return null
}
