import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { t } from '../i18n/index.js'
import { distanceLabel, levelLabel } from '../lib/labels.js'

function StatusBadge({ status }) {
  const known = ['ready', 'generating', 'failed'].includes(status)
  const cls = known ? `status-${status}` : ''
  return <span className={`status-badge ${cls}`}>{known ? t(`status.${status}`) : status}</span>
}

export default function GoalHistory() {
  const [goals, setGoals] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [deleting, setDeleting] = useState(null)

  async function load() {
    try {
      const res = await fetch('/goals')
      if (!res.ok) throw new Error('Failed to load')
      const data = await res.json()
      setGoals(data.goals)
    } catch {
      setError(t('history.loadError'))
    } finally {
      setLoading(false)
    }
  }

  async function handleDelete(goalId) {
    if (!confirm(t('history.confirmDelete'))) return
    setDeleting(goalId)
    try {
      const res = await fetch(`/goal/${goalId}`, { method: 'DELETE' })
      if (!res.ok) throw new Error()
      setGoals(g => g.filter(x => x.goalId !== goalId))
    } catch {
      alert(t('history.deleteFailed'))
    } finally {
      setDeleting(null)
    }
  }

  useEffect(() => { load() }, [])

  if (loading) return <p>{t('common.loading')}</p>
  if (error) return <p className="api-error">{error}</p>

  return (
    <div className="history-page">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem' }}>
        <h1 style={{ margin: 0 }}>{t('history.title')}</h1>
        <Link to="/new"><button>{t('history.new')}</button></Link>
      </div>

      {goals.length === 0 ? (
        <p style={{ color: '#6c757d' }}>
          {t('history.empty')} <Link to="/new">{t('dashboard.createFirst')}</Link>
        </p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>{t('history.submitted')}</th>
              <th>{t('table.distance')}</th>
              <th>{t('history.target')}</th>
              <th>{t('history.raceDate')}</th>
              <th>{t('history.fitness')}</th>
              <th>{t('history.status')}</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {goals.map(g => (
              <tr key={g.goalId}>
                <td style={{ whiteSpace: 'nowrap' }}>{g.createdAt.slice(0, 10)}</td>
                <td>{distanceLabel(g.distance)}</td>
                <td>{g.targetTime}</td>
                <td>{g.raceDate}</td>
                <td>{levelLabel(g.fitnessLevel)}</td>
                <td><StatusBadge status={g.planStatus} /></td>
                <td>
                  <div className="row-actions">
                    {g.planStatus !== 'failed' && (
                      <Link to={`/goals/${g.goalId}`}>
                        <button className="btn-sm">
                          {g.planStatus === 'ready' ? t('history.viewPlan') : t('history.track')}
                        </button>
                      </Link>
                    )}
                    <button
                      className="btn-danger btn-sm"
                      disabled={deleting === g.goalId}
                      onClick={() => handleDelete(g.goalId)}
                    >
                      {deleting === g.goalId ? '…' : t('history.delete')}
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}
