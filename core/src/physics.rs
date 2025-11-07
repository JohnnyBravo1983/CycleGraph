#![cfg_attr(not(debug_assertions), allow(dead_code))]

// core/src/physics.rs
use crate::models::{Profile, Sample, Weather};

// --- helper: tåler både f64 og Option<f64> -------------------------------
trait OrValue {
    fn orv(self, default: f64) -> f64;
}
impl OrValue for f64 {
    #[inline]
    fn orv(self, default: f64) -> f64 {
        if self.is_finite() { self } else { default }
    }
}
impl OrValue for Option<f64> {
    #[inline]
    fn orv(self, default: f64) -> f64 {
        self.unwrap_or(default)
    }
}
// -------------------------------------------------------------------------

const G: f64 = 9.80665;

// -------------------------------
// Små helpers
// -------------------------------
pub trait RoundTo {
    fn round_to(self, dp: u32) -> f64;
}
impl RoundTo for f64 {
    #[inline]
    fn round_to(self, dp: u32) -> f64 {
        if dp == 0 {
            return self.round();
        }
        let factor = 10_f64.powi(dp as i32);
        (self * factor).round() / factor
    }
}

/// Total masse (kg) = rytter + sykkel
#[inline]
pub fn total_mass(rider_weight_kg: f64, bike_weight_kg: f64) -> f64 {
    (rider_weight_kg + bike_weight_kg).round_to(5)
}

/// CdA ut fra sykkeltype (fallback)
fn cda_for(bike_type: Option<&str>) -> f64 {
    match bike_type.unwrap_or("road").to_lowercase().as_str() {
        "tt" | "tri" => 0.25,
        "mtb" | "gravel" => 0.40,
        _ => 0.30,
    }
}

/// Crr-estimat fra dekkbredde/kvalitet.
pub fn estimate_crr(_bike_type: &str, tire_width_mm: f64, tire_quality: &str) -> f64 {
    let w = if tire_width_mm < 20.0 { 25.0 } else { tire_width_mm };

    let quality_factor = match tire_quality {
        "Trening" => 1.2,
        "Vanlig" => 1.0,
        "Ritt" => 0.85,
        _ => 1.0,
    };

    let relative = (28.0 / w).powf(0.3);
    let crr = 0.005 * relative * quality_factor;

    crr.round_to(5)
}

// -------------------------------
// Geometri / vind
// -------------------------------
use std::f64::consts::PI;

#[inline]
pub(crate) fn cg_deg2rad(d: f64) -> f64 { d * PI / 180.0 }
#[inline]
pub(crate) fn cg_rad2deg(r: f64) -> f64 { r * 180.0 / PI }

#[inline]
pub(crate) fn cg_wrap360(mut d: f64) -> f64 {
    d = d % 360.0;
    if d < 0.0 { d + 360.0 } else { d }
}

#[inline]
fn deg_to_rad(d: f64) -> f64 { d * std::f64::consts::PI / 180.0 }

#[inline]
fn wrap360(mut d: f64) -> f64 {
    d = d % 360.0;
    if d < 0.0 { d + 360.0 } else { d }
}

/// Bearing A->B i grader [0,360), 0 = nord, 90 = øst
pub(crate) fn cg_bearing_deg(lat1: f64, lon1: f64, lat2: f64, lon2: f64) -> f64 {
    let (phi1, phi2) = (cg_deg2rad(lat1), cg_deg2rad(lat2));
    let dlam = cg_deg2rad(lon2 - lon1);
    let y = dlam.sin() * phi2.cos();
    let x = phi1.cos()*phi2.sin() - phi1.sin()*phi2.cos()*dlam.cos();
    let theta = y.atan2(x);
    let mut deg = (cg_rad2deg(theta) + 360.0) % 360.0;
    if deg < 0.0 { deg += 360.0; }
    deg
}

/// Vindretning kommer meteorologisk som "fra". Konverter til "til".
#[inline]
pub(crate) fn cg_wind_to_deg(wind_from_deg: f64) -> f64 {
    (wind_from_deg + 180.0) % 360.0
}

/// Vind-komponent langs syklistens heading (positiv = medvind, negativ = motvind).
#[inline]
pub(crate) fn cg_along_wind_component(heading_deg: f64, wind_from_deg: f64, wind_ms: f64) -> f64 {
    let wind_to = cg_wind_to_deg(wind_from_deg);
    let delta = cg_deg2rad(heading_deg - wind_to);
    wind_ms * delta.cos()
}

