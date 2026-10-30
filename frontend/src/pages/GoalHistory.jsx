import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

const DISTANCE_LABEL = {
  half_marathon: 'Bán Marathon',
  full_marathon: 'Marathon',
}

const FITNESS_LABEL = {
  beginner: 'Người mới',
  intermediate: 'Trung cấp',
  advanced: 'Nâng cao',
}

function StatusBadge({ status }) {
  const map = {
    ready: ['status-ready', 'Sẵn sàng'],
    generating: ['status-generating', 'Đang tạo…'],
    failed: ['status-failed', 'Thất bại'],
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
      setError('Không thể tải lịch sử mục tiêu.')
    } finally {
      setLoading(false)
    }
  }

  async function handleDelete(goalId) {
    if (!confirm('Xóa mục tiêu này và kế hoạch tập luyện của nó?')) return
    setDeleting(goalId)
    try {
      const res = await fetch(`/goal/${goalId}`, { method: 'DELETE' })
      if (!res.ok) throw new Error()
      setGoals(g => g.filter(x => x.goalId !== goalId))
    } catch {
      alert('Xóa thất bại — vui lòng thử lại.')
    } finally {
      setDeleting(null)
    }
  }

  useEffect(() => { load() }, [])

  if (loading) return <p>Đang tải…</p>
  if (error) return <p className="api-error">{error}</p>

  return (
    <div className="history-page">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem' }}>
        <h1 style={{ margin: 0 }}>Lịch Sử Mục Tiêu</h1>
        <Link to="/new"><button>+ Mục Tiêu Mới</button></Link>
      </div>

      {goals.length === 0 ? (
        <p style={{ color: '#6c757d' }}>
          Chưa có mục tiêu nào. <Link to="/new">Tạo mục tiêu đầu tiên của bạn.</Link>
        </p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Ngày gửi</th>
              <th>Quãng đường</th>
              <th>Mục tiêu</th>
              <th>Ngày thi đấu</th>
              <th>Thể lực</th>
              <th>Trạng thái</th>
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
                          {g.planStatus === 'ready' ? 'Xem kế hoạch' : 'Theo dõi'}
                        </button>
                      </Link>
                    )}
                    <button
                      className="btn-danger btn-sm"
                      disabled={deleting === g.goalId}
                      onClick={() => handleDelete(g.goalId)}
                    >
                      {deleting === g.goalId ? '…' : 'Xóa'}
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
