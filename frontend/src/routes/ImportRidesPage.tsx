// frontend/src/routes/ImportRidesPage.tsx
import { useEffect, useMemo, useRef, useState } from "react";
import { cgApi } from "../lib/cgApi";

type Period = "all" | "3years" | "1year" | "6months";

type SyncOkResp = {
  ok: true;
  uid?: string;
  after?: number;
  before?: number;
  days?: number | null;

  page?: number;
  per_page?: number;
  batch_limit?: number;

  imported_count?: number;
  imported?: string[];

  errors_count?: number;
  errors?: Array<Record<string, unknown>>;

  next_page?: number | null;
  done?: boolean;

  // ✅ chunked sync: soft-429 “pause & continue”
  rate_limited?: boolean;
  retry_after_s?: number;

  [k: string]: unknown;
};

type SyncErrResp = {
  ok: false;
  error?: string;
  detail?: string;
  [k: string]: unknown;
};

type SyncResp = SyncOkResp | SyncErrResp;

type ImportStatus = "idle" | "importing" | "done" | "error" | "cancelled";

function prettyPeriod(p: Period) {
  switch (p) {
    case "all":
      return "All (begrenset av server-cap)";
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
  const s = raw.toLowerCase();

  if (s.includes("missing_server_tokens_for_user") || s.includes("tokens")) {
    return "Strava-tilkobling mangler eller er utløpt. Koble til Strava på nytt.";
  }
  if (s.includes("not authenticated") || s.includes("unauthorized") || s.includes("http 401")) {
    return "Du er ikke logget inn (session utløpt). Logg inn på nytt.";
  }
  if (s.includes("http 422")) {
    return "Ugyldige parametre til sync-endpointet (422).";
  }
  if (s.includes("rate_limited") || s.includes("429") || s.includes("strava_error_429")) {
    return "Strava rate-limited (429). Importen vil prøve igjen automatisk.";
  }

  return raw;
}

function daysForPeriod(p: Period): number {
  // Backend cap: days <= 365 per request/window.
  switch (p) {
    case "6months":
      return 183;
    case "1year":
      return 365;
    case "3years":
      return 365; // i denne versjonen henter vi i praksis 1 år per “run”
    case "all":
      return 365;
  }
}

function defaultBatchLimit(p: Period): number {
  // Backend cap: batch_limit <= 200
  switch (p) {
    case "6months":
      return 100;
    case "1year":
      return 150;
    case "3years":
      return 150;
    case "all":
      return 150;
  }
}

function defaultPerPage(_p: Period): number {
  // Backend cap: per_page <= 200 (Strava per_page)
  return 50;
}

function safeNum(x: unknown, fallback: number): number {
  const n = Number(x);
  return Number.isFinite(n) ? n : fallback;
}

function isRecord(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null;
}

export default function ImportRidesPage() {
  const goDashboard = () => window.location.replace("/dashboard");

  // ✅ PATCH C1 — default period til 6 months
  const [period, setPeriod] = useState<Period>("6months"); // ✅ early onboarding: only option enabled

  // ✅ PATCH C2 — MVP launch copy + helper
  const MVP_LAUNCH_COPY = "Available on MVP launch 1 April 2026";
  const ENABLED_PERIOD: Period = "6months";

  function isEnabledPeriod(p: Period) {
    return p === ENABLED_PERIOD;
  }

  const [status, setStatus] = useState<ImportStatus>("idle");
  const [error, setError] = useState<string | null>(null);

  // Progress UI
  const [progressMsg, setProgressMsg] = useState<string | null>(null);
  const [importedTotal, setImportedTotal] = useState<number>(0);
  const [lastBatchCount, setLastBatchCount] = useState<number>(0);
  const [page, setPage] = useState<number>(1);
  const [nextPage, setNextPage] = useState<number | null>(null);
  const [done, setDone] = useState<boolean>(false);

  // Optional debug info
  const [lastImported, setLastImported] = useState<string[] | null>(null);
  const [lastErrors, setLastErrors] = useState<Array<Record<string, unknown>> | null>(null);

  const disabled = status === "importing";
  const canContinue = status === "done" || status === "error" || status === "cancelled";

  const abortRef = useRef<AbortController | null>(null);
  const runningRef = useRef(false);
  const importedSetRef = useRef<Set<string>>(new Set());

  const title = useMemo(() => {
    if (status === "importing") return "Importerer rides…";
    if (status === "done") return "Import ferdig";
    if (status === "cancelled") return "Import stoppet";
    if (status === "error") return "Import feilet";
    return "Import rides?";
  }, [status]);

  function resetProgress() {
    setError(null);
    setProgressMsg(null);
    setImportedTotal(0);
    setLastBatchCount(0);
    setPage(1);
    setNextPage(null);
    setDone(false);
    setLastImported(null);
    setLastErrors(null);
    importedSetRef.current = new Set();
  }

  async function sleep(ms: number) {
    await new Promise((r) => setTimeout(r, ms));
  }

  async function callSyncOnce(opts: {
    page: number;
    days: number;
    perPage: number;
    batchLimit: number;
    analyze: boolean;
    signal: AbortSignal;
  }): Promise<{ resp: Response; data: SyncResp | null }> {
    const qs = new URLSearchParams();
    qs.set("days", String(opts.days));
    qs.set("page", String(opts.page));
    qs.set("per_page", String(opts.perPage));
    qs.set("batch_limit", String(opts.batchLimit));
    qs.set("analyze", opts.analyze ? "1" : "0");

    // ✅ PATCH S2.5B-IMPORT-BASEURL (bruk backend base, ikke relativ /api)
    const url = `${cgApi.baseUrl()}/api/strava/sync?${qs.toString()}`;
  const resp = await fetch(url, {
  method: "POST",
  credentials: "include",
  headers: { "Content-Type": "application/json" },
  body: "{}",
  signal: opts.signal,
});


    let data: SyncResp | null = null;
    try {
      data = (await resp.json()) as SyncResp;
    } catch {
      data = null;
    }
    return { resp, data };
  }

  function extractRetryAfterMs(resp: Response): number | null {
    // Hvis backend forwarder Retry-After (kan forekomme ved ikke-chunked eller fremtidig endring)
    const ra = resp.headers.get("Retry-After");
    if (!ra) return null;
    const n = Number(ra);
    if (!Number.isFinite(n) || n <= 0) return null;
    return Math.min(120, Math.max(1, n)) * 1000;
  }

  async function runImport() {
    if (runningRef.current) return;
    runningRef.current = true;

    resetProgress();
    setStatus("importing");

    const controller = new AbortController();
    abortRef.current = controller;

    const days = daysForPeriod(period);
    const perPage = defaultPerPage(period);
    const batchLimit = defaultBatchLimit(period);

    let currentPage = 1;

    // ekstra safety hvis noe spinner evig uten fremdrift
    let hardStops = 0;
    const maxHardStops = 30;

    try {
      while (true) {
        if (controller.signal.aborted) {
          setStatus("cancelled");
          setProgressMsg("Import stoppet av bruker.");
          return;
        }

        setPage(currentPage);
        setProgressMsg(`Henter batch… (page ${currentPage})`);

        let resp: Response | null = null;
        let data: SyncResp | null = null;

        try {
          const out = await callSyncOnce({
            page: currentPage,
            days,
            perPage,
            batchLimit,
            analyze: true,
            signal: controller.signal,
          });
          resp = out.resp;
          data = out.data;
        } catch (e: any) {
          if (controller.signal.aborted) {
            setStatus("cancelled");
            setProgressMsg("Import stoppet av bruker.");
            return;
          }
          setProgressMsg("Nettverksfeil – prøver igjen om 5 sek…");
          await sleep(5000);
          continue;
        }

        // Hvis backend faktisk svarer med non-2xx (burde være sjeldent nå)
        if (!resp.ok) {
          const statusCode = resp.status;

          let msg = `HTTP ${statusCode}`;
          if (data && isRecord(data)) {
            const d = (data as any).detail;
            const e = (data as any).error;
            if (typeof d === "string" && d) msg = d;
            else if (typeof e === "string" && e) msg = e;
          }

          const mapped = mapErrorMessage(msg);

          if (statusCode === 429 || mapped.toLowerCase().includes("rate-limited")) {
            const raMs = extractRetryAfterMs(resp);
            const waitMs = raMs ?? 15000;
            setProgressMsg(`Rate limited (429) – venter ${Math.round(waitMs / 1000)}s og fortsetter…`);
            await sleep(waitMs);
            continue;
          }

          if (statusCode === 502) {
            setProgressMsg("Backend/Strava hiccup (502) – venter 5 sek og fortsetter…");
            await sleep(5000);
            continue;
          }

          setError(mapped);
          setStatus("error");
          return;
        }

        // OK, men valider data
        if (!data || typeof data !== "object") {
          setProgressMsg("Ugyldig respons fra server – prøver igjen om 3 sek…");
          await sleep(3000);
          continue;
        }

        if ("ok" in data && data.ok === false) {
          const msg =
            (typeof data.error === "string" && data.error) ||
            (typeof (data as any).detail === "string" && String((data as any).detail)) ||
            "Ukjent feil.";
          const mapped = mapErrorMessage(msg);

          if (mapped.toLowerCase().includes("rate-limited") || mapped.includes("429")) {
            setProgressMsg("Rate limited – venter 15 sek og fortsetter…");
            await sleep(15000);
            continue;
          }

          setError(mapped);
          setStatus("error");
          return;
        }

        const ok = data as SyncOkResp;

        // ✅ PATCH: backend kan returnere rate_limited=true som 200 OK payload
        if (ok.rate_limited === true) {
          const retryS = safeNum(ok.retry_after_s, 15);
          const waitS = Math.min(120, Math.max(5, retryS));
          setProgressMsg(`Rate limited – venter ${waitS}s og fortsetter (samme page)…`);
          await sleep(waitS * 1000);
          continue;
        }

        // Oppdater UI-progresjon
        const batchImported = Array.isArray(ok.imported) ? ok.imported.map(String) : [];
        const batchCount = safeNum(ok.imported_count, batchImported.length);

        let newlyAdded = 0;
        for (const rid of batchImported) {
          if (!importedSetRef.current.has(rid)) {
            importedSetRef.current.add(rid);
            newlyAdded += 1;
          }
        }

        setLastBatchCount(batchCount);
        setImportedTotal(importedSetRef.current.size);
        setLastImported(batchImported);
        setLastErrors(Array.isArray(ok.errors) ? (ok.errors as Array<Record<string, unknown>>) : []);

        const nxtRaw = ok.next_page;
        const nxt = nxtRaw == null ? null : safeNum(nxtRaw, 0);
        const isDone = ok.done === true;

        setNextPage(nxt ? nxt : null);
        setDone(isDone);

        const per = safeNum(ok.per_page, perPage);
        const limit = safeNum(ok.batch_limit, batchLimit);

        setProgressMsg(
          isDone
            ? `Ferdig. Importert totalt ${importedSetRef.current.size} rides.`
            : `Importert ${importedSetRef.current.size} (siste batch ${batchCount}). Page ${currentPage}. ` +
              `per_page ${per}. batch_limit ${limit}. Fortsetter…`
        );

        if (isDone) {
          try {
            const total = importedSetRef.current.size;
            sessionStorage.setItem("cg_toast", `✅ Import ferdig: ${total} rides importert!`);
          } catch {
            // ignore
          }
          setStatus("done");
          return;
        }

        // Ikke ferdig: gå til neste page (backend gir fasit)
        if (nxt && Number.isFinite(nxt) && nxt >= currentPage) {
          currentPage = nxt;
        } else {
          currentPage += 1;
        }

        // Safety: hvis vi spinner uten at total øker over tid, break med feilmelding
        if (newlyAdded === 0) hardStops += 1;
        else hardStops = 0;

        if (hardStops >= maxHardStops) {
          setError(
            "Import stoppet: ingen fremdrift over flere batches. Dette kan bety at Strava ikke returnerer flere aktiviteter i perioden, eller at vi treffer en edge-case."
          );
          setStatus("error");
          return;
        }

        // liten pause mellom batches for å dempe 429 ytterligere
        await sleep(250);
      }
    } finally {
      runningRef.current = false;
      abortRef.current = null;
    }
  }

  function onImportClick() {
    void runImport();
  }

  function onCancel() {
    if (abortRef.current) {
      abortRef.current.abort();
    }
  }

  function onSkip() {
    goDashboard();
  }

  function onContinue() {
    goDashboard();
  }

  useEffect(() => {
    return () => {
      if (abortRef.current) abortRef.current.abort();
    };
  }, []);

  return (
    <div className="p-6 max-w-xl">
      <h1 className="text-2xl font-semibold">{title}</h1>

      <p className="mt-2 text-sm opacity-80">
        Velg hvor langt tilbake vi skal hente rides fra Strava. Du kan også hoppe over og importere
        senere.
      </p>

      {/* ✅ PATCH C4 — mer relevant melding nå som kun 6 months er aktiv */}
      <div style={{ marginTop: 8, fontSize: 13 }}>
        Vi importerer opptil 150 nylige sykkelturer for å komme raskt i gang.
      </div>

      <div className="mt-6 space-y-3">
        {/* ✅ PATCH C3 — disable 3 alternativer + MVP copy */}
        <label
          style={{
            display: "flex",
            alignItems: "baseline",
            gap: 10,
            opacity: 0.45,
            cursor: "not-allowed",
          }}
        >
          <input type="radio" name="period" value="all" checked={period === "all"} disabled onChange={() => {}} />
          <span>All</span>
          <span style={{ fontSize: 12 }}>{MVP_LAUNCH_COPY}</span>
        </label>

        <label
          style={{
            display: "flex",
            alignItems: "baseline",
            gap: 10,
            opacity: 0.45,
            cursor: "not-allowed",
          }}
        >
          <input
            type="radio"
            name="period"
            value="3years"
            checked={period === "3years"}
            disabled
            onChange={() => {}}
          />
          <span>Last 3 years</span>
          <span style={{ fontSize: 12 }}>{MVP_LAUNCH_COPY}</span>
        </label>

        <label
          style={{
            display: "flex",
            alignItems: "baseline",
            gap: 10,
            opacity: 0.45,
            cursor: "not-allowed",
          }}
        >
          <input type="radio" name="period" value="1year" checked={period === "1year"} disabled onChange={() => {}} />
          <span>Last 1 year</span>
          <span style={{ fontSize: 12 }}>{MVP_LAUNCH_COPY}</span>
        </label>

        <label
          style={{
            display: "flex",
            alignItems: "baseline",
            gap: 10,
            background: "#fff3cd",
            border: "1px solid #ffe69c",
            padding: "8px 10px",
            borderRadius: 8,
          }}
        >
          <input
            type="radio"
            name="period"
            value="6months"
            checked={period === "6months"}
            disabled={disabled || !isEnabledPeriod("6months")}
            onChange={() => setPeriod("6months")}
          />
          <span>Last 6 months</span>
          <span style={{ fontSize: 12, fontWeight: 600 }}>(default)</span>
        </label>
      </div>

      {status === "importing" && (
        <div className="mt-6 space-y-2">
          <div className="flex items-center gap-3">
            <div className="h-5 w-5 rounded-full border-2 border-current border-t-transparent animate-spin" />
            <div className="text-sm">
              Dette kan ta en stund… du trenger ikke gjøre noe. Importen fortsetter automatisk.
            </div>
          </div>

          <div className="text-sm opacity-90">
            <div>
              <b>Importert:</b> {importedTotal}
              {lastBatchCount > 0 ? <span className="opacity-80"> (siste batch {lastBatchCount})</span> : null}
            </div>
            <div className="opacity-80">
              <b>Page:</b> {page}
              {nextPage ? <span> → next {nextPage}</span> : null}
              {done ? <span> • done</span> : null}
            </div>
            {progressMsg ? <div className="opacity-80 mt-1">{progressMsg}</div> : null}
          </div>
        </div>
      )}

      {status === "done" && (
        <div className="mt-6 text-sm">
          <div className="font-medium">✅ Import ferdig: {importedTotal} rides importert</div>
          <div className="opacity-80 mt-1">Trykk “Fortsett til dashboard”.</div>
        </div>
      )}

      {status === "cancelled" && (
        <div className="mt-6 text-sm">
          <div className="font-medium">⏸️ Import stoppet</div>
          <div className="opacity-80 mt-1">
            Importert så langt: <b>{importedTotal}</b>. Du kan starte importen igjen senere.
          </div>
        </div>
      )}

      {status === "error" && (
        <div className="mt-6 text-sm">
          <div className="font-medium">⚠️ Import feilet</div>
          <div className="mt-1 opacity-90">{error ?? "Ukjent feil."}</div>
          <div className="mt-2 opacity-80">
            Du kan likevel fortsette til dashboard. (Du kan også prøve import igjen senere.)
          </div>
        </div>
      )}

      <div className="mt-8 flex gap-3 flex-wrap">
        <button className="px-4 py-2 rounded border" disabled={disabled} onClick={onImportClick} aria-disabled={disabled}>
          Importer rides
        </button>

        {status === "importing" && (
          <button className="px-4 py-2 rounded border" onClick={onCancel}>
            Stopp import
          </button>
        )}

        <button className="px-4 py-2 rounded border" disabled={disabled} onClick={onSkip}>
          Hopp over
        </button>

        {canContinue && (
          <button className="px-4 py-2 rounded border" onClick={onContinue}>
            Fortsett til dashboard
          </button>
        )}
      </div>

      {(status === "importing" || status === "done") && (
        <details className="mt-6 text-xs opacity-80">
          <summary className="cursor-pointer">Debug</summary>
          <div className="mt-2">
            <div>importedTotal: {importedTotal}</div>
            <div>page: {page}</div>
            <div>nextPage: {String(nextPage)}</div>
            <div>done: {String(done)}</div>
            <div>lastImported: {lastImported ? lastImported.slice(0, 10).join(", ") : "null"}</div>
            <div>lastErrorsCount: {lastErrors ? lastErrors.length : "null"}</div>
          </div>
        </details>
      )}
    </div>
  );
}
