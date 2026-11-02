import { BrowserRouter, NavLink, Route, Routes } from 'react-router-dom'
import GoalForm from './pages/GoalForm.jsx'
import GoalHistory from './pages/GoalHistory.jsx'
import PlanView from './pages/PlanView.jsx'
import { t } from './i18n/index.js'

export default function App() {
  return (
    <BrowserRouter basename="/app">
      <nav>
        <span className="nav-brand">{t('nav.brand')}</span>
        <div className="nav-links">
          <NavLink to="/new">{t('nav.newGoal')}</NavLink>
          <NavLink to="/history">{t('nav.history')}</NavLink>
          <NavLink to="/" end>{t('nav.thisWeek')}</NavLink>
        </div>
      </nav>
      <main>
        <Routes>
          <Route path="/" element={<GoalForm />} />
          <Route path="/goals/:goalId" element={<PlanView />} />
          <Route path="/history" element={<GoalHistory />} />
        </Routes>
      </main>
    </BrowserRouter>
  )
}
