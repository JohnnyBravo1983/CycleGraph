// frontend/src/routes/TrendsPage.tsx

export default function TrendsPage() {
  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-2xl font-semibold tracking-tight">Trends / Trender</h1>
      <p className="text-slate-600 max-w-xl">
        Her vil du etter hvert kunne se utviklingen din over tid, for eksempel
        FTP-trend og forholdet mellom watt og puls (W/HR) for ulike perioder.
      </p>

      <div className="border border-dashed border-slate-300 rounded-lg px-4 py-8 text-slate-500 text-sm">
        TODO: Implementer trendgrafer basert på analyserte økter og filtrering
        på periode.
      </div>
    </div>
  );
}
