import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { currentWeekNumber } from '../lib/weeks.js'
import { dayLabel, phaseLabel, typeLabel } from '../lib/labels.js'

const PHASE_CLASS = {
  base: 'phase-base',
  build: 'phase-build',
  peak: 'phase-peak',
  taper: 'phase-taper',
}

export default function Dashboard() {
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [goal, setGoal] = useState(null) // the chosen goal row from /goals
  const [plan, setPlan] = useState(null) // full plan detail from /goal/{id}/plan

  useEffect(() => {
    async function load() {
      try {
        const res = await fetch('/goals')
        if (!res.ok) throw new Error()
        const { goals } = await res.json()

        const ready = goals.find(g => g.planStatus === 'ready')
        const chosen = ready || goals.find(g => g.planStatus === 'generating') || goals[0] || null
        setGoal(chosen)

        if (chosen && chosen.planStatus === 'ready') {
          const planRes = await fetch(`/goal/${chosen.goalId}/plan`)
          if (!planRes.ok) throw new Error()
          setPlan(await planRes.json())
        }
      } catch {
        setError('Không thể tải trang tổng quan của bạn.')
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  if (loading) return <p>Đang tải…</p>
  if (error) return <p className="api-error">{error}</p>

  if (!goal) {
    return (
      <div>
        <p style={{ color: '#6c757d' }}>
          Chưa có kế hoạch tập luyện nào. <Link to="/new">Tạo mục tiêu đầu tiên của bạn.</Link>
        </p>
      </div>
    )
  }

  if (goal.planStatus === 'generating') {
    return (
      <div className="generating">
        <div className="spinner" />
        <p>Đang tạo kế hoạch tập luyện của bạn…</p>
        <p className="hint">Quá trình này thường mất 10–15 giây. Làm mới trang để kiểm tra lại.</p>
      </div>
    )
  }

  if (goal.planStatus === 'failed') {
    return (
      <div>
        <p className="api-error" style={{ marginBottom: '1rem' }}>
          Tạo kế hoạch cho mục tiêu gần nhất của bạn đã thất bại.
        </p>
        <Link to="/new">Thử gửi lại mục tiêu của bạn →</Link>
      </div>
    )
  }

  const { weekNumber, status, daysUntilStart } = currentWeekNumber(plan.startDate, plan.totalWeeks)
  const week = plan.weeks.find(w => w.weekNumber === weekNumber)

  return (
    <div className="plan-page">
      <h1>Tuần Này</h1>

      {status === 'upcoming' && (
        <p className="hint" style={{ marginBottom: '1rem' }}>
          Kế hoạch của bạn sẽ bắt đầu sau {daysUntilStart} ngày nữa — đây là tuần 1.
        </p>
      )}
      {status === 'finished' && (
        <p className="hint" style={{ marginBottom: '1rem' }}>
          Ngày thi đấu đã qua — làm tốt lắm! Đây là tuần cuối cùng của bạn.
        </p>
      )}

      <div className="plan-meta">
        <span className="badge">Tuần {week.weekNumber}/{plan.totalWeeks}</span>
        <span className={`phase-tag ${PHASE_CLASS[week.phase] || ''}`}>{phaseLabel(week.phase)}</span>
      </div>

      <table>
        <thead>
          <tr>
            <th>Ngày</th>
            <th>Loại</th>
            <th>Quãng đường</th>
            <th>Vùng</th>
            <th>Ghi chú</th>
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

      <p style={{ marginTop: '1.5rem' }}>
        <Link to={`/goals/${goal.goalId}`}>Xem toàn bộ kế hoạch →</Link>
      </p>
    </div>
  )
}
