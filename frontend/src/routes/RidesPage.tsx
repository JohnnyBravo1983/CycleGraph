// frontend/src/routes/RidesPage.tsx

export default function RidesPage() {
  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-2xl font-semibold tracking-tight">Rides / Økter</h1>
      <p className="text-slate-600 max-w-xl">
        Her vil du etter hvert se en liste over øktene dine, hentet fra Strava
        og analysert med CycleGraph. Du vil kunne filtrere, merke FTP-økter og
        åpne detaljer for hver ride.
      </p>

      <div className="border border-dashed border-slate-300 rounded-lg px-4 py-8 text-slate-500 text-sm">
        TODO: Implementer øktliste med kobling til backend (summary.csv / sessions-API).
      </div>
    </div>
  );
}
