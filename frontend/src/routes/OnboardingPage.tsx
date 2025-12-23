import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useProfileStore } from "../state/profileStore";
import ProfileForm from "../components/ProfileForm";
import { cgApi, type StatusResp } from "../lib/cgApi";

export default function OnboardingPage() {
  const navigate = useNavigate();
  const { draft, loading, error, init, setDraft, applyDefaults, commit } =
    useProfileStore();

  // Strava status UI state
  const [st, setSt] = useState<StatusResp | null>(null);
  const [stBusy, setStBusy] = useState(false);
  const [stErr, setStErr] = useState<string | null>(null);

  useEffect(() => {
    init();
  }, [init]);

  const onFinish = async () => {
    const ok = await commit();
    if (ok) navigate("/dashboard");
  };

  async function checkStravaStatus() {
    setStBusy(true);
    setStErr(null);
    try {
      // IMPORTANT: /status sets cg_uid cookie (backend-origin),
      // and cgApi must use credentials:"include"
      const s = await cgApi.status();
      setSt(s);
    } catch (e: any) {
      setStErr(e?.message || String(e));
    } finally {
      setStBusy(false);
    }
  }

  function connectStrava() {
    // Open in same tab so OAuth callback flow is clean
    window.open(`${cgApi.baseUrl()}/login`, "_self");
  }

  const hasTokens = st?.has_tokens === true;

  return (
    <div className="max-w-xl mx-auto flex flex-col gap-4">
      <h1 className="text-2xl font-semibold tracking-tight">
        Velkommen til CycleGraph
      </h1>

      <p className="text-slate-600">
        Før vi starter trenger vi et grovt utgangspunkt for profilen din.
        Dette kan justeres senere.
      </p>

      {error ? <div className="text-red-600 text-sm">{error}</div> : null}

      <ProfileForm value={draft} onChange={setDraft} disabled={loading} />

      {/* Strava Connect section (Onboarding-appropriate) */}
      <div className="rounded-lg border bg-white p-4">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h2 className="font-semibold">Koble til Strava</h2>
            <p className="text-sm text-slate-600 mt-1">
              For å hente turer og bygge din første analyse trenger vi tilgang til Strava.
            </p>
            <p className="text-xs text-slate-500 mt-1">
              Backend: <span className="font-mono">{cgApi.baseUrl()}</span>
            </p>
          </div>

          <div className="flex gap-2 shrink-0">
            <button
              type="button"
              onClick={checkStravaStatus}
              disabled={stBusy}
              className="px-3 py-2 rounded border text-sm disabled:opacity-60"
              title="Kaller /status og setter cg_uid cookie"
            >
              {stBusy ? "Sjekker…" : "Check status"}
            </button>

            <button
              type="button"
              onClick={connectStrava}
              disabled={stBusy}
              className="px-3 py-2 rounded bg-slate-900 text-white text-sm hover:bg-slate-800 disabled:bg-slate-400"
              title="Åpner backend /login"
            >
              Connect Strava
            </button>
          </div>
        </div>

        <div className="mt-3 text-sm">
          <div className="flex flex-wrap gap-x-4 gap-y-1 text-slate-700">
            <div>
              has_tokens:{" "}
              <span className="font-semibold">
                {String(st?.has_tokens ?? "unknown")}
              </span>
            </div>
            <div>
              expires_in_sec:{" "}
              <span className="font-semibold">
                {String(st?.expires_in_sec ?? "n/a")}
              </span>
            </div>
            <div>
              uid:{" "}
              <span className="font-mono text-xs">
                {String(st?.uid ?? "n/a")}
              </span>
            </div>
          </div>

          {!hasTokens && st ? (
            <div className="mt-2 text-xs text-slate-600">
              Mangler token. Trykk <span className="font-semibold">Connect Strava</span>, fullfør innlogging,
              kom tilbake hit og trykk <span className="font-semibold">Check status</span>.
            </div>
          ) : null}

          {stErr ? (
            <div className="mt-2 text-xs text-red-600 whitespace-pre-wrap">
              {stErr}
            </div>
          ) : null}
        </div>
      </div>

      <div className="flex gap-3 pt-2">
        <button
          type="button"
          onClick={applyDefaults}
          disabled={loading}
          className="px-4 py-2 rounded border"
        >
          Bruk standardverdier
        </button>

        <button
          type="button"
          onClick={onFinish}
          disabled={loading}
          className="px-4 py-2 rounded bg-slate-900 text-white hover:bg-slate-800 disabled:bg-slate-400"
        >
          Fullfør og gå videre
        </button>
      </div>
    </div>
  );
}
