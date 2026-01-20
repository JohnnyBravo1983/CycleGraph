// frontend/src/routes/ImportRidesPage.tsx
import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

type Period = "all" | "3years" | "1year" | "6months";

type SyncOkResp = {
  ok: true;
  imported_count?: number;
  ride_ids?: string[];
  [k: string]: unknown;
};

type SyncErrResp = {
  ok: false;
  error?: string;
  [k: string]: unknown;
};

type SyncResp = SyncOkResp | SyncErrResp;

function prettyPeriod(p: Period) {
  switch (p) {
    case "all":
      return "All";
    case "3years":
      return "Last 3 years";
    case "1year":
      return "Last 1 year";
    case "6months":
      return "Last 6 months";
  }
}

function mapErrorMessage(raw?: string) {
  if (!raw) return "Ukjent feil.";
  // små, nyttige mapper (Sprint 2)
  if (raw.includes("tokens")) return "Strava-tilkobling mangler eller er utløpt. Koble til Strava på nytt.";
  if (raw.includes("unauthorized")) return "Du er ikke logget inn (session utløpt). Logg inn på nytt.";
  return raw;
}

export default function ImportRidesPage() {
  const navigate = useNavigate();

  const [period, setPeriod] = useState<Period>("3years"); // ✅ default hard krav
  const [status, setStatus] = useState<"idle" | "importing" | "done" | "error">("idle");
  const [error, setError] = useState<string | null>(null);
  const [importedCount, setImportedCount] = useState<number | null>(null);

  const disabled = status === "importing";
  const canContinue = status === "done" || status === "error";

  const title = useMemo(() => {
    if (status === "importing") return "Importerer rides…";
    if (status === "done") return "Import ferdig";
    if (status === "error") return "Import feilet";
    return "Import rides?";
  }, [status]);

  async function onImport() {
    setError(null);
    setImportedCount(null);
    setStatus("importing");

    try {
      const resp = await fetch("/api/strava/sync", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ period }),
      });

      // backend skal returnere deterministisk JSON, men vi håndterer robust
      let data: SyncResp | null = null;
      try {
        data = (await resp.json()) as SyncResp;
      } catch {
        data = null;
      }

      if (!resp.ok) {
        const msg =
          (data && "error" in data && typeof data.error === "string" && data.error) ||
          `HTTP ${resp.status}`;
        setError(mapErrorMessage(msg));
        setStatus("error");
        return;
      }

      if (!data || typeof data !== "object") {
        setError("Ugyldig respons fra server.");
        setStatus("error");
        return;
      }

      if ("ok" in data && data.ok === false) {
        setError(mapErrorMessage(data.error));
        setStatus("error");
        return;
      }

      const count = (data.imported_count ?? 0) as number;
      setImportedCount(count);
      setStatus("done");

      // Sprint 2 "toast": lagre en enkel melding vi kan lese på dashboard senere (PATCH 2.4-C)
      // Dette er ufarlig selv om dashboard ikke leser den enda.
      try {
        if (count > 0) {
          sessionStorage.setItem("cg_toast", `✅ ${count} rides importert!`);
        } else {
          sessionStorage.setItem("cg_toast", `Ingen rides funnet i perioden (${prettyPeriod(period)}).`);
        }
      } catch {
        // ignore
      }
    } catch (e: unknown) {
      setError("Network error – kunne ikke kontakte serveren.");
      setStatus("error");
    }
  }

  function onSkip() {
    // Ingen import: rett til dashboard
    navigate("/dashboard", { replace: true });
  }

  function onContinue() {
    navigate("/dashboard", { replace: true });
  }

  return (
    <div className="p-6 max-w-xl">
      <h1 className="text-2xl font-semibold">{title}</h1>

      <p className="mt-2 text-sm opacity-80">
        Velg hvor langt tilbake vi skal hente rides fra Strava. Du kan også hoppe over og importere senere.
      </p>

      <div className="mt-6 space-y-3">
        <label className="flex items-center gap-3 cursor-pointer">
          <input
            type="radio"
            name="period"
            value="all"
            checked={period === "all"}
            disabled={disabled}
            onChange={() => setPeriod("all")}
          />
          <span>All</span>
        </label>

        <label className="flex items-center gap-3 cursor-pointer">
          <input
            type="radio"
            name="period"
            value="3years"
            checked={period === "3years"}
            disabled={disabled}
            onChange={() => setPeriod("3years")}
          />
          <span>Last 3 years</span>
          <span className="text-xs opacity-70">(default)</span>
        </label>

        <label className="flex items-center gap-3 cursor-pointer">
          <input
            type="radio"
            name="period"
            value="1year"
            checked={period === "1year"}
            disabled={disabled}
            onChange={() => setPeriod("1year")}
          />
          <span>Last 1 year</span>
        </label>

        <label className="flex items-center gap-3 cursor-pointer">
          <input
            type="radio"
            name="period"
            value="6months"
            checked={period === "6months"}
            disabled={disabled}
            onChange={() => setPeriod("6months")}
          />
          <span>Last 6 months</span>
        </label>
      </div>

      {/* importing UX */}
      {status === "importing" && (
        <div className="mt-6 flex items-center gap-3">
          <div className="h-5 w-5 rounded-full border-2 border-current border-t-transparent animate-spin" />
          <div className="text-sm">
            Dette kan ta noen minutter… Du kan fortsette til dashboard når importen er ferdig.
          </div>
        </div>
      )}

      {/* success */}
      {status === "done" && (
        <div className="mt-6 text-sm">
          <div className="font-medium">
            {importedCount && importedCount > 0
              ? `✅ Import ferdig: ${importedCount} rides importert`
              : "✅ Import ferdig: Ingen rides funnet i valgt periode"}
          </div>
          <div className="opacity-80 mt-1">Trykk “Fortsett til dashboard”.</div>
        </div>
      )}

      {/* error */}
      {status === "error" && (
        <div className="mt-6 text-sm">
          <div className="font-medium">⚠️ Import feilet</div>
          <div className="mt-1 opacity-90">{error ?? "Ukjent feil."}</div>
          <div className="mt-2 opacity-80">Du kan likevel fortsette til dashboard.</div>
        </div>
      )}

      {/* actions */}
      <div className="mt-8 flex gap-3">
        <button
          className="px-4 py-2 rounded border"
          disabled={disabled}
          onClick={onImport}
          aria-disabled={disabled}
        >
          Importer rides
        </button>

        <button className="px-4 py-2 rounded border" disabled={disabled} onClick={onSkip}>
          Hopp over
        </button>

        {canContinue && (
          <button className="px-4 py-2 rounded border" onClick={onContinue}>
            Fortsett til dashboard
          </button>
        )}
      </div>
    </div>
  );
}
