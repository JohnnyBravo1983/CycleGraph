// frontend/src/App.tsx
import { Link, Outlet } from "react-router-dom";

export default function App() {
  return (
    <div className="min-h-screen bg-slate-50">
      <header className="border-b bg-white">
        <div className="max-w-5xl mx-auto px-6 py-4 flex items-center justify-between">
          {/* Brand */}
          <Link
            to="/"
            className="flex items-center gap-2 select-none"
            aria-label="CycleGraph home"
          >
            <div className="h-9 w-9 rounded-2xl bg-slate-900 flex items-center justify-center text-white font-bold">
              CG
            </div>
            <div className="leading-tight">
              <div className="text-lg font-semibold tracking-tight text-slate-900">
                CycleGraph
              </div>
              <div className="text-xs text-slate-500 -mt-0.5">
                Precision Watt insights
              </div>
            </div>
          </Link>

          {/* Main navigation */}
          <nav className="flex items-center gap-2">
            <Link
              to="/dashboard"
              className="px-3 py-2 rounded-xl text-sm font-medium text-slate-700 hover:bg-slate-100"
            >
              Dashboard
            </Link>
            <Link
              to="/rides"
              className="px-3 py-2 rounded-xl text-sm font-medium text-slate-700 hover:bg-slate-100"
            >
              Rides
            </Link>
            <Link
              to="/leaderboards"
              className="px-3 py-2 rounded-xl text-sm font-medium text-slate-700 hover:bg-slate-100"
            >
              Leaderboards
            </Link>
            <Link
              to="/how-it-works"
              className="px-3 py-2 rounded-xl text-sm font-medium text-slate-700 hover:bg-slate-100"
            >
              How it works
            </Link>
          </nav>

          {/* Auth entry */}
          <nav className="flex items-center gap-2">
            <Link
              to="/login"
              className="px-3 py-2 rounded-xl text-sm font-medium text-slate-700 hover:bg-slate-100"
            >
              Log in
            </Link>
            <Link
              to="/signup"
              className="px-3 py-2 rounded-xl text-sm font-semibold text-white bg-slate-900 hover:bg-slate-800 rounded-xl px-3 py-2"
            >
              Sign up
            </Link>
          </nav>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-6 py-6">
        <Outlet />
      </main>
    </div>
  );
}
