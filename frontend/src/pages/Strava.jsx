import { useEffect, useState } from 'react'
import { t } from '../i18n/index.js'
import { typeLabel } from '../lib/labels.js'

const pace = sec => (sec == null ? '–' : `${Math.floor(sec / 60)}:${String(sec % 60).padStart(2, '0')}/km`)

export default function Strava() {
  const [status, setStatus] = useState(null) // { connected, athlete: {id, name, profile_url}, activities }
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const justConnected = new URLSearchParams(window.location.search).get('connected') === '1'

  useEffect(() => {
    async function load() {
      try {
        const res = await fetch('/strava/overview')
        if (!res.ok) throw new Error()
        setStatus(await res.json())
      } catch {
        setError(t('strava.loadError'))
      }
    }
    load()
  }, [])

  async function disconnect() {
    setBusy(true)
    setError(null)
    try {
      const res = await fetch('/strava/disconnect', { method: 'POST' })
      if (!res.ok) throw new Error()
      setStatus({ connected: false, athlete: null, activities: [] })
    } catch {
      setError(t('strava.disconnectFailed'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="strava-page">
      <h1>{t('strava.title')}</h1>
      <p className="strava-page__intro">{t('strava.intro')}</p>

      {error && <p className="error-msg">{error}</p>}
      {!status && !error && <p>{t('common.loading')}</p>}

      {status && (
        <div className="strava-card">
          {status.connected ? (
            <>
              {justConnected && <p className="strava-card__ok">{t('strava.justConnected')}</p>}
              <div className="strava-athlete">
                {status.athlete?.profile_url && (
                  <img className="strava-athlete__avatar" src={status.athlete.profile_url} alt="" />
                )}
                <p>
                  {status.athlete?.name
                    ? t('strava.connectedAsName', { name: status.athlete.name })
                    : t('strava.connectedAs', { id: status.athlete?.id })}
                </p>
              </div>
              <button className="btn-danger" disabled={busy} onClick={disconnect}>
                {t('strava.disconnect')}
              </button>
            </>
          ) : (
            <>
              <p>{t('strava.notConnected')}</p>
              {/* Full navigation: the server redirects on to Strava's consent page. */}
              <a className="strava-connect" href="/strava/connect">{t('strava.connect')}</a>
            </>
          )}
        </div>
      )}

      {status?.connected && (
        <section className="strava-runs">
          <h2>{t('strava.recentRuns')}</h2>
          {status.activities.length === 0 ? (
            <p>{t('strava.noRuns')}</p>
          ) : (
            <table className="strava-runs__table">
              <thead>
                <tr>
                  <th>{t('strava.col.date')}</th>
                  <th>{t('strava.col.run')}</th>
                  <th>{t('strava.col.distance')}</th>
                  <th>{t('strava.col.pace')}</th>
                  <th>{t('strava.col.hr')}</th>
                  <th>{t('strava.col.match')}</th>
                </tr>
              </thead>
              <tbody>
                {status.activities.map(a => (
                  <tr key={a.id}>
                    <td>{a.date}</td>
                    <td>{a.name}</td>
                    <td>{a.distance_km} km</td>
                    <td>{pace(a.pace_sec_per_km)}</td>
                    <td>{a.avg_hr_bpm == null ? t('strava.hrUnavailable') : Math.round(a.avg_hr_bpm)}</td>
                    <td>
                      {a.match
                        ? [typeLabel(a.match.workout_type), a.match.load_adherence].filter(Boolean).join(' · ')
                        : t('strava.unmatched')}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>
      )}
    </div>
  )
}
