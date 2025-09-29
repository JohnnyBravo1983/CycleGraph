import type { SessionReport } from "../types/session";


export const mockSession: SessionReport = {
schema_version: "1.0.0",
avg_hr: 145,
calibrated: false,
status: "hr_only_demo",
// HR-only → ingen watt-verdier
watts: null,
wind_rel: [0.5, -0.2, 0.1],
v_rel: [7.1, 6.8, 7.4],
};