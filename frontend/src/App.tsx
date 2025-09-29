// frontend/src/App.tsx
import { NavLink, Outlet } from "react-router-dom";

export default function App() {
  return (
    <div className="min-h-screen">
      <header className="border-b bg-white">
        <div className="max-w-5xl mx-auto px-6 py-3 flex items-center justify-between">
          <div className="text-lg font-semibold">CycleGraph</div>
          <nav className="flex items-center gap-2 text-sm">
            <NavLink
              to="/session/mock"
              className={({ isActive }) =>
                `px-3 py-1.5 rounded-2xl border ${isActive ? "shadow" : ""}`
              }
              end
            >
              Home
            </NavLink>
            <NavLink
              to="/session/mock"
              className={({ isActive }) =>
                `px-3 py-1.5 rounded-2xl border ${isActive ? "shadow" : ""}`
              }
            >
              Session
            </NavLink>
          </nav>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-6 py-6">
        <Outlet />
      </main>
    </div>
  );
}