/// Relativ luftfart som vektor-differanse |v_vec − wind_vec|
#[inline]
pub(crate) fn cg_relative_air_speed(v_ms: f64, heading_deg: f64, wind_from_deg: f64, wind_ms: f64) -> f64 {
    let v = v_ms.max(0.0);
    let wind_towards = cg_wind_to_deg(wind_from_deg);

    let vh = cg_deg2rad(heading_deg);
    let wh = cg_deg2rad(wind_towards);

    // 0° = nord, x=øst, y=nord
    let vx = v * vh.sin();
    let vy = v * vh.cos();
    let wx = wind_ms * wh.sin();
    let wy = wind_ms * wh.cos();

    let rx = vx - wx;
    let ry = vy - wy;
    (rx*rx + ry*ry).sqrt().max(0.0)
}

// --- Bonus: trygg projeksjon + enkel v_air (skalar) for tester -------------
#[inline]
fn apparent_air_speed(v_ms: f64, bike_heading_deg: f64, wind_from_deg: f64, wind_ms: f64) -> f64 {
    let wind_to_deg = wrap360(wind_from_deg + 180.0);
    let delta = deg_to_rad(wrap360(bike_heading_deg - wind_to_deg));
    let along = wind_ms * delta.cos();   // + medvind, - motvind
    (v_ms - along).max(0.1)
}

// -------------------------------
// Lufttetthet
// -------------------------------

/// Lufttetthet ρ = p / (R * T). Inndata: °C og hPa (konverteres her).
#[inline]
fn air_density(air_temp_c: f64, air_pressure_hpa: f64) -> f64 {
    let p_pa = air_pressure_hpa * 100.0; // hPa -> Pa
    let t_k  = air_temp_c + 273.15;      // °C -> K
    let r = 287.05_f64;                  // J/(kg·K)
    (p_pa / (r * t_k)).clamp(0.9, 1.4)
}

// ------------------------------------------------------
// Gravity component (Sprint 14.7 – isolert testversjon)
// ------------------------------------------------------
pub fn compute_gravity_component(
    mass_kg: f64,
    altitude_series: &[f64],
    dt_series: &[f64],
) -> Vec<f64> {
    let n = altitude_series.len();
    let mut out = Vec::with_capacity(n);
    let win: usize = 2;

    for i in 0..n {
        let prev_i = if i >= win { i - win } else { 0 };
        let next_i = if i + win < n { i + win } else { n - 1 };
        let dh = altitude_series[next_i] - altitude_series[prev_i];
        let dt_sum = dt_series[prev_i..=next_i].iter().sum::<f64>().max(0.01);
        let dh_dt = dh / dt_sum;
        let p_g = mass_kg * G * dh_dt;

        #[cfg(debug_assertions)]
        if i < 20 {
            eprintln!("[DBG] sample={} dh/dt={:.4}  grav={:.2} W", i, dh_dt, p_g);
        }

        out.push(p_g);
    }

    out
}

/// Utdata fra kraftberegning med vind
#[derive(Debug, Clone)]
pub struct PowerOutputs {
    pub power: Vec<f64>,
    pub wind_rel: Vec<f64>, // + medvind (m/s), − motvind
    pub v_rel: Vec<f64>,    // relativ luftfart (m/s)
}

#[inline]
fn sample_heading_deg(i: usize, samples: &[Sample]) -> f64 {
    let s = samples[i];
    let h = s.heading_deg.orv(f64::NAN);
    if h.is_finite() {
        return h;
    }
    if i + 1 < samples.len() {
        return samples[i].heading_to(&samples[i + 1]).unwrap_or(0.0);
    }
    if i >= 1 {
        return samples[i - 1].heading_to(&samples[i]).unwrap_or(0.0);
    }
    0.0
}

