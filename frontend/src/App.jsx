import { BrowserRouter, NavLink, Route, Routes } from 'react-router-dom'
import GoalForm from './pages/GoalForm.jsx'
import GoalHistory from './pages/GoalHistory.jsx'
import PlanView from './pages/PlanView.jsx'

export default function App() {
  return (
    <BrowserRouter basename="/app">
      <nav>
        <span className="nav-brand">Running Coach</span>
        <div className="nav-links">
          <NavLink to="/" end>New Goal</NavLink>
          <NavLink to="/history">History</NavLink>
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
