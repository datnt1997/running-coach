import { useCallback, useEffect, useState } from 'react'
import { BrowserRouter, NavLink, Route, Routes } from 'react-router-dom'
import SignIn from './components/SignIn.jsx'
import Dashboard from './pages/Dashboard.jsx'
import GoalForm from './pages/GoalForm.jsx'
import GoalHistory from './pages/GoalHistory.jsx'
import PlanView from './pages/PlanView.jsx'
import Strava from './pages/Strava.jsx'
import { AUTH_EXPIRED_EVENT, fetchMe, installUnauthorizedHandler, signOut } from './lib/auth.js'
import { t } from './i18n/index.js'

installUnauthorizedHandler()

export default function App() {
  // undefined: still asking the server; null: signed out; string: the signed-in email
  const [email, setEmail] = useState(undefined)

  useEffect(() => {
    fetchMe().then(setEmail, () => setEmail(null))
    const expired = () => setEmail(null)
    window.addEventListener(AUTH_EXPIRED_EVENT, expired)
    return () => window.removeEventListener(AUTH_EXPIRED_EVENT, expired)
  }, [])

  const handleSignedIn = useCallback(setEmail, [])

  if (email === undefined) return <main><p>{t('common.loading')}</p></main>
  if (email === null) return <SignIn onSignedIn={handleSignedIn} />

  return (
    <BrowserRouter basename="/app">
      <nav>
        <span className="nav-brand">{t('nav.brand')}</span>
        <div className="nav-links">
          <NavLink to="/new">{t('nav.newGoal')}</NavLink>
          <NavLink to="/history">{t('nav.history')}</NavLink>
          <NavLink to="/strava">{t('nav.strava')}</NavLink>
          <NavLink to="/" end>{t('nav.thisWeek')}</NavLink>
          <button
            type="button"
            className="nav-signout"
            title={email}
            onClick={async () => { await signOut(); setEmail(null) }}
          >
            {t('auth.signOut')}
          </button>
        </div>
      </nav>
      <main>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/new" element={<GoalForm />} />
          <Route path="/goals/:goalId" element={<PlanView />} />
          <Route path="/history" element={<GoalHistory />} />
          <Route path="/strava" element={<Strava />} />
        </Routes>
      </main>
    </BrowserRouter>
  )
}