/// Full beregning med v_rel/wind_rel tilgjengelig.
/// Full beregning med v_rel/wind_rel tilgjengelig.
pub fn compute_power_with_wind(
    samples: &[Sample],
    profile: &Profile,
    weather: &Weather,
) -> PowerOutputs {
    let n = samples.len();
    if n == 0 {
        return PowerOutputs { power: vec![], wind_rel: vec![], v_rel: vec![] };
    }

    // Profilparametre (robuste defaults)
    let mass = profile.total_weight.unwrap_or(75.0);
    let crr  = profile.crr.unwrap_or(0.005);
    let cda  = profile.cda.unwrap_or_else(|| cda_for(profile.bike_type.as_deref()));

    // Glatt høyde for robust stigning
    let alt = crate::smoothing::smooth_altitude(samples);

    // --- Gravity probe ---
    let mut dt_series: Vec<f64> = samples
        .windows(2)
        .map(|w| (w[1].t - w[0].t).abs().max(0.01))
        .collect();
    if dt_series.len() < alt.len() {
        let pad = *dt_series.last().unwrap_or(&1.0);
        dt_series.resize(alt.len(), pad);
    }
    let g_raw = compute_gravity_component(mass, &alt, &dt_series);
    let first5_len = g_raw.len().min(5);
    eprintln!("[DBG] gravity_probe n={} first5={:?}", g_raw.len(), &g_raw[..first5_len]);

    
    // Lufttetthet: bruk eksplisitt rho hvis gitt, ellers beregn fra T/P
// --- Lufttetthet (T/P → rho) ---
let rho = air_density(
    weather.air_temp_c.orv(15.0),
    weather.air_pressure_hpa.orv(1013.25),
);

// --- Debug: værdata som faktisk når Rust ---
eprintln!(
    "[DBG] weather_in => T={:.1}°C  P={:.0}hPa  wind_ms={:.1}  wind_dir={:.0}°  rho={:.3}",
    weather.air_temp_c.orv(15.0),
    weather.air_pressure_hpa.orv(1013.25),
    weather.wind_ms.orv(0.0),
    weather.wind_dir_deg.orv(0.0),
    rho
);

let mut power_out    = Vec::with_capacity(n);
let mut wind_rel_out = Vec::with_capacity(n);
let mut v_rel_out    = Vec::with_capacity(n);

for i in 0..n {
    let s = samples[i];

    // Tid og forrige fart
    let (dt, v_prev) = if i == 0 {
        (1.0, s.v_ms.max(0.0))
    } else {
        let sp = samples[i - 1];
        (((s.t - sp.t).abs()).max(1e-3), sp.v_ms.max(0.0))
    };

    // Midtfart og akselerasjon (stabil integrasjon)
    let v = s.v_ms.max(0.0);
    let v_mid = 0.5 * (v + v_prev);
    let a = (v - v_prev) / dt;

    // Heading fra sample hvis satt; ellers bearing
    let heading_deg = sample_heading_deg(i, samples);

    // --- Vind: hos deg er feltene f64 (ikke Option)
    let wind_ms: f64 = weather.wind_ms.orv(0.0).max(0.0);
    // wind_dir_deg tolkes som "TO"-retning allerede; normaliser til [0,360)
    let wind_dir_to_deg: f64 = cg_wrap360(weather.wind_dir_deg.orv(0.0));

    // Langs-komponent (+ medvind, − motvind)
    let delta_rad = cg_deg2rad(cg_wrap360(heading_deg - wind_dir_to_deg));
    let along = wind_ms * delta_rad.cos();

    // Relativ luftfart (skalar)
    let v_rel = (v - along).max(0.1);

    // Komponenter
    let p_roll = mass * G * crr * v_mid;
    let p_aero = 0.5 * rho * cda * v_rel.abs().powi(3);
    let p_grav = g_raw[i].max(0.0);
    let p_acc  = (mass * a * v_mid).max(0.0);

    let p = p_roll + p_aero + p_grav + p_acc;

    power_out.push(if p.is_finite() { p.max(0.0) } else { 0.0 });
    wind_rel_out.push(along);
    v_rel_out.push(v_rel);
}


    PowerOutputs { power: power_out, wind_rel: wind_rel_out, v_rel: v_rel_out }
}


/// Bakoverkompatibel wrapper
pub fn compute_power(samples: &[Sample], profile: &Profile, weather: &Weather) -> Vec<f64> {
    compute_power_with_wind(samples, profile, weather).power
}

/// Indoor-beregning
pub fn compute_indoor_power(sample: &Sample, profile: &Profile) -> f64 {
    if let Some(watts) = sample.device_watts {
        return watts;
    }

    let v = sample.v_ms.max(0.0);
    let cda = profile.cda.unwrap_or_else(|| cda_for(profile.bike_type.as_deref()));
    let crr = profile.crr.unwrap_or(0.004);
    let mass = profile.total_weight.unwrap_or(75.0);

    let rho = 1.225;
    let p_aero = 0.5 * rho * cda * v.abs().powi(3);
    let p_roll = mass * G * crr * v;

    (p_aero + p_roll).max(0.0)
}

