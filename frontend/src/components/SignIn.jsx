import { useEffect, useRef, useState } from 'react'
import { GOOGLE_CLIENT_ID, signInWithGoogle } from '../lib/auth.js'
import { t } from '../i18n/index.js'

const GIS_SRC = 'https://accounts.google.com/gsi/client'

function loadGoogleIdentity() {
  if (window.google?.accounts?.id) return Promise.resolve()
  return new Promise((resolve, reject) => {
    const script = document.createElement('script')
    script.src = GIS_SRC
    script.async = true
    script.onload = resolve
    script.onerror = reject
    document.head.appendChild(script)
  })
}

export default function SignIn({ onSignedIn }) {
  const buttonRef = useRef(null)
  const [error, setError] = useState(GOOGLE_CLIENT_ID ? null : 'config')

  useEffect(() => {
    if (!GOOGLE_CLIENT_ID) return
    let cancelled = false
    loadGoogleIdentity()
      .then(() => {
        if (cancelled) return
        window.google.accounts.id.initialize({
          client_id: GOOGLE_CLIENT_ID,
          callback: async ({ credential }) => {
            const result = await signInWithGoogle(credential)
            if (result.email) onSignedIn(result.email)
            else setError(result.error)
          },
        })
        window.google.accounts.id.renderButton(buttonRef.current, { theme: 'outline', size: 'large' })
      })
      .catch(() => !cancelled && setError('network'))
    return () => { cancelled = true }
  }, [onSignedIn])

  return (
    <main className="signin">
      <h1>{t('auth.title')}</h1>
      <p>{t('auth.intro')}</p>
      <div ref={buttonRef} />
      {error && <p className="api-error" role="alert">{t(`auth.error.${error}`)}</p>}
    </main>
  )
}
