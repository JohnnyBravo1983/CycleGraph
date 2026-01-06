// frontend/src/demo/demoData.ts
export type DemoRide = {
  id: string; // matches router param for SessionView (we will use "session/:id")
  title: string;
  date: string; // ISO
  distanceKm: number;
  durationMin: number;
  precisionWattAvg: number;
};

export type DemoDashboard = {
  athleteName: string;
  weekSummary: {
    rides: number;
    hours: number;
    distanceKm: number;
    avgPw: number;
  };
  recentRides: DemoRide[];
};

export const demoDashboard: DemoDashboard = {
  athleteName: "Magnus",
  weekSummary: { rides: 4, hours: 6.2, distanceKm: 182, avgPw: 236 },
  recentRides: [
    {
      id: "16007374633",
      title: "Tempo / Sweet Spot",
      date: "2026-01-03T10:12:00Z",
      distanceKm: 54.2,
      durationMin: 92,
      precisionWattAvg: 241,
    },
    {
      id: "16127771073",
      title: "Endurance (Z2)",
      date: "2025-12-14T16:09:41Z",
      distanceKm: 71.8,
      durationMin: 145,
      precisionWattAvg: 228,
    },
  ],
};

export function getDemoRide(id: string): DemoRide | null {
  return demoDashboard.recentRides.find((r) => r.id === id) ?? null;
}
