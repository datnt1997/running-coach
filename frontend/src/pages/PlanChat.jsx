import { useEffect, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { label, t } from '../i18n/index.js'

function runsText(runs) {
  if (!runs.length) return t('planEdit.nothing')
  return runs.map(r => `${label('type', r.type)} ${r.distanceKm} km`).join(', ')
}

function reasonText(r) {
  const params = { ...r.params, day: r.params.day ? label('day', r.params.day) : undefined, type: r.params.type ? label('type', r.params.type) : undefined }
  const text = t(`planEdit.reason.${r.code}`, params)
  return text === `planEdit.reason.${r.code}` ? r.text : text
}

function Changes({ edit }) {
  return (
    <ul>
      {edit.changes.map(c => (
        <li key={`${c.week}-${c.day}`}>
          {t('planEdit.dayLabel', { week: c.week, day: label('day', c.day) })}:{' '}
          <del>{runsText(c.before)}</del> → <strong>{runsText(c.after)}</strong>
        </li>
      ))}
    </ul>
  )
}

function PlanEditCard({ edit, onDecide }) {
  return (
    <div className="plan-edit">
      {edit.status === 'rejected' ? (
        <>
          <div>{t('planEdit.rejected')}</div>
          <ul>{edit.reasons.map((r, i) => <li key={i}>{reasonText(r)}</li>)}</ul>
        </>
      ) : (
        <>
          <div><strong>{t('planEdit.title')}</strong>{edit.summary ? `: ${edit.summary}` : ''}</div>
          <Changes edit={edit} />
          {edit.override && (
            <div>
              {t('planEdit.override', { week: edit.override.week, day: label('day', edit.override.day) })}
              <ul>{edit.override.limits.map((r, i) => <li key={i}>{reasonText(r)}</li>)}</ul>
            </div>
          )}
          {edit.status === 'pending' && (
            <div className="proposal-actions">
              <button type="button" onClick={() => onDecide('confirm')}>{t('planEdit.apply')}</button>
              <button type="button" onClick={() => onDecide('decline')}>{t('planEdit.decline')}</button>
            </div>
          )}
          {edit.status === 'applied' && <div className="proposal-result">{t('planEdit.applied')}</div>}
          {edit.status === 'declined' && <div className="proposal-result">{t('planEdit.declined')}</div>}
        </>
      )}
    </div>
  )
}

async function post(path, body, key = 'messages') {
  const res = await fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  if (!res.ok) throw new Error(String(res.status))
  const data = await res.json()
  return key === 'messages' ? data.messages : data
}

export default function PlanChat() {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loaded, setLoaded] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const threadRef = useRef(null)

  const [editLog, setEditLog] = useState([])

  function loadEditLog() {
    fetch('/plan-edits')
      .then(r => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
      .then(data => setEditLog(data.edits))
      .catch(() => { /* the log is secondary; the chat still works */ })
  }

  useEffect(() => {
    fetch('/plan-chat/messages')
      .then(r => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
      .then(data => setMessages(data.messages))
      .catch(() => setError(t('planChat.loadError')))
      .finally(() => setLoaded(true))
    loadEditLog()
  }, [])

  useEffect(() => {
    const thread = threadRef.current
    thread?.scrollTo({ top: thread.scrollHeight, behavior: 'smooth' })
  }, [messages, loading])

  // The last message is the runner's own: the model did not answer it (yet).
  const unanswered = messages.length > 0 && messages[messages.length - 1].role === 'user'

  async function send() {
    const text = input.trim()
    if (!text || loading) return
    setInput('')
    setError(null)
    setLoading(true)
    // Show the message at once; the server stores it even when the model fails.
    const pending = { id: `pending-${Date.now()}`, role: 'user', content: text }
    setMessages(prev => [...prev, pending])
    try {
      const added = await post('/plan-chat/messages', { message: text })
      setMessages(prev => [...prev.filter(m => m.id !== pending.id), ...added])
    } catch {
      setError(t('planChat.sendError'))
      // Replace the temporary copy with what is stored, so the thread matches storage.
      try {
        const res = await fetch('/plan-chat/messages')
        if (res.ok) setMessages((await res.json()).messages)
      } catch { /* keep the optimistic copy; the error banner is already shown */ }
    } finally {
      setLoading(false)
    }
  }

  async function decide(id, action) {
    setError(null)
    try {
      const { message } = await post(`/plan-chat/messages/${id}/proposal/${action}`, undefined, 'message')
      setMessages(prev => prev.map(m => (m.id === id ? message : m)))
    } catch {
      setError(t('planChat.proposalError'))
    }
  }

  async function decideEdit(id, action) {
    setError(null)
    try {
      const res = await fetch(`/plan-chat/messages/${id}/edit/${action}`, { method: 'POST' })
      const data = await res.json()
      // A 409 after a re-check carries the edit, now rejected with its reasons.
      const edit = res.ok ? data.edit : data.detail?.edit
      if (edit) setMessages(prev => prev.map(m => (m.id === id ? { ...m, planEdit: edit } : m)))
      if (!res.ok && !edit) throw new Error(String(res.status))
      if (res.ok && action === 'confirm') loadEditLog()
    } catch {
      setError(t('planEdit.error'))
    }
  }

  async function resend() {
    if (loading) return
    setError(null)
    setLoading(true)
    try {
      const added = await post('/plan-chat/retry')
      setMessages(prev => [...prev, ...added])
    } catch {
      setError(t('planChat.sendError'))
    } finally {
      setLoading(false)
    }
  }

  if (!loaded) return <p>{t('common.loading')}</p>

  return (
    <div className="plan-chat">
      <h1>{t('planChat.title')}</h1>
      <p className="muted">{t('planChat.intro')}</p>
      <div className="fitness-chat">
        <div className="fc-thread plan-chat-thread" ref={threadRef}>
          {messages.length === 0 && !error && <p className="muted">{t('planChat.empty')}</p>}
          {messages.map(m => (
            <div key={m.id} className={`fc-bubble fc-bubble--${m.role}${m.role === 'assistant' ? ' fc-bubble--md' : ''}`}>
              {m.role === 'assistant'
                ? <ReactMarkdown remarkPlugins={[remarkGfm]}>{m.content}</ReactMarkdown>
                : m.content}
              {m.proposal?.status === 'pending' && (
                <div className="proposal-actions">
                  <div className="proposal-text">{m.proposal.text}</div>
                  <button type="button" onClick={() => decide(m.id, 'confirm')}>{t('planChat.proposalSave')}</button>
                  <button type="button" onClick={() => decide(m.id, 'decline')}>{t('planChat.proposalDecline')}</button>
                </div>
              )}
              {m.proposal?.status === 'saved' && (
                <div className="proposal-result">{t('planChat.proposalSaved', { text: m.proposal.text })}</div>
              )}
              {m.proposal?.status === 'declined' && (
                <div className="proposal-result">{t('planChat.proposalDeclined')}</div>
              )}
              {m.planEdit && <PlanEditCard edit={m.planEdit} onDecide={action => decideEdit(m.id, action)} />}
            </div>
          ))}
          {loading && (
            <div className="fc-bubble fc-bubble--assistant fc-bubble--loading">
              <span className="fc-dot" /><span className="fc-dot" /><span className="fc-dot" />
            </div>
          )}
        </div>
        {error && (
          <div className="plan-chat-error" role="alert">
            <span>{error}</span>
            {unanswered && (
              <button type="button" onClick={resend} disabled={loading}>{t('planChat.resend')}</button>
            )}
          </div>
        )}
        <div className="fc-input-row">
          <input
            type="text"
            placeholder={t('planChat.placeholder')}
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => {
              if (e.nativeEvent.isComposing || e.keyCode === 229) return // IME (Telex/VNI) is still composing
              if (e.key === 'Enter') { e.preventDefault(); send() }
            }}
            disabled={loading}
          />
          <button type="button" onClick={send} disabled={loading || !input.trim()}>{t('chat.send')}</button>
        </div>
      </div>
      <details className="plan-edit-log">
        <summary>{t('planEdit.log')}</summary>
        {editLog.length === 0 && <p className="muted">{t('planEdit.logEmpty')}</p>}
        {editLog.map(e => (
          <div key={e.id} className="plan-edit">
            <div className="muted">{new Date(e.decidedAt).toLocaleString()}</div>
            <div>{e.summary || e.request}</div>
            <Changes edit={e} />
            {e.override && (
              <div>{t('planEdit.override', { week: e.override.week, day: label('day', e.override.day) })}{' '}
                {e.override.limits.map(reasonText).join(' ')}</div>
            )}
          </div>
        ))}
      </details>
    </div>
  )
}
