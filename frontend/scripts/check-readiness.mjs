// Pins the low-load recommendation: below either minimum warns, at or above both does not.
import { RECOMMENDED_LOAD, loadAdvice } from '../src/lib/readiness.js'

let failed = false
const fail = msg => { console.error('FAIL', msg); failed = true }

const CASES = [
  // distance, weekly, longest, warns
  ['half_marathon', 20, 10, true],   // both low
  ['half_marathon', 40, 8, true],    // long run low
  ['half_marathon', 20, 14, true],   // week low
  ['half_marathon', 25, 12, false],  // exactly the minimum
  ['half_marathon', 50, 22, false],
  ['full_marathon', 30, 14, true],
  ['full_marathon', 40, 18, false],
  ['full_marathon', 60, 25, false],
  ['5k', 5, 2, false],               // no recommendation for other races
  ['half_marathon', '', 10, false],  // unusable numbers are not judged
]
for (const [dist, w, l, warns] of CASES) {
  const got = loadAdvice(dist, w, l) !== null
  if (got !== warns) fail(`${dist} ${w} km/week, ${l} km long: warns ${got}, want ${warns}`)
}
if (loadAdvice('half_marathon', 20, 10) !== RECOMMENDED_LOAD.half_marathon) fail('advice should return the recommended load')

if (failed) process.exit(1)
console.log('readiness ok')
