// Keeps the Weekly availability rules in step across app/models/goal.py,
// src/lib/availability.js and the Vietnamese messages in src/i18n/vi.js.
import { readFileSync } from 'node:fs'
import { MAX_WORKOUT_KM, MIN_TRAINING_DAYS, WEEKDAYS } from '../src/lib/availability.js'
import vi from '../src/i18n/vi.js'

const py = readFileSync(new URL('../../app/models/goal.py', import.meta.url), 'utf8')
const num = name => Number(py.match(new RegExp(`^${name} = (\\d+)`, 'm'))?.[1])
const weekdays = [...(py.match(/^WEEKDAYS = \(([^)]*)\)/m)?.[1] ?? '').matchAll(/"(\w+)"/g)].map(m => m[1])

let failed = false
const fail = msg => { console.error('FAIL', msg); failed = true }

if (num('MAX_WORKOUT_KM') !== MAX_WORKOUT_KM)
  fail(`MAX_WORKOUT_KM: goal.py ${num('MAX_WORKOUT_KM')} vs availability.js ${MAX_WORKOUT_KM}`)
if (num('MIN_TRAINING_DAYS') !== MIN_TRAINING_DAYS)
  fail(`MIN_TRAINING_DAYS: goal.py ${num('MIN_TRAINING_DAYS')} vs availability.js ${MIN_TRAINING_DAYS}`)
if (weekdays.join() !== WEEKDAYS.join())
  fail(`WEEKDAYS: goal.py [${weekdays}] vs availability.js [${WEEKDAYS}]`)
if (!vi['goal.availabilityMinDays'].includes(String(MIN_TRAINING_DAYS)))
  fail(`goal.availabilityMinDays does not mention ${MIN_TRAINING_DAYS}`)
if (!vi['goal.availabilityCap'].includes(String(MAX_WORKOUT_KM)))
  fail(`goal.availabilityCap does not mention ${MAX_WORKOUT_KM}`)

if (failed) process.exit(1)
console.log(`availability parity ok: min ${MIN_TRAINING_DAYS} days, cap ${MAX_WORKOUT_KM} km, ${WEEKDAYS.length} weekdays`)
