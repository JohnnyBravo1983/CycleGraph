// frontend/src/App.tsx
import { Outlet } from "react-router-dom";
import DemoBanner from "./components/DemoBanner";

export default function App() {
  return (
    <div className="min-h-screen bg-slate-50">
      <header className="border-b bg-white">
        <div className="max-w-5xl mx-auto px-6 py-3 flex items-center justify-between">
          <div className="text-lg font-semibold tracking-tight">CycleGraph</div>
          {/* Navigasjon kommer senere (Dashboard / Rides / Profile osv.) */}
        </div>
      </header>

      <DemoBanner />

      <main className="max-w-5xl mx-auto px-6 py-6">
        <Outlet />
      </main>
    </div>
  );
}
