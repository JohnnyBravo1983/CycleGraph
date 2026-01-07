export type RawRideInput = {
  stravaId: string
  date: string
  startTime: string
  distance_km: number
  elevation_m: number | null
  moving_time_s: number | null
  hr_avg: number | null
  weight_kg: number | null
  precision_watt_avg: number
  strava_watt_avg: number | null
  ride_type_raw: string
  weather: {
    temp_c: number | null
    air_pressure_hpa: number | null
    wind_speed_ms: number | null
    wind_dir_deg: number | null
    conditions: string
  }
}

export const rawRides: RawRideInput[] = [
  // -------- 2022 --------
  {
    stravaId: "7763830562",
    date: "2022-09-06",
    startTime: "14:44",
    distance_km: 23.0,
    elevation_m: 225,
    moving_time_s: 3192,
    hr_avg: 160,
    weight_kg: 117.4,
    precision_watt_avg: 206.4,
    strava_watt_avg: 161,
    ride_type_raw: "FTP",
    weather: {
      temp_c: 18.2,
      air_pressure_hpa: 1026,
      wind_speed_ms: 1.9,
      wind_dir_deg: 169,
      conditions: "Clear",
    },
  },
  {
    stravaId: "7435441478",
    date: "2022-08-07",
    startTime: "09:23",
    distance_km: 91.03,
    elevation_m: 650,
    moving_time_s: 16762,
    hr_avg: 139,
    weight_kg: 116.8,
    precision_watt_avg: 145.6,
    strava_watt_avg: 112,
    ride_type_raw: "Long Ride",
    weather: {
      temp_c: null,
      air_pressure_hpa: 1018,
      wind_speed_ms: 1.9,
      wind_dir_deg: 347,
      conditions: "Clear",
    },
  },

  // -------- 2023 --------
  {
    stravaId: "9157368419",
    date: "2023-05-28",
    startTime: "15:29",
    distance_km: 30.5,
    elevation_m: 208,
    moving_time_s: 4055,
    hr_avg: 159,
    weight_kg: 111.9,
    precision_watt_avg: 215.7,
    strava_watt_avg: 182,
    ride_type_raw: "FTP",
    weather: {
      temp_c: 17.2,
      air_pressure_hpa: 1017,
      wind_speed_ms: 2.9,
      wind_dir_deg: 309,
      conditions: "Clear",
    },
  },
  {
    stravaId: "9582853971",
    date: "2023-08-04",
    startTime: "08:56",
    distance_km: 151.35,
    elevation_m: 1946,
    moving_time_s: 24749,
    hr_avg: 139,
    weight_kg: 111.1,
    precision_watt_avg: 180.2,
    strava_watt_avg: 159,
    ride_type_raw: "Long Ride",
    weather: {
      temp_c: 13.2,
      air_pressure_hpa: 1002,
      wind_speed_ms: 1.4,
      wind_dir_deg: 338,
      conditions: "Cloudy",
    },
  },
  {
    stravaId: "9676729713",
    date: "2023-08-19",
    startTime: "09:15",
    distance_km: 30.02,
    elevation_m: 166,
    moving_time_s: 3499,
    hr_avg: 139,
    weight_kg: 110.1,
    precision_watt_avg: 242.8,
    strava_watt_avg: 182,
    ride_type_raw: "FTP",
    weather: {
      temp_c: 16.1,
      air_pressure_hpa: 1024,
      wind_speed_ms: 2.6,
      wind_dir_deg: 51,
      conditions: "Cloudy",
    },
  },

  // -------- 2024 --------
  {
    stravaId: "11440045532",
    date: "2024-05-18",
    startTime: "16:05",
    distance_km: 30.23,
    elevation_m: 167,
    moving_time_s: 3578,
    hr_avg: 157,
    weight_kg: 112.2,
    precision_watt_avg: 249.9,
    strava_watt_avg: 177,
    ride_type_raw: "FTP",
    weather: {
      temp_c: 21.5,
      air_pressure_hpa: 1016,
      wind_speed_ms: 3.0,
      wind_dir_deg: 187,
      conditions: "Clear",
    },
  },
  {
    stravaId: "12003878506",
    date: "2024-07-28",
    startTime: "16:05",
    distance_km: 92.5,
    elevation_m: 167,
    moving_time_s: 13009,
    hr_avg: 144,
    weight_kg: 110.2,
    precision_watt_avg: 207,
    strava_watt_avg: 151,
    ride_type_raw: "Long Ride",
    weather: {
      temp_c: 21.2,
      air_pressure_hpa: 1015,
      wind_speed_ms: 2.4,
      wind_dir_deg: 355,
      conditions: "Clear",
    },
  },
  {
    stravaId: "11918764501",
    date: "2024-07-24",
    startTime: "13:38",
    distance_km: 30.25,
    elevation_m: 170,
    moving_time_s: 13009,
    hr_avg: 165,
    weight_kg: 109.4,
    precision_watt_avg: 242.5,
    strava_watt_avg: 182,
    ride_type_raw: "FTP",
    weather: {
      temp_c: 22.5,
      air_pressure_hpa: 1016,
      wind_speed_ms: 2.0,
      wind_dir_deg: 178,
      conditions: "Clear",
    },
  },

  // -------- 2025 --------
  {
    stravaId: "14080123026",
    date: "2025-04-04",
    startTime: "18:53",
    distance_km: 29.9,
    elevation_m: 167,
    moving_time_s: 3416,
    hr_avg: 148,
    weight_kg: 103.4,
    precision_watt_avg: 243.4,
    strava_watt_avg: 188,
    ride_type_raw: "FTP",
    weather: {
      temp_c: 10.6,
      air_pressure_hpa: 1024,
      wind_speed_ms: 2.6,
      wind_dir_deg: 6,
      conditions: "Partly Cloudy",
    },
  },
  {
    stravaId: "15188321826",
    date: "2025-07-21",
    startTime: "16:02",
    distance_km: 29.9,
    elevation_m: 167,
    moving_time_s: 3416,
    hr_avg: 148,
    weight_kg: 103.9,
    precision_watt_avg: 210.7,
    strava_watt_avg: 179,
    ride_type_raw: "Long",
    weather: {
      temp_c: 22.5,
      air_pressure_hpa: 1009,
      wind_speed_ms: 2.4,
      wind_dir_deg: 111,
      conditions: "Cloudy",
    },
  },
  {
    stravaId: "15908409437",
    date: "2025-09-23",
    startTime: "12:22",
    distance_km: 29.9,
    elevation_m: 167,
    moving_time_s: 3416,
    hr_avg: 160,
    weight_kg: 104.5,
    precision_watt_avg: 256.0,
    strava_watt_avg: 194,
    ride_type_raw: "FTP",
    weather: {
      temp_c: 12.0,
      air_pressure_hpa: 1026,
      wind_speed_ms: 2.7,
      wind_dir_deg: 358,
      conditions: "Partly Cloudy",
    },
  },
  {
    stravaId: "16053034149",
    date: "2025-10-06",
    startTime: "16:22",
    distance_km: 42.13,
    elevation_m: 401,
    moving_time_s: 5223,
    hr_avg: 161,
    weight_kg: 105.9,
    precision_watt_avg: 257.9,
    strava_watt_avg: 199,
    ride_type_raw: "FTP",
    weather: {
      temp_c: 14.5,
      air_pressure_hpa: 1013,
      wind_speed_ms: 2.3,
      wind_dir_deg: 108,
      conditions: "Cloudy",
    },
  },
]
