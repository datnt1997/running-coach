import { useEffect, useRef, useState } from 'react'

export default function FitnessChat({ onResult }) {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const bottomRef = useRef(null)
  const startedRef = useRef(false)

  useEffect(() => {
    // Guard against StrictMode's double-invocation so we only fetch the
    // opening question once.
    if (startedRef.current) return
    startedRef.current = true
    sendTurn('')
  }, [])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  async function sendTurn(userText) {
    const history = messages.map(m => ({ role: m.role, content: m.content }))

    if (userText) {
      setMessages(prev => [...prev, { role: 'user', content: userText }])
    }

    setLoading(true)
    try {
      const res = await fetch('/fitness-chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ history, message: userText }),
      })
      const data = await res.json()

      setMessages(prev => [...prev, { role: 'assistant', content: data.message }])

      if (data.done) {
        onResult(data.fitnessLevel, data.vdot, data.weeklyKm, data.longestRunKm, data.reasoning)
      }
    } catch (err) {
      setMessages(prev => [...prev, { role: 'assistant', content: 'Something went wrong — please try again.' }])
    } finally {
      setLoading(false)
    }
  }

  function handleSend() {
    const text = input.trim()
    if (!text || loading) return
    setInput('')
    sendTurn(text)
  }

  function handleKeyDown(e) {
    if (e.key === 'Enter') {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div className="fitness-chat">
      <div className="fc-thread">
        {messages.map((m, i) => (
          <div key={i} className={`fc-bubble fc-bubble--${m.role}`}>
            {m.content}
          </div>
        ))}
        {loading && (
          <div className="fc-bubble fc-bubble--assistant fc-bubble--loading">
            <span className="fc-dot" /><span className="fc-dot" /><span className="fc-dot" />
          </div>
        )}
        <div ref={bottomRef} />
      </div>
      <div className="fc-input-row">
        <input
          type="text"
          placeholder="Type your answer…"
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={loading}
          autoFocus
        />
        <button type="button" onClick={handleSend} disabled={loading || !input.trim()}>Send</button>
      </div>
    </div>
  )
}
