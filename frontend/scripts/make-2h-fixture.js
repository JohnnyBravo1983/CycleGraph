// frontend/scripts/make-2h-fixture.cjs
const fs = require("fs");
const path = require("path");

const N = 7200; // 2 timer @ 1Hz
const OUT_DIR = path.join(process.cwd(), "public", "devdata");
const OUT_FILE = path.join(OUT_DIR, "session_full_2h.json");

// Liten hjelpefunksjon for pene kurver
function mkSeries(n, { base, a1 = 8, a2 = 4, f1 = 50, f2 = 200 }) {
  return Array.from({ length: n }, (_, i) =>
    base + Math.round(a1 * Math.sin(i / f1) + a2 * Math.sin(i / f2))
  );
}

function build(mode) {
  const watts = mkSeries(N, { base: 200, a1: 8, a2: 4, f1: 50, f2: 200 });
  const hr = mkSeries(N, { base: 140, a1: 6, a2: 3, f1: 60, f2: 300 });

  // Base FULL + CI + kalibrert
  const base = {
    schema_version: "1",
    watts,
    hr,
    precision_watt_ci: {
      lower: watts.map((w) => w - 10),
      upper: watts.map((w) => w + 10),
    },
    calibrated: true,
    status: "FULL",
    wind_rel: 0,
    v_rel: 0,
  };

  switch (mode) {
    case "full":
      return base;

    case "uncal": // kalibrert=false, data fortsatt til stede
      return { ...base, calibrated: false };

    case "hr": // HR-only: ingen watts, ingen CI
      return {
        ...base,
        watts: [],
        precision_watt_ci: undefined,
        status: "HR-only",
      };

    case "limited": // LIMITED: kun power (watt), HR tom, CI beholdes
      return {
        ...base,
        hr: [],
        status: "LIMITED",
      };

    case "ci-missing": // Mangler CI, ellers FULL
      return {
        ...base,
        precision_watt_ci: undefined,
      };

    case "empty": // Fail-closed test: ingen dataserier
      return {
        ...base,
        watts: [],
        hr: [],
        precision_watt_ci: undefined,
        status: "EMPTY",
      };

    default:
      // Fallback = FULL
      return base;
  }
}

function main() {
  // Mode kan sendes som CLI-arg: `npm run make:2h -- full`
  const mode = (process.argv[2] || "").trim().toLowerCase() || "full";

  const data = build(mode);

  fs.mkdirSync(OUT_DIR, { recursive: true });
  fs.writeFileSync(OUT_FILE, JSON.stringify(data));
  console.log(`✅ Wrote ${path.relative(process.cwd(), OUT_FILE)} (mode: ${mode})`);
  const w = Array.isArray(data.watts) ? data.watts.length : 0;
  const h = Array.isArray(data.hr) ? data.hr.length : 0;
  console.log("   points:", { watts: w, hr: h, ci: !!data.precision_watt_ci });
  console.log("   flags:", { calibrated: data.calibrated, status: data.status });
}

try {
  main();
} catch (e) {
  console.error("❌ make-2h-fixture failed:", e?.message || e);
  process.exit(1);
}
