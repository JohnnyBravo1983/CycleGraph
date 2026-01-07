// frontend/src/data/demoClient.ts
import { isDemoMode } from "./demoMode";
import { demoRides, progressionSummary, type DemoRide } from "./demoRides";

export type DemoDashboard = {
  progressionSummary: typeof progressionSummary;
  recentRides: DemoRide[];
};

function sortByDateDesc(a: DemoRide, b: DemoRide) {
  // Dates are YYYY-MM-DD, string compare works
  return b.date.localeCompare(a.date);
}

export async function getDashboard(): Promise<DemoDashboard> {
  if (!isDemoMode()) throw new Error("Not in demo mode");

  const recentRides = [...demoRides].sort(sortByDateDesc);

  return {
    progressionSummary,
    recentRides,
  };
}

export async function listRides(): Promise<DemoRide[]> {
  if (!isDemoMode()) throw new Error("Not in demo mode");
  return [...demoRides].sort(sortByDateDesc);
}

export async function getRide(id: string): Promise<DemoRide> {
  if (!isDemoMode()) throw new Error("Not in demo mode");

  const r = demoRides.find((x) => String(x.id) === String(id));
  if (!r) throw new Error(`Ride not found (demo): ${id}`);

  return r;
}
