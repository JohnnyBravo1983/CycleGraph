// frontend/scripts/make-2h-fixture.js
const fs = require("fs");

const n = 7200; // 2 timer @ 1 Hz

// Jevn, realistisk variasjon for visualisering
const watts = Array.from({ length: n }, (_, i) => 200 + Math.round(8 * Math.sin(i / 50) + 4 * Math.sin(i / 200)));
const hr    = Array.from({ length: n }, (_, i) => 140 + Math.round(6 * Math.sin(i / 60) + 3 * Math.sin(i / 300)));

const data = {
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

fs.mkdirSync("public/devdata", { recursive: true });
fs.writeFileSync("public/devdata/session_full_2h.json", JSON.stringify(data));
console.log("✅ Wrote public/devdata/session_full_2h.json");
console.log("   points:", { watts: watts.length, hr: hr.length });
