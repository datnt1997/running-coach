// Vietnamese display labels for the English enum values the API returns.
// Unknown values fall back to the raw string.

const DAY = {
  Mon: 'Thứ 2',
  Tue: 'Thứ 3',
  Wed: 'Thứ 4',
  Thu: 'Thứ 5',
  Fri: 'Thứ 6',
  Sat: 'Thứ 7',
  Sun: 'Chủ nhật',
}

const WORKOUT_TYPE = {
  rest: 'Nghỉ',
  easy: 'Chạy nhẹ',
  recovery: 'Hồi phục',
  tempo: 'Tempo',
  interval: 'Interval',
  long: 'Chạy dài',
  cross: 'Tập chéo',
}

const PHASE = {
  base: 'Nền tảng',
  build: 'Tăng tiến',
  peak: 'Đỉnh cao',
  taper: 'Giảm tải',
}

const lookup = (table, value) => table[value] ?? table[String(value).toLowerCase()] ?? value

export const dayLabel = day => lookup(DAY, day)
export const typeLabel = type => lookup(WORKOUT_TYPE, type)
export const phaseLabel = phase => lookup(PHASE, phase)
