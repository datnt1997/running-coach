import { useEffect, useState } from 'react'
import { t } from '../i18n/index.js'

// Ranges mirror app/models/profile.py (and the table CHECKs).
const FIELDS = [
  ['maxHr', 'profile.maxHr', null, 100, 230],
  ['restingHr', 'profile.restingHr', null, 25, 120],
  ['lactateThresholdHr', 'profile.lactateThresholdHr', 'profile.lactateThresholdHrHint', 80, 220],
]

// Needed to compute the heart-rate zones; lactate-threshold HR is optional.
const REQUIRED = ['maxHr', 'restingHr']

// First problem in the form as a message key (with params), or null.
function validate(form) {
  for (const [key, , , min, max] of FIELDS) {
    if (form[key] === '') {
      if (REQUIRED.includes(key)) return { key: 'profile.required', label: key }
      continue
    }
    const n = Number(form[key])
    if (!Number.isInteger(n) || n < min || n > max) {
      return { key: 'profile.outOfRange', label: key, min, max }
    }
  }
  const { maxHr, restingHr, lactateThresholdHr } = form
  if (maxHr !== '' && restingHr !== '' && Number(restingHr) >= Number(maxHr)) {
    return { key: 'profile.restingAboveMax' }
  }
  if (maxHr !== '' && lactateThresholdHr !== '' && Number(lactateThresholdHr) >= Number(maxHr)) {
    return { key: 'profile.lactateAboveMax' }
  }
  return null
}

const toForm = data => Object.fromEntries(FIELDS.map(([k]) => [k, data[k] ?? '']))

export default function Profile() {
  const [data, setData] = useState(null) // the API response, zones included
  const [form, setForm] = useState({})
  const [error, setError] = useState(null)
  const [saved, setSaved] = useState(false)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    fetch('/profile')
      .then(res => { if (!res.ok) throw new Error(); return res.json() })
      .then(body => { setData(body); setForm(toForm(body)) })
      .catch(() => setError({ text: t('profile.loadError') }))
  }, [])

  async function save(e) {
    e.preventDefault()
    setSaved(false)
    const problem = validate(form)
    if (problem) {
      const label = problem.label ? t(FIELDS.find(f => f[0] === problem.label)[1]) : ''
      setError({ field: problem.label, text: t(problem.key, { field: label, min: problem.min, max: problem.max }) })
      return
    }
    setBusy(true)
    setError(null)
    try {
      const payload = Object.fromEntries(
        FIELDS.map(([k]) => [k, form[k] === '' ? null : Number(form[k])]),
      )
      const res = await fetch('/profile', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      if (res.status === 422) { setError({ text: t('profile.invalid') }); return }
      if (!res.ok) throw new Error()
      const body = await res.json()
      setData(body)
      setForm(toForm(body))
      setSaved(true)
    } catch {
      setError({ text: t('profile.saveError') })
    } finally {
      setBusy(false)
    }
  }

  if (!data) return error ? <p className="error-msg">{error.text}</p> : <p>{t('common.loading')}</p>

  return (
    <div className="profile-page">
      <header className="profile-page__header">
        <h1>{t('profile.title')}</h1>
        <p className="profile-page__intro">{t('profile.intro')}</p>
      </header>

      <div className="profile-page__grid">
        <form className="profile-card" onSubmit={save} noValidate>
          {FIELDS.map(([key, labelKey, hintKey, min, max]) => {
            const required = REQUIRED.includes(key)
            const invalid = error?.field === key
            return (
              <div className="profile-field" key={key}>
                <label className="profile-field__label" htmlFor={key}>
                  {t(labelKey)}
                  {required && <span className="profile-field__req" aria-hidden="true"> *</span>}
                </label>
                <div className="profile-field__control">
                  <input
                    id={key}
                    className={`profile-field__input${invalid ? ' is-invalid' : ''}`}
                    type="number"
                    inputMode="numeric"
                    min={min}
                    max={max}
                    step="1"
                    required={required}
                    placeholder={`${min}–${max}`}
                    aria-invalid={invalid || undefined}
                    aria-describedby={hintKey ? `${key}-hint` : undefined}
                    value={form[key]}
                    onChange={e => {
                      setForm({ ...form, [key]: e.target.value })
                      setSaved(false)
                      setError(null)
                    }}
                  />
                  <span className="profile-field__unit" aria-hidden="true">bpm</span>
                </div>
                {hintKey && <small id={`${key}-hint`} className="profile-field__hint">{t(hintKey)}</small>}
              </div>
            )
          })}
          <div className="profile-card__footer">
            <button type="submit" disabled={busy}>{t('profile.save')}</button>
            {error && <p className="profile-msg profile-msg--error" role="alert">{error.text}</p>}
            {saved && <p className="profile-msg profile-msg--ok" role="status">{t('profile.saved')}</p>}
          </div>
        </form>

        <section className="profile-card" aria-labelledby="zones-title">
          <h2 id="zones-title">{t('profile.zonesTitle')}</h2>
          {data.zones ? (
            <table className="zone-table">
              <thead>
                <tr><th>{t('table.zone')}</th><th>{t('profile.bpm')}</th></tr>
              </thead>
              <tbody>
                {data.zones.map(z => (
                  <tr key={z.zone}>
                    <td><span className={`zone-chip zone-chip--${z.zone}`}>Z{z.zone}</span></td>
                    <td>{z.min}–{z.max}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p className="profile-empty">
              {data.missing.length
                ? t('profile.zonesMissing', { fields: data.missing.map(k => t(`profile.${k}`)).join(', ') })
                : t('profile.zonesInconsistent')}
            </p>
          )}
        </section>
      </div>
    </div>
  )
}
