// Keeps src/lib/vdot.js in step with app/vdot.py. Uses rows of Daniels Table 5.6
// (printed race times at exact VDOTs), the same fixtures as tests/test_vdot.py.
import { plannerLabel, vdotFromRace } from '../src/lib/vdot.js'

const secs = t => t.split(':').reduce((n, p) => n * 60 + Number(p), 0)
const ROWS = [
  [35.0, '26:59', '56:03', '2:04:13', '4:16:02'],
  [50.0, '19:56', '41:21', '1:31:36', '3:10:49'],
  [65.0, '15:54', '33:01', '1:12:54', '2:32:35'],
  [80.0, '13:18', '27:41', '1:00:55', '2:07:39'],
  [31.4, '29:32', '1:01:24', '2:15:55', '4:39:07'],
  [53.4, '18:50', '39:05', '1:26:30', '3:00:29'],
]
const DISTANCES = [5000, 10000, 21097.5, 42195]

let failed = false
const fail = msg => { console.error('FAIL', msg); failed = true }

for (const [vdot, ...times] of ROWS) {
  times.forEach((t, i) => {
    const got = vdotFromRace(DISTANCES[i], secs(t))
    if (Math.abs(got - vdot) > 0.15) fail(`vdot ${vdot} at ${DISTANCES[i]} m: got ${got.toFixed(2)}`)
  })
}

// Same expectations as test_planner_label in tests/test_vdot.py.
const LABELS = [[20, 'beginner'], [34.9, 'beginner'], [35, 'intermediate'], [40.2, 'intermediate'], [49.9, 'intermediate'], [50, 'advanced'], [80, 'advanced']]
for (const [vdot, label] of LABELS) {
  if (plannerLabel(vdot) !== label) fail(`label for ${vdot}: got ${plannerLabel(vdot)}, want ${label}`)
}

if (failed) process.exit(1)
console.log('vdot parity ok')
