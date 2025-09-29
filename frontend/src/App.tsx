import { Link, Routes, Route } from 'react-router-dom'
import Home from './routes/Home'
import SessionView from './routes/SessionView'

export default function App() {
  return (
    <div className="min-h-screen bg-gray-50 text-gray-800">
      <header className="border-b bg-white">
        <div className="mx-auto max-w-4xl px-4 py-3 flex items-center justify-between">
          <h1 className="text-lg font-semibold">CycleGraph — Sprint 8</h1>
          <nav className="text-sm space-x-4">
            <Link className="hover:underline" to="/">Home</Link>
            <Link className="hover:underline" to="/session/mock">Session (mock)</Link>
          </nav>
        </div>
      </header>

      <main className="mx-auto max-w-4xl px-4 py-6">
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/session/:id" element={<SessionView />} />
          <Route path="*" element={<div>Not found</div>} />
        </Routes>
      </main>
    </div>
  )
}
