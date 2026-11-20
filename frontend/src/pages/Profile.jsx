import { useEffect, useState } from 'react'
import { t } from '../i18n/index.js'

// Ranges mirror app/models/profile.py (and the table CHECKs).
const FIELDS = [
  ['maxHr', 'profile.maxHr', null, 100, 230],
  ['restingHr', 'profile.restingHr', null, 25, 120],
  ['lactateThresholdHr', 'profile.lactateThresholdHr', 'profile.lactateThresholdHrHint', 80, 220],
]

// First problem in the form as a message key (with params), or null.
function validate(form) {
  for (const [key, , , min, max] of FIELDS) {
    if (form[key] === '') continue
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
      .catch(() => setError(t('profile.loadError')))
  }, [])

  async function save(e) {
    e.preventDefault()
    setSaved(false)
    const problem = validate(form)
    if (problem) {
      const label = problem.label ? t(FIELDS.find(f => f[0] === problem.label)[1]) : ''
      setError(t(problem.key, { field: label, min: problem.min, max: problem.max }))
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
      if (res.status === 422) { setError(t('profile.invalid')); return }
      if (!res.ok) throw new Error()
      const body = await res.json()
      setData(body)
      setForm(toForm(body))
      setSaved(true)
    } catch {
      setError(t('profile.saveError'))
    } finally {
      setBusy(false)
    }
  }

  if (!data) return error ? <p className="error-msg">{error}</p> : <p>{t('common.loading')}</p>

  return (
    <div className="profile-page">
      <h1>{t('profile.title')}</h1>
      <p>{t('profile.intro')}</p>

      <form onSubmit={save}>
        {FIELDS.map(([key, labelKey, hintKey, min, max]) => (
          <div className="field" key={key}>
            <label className="field__label" htmlFor={key}>{t(labelKey)}</label>
            <input
              id={key}
              className="field__input"
              type="number"
              inputMode="numeric"
              min={min}
              max={max}
              step="1"
              value={form[key]}
              onChange={e => setForm({ ...form, [key]: e.target.value })}
            />
            {hintKey && <small className="field__hint">{t(hintKey)}</small>}
          </div>
        ))}
        {error && <p className="error-msg">{error}</p>}
        {saved && <p>{t('profile.saved')}</p>}
        <button type="submit" disabled={busy}>{t('profile.save')}</button>
      </form>

      <h2>{t('profile.zonesTitle')}</h2>
      {data.zones ? (
        <table>
          <thead>
            <tr><th>{t('table.zone')}</th><th>{t('profile.bpm')}</th></tr>
          </thead>
          <tbody>
            {data.zones.map(z => (
              <tr key={z.zone}>
                <td>Z{z.zone}</td>
                <td>{z.min}–{z.max}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <p className="hint">
          {data.missing.length
            ? t('profile.zonesMissing', { fields: data.missing.map(k => t(`profile.${k}`)).join(', ') })
            : t('profile.zonesInconsistent')}
        </p>
      )}
    </div>
  )
}
