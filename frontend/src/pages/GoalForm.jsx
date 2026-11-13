import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import FitnessChat from '../components/FitnessChat.jsx'
import WeeklyAvailability from '../components/WeeklyAvailability.jsx'
import { t } from '../i18n/index.js'
import { availabilityErrors, defaultWeek } from '../lib/availability.js'
import { distanceLabel } from '../lib/labels.js'
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
  weeklyAvailability: defaultWeek(),
  injuryHistory: '',
}

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
  const [assessBefore, assessAfter] = t('goal.assessDesc').split('{vdot}')

  function set(field, value) {
    setForm(f => ({ ...f, [field]: value }))
    setErrors(e => ({ ...e, [field]: undefined }))
    setApiError(null)
  }

  function validate() {
    const e = {}
    if (!/^\d{1,2}:\d{2}:\d{2}$/.test(form.targetTime))
      e.targetTime = t('goal.targetFormat')
    if (!form.raceDate)
      e.raceDate = t('goal.required')
    else if (form.raceDate < MIN_RACE_DATE)
      e.raceDate = t('goal.raceTooSoon')
    const availability = availabilityErrors(form.weeklyAvailability)
    if (availability) e.weeklyAvailability = availability
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
          injuryHistory: form.injuryHistory.trim() || null,
          vdot: assessmentData?.vdot ?? null,
        }),
      })
      const data = await res.json()
      if (res.status === 422) {
        setApiError(data.detail?.message || t('goal.outOfScope'))
        return
      }
      if (!res.ok) throw new Error(t('goal.serverError'))
      navigate(`/goals/${data.goalId}`)
    } catch (err) {
      setApiError(err.message)
    } finally {
      setSubmitting(false)
    }
  }

  // Chat result: { fitnessLevel, vdot, predictions, weeklyKm, longestRunKm, reasoning }
  function handleAssessmentResult(data) {
    set('fitnessLevel', data.fitnessLevel)
    setAssessmentData({
      level: data.fitnessLevel,
      vdot: data.vdot,
      predictions: data.predictions,
      weeklyKm: data.weeklyKm,
      longestRunKm: data.longestRunKm,
      reasoning: data.reasoning,
    })
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
      ? t('goal.manualReasoningRace', { vdot: manualPreview.vdot, distance: distanceLabel(raceDist) })
      : t('goal.manualReasoningVdot', { vdot: manualPreview.vdot })
    handleAssessmentResult({
      fitnessLevel: manualPreview.level,
      vdot: manualPreview.vdot,
      weeklyKm: 0,
      longestRunKm: 0,
      reasoning,
    })
  }

  return (
    <div className="goal-form-page">
      <div className="goal-form-header">
        <h1 className="goal-form-title">{t('goal.title')}</h1>
        <p className="goal-form-subtitle">{t('goal.subtitle')}</p>
      </div>

      <form className="goal-form" onSubmit={handleSubmit} noValidate>

        {/* ── Section 1: Race Goal ── */}
        <section className="form-section">
          <h2 className="form-section__title">{t('goal.sectionRace')}</h2>

          <label className="field">
            <span className="field__label">{t('goal.distance')}</span>
            <select className="field__input" value={form.distance} onChange={e => set('distance', e.target.value)}>
              <option value="half_marathon">{t('goal.halfOption')}</option>
              <option value="full_marathon">{t('goal.fullOption')}</option>
            </select>
          </label>

          <div className="field-row">
            <label className="field">
              <span className="field__label">{t('goal.targetTime')} <span className="field__hint">H:MM:SS</span></span>
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
              <span className="field__label">{t('goal.raceDate')}</span>
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
          <h2 className="form-section__title">{t('goal.sectionCapacity')}</h2>

          {/* Fitness Assessment */}
          <div className="field">
            <span className="field__label">{t('goal.currentFitness')}</span>

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
                      {assessBefore}<strong>VDOT</strong>{assessAfter}
                    </p>
                    <button
                      type="button"
                      className="btn-assess"
                      onClick={() => setChatOpen(true)}
                    >
                      {t('goal.startAssessment')}
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                        <line x1="5" y1="12" x2="19" y2="12" /><polyline points="12 5 19 12 12 19" />
                      </svg>
                    </button>
                    <button type="button" className="link-subtle" onClick={() => setShowManual(true)}>
                      {t('goal.alreadyKnow')}
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
                        {t('goal.modeRace')}
                      </button>
                      <button
                        type="button"
                        className={`seg-toggle__btn${manualMode === 'vdot' ? ' seg-toggle__btn--active' : ''}`}
                        onClick={() => setManualMode('vdot')}
                      >
                        {t('goal.modeVdot')}
                      </button>
                    </div>

                    {manualMode === 'race' ? (
                      <div className="field-row">
                        <label className="field">
                          <span className="field__label">{t('goal.distance')}</span>
                          <select className="field__input" value={raceDist} onChange={e => setRaceDist(e.target.value)}>
                            {Object.entries(RACE_DISTANCES).map(([key, d]) => (
                              <option key={key} value={key}>{distanceLabel(key)}</option>
                            ))}
                          </select>
                        </label>
                        <label className="field">
                          <span className="field__label">
                            {t('goal.yourTime')} <span className="field__hint">{RACE_DISTANCES[raceDist].timeHint}</span>
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
                          {t('goal.yourVdot')} <span className="field__hint">20 – 85</span>
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
                      </div>
                    )}

                    <div className="manual-actions">
                      <button type="button" className="link-subtle" onClick={() => setShowManual(false)}>
                        {t('common.back')}
                      </button>
                      <button
                        type="button"
                        className="btn-assess"
                        disabled={!manualPreview}
                        onClick={confirmManual}
                      >
                        {t('common.use')}
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
                <div className="assessment-result__meta">
                  <span className="vdot-pill">VDOT {assessmentData.vdot}</span>
                  {assessmentData.weeklyKm > 0 && (
                    <span className="meta-chip">{t('goal.weeklyKm', { km: assessmentData.weeklyKm })}</span>
                  )}
                  {assessmentData.longestRunKm > 0 && (
                    <span className="meta-chip">{t('goal.longRunKm', { km: assessmentData.longestRunKm })}</span>
                  )}
                </div>
                {assessmentData.predictions && (
                  <div className="assessment-result__predictions">
                    <span className="field__label">{t('goal.predictions')}</span>
                    <ul>
                      {Object.entries(assessmentData.predictions).map(([key, time]) => (
                        <li key={key}>{distanceLabel(key)}: <strong>{time}</strong></li>
                      ))}
                    </ul>
                  </div>
                )}
                {assessmentData.reasoning && (
                  <p className="assessment-result__reasoning">{assessmentData.reasoning}</p>
                )}
                <button type="button" className="link-subtle" onClick={handleReassess}>
                  {t('goal.reassess')}
                </button>
              </div>
            )}
          </div>

          <WeeklyAvailability
            value={form.weeklyAvailability}
            onChange={week => set('weeklyAvailability', week)}
            errors={errors.weeklyAvailability}
          />
        </section>

        {/* ── Section 3: Health Notes ── */}
        <section className="form-section">
          <h2 className="form-section__title">
            {t('goal.sectionHealth')}
            <span className="section-optional">{t('goal.optional')}</span>
          </h2>

          <label className="field">
            <span className="field__label">{t('goal.injuryHistory')}</span>
            <textarea
              className="field__input"
              rows={3}
              placeholder={t('goal.injuryPlaceholder')}
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
              {t('goal.building')}
            </>
          ) : (
            <>
              {t('goal.submit')}
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
