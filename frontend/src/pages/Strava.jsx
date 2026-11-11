import { useEffect, useState } from 'react'
import { t } from '../i18n/index.js'

export default function Strava() {
  const [status, setStatus] = useState(null) // { connected, athlete_id }
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const justConnected = new URLSearchParams(window.location.search).get('connected') === '1'

  useEffect(() => {
    async function load() {
      try {
        const res = await fetch('/strava/status')
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
      setStatus({ connected: false, athlete_id: null })
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
              <p>{t('strava.connectedAs', { id: status.athlete_id })}</p>
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
    </div>
  )
}
