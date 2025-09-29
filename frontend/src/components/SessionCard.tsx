// frontend/src/components/SessionCard.tsx
import type { SessionReport } from "../types/session";
import ModeBadge from "./ModeBadge";

type Props = {
  session: SessionReport;
  className?: string;
};

function CalibBadge({ ok }: { ok: boolean }) {
  const base =
    "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium";
  const tone = ok
    ? "bg-emerald-100 text-emerald-800" // Kalibrert = grønn
    : "bg-yellow-100 text-yellow-800"; // Ukalibrert = gul
  const dot = ok ? "bg-emerald-500" : "bg-yellow-500";
  return (
    <span className={`${base} ${tone}`} title={ok ? "Kalibrert" : "Ukalibrert"}>
      <span className={`mr-1 inline-block h-2 w-2 rounded-full ${dot}`} />
      {ok ? "Kalibrert" : "Ukalibrert"}
    </span>
  );
}

const isFiniteNumber = (x: unknown): x is number =>
  typeof x === "number" && Number.isFinite(x);

function fmtWatts(w: number | number[] | null | undefined): string | null {
  if (isFiniteNumber(w)) return `${Math.round(w)} W`;

  if (Array.isArray(w) && w.length > 0) {
    const nums = w.filter(isFiniteNumber);
    if (nums.length === 0) return null;
    const avg = nums.reduce((a, b) => a + b, 0) / nums.length;
    return `${Math.round(avg)} W`;
  }

  return null;
}

export default function SessionCard({ session, className }: Props) {
  const { avg_hr, calibrated, status, watts } = session;
  const wattsText = fmtWatts(watts);

  return (
    <article
      className={[
        "rounded-2xl border border-gray-200 bg-white p-4 shadow-sm",
        "transition-colors",
        className ?? "",
      ]
        .filter(Boolean)
        .join(" ")}
      data-testid="session-card"
    >
      <header className="mb-3 flex items-center justify-between">
        <h2 className="text-lg font-semibold">Økt</h2>
        <div className="flex items-center gap-2">
          <CalibBadge ok={!!calibrated} />
          <ModeBadge />
        </div>
      </header>

      <dl className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <div className="col-span-1 rounded-xl bg-gray-50 p-3">
          <dt className="text-[11px] text-gray-500">Gjennomsnittspuls</dt>
          <dd className="text-base font-medium">
            {isFiniteNumber(avg_hr) ? `${Math.round(avg_hr)} bpm` : "—"}
          </dd>
        </div>

        <div className="col-span-1 rounded-xl bg-gray-50 p-3">
          <dt className="text-[11px] text-gray-500">Status</dt>
          <dd className="text-base font-medium">{status ?? "—"}</dd>
        </div>

        <div className="col-span-2 rounded-xl bg-gray-50 p-3 sm:col-span-2">
          <dt className="text-[11px] text-gray-500">Watt</dt>
          <dd className="text-base font-medium">
            {wattsText ? (
              wattsText
            ) : (
              <span className="inline-flex items-center text-gray-600">
                <span className="mr-2 inline-block h-2 w-2 rounded-full bg-gray-400" />
                Ingen watt-data (HR-only)
              </span>
            )}
          </dd>
        </div>
      </dl>
    </article>
  );
}
