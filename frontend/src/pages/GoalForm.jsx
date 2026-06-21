import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

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

export default function GoalForm() {
  const navigate = useNavigate()
  const [form, setForm] = useState(INITIAL)
  const [errors, setErrors] = useState({})
  const [apiError, setApiError] = useState(null)
  const [submitting, setSubmitting] = useState(false)

  function set(field, value) {
    setForm(f => ({ ...f, [field]: value }))
    setErrors(e => ({ ...e, [field]: undefined }))
    setApiError(null)
  }

  function validate() {
    const e = {}
    if (!/^\d{1,2}:\d{2}:\d{2}$/.test(form.targetTime))
      e.targetTime = 'Use format H:MM:SS (e.g. 1:55:00)'
    if (!form.raceDate)
      e.raceDate = 'Required'
    else if (form.raceDate < MIN_RACE_DATE)
      e.raceDate = 'Race date must be at least 10 weeks from today'
    const days = Number(form.daysPerWeek)
    if (!Number.isInteger(days) || days < 3 || days > 7)
      e.daysPerWeek = 'Must be between 3 and 7'
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
        setApiError(data.detail?.message || 'Goal is out of supported scope.')
        return
      }
      if (!res.ok) throw new Error('Unexpected server error')
      navigate(`/goals/${data.goalId}`)
    } catch (err) {
      setApiError(err.message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="form-page">
      <h1>Set Your Goal</h1>
      <form onSubmit={handleSubmit} noValidate>

        <label>
          Distance
          <select value={form.distance} onChange={e => set('distance', e.target.value)}>
            <option value="half_marathon">Half Marathon (21.1 km)</option>
            <option value="full_marathon">Full Marathon (42.2 km)</option>
          </select>
        </label>

        <label>
          Target Time <small style={{ fontWeight: 400, color: '#6c757d' }}>(H:MM:SS)</small>
          <input
            type="text"
            placeholder="1:55:00"
            value={form.targetTime}
            onChange={e => set('targetTime', e.target.value)}
          />
          {errors.targetTime && <span className="field-error">{errors.targetTime}</span>}
        </label>

        <label>
          Race Date
          <input
            type="date"
            min={MIN_RACE_DATE}
            value={form.raceDate}
            onChange={e => set('raceDate', e.target.value)}
          />
          {errors.raceDate && <span className="field-error">{errors.raceDate}</span>}
        </label>

        <label>
          Fitness Level
          <select value={form.fitnessLevel} onChange={e => set('fitnessLevel', e.target.value)}>
            <option value="beginner">Beginner</option>
            <option value="intermediate">Intermediate</option>
            <option value="advanced">Advanced</option>
          </select>
        </label>

        <label>
          Days Per Week
          <input
            type="number"
            min={3}
            max={7}
            value={form.daysPerWeek}
            onChange={e => set('daysPerWeek', e.target.value)}
          />
          {errors.daysPerWeek && <span className="field-error">{errors.daysPerWeek}</span>}
        </label>

        <label>
          Injury History <small style={{ fontWeight: 400, color: '#6c757d' }}>(optional)</small>
          <textarea
            rows={3}
            placeholder="e.g. left knee tendinopathy, recovered"
            value={form.injuryHistory}
            onChange={e => set('injuryHistory', e.target.value)}
          />
        </label>

        {apiError && <p className="api-error">{apiError}</p>}

        <button type="submit" disabled={submitting}>
          {submitting ? 'Submitting…' : 'Generate Plan'}
        </button>

      </form>
    </div>
  )
}
