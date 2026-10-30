import { useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { dayLabel, phaseLabel, typeLabel } from '../lib/labels.js'

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
        setError('Không tìm thấy mục tiêu.')
        clearInterval(timer.current)
        return
      }
      const data = await res.json()
      setStatus(data.status)
      if (data.status === 'ready') {
        setPlan(data)
        clearInterval(timer.current)
      } else if (data.status === 'failed') {
        setError('Tạo kế hoạch thất bại. Vui lòng quay lại và thử gửi lại mục tiêu của bạn.')
        clearInterval(timer.current)
      }
    } catch {
      setError('Lỗi mạng — vui lòng làm mới trang.')
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
      <Link to="/new">← Mục tiêu mới</Link>
    </div>
  )

  if (status !== 'ready') return (
    <div className="generating">
      <div className="spinner" />
      <p>Đang tạo kế hoạch tập luyện của bạn…</p>
      <p className="hint">Quá trình này thường mất 10–15 giây.</p>
    </div>
  )

  return (
    <div className="plan-page">
      <h1>Kế Hoạch Tập Luyện Của Bạn</h1>

      <p className="plan-summary">{plan.summary}</p>

      <div className="plan-meta">
        <span className="badge">{plan.totalWeeks} tuần</span>
        {Object.entries(plan.phaseBreakdown).map(([phase, weeks]) => (
          <span key={phase} className={`badge ${PHASE_CLASS[phase] || ''}`}>
            {phaseLabel(phase)} · {weeks} tuần
          </span>
        ))}
      </div>

      {plan.weeks.map(week => (
        <details key={week.weekNumber} open={week.weekNumber <= 2}>
          <summary>
            Tuần {week.weekNumber}
            <span className={`phase-tag ${PHASE_CLASS[week.phase] || ''}`}>
              {phaseLabel(week.phase)}
            </span>
          </summary>
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
        </details>
      ))}

      <p style={{ marginTop: '1.5rem' }}>
        <Link to="/history">← Quay lại lịch sử</Link>
      </p>
    </div>
  )
}