/* -------------------------------------------------------------------------
   Nye komponent-beregninger (drag/rolling/climb) for tidsserier.
   ------------------------------------------------------------------------- */

#[derive(Debug, Clone)]
pub struct Components {
    pub total: Vec<f64>,
    pub drag: Vec<f64>,
    pub rolling: Vec<f64>,
}

fn gradient_from_alt(alt: &Vec<f64>, vel_len: usize, vel: &Vec<f64>) -> Vec<f64> {
    let n = vel_len.min(alt.len());
    if n == 0 {
        return Vec::new();
    }
    let mut grad = vec![0.0; n];
    for i in 1..n {
        let v_mid = 0.5 * (vel[i].max(0.0) + vel[i - 1].max(0.0));
        let ds = (v_mid * 1.0).max(1e-3);
        grad[i] = ((alt[i] - alt[i - 1]) / ds).clamp(-0.3, 0.3);
    }
    grad
}

pub fn compute_components(
    vel: &Vec<f64>,
    alt: &Vec<f64>,
    cda: f64,
    crr: f64,
    weight: f64,
    rho: f64,
) -> Components {
    let mass = weight;
    let n = vel.len();
    let mut total = Vec::with_capacity(n);
    let mut drag = Vec::with_capacity(n);
    let mut rolling = Vec::with_capacity(n);

    let grad = gradient_from_alt(alt, n, vel);

    for i in 0..n {
        let v = vel[i].max(0.0);
        let p_drag = 0.5 * rho * cda * v.powi(3);
        let p_roll = crr * mass * G * v * (1.0 - 0.5 * grad[i] * grad[i]);
        let p_climb = (mass * G * v * grad[i]).max(0.0);

        let p = p_drag + p_roll + p_climb;

        drag.push(if p_drag.is_finite() { p_drag.max(0.0) } else { 0.0 });
        rolling.push(if p_roll.is_finite() { p_roll.max(0.0) } else { 0.0 });
        total.push(if p.is_finite() { p.max(0.0) } else { 0.0 });
    }

    Components { total, drag, rolling }
}

// -------------------------------
// Tester (syntetisk vind sanity)
// -------------------------------
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn relative_air_speed_tail_vs_headwind() {
        // v = 10 m/s. Vind = 5 m/s.
        // Case A (medvind): wind_from = heading + 180 => v_air ~ 5
        // Case B (motvind): wind_from = heading       => v_air ~ 15
        let v = 10.0;
        let wind = 5.0;
        let heading = 90.0; // øst

        // medvind: vind fra vest (heading+180)
        let v_air_tail = cg_relative_air_speed(v, heading, heading + 180.0, wind);
        // motvind: vind fra øst (samme som heading)
        let v_air_head = cg_relative_air_speed(v, heading, heading, wind);

        assert!(
            (v_air_tail - 5.0).abs() < 1e-9,
            "tailwind v_air expected ~5, got {v_air_tail}"
        );
        assert!(
            (v_air_head - 15.0).abs() < 1e-9,
            "headwind v_air expected ~15, got {v_air_head}"
        );

        // Sjekk også at langs-komponenten har rett fortegn
        let along_tail = cg_along_wind_component(heading, heading + 180.0, wind);
        let along_head = cg_along_wind_component(heading, heading, wind);
        assert!(
            along_tail > 0.0 && (along_tail - 5.0).abs() < 1e-9,
            "tailwind along ~+5"
        );
        assert!(
            along_head < 0.0 && (along_head + 5.0).abs() < 1e-9,
            "headwind along ~-5"
        );
    }

    #[test]
    fn test_apparent_air_speed_sign() {
        let v = 10.0;
        let w = 5.0;
        let h = 90.0; // øst

        // Medvind: vind FRA vest (270) -> TIL øst (90)
        let v_air_med = super::apparent_air_speed(v, h, 270.0, w);
        assert!(
            (v_air_med - 5.0).abs() < 1e-6,
            "medvind burde gi ~5 m/s, fikk {v_air_med}"
        );

        // Motvind: vind FRA øst (90) -> TIL vest (270)
        let v_air_mot = super::apparent_air_speed(v, h, 90.0, w);
        assert!(
            (v_air_mot - 15.0).abs() < 1e-6,
            "motvind burde gi ~15 m/s, fikk {v_air_mot}"
        );
    }
}
