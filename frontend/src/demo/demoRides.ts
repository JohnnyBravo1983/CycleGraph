// frontend/src/demo/demoRides.ts
// Single source of truth for demo rides + progression summary.
// Derived from your pipeline numbers (normalized + mapped).

export interface DemoRide {
  id: string | number
  date: string // YYYY-MM-DD
  name: string
  distance: number // meters
  duration: number // seconds
  precisionWatt: number
  stravaWatt: number
  elevation: number // meters climbed
  avgSpeed: number // km/h

  year: number
  rideType: 'ftp-sweetspot' | 'long-ride' | 'windy' | 'climbing'
  ridingConditions: 'solo' | 'group' | 'mixed'

  weather: {
    temp: number // celsius (0 if unknown)
    wind: {
      speed: number // m/s
      direction: number // degrees (0=N)
    }
    conditions: string
  }

  riderWeight: number // kg

  tags?: string[]
  description?: string
}

// ---------- helpers ----------
const toMeters = (km: number) => Math.round(km * 1000)

const calcAvgSpeedKmh = (distance_m: number, duration_s: number) => {
  if (!duration_s || duration_s <= 0) return 0
  return Math.round(((distance_m / duration_s) * 3.6) * 10) / 10
}

// If a value is missing in source (e.g., temp), we default to 0.
// In UI you can render 0 as "—" if you prefer.
const numOr0 = (v: number | null | undefined) =>
  typeof v === 'number' && Number.isFinite(v) ? v : 0

