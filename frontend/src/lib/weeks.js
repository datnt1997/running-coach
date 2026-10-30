// Maps a plan's start date + total weeks to "which week is happening now".

// "YYYY-MM-DD" → local midnight Date (avoids UTC parsing off-by-one at day boundaries).
function parseLocalDate(isoDate) {
  const [y, m, d] = isoDate.split('-').map(Number)
  return new Date(y, m - 1, d)
}

function daysBetween(a, b) {
  const MS_PER_DAY = 24 * 60 * 60 * 1000
  return Math.floor((b.getTime() - a.getTime()) / MS_PER_DAY)
}

// Returns { weekNumber, status, daysUntilStart } for a plan given its startDate/totalWeeks.
// status: 'upcoming' (before start), 'active' (mid-plan), 'finished' (past last week).
export function currentWeekNumber(startDate, totalWeeks, today = new Date()) {
  const start = parseLocalDate(startDate)
  const todayMidnight = new Date(today.getFullYear(), today.getMonth(), today.getDate())
  const daysSinceStart = daysBetween(start, todayMidnight)

  if (daysSinceStart < 0) {
    return { weekNumber: 1, status: 'upcoming', daysUntilStart: -daysSinceStart }
  }

  const rawWeek = Math.floor(daysSinceStart / 7) + 1
  if (rawWeek > totalWeeks) {
    return { weekNumber: totalWeeks, status: 'finished', daysUntilStart: 0 }
  }

  return { weekNumber: rawWeek, status: 'active', daysUntilStart: 0 }
}
