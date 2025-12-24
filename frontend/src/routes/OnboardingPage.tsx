import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { useProfileStore } from "../state/profileStore";
import ProfileForm from "../components/ProfileForm";
import { cgApi, type StatusResp } from "../lib/cgApi";

function getErrMsg(err: unknown): string {
  if (err instanceof Error) return err.message;
  if (typeof err === "string") return err;
  try {
    return JSON.stringify(err);
  } catch {
    return String(err);
  }
}

type TokenState = "unknown" | "missing" | "expired" | "valid";

function getTokenState(st: StatusResp | null): TokenState {
  if (!st) return "unknown";
  if (st.has_tokens !== true) return "missing";
  const exp = typeof st.expires_in_sec === "number" ? st.expires_in_sec : null;
  if (exp !== null && exp <= 0) return "expired";
  return "valid";
}

export default function OnboardingPage() {
  const navigate = useNavigate();
  const location = useLocation();

  const { draft, loading, error, init, setDraft, applyDefaults, commit } =
    useProfileStore();

  // Strava status UI state
  const [st, setSt] = useState<StatusResp | null>(null);
  const [stBusy, setStBusy] = useState(false);
  const [stErr, setStErr] = useState<string | null>(null);

  useEffect(() => {
    init();
  }, [init]);

  // Auto-check status:
  // - on mount
  // - when URL changes (OAuth redirect back often changes ?code/&state, etc.)
  useEffect(() => {
    (async () => {
      setStBusy(true);
      setStErr(null);
      try {
        const s = await cgApi.status(); // sets cg_uid cookie (backend-origin)
        setSt(s);
      } catch (e: unknown) {
        setSt(null);
        setStErr(getErrMsg(e));
      } finally {
        setStBusy(false);
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.pathname, location.search]);

  const onFinish = async () => {
    const ok = await commit();
    if (ok) navigate("/dashboard");
  };

  function connectStrava() {
    // One-button flow: start OAuth and come back here
    const next = encodeURIComponent(window.location.href);
    window.open(`${cgApi.baseUrl()}/login?next=${next}`, "_self");
  }

  const tokenState = getTokenState(st);
  const tokenValid = tokenState === "valid";
  const tokenExpired = tokenState === "expired";
  const hasTokens = st?.has_tokens === true;

  return (
    <div className="max-w-xl mx-auto flex flex-col gap-4">
      <h1 className="text-2xl font-semibold tracking-tight">
        Velkommen til CycleGraph
      </h1>

      <p className="text-slate-600">
        Før vi starter trenger vi et grovt utgangspunkt for profilen din. Dette
        kan justeres senere.
      </p>

      {error ? <div className="text-red-600 text-sm">{error}</div> : null}

      <ProfileForm value={draft} onChange={setDraft} disabled={loading} />

      {/* Strava Connect section (Onboarding-appropriate) */}
      <div className="rounded-lg border bg-white p-4">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h2 className="font-semibold">Koble til Strava</h2>
            <p className="text-sm text-slate-600 mt-1">
              For å hente turer og bygge din første analyse trenger vi tilgang
              til Strava.
            </p>
            <p className="text-xs text-slate-500 mt-1">
              Backend: <span className="font-mono">{cgApi.baseUrl()}</span>
            </p>
          </div>

          {/* Single action button (no "Check status") */}
          <div className="shrink-0">
            {tokenValid ? (
              <div className="px-3 py-2 rounded border text-sm text-slate-700 bg-slate-50">
                Strava er tilkoblet ✅
              </div>
            ) : (
              <button
                type="button"
                onClick={connectStrava}
                disabled={stBusy}
                className="px-3 py-2 rounded bg-slate-900 text-white text-sm hover:bg-slate-800 disabled:bg-slate-400"
                title={
                  tokenExpired
                    ? "Token er utløpt – koble til på nytt"
                    : "Koble til Strava"
                }
              >
                {stBusy
                  ? "Sjekker…"
                  : tokenExpired
                  ? "Reconnect Strava"
                  : "Connect Strava"}
              </button>
            )}
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

          {tokenExpired ? (
            <div className="mt-2 text-xs text-amber-700">
              Strava-token er utløpt. Trykk <b>Reconnect Strava</b> eller importer
              en tur senere i Dashboard for å trigge refresh.
            </div>
          ) : null}

          {!hasTokens && st ? (
            <div className="mt-2 text-xs text-slate-600">
              Du har ikke koblet til Strava ennå. Trykk{" "}
              <span className="font-semibold">Connect Strava</span> og fullfør
              innlogging – så oppdateres status automatisk når du kommer tilbake.
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
