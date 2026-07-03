import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

const DISTANCE_LABEL = {
  half_marathon: 'Half Marathon',
  full_marathon: 'Full Marathon',
}

const FITNESS_LABEL = {
  beginner: 'Beginner',
  intermediate: 'Intermediate',
  advanced: 'Advanced',
}

function StatusBadge({ status }) {
  const map = {
    ready: ['status-ready', 'Ready'],
    generating: ['status-generating', 'Generating…'],
    failed: ['status-failed', 'Failed'],
  }
  const [cls, label] = map[status] || ['', status]
  return <span className={`status-badge ${cls}`}>{label}</span>
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
      setError('Failed to load goal history.')
    } finally {
      setLoading(false)
    }
  }

  async function handleDelete(goalId) {
    if (!confirm('Delete this goal and its training plan?')) return
    setDeleting(goalId)
    try {
      const res = await fetch(`/goal/${goalId}`, { method: 'DELETE' })
      if (!res.ok) throw new Error()
      setGoals(g => g.filter(x => x.goalId !== goalId))
    } catch {
      alert('Delete failed — please try again.')
    } finally {
      setDeleting(null)
    }
  }

  useEffect(() => { load() }, [])

  if (loading) return <p>Loading…</p>
  if (error) return <p className="api-error">{error}</p>

  return (
    <div className="history-page">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem' }}>
        <h1 style={{ margin: 0 }}>Goal History</h1>
        <Link to="/"><button>+ New Goal</button></Link>
      </div>

      {goals.length === 0 ? (
        <p style={{ color: '#6c757d' }}>
          No goals yet. <Link to="/">Create your first goal.</Link>
        </p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Submitted</th>
              <th>Distance</th>
              <th>Target</th>
              <th>Race Date</th>
              <th>Fitness</th>
              <th>Status</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {goals.map(g => (
              <tr key={g.goalId}>
                <td style={{ whiteSpace: 'nowrap' }}>{g.createdAt.slice(0, 10)}</td>
                <td>{DISTANCE_LABEL[g.distance] || g.distance}</td>
                <td>{g.targetTime}</td>
                <td>{g.raceDate}</td>
                <td>{FITNESS_LABEL[g.fitnessLevel] || g.fitnessLevel}</td>
                <td><StatusBadge status={g.planStatus} /></td>
                <td>
                  <div className="row-actions">
                    {g.planStatus !== 'failed' && (
                      <Link to={`/goals/${g.goalId}`}>
                        <button className="btn-sm">
                          {g.planStatus === 'ready' ? 'View Plan' : 'Track'}
                        </button>
                      </Link>
                    )}
                    <button
                      className="btn-danger btn-sm"
                      disabled={deleting === g.goalId}
                      onClick={() => handleDelete(g.goalId)}
                    >
                      {deleting === g.goalId ? '…' : 'Delete'}
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
