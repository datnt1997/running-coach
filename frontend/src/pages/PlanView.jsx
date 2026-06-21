import { useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

const POLL_MS = 3000

const PHASE_CLASS = {
  base: 'phase-base',
  build: 'phase-build',
  peak: 'phase-peak',
  taper: 'phase-taper',
}

const DISTANCE_LABEL = {
  half_marathon: 'Half Marathon',
  full_marathon: 'Full Marathon',
}

export default function PlanView() {
  const { goalId } = useParams()
  const [plan, setPlan] = useState(null)
  const [status, setStatus] = useState('generating')
  const [error, setError] = useState(null)
  const timer = useRef(null)

  async function poll() {
    try {
      const res = await fetch(`/goal/${goalId}/plan`)
      if (res.status === 404) {
        setError('Goal not found.')
        clearInterval(timer.current)
        return
      }
      const data = await res.json()
      setStatus(data.status)
      if (data.status === 'ready') {
        setPlan(data)
        clearInterval(timer.current)
      } else if (data.status === 'failed') {
        setError('Plan generation failed. Please go back and try submitting your goal again.')
        clearInterval(timer.current)
      }
    } catch {
      setError('Network error — please refresh.')
      clearInterval(timer.current)
    }
  }

  useEffect(() => {
    poll()
    timer.current = setInterval(poll, POLL_MS)
    return () => clearInterval(timer.current)
  }, [goalId])

  if (error) return (
    <div>
      <p className="api-error" style={{ marginBottom: '1rem' }}>{error}</p>
      <Link to="/">← New goal</Link>
    </div>
  )

  if (status !== 'ready') return (
    <div className="generating">
      <div className="spinner" />
      <p>Generating your training plan…</p>
      <p className="hint">This usually takes 10–15 seconds.</p>
    </div>
  )

  return (
    <div className="plan-page">
      <h1>Your Training Plan</h1>

      <p className="plan-summary">{plan.summary}</p>

      <div className="plan-meta">
        <span className="badge">{plan.totalWeeks} weeks</span>
        {Object.entries(plan.phaseBreakdown).map(([phase, weeks]) => (
          <span key={phase} className={`badge ${PHASE_CLASS[phase] || ''}`}>
            {phase} · {weeks}w
          </span>
        ))}
      </div>

      {plan.weeks.map(week => (
        <details key={week.weekNumber} open={week.weekNumber <= 2}>
          <summary>
            Week {week.weekNumber}
            <span className={`phase-tag ${PHASE_CLASS[week.phase] || ''}`}>
              {week.phase}
            </span>
          </summary>
          <table>
            <thead>
              <tr>
                <th>Day</th>
                <th>Type</th>
                <th>Distance</th>
                <th>Zone</th>
                <th>Notes</th>
              </tr>
            </thead>
            <tbody>
              {week.workouts.map((w, i) => (
                <tr key={i}>
                  <td><strong>{w.day}</strong></td>
                  <td style={{ textTransform: 'capitalize' }}>{w.type}</td>
                  <td>{w.distanceKm} km</td>
                  <td>{w.paceZone}</td>
                  <td style={{ color: '#6c757d', fontSize: '.85rem' }}>{w.notes}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </details>
      ))}

      <p style={{ marginTop: '1.5rem' }}>
        <Link to="/history">← Back to history</Link>
      </p>
    </div>
  )
}
