// frontend/src/routes/GoalsPage.tsx

export default function GoalsPage() {
  return (
    <div className="flex flex-col gap-4 max-w-xl">
      <h1 className="text-2xl font-semibold tracking-tight">Goals / Mål</h1>
      <p className="text-slate-600">
        Her vil du etter hvert kunne sette mål for FTP, watt/puls-effektivitet
        og datoer for når du ønsker å nå målene dine. Disse vil kobles mot
        trendgrafene slik at du ser om du er i rute.
      </p>

      <div className="border border-dashed border-slate-300 rounded-lg px-4 py-8 text-slate-500 text-sm">
        TODO: Implementer målsetting og visning av progresjon mot mål.
      </div>
    </div>
  );
}
