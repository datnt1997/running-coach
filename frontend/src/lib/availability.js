// Weekly availability: per weekday, how many workouts (0-2), the longest distance
// for one workout (or none), and whether Quality workouts are allowed.
// Limits mirror app/models/goal.py.

export const WEEKDAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
export const MIN_TRAINING_DAYS = 3
export const MAX_WORKOUT_KM = 60

const day = (name, slots, maxKm = null, qualityAllowed = true) => ({
  day: name, slots, maxKm, qualityAllowed,
})

// Same as the old default of four days a week.
export function defaultWeek() {
  return WEEKDAYS.map(d => day(d, ['Mon', 'Wed', 'Fri', 'Sat'].includes(d) ? 1 : 0))
}

export const PRESETS = {
  sameEveryDay: () => WEEKDAYS.map(d => day(d, 1)),
  weekdaysShort: () =>
    WEEKDAYS.map(d =>
      ['Sat', 'Sun'].includes(d) ? day(d, 1) : day(d, 1, 8, false),
    ),
}

// A Training day has at least one slot; two slots on one day still count once.
export function trainingDays(week) {
  return week.filter(d => d.slots > 0).length
}

// Returns an i18n key for the first problem, or null. A rest day ignores its cap.
export function availabilityError(week) {
  if (trainingDays(week) < MIN_TRAINING_DAYS) return 'goal.availabilityMinDays'
  const badCap = week.some(
    d => d.slots > 0 && d.maxKm !== null && !(d.maxKm > 0 && d.maxKm <= MAX_WORKOUT_KM),
  )
  return badCap ? 'goal.availabilityCap' : null
}
