import { BrowserRouter, NavLink, Route, Routes } from 'react-router-dom'
import Dashboard from './pages/Dashboard.jsx'
import GoalForm from './pages/GoalForm.jsx'
import GoalHistory from './pages/GoalHistory.jsx'
import PlanView from './pages/PlanView.jsx'

export default function App() {
  return (
    <BrowserRouter basename="/app">
      <nav>
        <span className="nav-brand">Running Coach</span>
        <div className="nav-links">
          <NavLink to="/new">Mục Tiêu Mới</NavLink>
          <NavLink to="/history">Lịch Sử</NavLink>
          <NavLink to="/" end>Tuần Này</NavLink>
        </div>
      </nav>
      <main>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/new" element={<GoalForm />} />
          <Route path="/goals/:goalId" element={<PlanView />} />
          <Route path="/history" element={<GoalHistory />} />
        </Routes>
      </main>
    </BrowserRouter>
  )
}
