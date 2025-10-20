use chrono::{DateTime, Utc};

use crate::physics::{estimate_crr, total_mass};
use crate::weather::{StaticWeatherProvider, WeatherClient, WeatherProvider, WeatherSummary};
use crate::weather_api::OpenMeteoClient;

/// Robust median for sammendragsverdi
fn median(mut xs: Vec<f64>) -> f64 {
    if xs.is_empty() {
        return 0.0;
    }
    xs.sort_by(|a, b| a.partial_cmp(b).unwrap());
    let n = xs.len();
    if n % 2 == 1 {
        xs[n / 2]
    } else {
        (xs[n / 2 - 1] + xs[n / 2]) / 2.0
    }
}

/// Normaliser vinkel til [0, 360)
fn norm_deg(d: f64) -> f64 {
    let mut x = d % 360.0;
    if x < 0.0 {
        x += 360.0;
    }
    x
}

/// Relativ vinkel (vind fra) minus heading, foldet til [-180, 180]
fn relative_angle_deg(heading_deg: f64, wind_from_dir_deg: f64) -> f64 {
    let mut delta = norm_deg(wind_from_dir_deg) - norm_deg(heading_deg);
    if delta > 180.0 {
        delta -= 360.0;
    }
    if delta < -180.0 {
        delta += 360.0;
    }
    delta
}

/// Headwind-komponent (positiv = motvind) per sample-heading.
/// meteorologisk vindretning = hvorfra vinden kommer.
fn relative_wind_series_ms(
    headings_deg: &[f64],
    wind_from_dir_deg: f64,
    wind_speed_ms: f64,
) -> Vec<f64> {
    let mut out = Vec::with_capacity(headings_deg.len());
    for &h in headings_deg {
        let rel = relative_angle_deg(h, wind_from_dir_deg).to_radians();
        // cos(0)=1  => full motvind; cos(180)=-1 => full medvind
        out.push(wind_speed_ms * rel.cos());
    }
    out
}

#[derive(Clone)]
pub struct AnalyzeInputs<'a> {
    pub start_time: DateTime<Utc>,
    pub lat: f64,
    pub lon: f64,
    /// GPS-heading per sample (0–360). Tom => fallback.
    pub headings_deg: &'a [f64],
    /// Total varighet (sek) – brukes når headings mangler for å gi riktig lengde på vektor.
    pub duration_secs: u32,
    /// Værtilbyder (prod: WeatherClient, test: StaticWeatherProvider)
    pub weather: Option<&'a dyn WeatherProvider>,

    // --- Bike Setup / profil for Crr og masse ---
    /// f.eks. "Road", "Gravel", "MTB", "TT"
    pub bike_type: &'a str,
    /// Dekkbredde i millimeter (mm), f.eks. 28.0
    pub tire_width_mm: f64,
    /// "Trening" | "Vanlig" | "Ritt" | annet (fallback=1.0)
    pub tire_quality: &'a str,
    /// Ryttervekt i kg
    pub rider_weight_kg: f64,
    /// Sykkelvekt i kg
    pub bike_weight_kg: f64,
    // TODO: legg til øvrige signaler (hr/watts/speed) når vi kobler PW-formelen i neste trinn
}

#[derive(Debug, Clone)]
pub struct AnalyzeOutputs {
    /// Relativ vind (m/s) langs bevegelsesretningen, per sample (positiv = motvind)
    pub v_rel_ms: Vec<f64>,
    /// Sammendragsverdi (median) av relativ vinkel (grader). 0.0 hvis mangler vær/headings.
    pub wind_rel_deg: f64,
    /// Faktisk brukt vær (None hvis ikke tilgjengelig)
    pub weather_used: Option<WeatherSummary>,

    /// Estimert rullemotstand brukt (Crr)
    pub crr_used: f64,
    /// Ryttervekt (kg) brukt i beregning/persist
    pub rider_weight_kg: f64,
    /// Sykkelvekt (kg) brukt i beregning/persist
    pub bike_weight_kg: f64,
    /// Total masse (kg) = rytter + sykkel
    pub total_mass_kg: f64,
}

pub fn analyze_session(inputs: AnalyzeInputs) -> AnalyzeOutputs {
    // 0️⃣ Beregn Crr + total masse fra Bike Setup / profil
    let crr_used = estimate_crr(inputs.bike_type, inputs.tire_width_mm, inputs.tire_quality);
    let total_mass_kg = total_mass(inputs.rider_weight_kg, inputs.bike_weight_kg);

    // 1️⃣ Prøv Open-Meteo (nett)
    let api = OpenMeteoClient::new();
    let weather_opt = api
        .get_weather_for_session(
            inputs.start_time,
            inputs.lat,
            inputs.lon,
            inputs.duration_secs,
        )
        // 2️⃣ Fallback til lokal cache
        .or_else(|| {
            let local = WeatherClient::new();
            local.get_weather_for_session(
                inputs.start_time,
                inputs.lat,
                inputs.lon,
                inputs.duration_secs,
            )
        })
        // 3️⃣ Fallback til statisk dummy
        .or_else(|| {
            let static_w = StaticWeatherProvider {
                summary: Some(WeatherSummary {
                    wind_speed_ms: 0.0,
                    wind_dir_deg: 0.0,
                    temperature_c: 20.0,
                    pressure_hpa: 1013.0,
                }),
            };
            static_w.get_weather_for_session(
                inputs.start_time,
                inputs.lat,
                inputs.lon,
                inputs.duration_secs,
            )
        });

    // 4️⃣ Beregn relativ vind per sample (med fallbacks)
    let (v_rel_ms, wind_rel_deg) = match (&weather_opt, !inputs.headings_deg.is_empty()) {
        (Some(w), true) => {
            // v_rel per sample (positiv = motvind)
            let v_rel =
                relative_wind_series_ms(inputs.headings_deg, w.wind_dir_deg, w.wind_speed_ms);

            // Vindstille edge-case
            let v_rel: Vec<f64> = v_rel
                .into_iter()
                .map(|v| if v.abs() < 0.001 { 0.0 } else { v })
                .collect();

            // median relativ vinkel (grader)
            let rel_angles: Vec<f64> = inputs
                .headings_deg
                .iter()
                .map(|h| relative_angle_deg(*h, w.wind_dir_deg))
                .collect();

            (v_rel, median(rel_angles))
        }
        (Some(_w), false) => {
            // Mangler heading → v_rel = 0
            (vec![0.0; inputs.duration_secs as usize], 0.0)
        }
        (None, _) => {
            // Mangler vær → v_rel = 0
            (vec![0.0; inputs.duration_secs as usize], 0.0)
        }
    };

    // 5️⃣ Returner resultatet (inkl. Crr og masse for persist/PW)
    AnalyzeOutputs {
        v_rel_ms,
        wind_rel_deg,
        weather_used: weather_opt,
        crr_used,
        rider_weight_kg: inputs.rider_weight_kg,
        bike_weight_kg: inputs.bike_weight_kg,
        total_mass_kg,
    }
}
