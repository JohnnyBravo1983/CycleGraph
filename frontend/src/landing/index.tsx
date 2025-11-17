// frontend/src/landing/index.tsx
import React, { useEffect, useState } from "react";
import { SEO } from "./SEO";
import { getTrendSummary } from "../lib/api";

type TrendTeaserState =
  | { status: "idle" | "loading" }
  | { status: "ok" }
  | { status: "error" };

export const Landing: React.FC = () => {
  const [trendState, setTrendState] = useState<TrendTeaserState>({ status: "idle" });

  useEffect(() => {
    let cancelled = false;
    setTrendState({ status: "loading" });

    getTrendSummary()
      .then(() => {
        if (!cancelled) {
          setTrendState({ status: "ok" });
        }
      })
      .catch(() => {
        if (!cancelled) {
          setTrendState({ status: "error" });
        }
      });

    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-50 flex flex-col">
      <SEO />

      <header className="border-b border-slate-800">
        <div className="mx-auto max-w-5xl px-4 py-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="h-8 w-8 rounded-full bg-sky-500/90 flex items-center justify-center font-bold text-xs">
              CG
            </div>
            <span className="font-semibold tracking-tight">CycleGraph</span>
          </div>
          <nav className="flex items-center gap-4 text-sm text-slate-300">
            <span className="hidden sm:inline">Precision watt</span>
            <span className="hidden sm:inline">Trendanalyse</span>
            <span className="hidden sm:inline">Tren smartere</span>
          </nav>
        </div>
      </header>

      <main className="flex-1">
        <section className="mx-auto max-w-5xl px-4 py-12 lg:py-20 grid lg:grid-cols-2 gap-10 items-center">
          <div>
            <h1 className="text-3xl md:text-5xl font-semibold tracking-tight mb-4">
              Få kontroll på watt, puls
              <span className="block text-sky-400">og hvor effektiv du egentlig er.</span>
            </h1>
            <p className="text-slate-300 text-base md:text-lg mb-6">
              CycleGraph kobler sammen watt, puls, vær og terreng for å gi deg et ærlig bilde av
              hvor mye kraft du faktisk legger i pedalene – og hvor mye som forsvinner i luftmotstand
              og rullemotstand.
            </p>

            <div className="flex flex-wrap items-center gap-3 mb-6">
              <a
                href="#"
                className="inline-flex items-center rounded-full px-5 py-2.5 text-sm font-medium bg-sky-500 hover:bg-sky-400 text-slate-950 transition"
              >
                Bli med i beta-listen
              </a>
              <span className="text-xs text-slate-400">
                Begrenset antall plasser – fokus på seriøse syklister.
              </span>
            </div>

            <ul className="space-y-2 text-sm text-slate-300">
              <li>• Se hvor mye watt som faktisk driver deg fremover.</li>
              <li>• Sammenlign økter på samme løype over tid med like forutsetninger.</li>
              <li>• Bruk precision watt som kompass når du skal justere trening og form.</li>
            </ul>
          </div>

          <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-4 md:p-5">
            <p className="text-xs font-medium text-sky-400 mb-2 uppercase tracking-wide">
              Live data fra backend
            </p>
            <p className="text-sm text-slate-200 mb-4">
              Landing-siden er koblet til samme analyse-motor som resten av CycleGraph. Her sjekker vi
              at trend-endepunktet svarer som forventet.
            </p>

            <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-4 text-sm">
              {trendState.status === "loading" && (
                <p data-testid="landing-trend-loading" className="text-slate-400">
                  Kobler til trend-endepunktet&hellip;
                </p>
              )}
              {trendState.status === "ok" && (
                <p data-testid="landing-trend-ok" className="text-emerald-400">
                  ✅ Trend-endepunktet svarer – klar for ekte watt- og pulsdata.
                </p>
              )}
              {trendState.status === "error" && (
                <p data-testid="landing-trend-error" className="text-amber-400">
                  ⚠️ Fikk ikke kontakt med trend-endepunktet akkurat nå. Det påvirker ikke innlogging
                  eller analyse, men bør sjekkes før full lansering.
                </p>
              )}
            </div>

            <p className="mt-4 text-xs text-slate-500">
              Denne boksen er primært for intern QA – den blir skjult eller forenklet i offentlig
              lansering.
            </p>
          </div>
        </section>
      </main>

      <footer className="border-t border-slate-800">
        <div className="mx-auto max-w-5xl px-4 py-4 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2">
          <p className="text-xs text-slate-500">
            © {new Date().getFullYear()} CycleGraph. Bygget for syklister som bryr seg om tallene.
          </p>
          <p className="text-xs text-slate-500">
            Denne siden er i <span className="text-sky-400">preview-modus</span> og vises kun på
            interne builds.
          </p>
        </div>
      </footer>
    </div>
  );
};

export default Landing;
