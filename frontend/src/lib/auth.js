// Session handling for the SPA, plus the timezone header every API call carries. The session itself is an HttpOnly cookie set by
// the backend; the SPA only asks "who am I" and reacts to 401s.

export const AUTH_EXPIRED_EVENT = 'auth:expired'

// Any 401 from the API (other than the /auth calls themselves) means the session
// is gone: tell the app so it returns to the sign-in screen.
let unauthorizedHandlerInstalled = false

function requestUrl(input) {
  const url = typeof input === 'string' ? input : input instanceof Request ? input.url : String(input)
  return new URL(url, window.location.href)
}

// The server runs on UTC; it works out the runner's "today" from this header.
export const TZ_HEADER = 'X-Timezone'

function browserTimeZone() {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || null
  } catch {
    return null
  }
}

export function installUnauthorizedHandler() {
  if (unauthorizedHandlerInstalled) return
  unauthorizedHandlerInstalled = true
  const original = window.fetch.bind(window)
  window.fetch = async (input, init) => {
    const url = requestUrl(input)
    const tz = browserTimeZone()
    if (tz && url.origin === window.location.origin) {
      const headers = new Headers(init?.headers ?? (input instanceof Request ? input.headers : undefined))
      if (!headers.has(TZ_HEADER)) headers.set(TZ_HEADER, tz)
      init = { ...init, headers }
    }
    const res = await original(input, init)
    if (res.status === 401 && !url.pathname.startsWith('/auth/')) {
      window.dispatchEvent(new Event(AUTH_EXPIRED_EVENT))
    }
    return res
  }
}

// Sign-in failure codes; each maps to the i18n key `auth.error.<code>`.
export const AUTH_ERROR = Object.freeze({
  CONFIG: 'config',
  FORBIDDEN: 'forbidden',
  INVALID: 'invalid',
  NETWORK: 'network',
})

export async function fetchMe() {
  const res = await fetch('/auth/me')
  return res.ok ? (await res.json()).email : null
}

// Returns { email } on success, or { error: AUTH_ERROR code }.
export async function signInWithGoogle(credential) {
  try {
    const res = await fetch('/auth/google', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ credential }),
    })
    if (res.ok) return { email: (await res.json()).email }
    return { error: res.status === 403 ? AUTH_ERROR.FORBIDDEN : AUTH_ERROR.INVALID }
  } catch {
    return { error: AUTH_ERROR.NETWORK }
  }
}

export async function signOut() {
  await fetch('/auth/logout', { method: 'POST' })
}

export const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID
