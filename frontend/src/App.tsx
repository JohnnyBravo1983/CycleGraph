// frontend/src/App.tsx
import { Link, Outlet } from "react-router-dom";
import DemoBanner from "./components/DemoBanner";

export default function App() {
  return (
    <div className="min-h-screen bg-slate-50">
      <header className="border-b bg-white">
        <div className="max-w-5xl mx-auto px-6 py-3 flex items-center justify-between">
          <div className="text-lg font-semibold tracking-tight">CycleGraph</div>

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

          {/* Auth entry (so login/signup never "disappear") */}
          <nav className="flex items-center gap-2">
            <Link
              to="/login"
              className="px-3 py-2 rounded-xl text-sm font-medium text-slate-700 hover:bg-slate-100"
            >
              Log in
            </Link>
            <Link
              to="/signup"
              className="px-3 py-2 rounded-xl text-sm font-medium text-slate-700 hover:bg-slate-100"
            >
              Sign up
            </Link>
          </nav>
        </div>
      </header>

      <DemoBanner />

      {/* PROD FINGERPRINT (temporary) */}
      <div className="max-w-5xl mx-auto px-6">
        <div className="mt-4 rounded-xl border border-red-300 bg-red-50 px-4 py-3 text-sm font-semibold text-red-800">
          PROD FINGERPRINT 2026-01-23
        </div>
      </div>

        <main className="max-w-5xl mx-auto px-6 py-6">
        <Outlet />
      </main>
    </div>
  );
}
