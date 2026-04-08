import { BrowserRouter, Routes, Route } from 'react-router-dom'

// Pages / Views (shells; populated in subsequent steps)
import DashboardPage from './components/Dashboard/DashboardPage.jsx'
import MapPage from './components/Map/MapPage.jsx'
import ScoresPage from './components/Scores/ScoresPage.jsx'
import ReportsPage from './components/Reports/ReportsPage.jsx'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/map" element={<MapPage />} />
        <Route path="/scores" element={<ScoresPage />} />
        <Route path="/reports" element={<ReportsPage />} />
      </Routes>
    </BrowserRouter>
  )
}
