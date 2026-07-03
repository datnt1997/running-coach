// Daniels–Gilbert VDOT model.
// Converts a race performance (distance + time) into a VDOT score — the
// same VO2max proxy professional coaches use to set training paces.

export const RACE_DISTANCES = {
  '5k': { meters: 5000, label: '5K', timeHint: 'MM:SS', placeholder: '24:30' },
  '10k': { meters: 10000, label: '10K', timeHint: 'MM:SS', placeholder: '52:00' },
  half_marathon: { meters: 21097.5, label: 'Half Marathon', timeHint: 'H:MM:SS', placeholder: '1:55:00' },
  full_marathon: { meters: 42195, label: 'Marathon', timeHint: 'H:MM:SS', placeholder: '4:00:00' },
}

// "MM:SS" or "H:MM:SS" / "HH:MM:SS" → total seconds, or null if invalid.
export function parseTimeToSeconds(str) {
  const parts = String(str).split(':').map(p => p.trim())
  if (parts.length < 2 || parts.length > 3) return null
  if (parts.some(p => p === '' || !/^\d+$/.test(p))) return null
  const nums = parts.map(Number)
  const seconds = parts.length === 2
    ? nums[0] * 60 + nums[1]
    : nums[0] * 3600 + nums[1] * 60 + nums[2]
  return seconds > 0 ? seconds : null
}

// Daniels–Gilbert formula. distanceMeters + timeSeconds → VDOT (float).
export function vdotFromRace(distanceMeters, timeSeconds) {
  const minutes = timeSeconds / 60
  const velocity = distanceMeters / minutes // metres per minute
  const vo2 = -4.6 + 0.182258 * velocity + 0.000104 * velocity * velocity
  const pctMax =
    0.8 +
    0.1894393 * Math.exp(-0.012778 * minutes) +
    0.2989558 * Math.exp(-0.1932605 * minutes)
  return vo2 / pctMax
}

// VDOT → fitness level. Thresholds match the backend chat classifier.
export function levelFromVdot(vdot) {
  if (vdot < 35) return 'beginner'
  if (vdot <= 50) return 'intermediate'
  return 'advanced'
}

// Convenience: race distance key + time string → { vdot, level } or null.
export function assessRace(distanceKey, timeStr) {
  const dist = RACE_DISTANCES[distanceKey]
  const seconds = parseTimeToSeconds(timeStr)
  if (!dist || !seconds) return null
  const raw = vdotFromRace(dist.meters, seconds)
  if (!Number.isFinite(raw) || raw < 20 || raw > 90) return null
  const vdot = Math.round(raw)
  return { vdot, level: levelFromVdot(vdot) }
}

// Convenience: raw VDOT input → { vdot, level } or null.
export function assessVdot(vdotInput) {
  const v = Number(vdotInput)
  if (!Number.isFinite(v) || v < 20 || v > 85) return null
  const vdot = Math.round(v)
  return { vdot, level: levelFromVdot(vdot) }
}
