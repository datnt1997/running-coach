import { useEffect, useState } from 'react'
import { t } from '../i18n/index.js'

async function send(method, path, body) {
  const res = await fetch(path, {
    method,
    headers: body ? { 'Content-Type': 'application/json' } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) throw new Error(String(res.status))
  return res.json()
}

export default function ProfileFacts() {
  const [facts, setFacts] = useState([])
  const [loaded, setLoaded] = useState(false)
  const [error, setError] = useState(null)
  const [editing, setEditing] = useState(null) // { id, text }

  useEffect(() => {
    send('GET', '/profile-facts')
      .then(data => setFacts(data.facts))
      .catch(() => setError(t('facts.loadError')))
      .finally(() => setLoaded(true))
  }, [])

  async function save() {
    const text = editing.text.trim()
    if (!text) return
    setError(null)
    try {
      const updated = await send('PUT', `/profile-facts/${editing.id}`, { text })
      setFacts(prev => prev.map(f => (f.id === updated.id ? updated : f)))
      setEditing(null)
    } catch {
      setError(t('facts.saveError'))
    }
  }

  async function remove(id) {
    if (!window.confirm(t('facts.confirmDelete'))) return
    setError(null)
    try {
      await send('DELETE', `/profile-facts/${id}`)
      setFacts(prev => prev.filter(f => f.id !== id))
    } catch {
      setError(t('facts.saveError'))
    }
  }

  if (!loaded) return <p>{t('common.loading')}</p>

  return (
    <div className="profile-facts">
      <h1>{t('facts.title')}</h1>
      <p className="muted">{t('facts.intro')}</p>
      {error && <p role="alert" className="error">{error}</p>}
      {facts.length === 0 && !error && <p className="muted">{t('facts.empty')}</p>}
      <ul className="facts-list">
        {facts.map(f => (
          <li key={f.id}>
            {editing?.id === f.id ? (
              <>
                <input
                  type="text"
                  value={editing.text}
                  maxLength={300}
                  onChange={e => setEditing({ id: f.id, text: e.target.value })}
                  onKeyDown={e => {
                    if (e.nativeEvent.isComposing || e.keyCode === 229) return
                    if (e.key === 'Enter') { e.preventDefault(); save() }
                  }}
                />
                <button type="button" onClick={save} disabled={!editing.text.trim()}>{t('facts.save')}</button>
                <button type="button" onClick={() => setEditing(null)}>{t('facts.cancel')}</button>
              </>
            ) : (
              <>
                <span className="fact-text">{f.text}</span>
                <button type="button" onClick={() => setEditing({ id: f.id, text: f.text })}>{t('facts.edit')}</button>
                <button type="button" onClick={() => remove(f.id)}>{t('facts.delete')}</button>
              </>
            )}
          </li>
        ))}
      </ul>
    </div>
  )
}
