// Session handling for the SPA. The session itself is an HttpOnly cookie set by
// the backend; the SPA only asks "who am I" and reacts to 401s.

export const AUTH_EXPIRED_EVENT = 'auth:expired'

// Any 401 from the API (other than the /auth calls themselves) means the session
// is gone: tell the app so it returns to the sign-in screen.
export function installUnauthorizedHandler() {
  if (window.__authFetchInstalled) return
  window.__authFetchInstalled = true
  const original = window.fetch.bind(window)
  window.fetch = async (input, init) => {
    const res = await original(input, init)
    const url = typeof input === 'string' ? input : input.url
    if (res.status === 401 && !url.startsWith('/auth/')) {
      window.dispatchEvent(new Event(AUTH_EXPIRED_EVENT))
    }
    return res
  }
}

export async function fetchMe() {
  const res = await fetch('/auth/me')
  return res.ok ? (await res.json()).email : null
}

// Returns { email } on success, or { error: 'forbidden' | 'invalid' | 'network' }.
export async function signInWithGoogle(credential) {
  try {
    const res = await fetch('/auth/google', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ credential }),
    })
    if (res.ok) return { email: (await res.json()).email }
    return { error: res.status === 403 ? 'forbidden' : 'invalid' }
  } catch {
    return { error: 'network' }
  }
}

export async function signOut() {
  await fetch('/auth/logout', { method: 'POST' })
}

export const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID
