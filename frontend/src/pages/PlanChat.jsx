import { useEffect, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { t } from '../i18n/index.js'

async function post(path, body) {
  const res = await fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  if (!res.ok) throw new Error(String(res.status))
  return (await res.json()).messages
}

export default function PlanChat() {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loaded, setLoaded] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const threadRef = useRef(null)

  useEffect(() => {
    fetch('/plan-chat/messages')
      .then(r => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
      .then(data => setMessages(data.messages))
      .catch(() => setError(t('planChat.loadError')))
      .finally(() => setLoaded(true))
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
    </div>
  )
}
