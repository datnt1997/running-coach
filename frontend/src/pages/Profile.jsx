import { useEffect, useState } from 'react'
import { t } from '../i18n/index.js'

const FIELDS = [
  ['maxHr', 'profile.maxHr'],
  ['lactateThresholdHr', 'profile.lactateThresholdHr'],
  ['restingHr', 'profile.restingHr'],
  ['cadence', 'profile.cadence'],
]

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
    setBusy(true)
    setError(null)
    setSaved(false)
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
        {FIELDS.map(([key, labelKey]) => (
          <div className="field" key={key}>
            <label className="field__label" htmlFor={key}>{t(labelKey)}</label>
            <input
              id={key}
              className="field__input"
              type="number"
              inputMode="numeric"
              value={form[key]}
              onChange={e => setForm({ ...form, [key]: e.target.value })}
            />
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
                <td>{z.min == null ? `≤ ${z.max}` : `${z.min}–${z.max}`}</td>
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
