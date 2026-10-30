import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import FitnessChat from '../components/FitnessChat.jsx'
import { RACE_DISTANCES, assessRace, assessVdot } from '../lib/vdot.js'

const today = new Date()
const minRaceDate = new Date(today)
minRaceDate.setDate(today.getDate() + 70) // 10 weeks
const MIN_RACE_DATE = minRaceDate.toISOString().split('T')[0]

const INITIAL = {
  distance: 'half_marathon',
  targetTime: '',
  raceDate: '',
  fitnessLevel: 'intermediate',
  daysPerWeek: 4,
  injuryHistory: '',
}

const LEVEL_LABELS = { beginner: 'Người mới', intermediate: 'Trung cấp', advanced: 'Nâng cao' }

export default function GoalForm() {
  const navigate = useNavigate()
  const [form, setForm] = useState(INITIAL)
  const [errors, setErrors] = useState({})
  const [apiError, setApiError] = useState(null)
  const [submitting, setSubmitting] = useState(false)

  // Fitness assessment state
  const [assessed, setAssessed] = useState(false)
  const [chatOpen, setChatOpen] = useState(false)
  const [showManual, setShowManual] = useState(false)
  const [assessmentData, setAssessmentData] = useState(null)

  // Manual entry (PR / VDOT)
  const [manualMode, setManualMode] = useState('race')
  const [raceDist, setRaceDist] = useState('10k')
  const [raceTime, setRaceTime] = useState('')
  const [vdotInput, setVdotInput] = useState('')

  const racePreview = assessRace(raceDist, raceTime)
  const vdotPreview = assessVdot(vdotInput)
  const manualPreview = manualMode === 'race' ? racePreview : vdotPreview

  function set(field, value) {
    setForm(f => ({ ...f, [field]: value }))
    setErrors(e => ({ ...e, [field]: undefined }))
    setApiError(null)
  }

  function validate() {
    const e = {}
    if (!/^\d{1,2}:\d{2}:\d{2}$/.test(form.targetTime))
      e.targetTime = 'Nhập theo định dạng H:MM:SS (vd: 1:55:00)'
    if (!form.raceDate)
      e.raceDate = 'Bắt buộc'
    else if (form.raceDate < MIN_RACE_DATE)
      e.raceDate = 'Ngày thi đấu phải cách hôm nay ít nhất 10 tuần'
    const days = Number(form.daysPerWeek)
    if (!Number.isInteger(days) || days < 3 || days > 7)
      e.daysPerWeek = 'Phải từ 3 đến 7'
    return e
  }

  async function handleSubmit(e) {
    e.preventDefault()
    const errs = validate()
    if (Object.keys(errs).length) { setErrors(errs); return }

    setSubmitting(true)
    setApiError(null)
    try {
      const res = await fetch('/goal', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ...form,
          daysPerWeek: Number(form.daysPerWeek),
          injuryHistory: form.injuryHistory.trim() || null,
        }),
      })
      const data = await res.json()
      if (res.status === 422) {
        setApiError(data.detail?.message || 'Mục tiêu nằm ngoài phạm vi hỗ trợ.')
        return
      }
      if (!res.ok) throw new Error('Đã xảy ra lỗi không mong muốn từ máy chủ')
      navigate(`/goals/${data.goalId}`)
    } catch (err) {
      setApiError(err.message)
    } finally {
      setSubmitting(false)
    }
  }

  function handleAssessmentResult(level, vdot, weeklyKm, longestRunKm, reasoning) {
    set('fitnessLevel', level)
    setAssessmentData({ level, vdot, weeklyKm, longestRunKm, reasoning })
    setAssessed(true)
    setChatOpen(false)
  }

  function handleReassess() {
    setAssessed(false)
    setChatOpen(false)
    setAssessmentData(null)
    setShowManual(false)
  }

  function confirmManual() {
    if (!manualPreview) return
    const reasoning = manualMode === 'race'
      ? `VDOT ${manualPreview.vdot} từ thời gian ${RACE_DISTANCES[raceDist].label} của bạn`
      : `VDOT ${manualPreview.vdot} (nhập trực tiếp)`
    handleAssessmentResult(manualPreview.level, manualPreview.vdot, 0, 0, reasoning)
  }

  return (
    <div className="goal-form-page">
      <div className="goal-form-header">
        <h1 className="goal-form-title">Đặt Mục Tiêu Cuộc Đua Của Bạn</h1>
        <p className="goal-form-subtitle">Trả lời một vài câu hỏi và chúng tôi sẽ xây dựng một kế hoạch tập luyện khoa học, được cá nhân hóa cho bạn.</p>
      </div>

      <form className="goal-form" onSubmit={handleSubmit} noValidate>

        {/* ── Section 1: Race Goal ── */}
        <section className="form-section">
          <h2 className="form-section__title">Mục Tiêu Cuộc Đua</h2>

          <label className="field">
            <span className="field__label">Quãng đường</span>
            <select className="field__input" value={form.distance} onChange={e => set('distance', e.target.value)}>
              <option value="half_marathon">Bán Marathon (21.1 km)</option>
              <option value="full_marathon">Marathon (42.2 km)</option>
            </select>
          </label>

          <div className="field-row">
            <label className="field">
              <span className="field__label">Thời Gian Mục Tiêu <span className="field__hint">H:MM:SS</span></span>
              <input
                className="field__input"
                type="text"
                placeholder="1:55:00"
                value={form.targetTime}
                onChange={e => set('targetTime', e.target.value)}
              />
              {errors.targetTime && <span className="field__error">{errors.targetTime}</span>}
            </label>

            <label className="field">
              <span className="field__label">Ngày Thi Đấu</span>
              <input
                className="field__input"
                type="date"
                min={MIN_RACE_DATE}
                value={form.raceDate}
                onChange={e => set('raceDate', e.target.value)}
              />
              {errors.raceDate && <span className="field__error">{errors.raceDate}</span>}
            </label>
          </div>
        </section>

        {/* ── Section 2: Training Capacity ── */}
        <section className="form-section">
          <h2 className="form-section__title">Khả Năng Tập Luyện</h2>

          {/* Fitness Assessment */}
          <div className="field">
            <span className="field__label">Thể Lực Hiện Tại</span>

            {/* State A: not yet assessed, chat closed */}
            {!assessed && !chatOpen && (
              <div className="assessment-card">
                <div className="assessment-card__icon">
                  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
                  </svg>
                </div>

                {!showManual ? (
                  <div className="assessment-card__body">
                    <p className="assessment-card__desc">
                      Chúng tôi sử dụng <strong>VDOT</strong> — phương pháp mà các huấn luyện viên thực thụ sử dụng — để hiệu chỉnh chính xác các vùng tập luyện của bạn. Trò chuyện với huấn luyện viên, hoặc nhập số liệu nếu bạn đã biết.
                    </p>
                    <button
                      type="button"
                      className="btn-assess"
                      onClick={() => setChatOpen(true)}
                    >
                      Bắt Đầu Đánh Giá
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                        <line x1="5" y1="12" x2="19" y2="12" /><polyline points="12 5 19 12 12 19" />
                      </svg>
                    </button>
                    <button type="button" className="link-subtle" onClick={() => setShowManual(true)}>
                      Tôi đã biết thời gian thi đấu hoặc VDOT của mình
                    </button>
                  </div>
                ) : (
                  <div className="manual-entry">
                    <div className="seg-toggle">
                      <button
                        type="button"
                        className={`seg-toggle__btn${manualMode === 'race' ? ' seg-toggle__btn--active' : ''}`}
                        onClick={() => setManualMode('race')}
                      >
                        Thời Gian Thi Đấu
                      </button>
                      <button
                        type="button"
                        className={`seg-toggle__btn${manualMode === 'vdot' ? ' seg-toggle__btn--active' : ''}`}
                        onClick={() => setManualMode('vdot')}
                      >
                        VDOT
                      </button>
                    </div>

                    {manualMode === 'race' ? (
                      <div className="field-row">
                        <label className="field">
                          <span className="field__label">Quãng đường</span>
                          <select className="field__input" value={raceDist} onChange={e => setRaceDist(e.target.value)}>
                            {Object.entries(RACE_DISTANCES).map(([key, d]) => (
                              <option key={key} value={key}>{d.label}</option>
                            ))}
                          </select>
                        </label>
                        <label className="field">
                          <span className="field__label">
                            Thời Gian Của Bạn <span className="field__hint">{RACE_DISTANCES[raceDist].timeHint}</span>
                          </span>
                          <input
                            className="field__input"
                            type="text"
                            inputMode="numeric"
                            placeholder={RACE_DISTANCES[raceDist].placeholder}
                            value={raceTime}
                            onChange={e => setRaceTime(e.target.value)}
                          />
                        </label>
                      </div>
                    ) : (
                      <label className="field">
                        <span className="field__label">
                          VDOT Của Bạn <span className="field__hint">20 – 85</span>
                        </span>
                        <input
                          className="field__input"
                          type="number"
                          min={20}
                          max={85}
                          placeholder="42"
                          value={vdotInput}
                          onChange={e => setVdotInput(e.target.value)}
                        />
                      </label>
                    )}

                    {manualPreview && (
                      <div className="manual-preview">
                        <span className="vdot-pill">VDOT {manualPreview.vdot}</span>
                        <span className={`level-badge level-badge--${manualPreview.level}`}>
                          {LEVEL_LABELS[manualPreview.level]}
                        </span>
                      </div>
                    )}

                    <div className="manual-actions">
                      <button type="button" className="link-subtle" onClick={() => setShowManual(false)}>
                        ← Quay lại
                      </button>
                      <button
                        type="button"
                        className="btn-assess"
                        disabled={!manualPreview}
                        onClick={confirmManual}
                      >
                        Sử dụng
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                          <line x1="5" y1="12" x2="19" y2="12" /><polyline points="12 5 19 12 12 19" />
                        </svg>
                      </button>
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* State B: chat open */}
            {chatOpen && !assessed && (
              <div className="assessment-chat-wrap">
                <FitnessChat onResult={handleAssessmentResult} />
              </div>
            )}

            {/* State C: assessed — show result card */}
            {assessed && assessmentData && (
              <div className="assessment-result">
                <div className={`level-badge level-badge--${assessmentData.level}`}>
                  {LEVEL_LABELS[assessmentData.level]}
                </div>
                <div className="assessment-result__meta">
                  <span className="vdot-pill">VDOT {assessmentData.vdot}</span>
                  {assessmentData.weeklyKm > 0 && (
                    <span className="meta-chip">{assessmentData.weeklyKm} km/week</span>
                  )}
                  {assessmentData.longestRunKm > 0 && (
                    <span className="meta-chip">{assessmentData.longestRunKm} km long run</span>
                  )}
                </div>
                {assessmentData.reasoning && (
                  <p className="assessment-result__reasoning">{assessmentData.reasoning}</p>
                )}
                <button type="button" className="link-subtle" onClick={handleReassess}>
                  Đánh giá lại →
                </button>
              </div>
            )}
          </div>

          <label className="field">
            <span className="field__label">
              Số Ngày Mỗi Tuần
              <span className="field__hint">3 – 7</span>
            </span>
            <div className="days-picker">
              {[3, 4, 5, 6, 7].map(d => (
                <button
                  key={d}
                  type="button"
                  className={`days-picker__btn${form.daysPerWeek == d ? ' days-picker__btn--active' : ''}`}
                  onClick={() => set('daysPerWeek', d)}
                >
                  {d}
                </button>
              ))}
            </div>
            {errors.daysPerWeek && <span className="field__error">{errors.daysPerWeek}</span>}
          </label>
        </section>

        {/* ── Section 3: Health Notes ── */}
        <section className="form-section">
          <h2 className="form-section__title">
            Ghi Chú Sức Khỏe
            <span className="section-optional">tùy chọn</span>
          </h2>

          <label className="field">
            <span className="field__label">Tiền Sử Chấn Thương</span>
            <textarea
              className="field__input"
              rows={3}
              placeholder="vd: viêm gân đầu gối trái, đã hồi phục 6 tháng trước"
              value={form.injuryHistory}
              onChange={e => set('injuryHistory', e.target.value)}
            />
          </label>
        </section>

        {apiError && <p className="api-error">{apiError}</p>}

        <button type="submit" className="btn-submit" disabled={submitting}>
          {submitting ? (
            <>
              <span className="btn-submit__spinner" />
              Đang xây dựng kế hoạch…
            </>
          ) : (
            <>
              Tạo Kế Hoạch Của Tôi
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <line x1="5" y1="12" x2="19" y2="12" /><polyline points="12 5 19 12 12 19" />
              </svg>
            </>
          )}
        </button>

      </form>
    </div>
  )
}
