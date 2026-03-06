import { Routes, Route, Navigate } from 'react-router-dom'
import { Layout } from './components/Layout'
import { Dashboard } from './pages/Dashboard'
import { NewTrade } from './pages/NewTrade'
import { History } from './pages/History'
import { Analytics } from './pages/Analytics'
import { Backtest } from './pages/Backtest'
import { Toaster } from './components/Toaster'

function App() {
  return (
    <Toaster>
      <Routes>
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
        <Route path="/" element={<Layout />}>
          <Route path="dashboard" element={<Dashboard />} />
          <Route path="trade" element={<NewTrade />} />
          <Route path="history" element={<History />} />
          <Route path="analytics" element={<Analytics />} />
          <Route path="backtest" element={<Backtest />} />
        </Route>
      </Routes>
    </Toaster>
  )
}

export default App
