// frontend/src/routes/LandingPage.tsx
import { Link } from "react-router-dom";

export function LandingPage() {
  return (
    <div className="flex flex-col gap-8">
      <section>
        <h1 className="text-3xl font-bold tracking-tight mb-2">
          CycleGraph
        </h1>
        <p className="text-slate-700 max-w-xl">
          CycleGraph hjelper deg å forstå{" "}
          <span className="font-semibold">Precision Watt</span>, se utviklingen
          i treningen din over tid og koble sammen økter, profiler og mål.
        </p>
      </section>

      <section className="flex flex-col md:flex-row gap-4">
        <Link
          to="/login"
          className="inline-flex items-center justify-center px-4 py-2 rounded-xl border border-slate-800 font-medium bg-slate-900 text-white hover:bg-slate-800"
        >
          Logg inn
        </Link>
        <Link
          to="/signup"
          className="inline-flex items-center justify-center px-4 py-2 rounded-xl border border-slate-300 font-medium bg-white text-slate-900 hover:bg-slate-50"
        >
          Registrer ny bruker
        </Link>
      </section>

      <section className="text-sm text-slate-600 max-w-xl">
        <h2 className="font-semibold mb-1">Hva er Precision Watt?</h2>
        <p>
          Precision Watt er et fysisk beregnet watt-tall som tar hensyn til
          aerodynamikk, motbakker, vind og rullemotstand. Målet er å gi deg en
          mer stabil måling av innsats enn bare hastighet eller puls alene.
        </p>
      </section>
    </div>
  );
}