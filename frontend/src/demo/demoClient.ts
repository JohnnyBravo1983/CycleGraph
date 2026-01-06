// frontend/src/data/demoClient.ts
import { isDemoMode } from "./demoMode";
import { demoDashboard, getDemoRide, type DemoDashboard, type DemoRide } from "./demoData";


export async function getDashboard(): Promise<DemoDashboard> {
  if (isDemoMode()) return demoDashboard;
  throw new Error("Not in demo mode");
}

export async function listRides(): Promise<DemoRide[]> {
  if (isDemoMode()) return demoDashboard.recentRides;
  throw new Error("Not in demo mode");
}

export async function getRide(id: string): Promise<DemoRide> {
  if (isDemoMode()) {
    const r = getDemoRide(id);
    if (!r) throw new Error("Ride not found (demo)");
    return r;
  }
  throw new Error("Not in demo mode");
}
