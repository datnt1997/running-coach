import { useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { t } from '../i18n/index.js'
import { dayLabel, phaseLabel, typeLabel } from '../lib/labels.js'

const POLL_MS = 3000

const PHASE_CLASS = {
  base: 'phase-base',
  build: 'phase-build',
  peak: 'phase-peak',
  taper: 'phase-taper',
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
        setError(t('plan.notFound'))
        clearInterval(timer.current)
        return
      }
      const data = await res.json()
      setStatus(data.status)
      if (data.status === 'ready') {
        setPlan(data)
        clearInterval(timer.current)
      } else if (data.status === 'failed') {
        setError(t('plan.failed'))
        clearInterval(timer.current)
      }
    } catch {
      setError(t('plan.networkError'))
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
      <Link to="/new">{t('plan.newGoal')}</Link>
    </div>
  )

  if (status !== 'ready') return (
    <div className="generating">
      <div className="spinner" />
      <p>{t('plan.generating')}</p>
      <p className="hint">{t('plan.generatingHint')}</p>
    </div>
  )

  return (
    <div className="plan-page">
      <h1>{t('plan.title')}</h1>

      <p className="plan-summary">{plan.summary}</p>

      <div className="plan-meta">
        <span className="badge">{t('plan.weeks', { count: plan.totalWeeks })}</span>
        {Object.entries(plan.phaseBreakdown).map(([phase, weeks]) => (
          <span key={phase} className={`badge ${PHASE_CLASS[phase] || ''}`}>
            {t('plan.phaseWeeks', { phase: phaseLabel(phase), count: weeks })}
          </span>
        ))}
      </div>

      {plan.weeks.map(week => (
        <details key={week.weekNumber} open={week.weekNumber <= 2}>
          <summary>
            {t('plan.week', { week: week.weekNumber })}
            <span className={`phase-tag ${PHASE_CLASS[week.phase] || ''}`}>
              {phaseLabel(week.phase)}
            </span>
          </summary>
          <table>
            <thead>
              <tr>
                <th>{t('table.day')}</th>
                <th>{t('table.type')}</th>
                <th>{t('table.distance')}</th>
                <th>{t('table.zone')}</th>
                <th>{t('table.notes')}</th>
              </tr>
            </thead>
            <tbody>
              {week.workouts.map((w, i) => (
                <tr key={i}>
                  <td><strong>{dayLabel(w.day)}</strong></td>
                  <td>{typeLabel(w.type)}</td>
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
        <Link to="/history">{t('plan.backToHistory')}</Link>
      </p>
    </div>
  )
}
