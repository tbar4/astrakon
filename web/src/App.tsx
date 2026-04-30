import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import SetupPage from './pages/SetupPage'
import GamePage from './pages/GamePage'
import ResultPage from './pages/ResultPage'
import SpectatePage from './pages/SpectatePage'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<SetupPage />} />
        <Route path="/game/:sessionId" element={<GamePage />} />
        <Route path="/spectate/:sessionId" element={<SpectatePage />} />
        <Route path="/result/:sessionId" element={<ResultPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