// ---------- demo rides ----------
export const demoRides: DemoRide[] = [
  // =========================
  // 2022
  // =========================
  {
    id: '2022-01',
    date: '2022-09-06',
    name: 'FTP Sweetspot — Horten → Nykirke (Short Tempo)',
    distance: toMeters(23.0),
    duration: 3192, // 53:12
    precisionWatt: 206.4,
    stravaWatt: 161,
    elevation: 225,
    avgSpeed: calcAvgSpeedKmh(toMeters(23.0), 3192),
    year: 2022,
    rideType: 'ftp-sweetspot',
    ridingConditions: 'solo',
    weather: {
      temp: 18.2,
      wind: { speed: 1.9, direction: 169 },
      conditions: 'Clear',
    },
    riderWeight: 117.4,
    tags: ['Progression baseline'],
    description:
      'Short tempo/FTP-style effort early in the journey. Clean comparison point for later years.',
  },
  {
    id: '2022-02',
    date: '2022-08-07',
    name: 'Long Ride — Endurance 91 km (2022 Base)',
    distance: toMeters(91.03),
    duration: 16762, // 4:39:22
    precisionWatt: 145.6,
    stravaWatt: 112,
    elevation: 650,
    avgSpeed: calcAvgSpeedKmh(toMeters(91.03), 16762),
    year: 2022,
    rideType: 'long-ride',
    ridingConditions: 'solo',
    weather: {
      temp: numOr0(null), // temp missing in source
      wind: { speed: 1.9, direction: 347 },
      conditions: 'Clear',
    },
    riderWeight: 116.8,
    tags: ['Endurance base', 'Temp missing'],
    description:
      'Solid endurance ride from 2022. Weather temp was missing in the source; everything else is from pipeline.',
  },

  // =========================
  // 2023
  // =========================
  {
    id: '2023-01',
    date: '2023-05-28',
    name: 'FTP Sweetspot — Horten → Nykirke (Tempo Builder)',
    distance: toMeters(30.5),
    duration: 4055, // 1:07:35
    precisionWatt: 215.7,
    stravaWatt: 182,
    elevation: 208,
    avgSpeed: calcAvgSpeedKmh(toMeters(30.5), 4055),
    year: 2023,
    rideType: 'ftp-sweetspot',
    ridingConditions: 'solo',
    weather: {
      temp: 17.2,
      wind: { speed: 2.9, direction: 309 },
      conditions: 'Clear',
    },
    riderWeight: 111.9,
    tags: ['Progression (+W/kg)'],
    description:
      'Clear step up in sustainable power vs 2022, with lower weight and similar route profile.',
  },
  {
    id: '2023-02',
    date: '2023-08-04',
    name: 'Climbing — Horten→Bergen Stage (Flesberg → Geilo)',
    distance: toMeters(151.35),
    duration: 24749, // 6:52:29
    precisionWatt: 180.2,
    stravaWatt: 159,
    elevation: 1946,
    avgSpeed: calcAvgSpeedKmh(toMeters(151.35), 24749),
    year: 2023,
    rideType: 'climbing',
    ridingConditions: 'solo',
    weather: {
      temp: 13.2,
      wind: { speed: 1.4, direction: 338 },
      conditions: 'Cloudy',
    },
    riderWeight: 111.1,
    tags: ['Climbing showcase', 'Elevation handling'],
    description:
      'High elevation day (1946m). Great for showing gravity + pacing variability in the model.',
  },
  {
    id: '2023-03',
    date: '2023-08-19',
    name: 'FTP Sweetspot — Horten → Tønsberg (Morning Tempo)',
    distance: toMeters(30.02),
    duration: 3499, // 58:19
    precisionWatt: 242.8,
    stravaWatt: 182,
    elevation: 166,
    avgSpeed: calcAvgSpeedKmh(toMeters(30.02), 3499),
    year: 2023,
    rideType: 'ftp-sweetspot',
    ridingConditions: 'solo',
    weather: {
      temp: 16.1,
      wind: { speed: 2.6, direction: 51 },
      conditions: 'Cloudy',
    },
    riderWeight: 110.1,
    tags: ['Strong tempo day', 'Check intensity'],
    description:
      'Very strong sustainable power for 2023. Keep as a “peak day” or swap if you want stricter sweetspot realism.',
  },

  // =========================
  // 2024
  // =========================
  {
    id: '2024-01',
    date: '2024-05-18',
    name: 'FTP Sweetspot — Horten → Tønsberg (Spring Builder)',
    distance: toMeters(30.23),
    duration: 3578, // 59:38
    precisionWatt: 249.9,
    stravaWatt: 177,
    elevation: 167,
    avgSpeed: calcAvgSpeedKmh(toMeters(30.23), 3578),
    year: 2024,
    rideType: 'ftp-sweetspot',
    ridingConditions: 'solo',
    weather: {
      temp: 21.5,
      wind: { speed: 3.0, direction: 187 },
      conditions: 'Clear',
    },
    riderWeight: 112.2,
    tags: ['Progression', 'Warm day'],
    description:
      'Strong 2024 sweetspot-style effort. Great mid-story anchor toward FTP ~258.',
  },
  {
    id: '2024-02',
    date: '2024-07-28',
    name: 'Long Ride — Sandefjord Endurance (92.5 km)',
    distance: toMeters(92.5),
    duration: 13009, // 3:36:49
    precisionWatt: 207,
    stravaWatt: 151,
    elevation: 167,
    avgSpeed: calcAvgSpeedKmh(toMeters(92.5), 13009),
    year: 2024,
    rideType: 'long-ride',
    ridingConditions: 'solo',
    weather: {
      temp: 21.2,
      wind: { speed: 2.4, direction: 355 },
      conditions: 'Clear',
    },
    riderWeight: 110.2,
    tags: ['Endurance', 'Check moving time'],
    description:
      'Endurance ride. Note: moving time equals another 2024 ride in your source; verify if needed.',
  },
  {
    id: '2024-03',
    date: '2024-07-24',
    name: 'FTP Sweetspot — Horten → Tønsberg (Summer Tempo)',
    distance: toMeters(30.25),
    duration: 3460, // 57:00 
    precisionWatt: 242.5,
    stravaWatt: 182,
    elevation: 170,
    avgSpeed: calcAvgSpeedKmh(toMeters(30.25), 13009),
    year: 2024,
    rideType: 'ftp-sweetspot',
    ridingConditions: 'solo',
    weather: {
      temp: 22.5,
      wind: { speed: 2.0, direction: 178 },
      conditions: 'Clear',
    },
    riderWeight: 109.4,
    tags: ['Check moving time'],
    description:
      'Power looks right for 2024, but moving time is identical to the 92.5 km ride in your source—worth double-checking.',
  },

  // =========================
  // 2025
  // =========================
  {
    id: '2025-01',
    date: '2025-04-04',
    name: 'FTP Sweetspot — Horten → Tønsberg (Early Season)',
    distance: toMeters(29.9),
    duration: 3416, // 56:56
    precisionWatt: 243.4,
    stravaWatt: 188,
    elevation: 167,
    avgSpeed: calcAvgSpeedKmh(toMeters(29.9), 3416),
    year: 2025,
    rideType: 'ftp-sweetspot',
    ridingConditions: 'solo',
    weather: {
      temp: 10.6,
      wind: { speed: 2.6, direction: 6 },
      conditions: 'Partly Cloudy',
    },
    riderWeight: 103.4,
    tags: ['2025 form', 'Check moving time'],
    description:
      'Early-season 2025 tempo/FTP-style ride. Great for showing stable performance at ~103kg.',
  },
  // REPLACE the existing 2025-02 object with this one:
{
  id: '2025-02',
  date: '2025-06-21',
  name: 'Long Ride — Endurance 84 km (Clear Summer)',
  distance: 84000,
  duration: 11223, // interpreted from "3:06:63" -> 3:07:03
  precisionWatt: 206.0,
  stravaWatt: 162,
  elevation: 679,
  avgSpeed: 27.0, // 84 km / 3:07:03
  year: 2025,
  rideType: 'long-ride',
  ridingConditions: 'solo',
  weather: {
    temp: 19.2,
    wind: { speed: 1.4, direction: 354 },
    conditions: 'Clear',
  },
  riderWeight: 103.9, // using same ballpark as your 2025 rides; adjust if you have exact
  tags: ['Endurance showcase', 'Clean solo', 'Strava gap (long ride)'],
  description:
    'Steady endurance ride used in the pipeline. Air pressure: 1016 hPa. Great “real-world long ride” demo anchor for 2025.',
},
  {
    id: '2025-03',
    date: '2025-09-23',
    name: 'FTP Sweetspot — Horten → Tønsberg (Autumn)',
    distance: toMeters(29.9),
    duration: 3416, // 56:56
    precisionWatt: 256.0,
    stravaWatt: 194,
    elevation: 167,
    avgSpeed: calcAvgSpeedKmh(toMeters(29.9), 3416),
    year: 2025,
    rideType: 'ftp-sweetspot',
    ridingConditions: 'solo',
    weather: {
      temp: 12.0,
      wind: { speed: 2.7, direction: 358 },
      conditions: 'Partly Cloudy',
    },
    riderWeight: 104.5,
    tags: ['Peak 2025 sweetspot', 'Check moving time'],
    description:
      'Late-season strong sustainable power. Great headline ride for the 260W FTP year.',
  },
  {
    id: '2025-04',
    date: '2025-10-06',
    name: 'FTP Sweetspot — Revetal Hard Tempo (Longer)',
    distance: toMeters(42.13),
    duration: 5223, // 1:27:03
    precisionWatt: 257.9,
    stravaWatt: 199,
    elevation: 401,
    avgSpeed: calcAvgSpeedKmh(toMeters(42.13), 5223),
    year: 2025,
    rideType: 'ftp-sweetspot',
    ridingConditions: 'solo',
    weather: {
      temp: 14.5,
      wind: { speed: 2.3, direction: 108 },
      conditions: 'Cloudy',
    },
    riderWeight: 105.9,
    tags: ['Longer tempo', 'Great for demo'],
    description:
      'Longer structured tempo/FTP-style session. Nice variety vs the ~30 km loops.',
  },
]

// ---------- progression summary ----------
export const progressionSummary = {
  '2022': {
    avgFTP: 210,
    weight: 116.8, // approx from the rides provided
    wkg: 1.8,
    rides: 2,
    totalKm: 114.03,
  },
  '2023': {
    avgFTP: 235,
    weight: 111.0,
    wkg: 2.12,
    rides: 3,
    totalKm: 211.87,
    improvement: {
      ftp: '+25W (+12%)',
      weight: '-~6kg',
      wkg: '+~18%',
    },
  },
  '2024': {
    avgFTP: 258,
    weight: 110.6,
    wkg: 2.33,
    rides: 3,
    totalKm: 152.98,
    improvement: {
      ftp: '+23W (+10%)',
      weight: '-~0.4kg',
      wkg: '+~10%',
    },
  },
  '2025': {
    currentFTP: 260,
    weight: 104.4,
    wkg: 2.49,
    rides: 4,
    totalKm: 131.83,
  },
} as const
