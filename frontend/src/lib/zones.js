// Display text for a Planned workout's heart-rate target, as the API sends it:
// { minZone, maxZone, min, max } (min is null for Z1), or null when there is none.
export function targetZoneText(target) {
  if (!target) return null
  const zone = target.minZone === target.maxZone
    ? `Z${target.minZone}`
    : `Z${target.minZone}-Z${target.maxZone}`
  const bpm = target.min == null ? `≤ ${target.max}` : `${target.min}–${target.max}`
  return `${zone} · ${bpm} bpm`
}
