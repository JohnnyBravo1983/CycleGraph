// core/src/physics.rs

pub const G: f64 = 9.80665;

// ===============================
// Helpers
// ===============================
#[inline]
pub fn wrap360(mut x: f64) -> f64 {
    x %= 360.0;
    if x < 0.0 {
        x += 360.0;
    }
    x
}
#[inline]
pub fn deg_to_rad(d: f64) -> f64 {
    d * std::f64::consts::PI / 180.0
}

// Kompatible alias brukt i tester/annet kode
#[inline]
pub fn cg_wrap360(x: f64) -> f64 {
    wrap360(x)
}
#[inline]
pub fn cg_deg2rad(d: f64) -> f64 {
    deg_to_rad(d)
}

// Enkle defaults lokalt (slipper import av bike::cda_for)
fn cda_for(bike_type: Option<&str>) -> f64 {
    match bike_type.unwrap_or("").to_ascii_lowercase().as_str() {
        "tt" | "tri" | "time_trial" => 0.21,
        "road" | "racer" => 0.25,
        "gravel" => 0.28,
        "mtb" => 0.35,
        "city" | "commuter" => 0.40,
        _ => 0.30,
    }
}

// ===============================
// Avhengige typer (hos deg i crate-roten)
// ===============================
use crate::smoothing;
use crate::{Profile, Sample, Weather}; // smooth_altitude(samples)

// -------------------------------
// Vindgeometri – utilities (brukes i tester)
// -------------------------------
#[inline]
pub fn cg_along_wind_component(bike_heading_deg: f64, wind_from_deg: f64, wind_ms: f64) -> f64 {
    let wind_to_deg = wrap360(wind_from_deg + 180.0); // meteorologisk "FRA" → "TIL"
    let delta = deg_to_rad(wrap360(bike_heading_deg - wind_to_deg));
    wind_ms.max(0.0) * delta.cos()
}

#[inline]
pub fn cg_relative_air_speed(
    v_ms: f64,
    bike_heading_deg: f64,
    wind_from_deg: f64,
    wind_ms: f64,
) -> f64 {
    let along = cg_along_wind_component(bike_heading_deg, wind_from_deg, wind_ms);
    (v_ms - along).max(0.1)
}

#[inline]
pub fn apparent_air_speed(
    v_ms: f64,
    bike_heading_deg: f64,
    wind_from_deg: f64,
    wind_ms: f64,
) -> f64 {
    cg_relative_air_speed(v_ms, bike_heading_deg, wind_from_deg, wind_ms)
}

// -------------------------------
// Lufttetthet
// -------------------------------
#[inline]
fn air_density(air_temp_c: f64, air_pressure_hpa: f64) -> f64 {
    let p_pa = air_pressure_hpa * 100.0; // hPa → Pa
    let t_k = air_temp_c + 273.15; // °C → K
    let r = 287.05_f64; // J/(kg·K)
    (p_pa / (r * t_k)).clamp(0.9, 1.4)
}

// ------------------------------------------------------
// Gravity component (Sprint 14.7 – isolert testversjon)
// ------------------------------------------------------
// Gravity component (Sprint 14.7 – verifiserbar versjon)
// ------------------------------------------------------
pub fn compute_gravity_component(
    mass_kg: f64,
    altitude_series: &[f64],
    dt_series: &[f64],
) -> Vec<f64> {
    let n = altitude_series.len();
    let mut out = Vec::with_capacity(n);
    let win: usize = 2;

    // ── ÉN gang: logg globale verdier slik at vi vet hva som faktisk brukes
    if n > 1 {
        let dh_total = altitude_series[n - 1] - altitude_series[0];
        let dt_total = dt_series.iter().sum::<f64>().max(0.01);
        let dh_dt_avg = dh_total / dt_total;

        eprintln!(
            "[DBG_GRAV] mass_kg={:.2} n={} dh_total={:.3} dt_total={:.3} dh_dt_avg={:.6}",
            mass_kg, n, dh_total, dt_total, dh_dt_avg
        );
    }

    for i in 0..n {
        let prev_i = if i >= win { i - win } else { 0 };
        let next_i = if i + win < n { i + win } else { n - 1 };

        let dh = altitude_series[next_i] - altitude_series[prev_i];
        let dt_sum = dt_series[prev_i..=next_i].iter().sum::<f64>().max(0.01);

        let dh_dt = dh / dt_sum;
        let p_g = mass_kg * G * dh_dt;

        #[cfg(debug_assertions)]
        if i < 10 {
            eprintln!(
                "[DBG_GRAV_SAMPLE] i={} dh/dt={:.6} grav={:.2} W",
                i, dh_dt, p_g
            );
        }

        out.push(p_g);
    }

    out
}
// -------------------------------
// Outputs
// -------------------------------
#[derive(Debug, Clone)]
pub struct PowerOutputs {
    pub power: Vec<f64>,
    pub wind_rel: Vec<f64>, // + medvind (m/s), − motvind
    pub v_rel: Vec<f64>,    // relativ luftfart (m/s)
}

#[inline]
fn sample_heading_deg(i: usize, samples: &[Sample]) -> f64 {
    let s = samples[i];
    // Hos deg er heading_deg et f64. Bruk direkte hvis finitt, ellers beregn bearing.
    let h = s.heading_deg;
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

// ==========================================
// Hovedberegning (med v_rel / wind_rel ut)
// ==========================================
pub fn compute_power_with_wind(
    samples: &[Sample],
    profile: &Profile,
    weather: &Weather,
) -> PowerOutputs {
    let n = samples.len();
    if n == 0 {
        return PowerOutputs {
            power: vec![],
            wind_rel: vec![],
            v_rel: vec![],
        };
    }

    // Profilparametre (robuste defaults)
    let mass = profile.total_weight.unwrap_or(75.0);
    let crr = profile.crr.unwrap_or(0.005);
    let cda = profile
        .cda
        .unwrap_or_else(|| cda_for(profile.bike_type.as_deref()));

    // Glatt høyde for robust stigning
    let alt = smoothing::smooth_altitude(samples);

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
    eprintln!(
        "[DBG] gravity_probe n={} first5={:?}",
        g_raw.len(),
        &g_raw[..first5_len]
    );

    // --- Lufttetthet (T/P → rho) ---
    // Weather-feltene er f64 hos deg. Bruk fornuftige defaults ved ikke-finite.
    let t_c = if weather.air_temp_c.is_finite() {
        weather.air_temp_c
    } else {
        15.0
    };
    let p_hpa = if weather.air_pressure_hpa.is_finite() {
        weather.air_pressure_hpa
    } else {
        1013.25
    };
    let w_ms = if weather.wind_ms.is_finite() {
        weather.wind_ms
    } else {
        0.0
    };
    let w_deg = if weather.wind_dir_deg.is_finite() {
        weather.wind_dir_deg
    } else {
        0.0
    };

    let rho = air_density(t_c, p_hpa);

    // --- Debug: værdata som faktisk når Rust ---
    eprintln!(
        "[DBG] weather_in => T={:.1}°C  P={:.0}hPa  wind_ms={:.1}  wind_dir={:.0}°  rho={:.3}",
        t_c, p_hpa, w_ms, w_deg, rho
    );

    let mut power_out = Vec::with_capacity(n);
    let mut wind_rel_out = Vec::with_capacity(n);
    let mut v_rel_out = Vec::with_capacity(n);

    for i in 0..n {
        let s = samples[i];

        // Tid og forrige fart
        let (dt, v_prev) = if i == 0 {
            (1.0, s.v_ms.max(0.0))
        } else {
            let sp = samples[i - 1];
            (((s.t - sp.t).abs()).max(1e-3), sp.v_ms.max(0.0))
        };

        // Midtfart og akselerasjon
        let v = s.v_ms.max(0.0);
        let v_mid = 0.5 * (v + v_prev);
        let a = (v - v_prev) / dt;

        // Heading
        let heading_deg = sample_heading_deg(i, samples);

        // --- WIND DIRECTION HANDLING (TO-konvensjon i hovedkjernen) ---
        let wind_ms = w_ms.max(0.0);
        let wind_to_deg = wrap360(w_deg); // tolkes som "TIL"-retning

        // Vektor-projeksjon langs bevegelsesretningen
        let delta_rad = deg_to_rad(wrap360(heading_deg - wind_to_deg));

        // Langskomponenten (positiv = medvind, negativ = motvind)
        let wind_along = wind_ms * delta_rad.cos();

        // Relativ luftfart (medvind ↓, motvind ↑)
        let v_rel = (v - wind_along).max(0.1);

        // Komponenter
        let p_roll = mass * G * crr * v_mid; // rullewatt bruker bakketempo
        let p_aero = 0.5 * rho * cda * v_rel.powi(3); // *** drag bruker v_rel^3 ***
        let p_grav = g_raw[i].max(0.0);
        let p_acc = (mass * a * v_mid).max(0.0);

        let p = p_roll + p_aero + p_grav + p_acc;

        power_out.push(if p.is_finite() { p.max(0.0) } else { 0.0 });
        wind_rel_out.push(wind_along);
        v_rel_out.push(v_rel);
    }

    PowerOutputs {
        power: power_out,
        wind_rel: wind_rel_out,
        v_rel: v_rel_out,
    }
}

// Bakoverkompatibel wrapper
pub fn compute_power(samples: &[Sample], profile: &Profile, weather: &Weather) -> Vec<f64> {
    compute_power_with_wind(samples, profile, weather).power
}

// Indoor-beregning
pub fn compute_indoor_power(sample: &Sample, profile: &Profile) -> f64 {
    if let Some(watts) = sample.device_watts {
        return watts;
    }

    let v = sample.v_ms.max(0.0);
    let cda = profile
        .cda
        .unwrap_or_else(|| cda_for(profile.bike_type.as_deref()));
    let crr = profile.crr.unwrap_or(0.004);
    let mass = profile.total_weight.unwrap_or(75.0);

    let rho = 1.225;
    let p_aero = 0.5 * rho * cda * v.abs().powi(3);
    let p_roll = mass * G * crr * v;

    (p_aero + p_roll).max(0.0_f64)
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
    // Nye valgfrie parametre for vind
    wind_ms_opt: Option<&Vec<f64>>,
    wind_dir_deg_opt: Option<&Vec<f64>>,
    heading_deg_opt: Option<&Vec<f64>>,
) -> Components {
    let mass = weight;
    let n = vel.len();
    let mut total = Vec::with_capacity(n);
    let mut drag = Vec::with_capacity(n);
    let mut rolling = Vec::with_capacity(n);

    let grad = gradient_from_alt(alt, n, vel);

    for i in 0..n {
        let v = vel[i].max(0.0);

        // --- beregn relativ luftfart ---
        let v_rel_ms = if let (Some(wind_ms), Some(wind_dir), Some(heading)) =
            (wind_ms_opt, wind_dir_deg_opt, heading_deg_opt)
        {
            let w_ms = wind_ms[i];
            let w_dir_deg = wind_dir[i];
            let hdg_deg = heading[i];

            // heading_deg er retning syklist, wind_dir_deg er "TO"-retning → gjør den om til "FROM"
            let heading_rad = hdg_deg.to_radians();
            let wind_from_rad = (w_dir_deg + 180.0).to_radians();

            let wind_vx = w_ms * wind_from_rad.sin();
            let wind_vy = w_ms * wind_from_rad.cos();

            let rider_vx = v * heading_rad.sin();
            let rider_vy = v * heading_rad.cos();

            let v_rel_x = rider_vx + wind_vx;
            let v_rel_y = rider_vy + wind_vy;
            (v_rel_x * v_rel_x + v_rel_y * v_rel_y).sqrt()
        } else {
            // fallback uten vinddata
            v
        };

        // --- komponenter ---
        let p_drag = 0.5 * rho * cda * v_rel_ms.powi(3);
        let p_roll = crr * mass * G * v * (1.0 - 0.5 * grad[i] * grad[i]);
        let p_climb = (mass * G * v * grad[i]).max(0.0);
        let p = p_drag + p_roll + p_climb;

        drag.push(if p_drag.is_finite() {
            p_drag.max(0.0)
        } else {
            0.0
        });
        rolling.push(if p_roll.is_finite() {
            p_roll.max(0.0)
        } else {
            0.0
        });
        total.push(if p.is_finite() { p.max(0.0) } else { 0.0 });
    }

    Components {
        total,
        drag,
        rolling,
    }
}

// ---------------------------------------
// API som andre moduler forventer finnes
// ---------------------------------------

// Match analyze_session-signaturen: (bike_type, tire_width_mm, tire_quality)
pub fn estimate_crr(bike_type: &str, tire_width_mm: f64, tire_quality: &str) -> f64 {
    let bt = bike_type.to_ascii_lowercase();

    // Grunnverdi basert på sykkeltype (enkle, konservative heuristikker)
    let mut crr: f64 = match bt.as_str() {
        "tt" | "tri" | "time_trial" => 0.0035_f64,
        "road" | "racer" => 0.0045_f64,
        "gravel" => 0.0065_f64,
        "mtb" => 0.0090_f64,
        _ => 0.0055_f64,
    };

    // ----- Bredde-guard -----
    // Testkrav: bredde <= 10 mm -> 25 mm (og NaN/inf -> 25 mm)
    let w_eff: f64 = if !tire_width_mm.is_finite() || tire_width_mm <= 10.0 {
        25.0_f64
    } else {
        tire_width_mm
    };

    // Breddejustering (kun for landevei/TT)
    if matches!(bt.as_str(), "road" | "racer" | "tt" | "tri" | "time_trial") {
        if w_eff >= 28.0 {
            crr -= 0.0003_f64;
        } else if w_eff <= 23.0 {
            crr += 0.0002_f64;
        }
    }

    // ----- Kvalitet -----
    let tq_raw = tire_quality.trim().to_ascii_lowercase();

    // Utvidet fallback: tolker ALT som inneholder disse ordene som "vanlig/ukjent" → 1.0
    let only_non_alpha = tq_raw.chars().all(|c| !c.is_alphabetic());
    let is_unknown_or_vanlig = tq_raw.is_empty()
        || only_non_alpha
        || tq_raw.contains("ukjent")
        || tq_raw.contains("unknown")
        || tq_raw.contains("vanlig")
        || tq_raw.contains("standard")
        || tq_raw.contains("normal")
        || tq_raw == "1"
        || tq_raw == "1.0"
        || tq_raw.contains("default")
        || tq_raw == "none"
        || tq_raw == "n/a"
        || tq_raw == "na";

    if is_unknown_or_vanlig {
        return crr.clamp(0.0025_f64, 0.0120_f64);
    }

    // "Trening" → høyere Crr
    let is_training = tq_raw.contains("trening")
        || tq_raw.contains("training")
        || tq_raw.contains("trainer")
        || tq_raw.contains("durable")
        || tq_raw.contains("commuter")
        || tq_raw.contains("winter")
        || tq_raw.contains("allseason")
        || tq_raw.contains("puncture")
        || tq_raw.contains("armour")
        || tq_raw.contains("armored")
        || tq_raw.contains("armoured")
        || tq_raw.contains("gatorskin")
        || tq_raw.contains("marathon")
        || tq_raw.contains("robust");

    // "Race/high-performance" → lavere Crr
    let is_race = tq_raw.contains("race")
        || tq_raw.contains("racing")
        || tq_raw.contains("tt")
        || tq_raw.contains("chrono")
        || tq_raw.contains("fast")
        || tq_raw.contains("supersonic")
        || tq_raw.contains("cotton")
        || tq_raw.contains("latex")
        || tq_raw.contains("tlr")
        || tq_raw.contains("tubeless")
        || tq_raw.contains("gp5000")
        || tq_raw.contains("pro one")
        || tq_raw.contains("corsa");

    if is_training {
        crr += 0.0004_f64; // trening ↑
    } else if is_race {
        crr -= 0.0003_f64; // race ↓
    } else if tq_raw.contains("cheap") {
        crr += 0.0003_f64; // eksplisitt "billig" ↑
    }

    crr.clamp(0.0025_f64, 0.0120_f64)
}

// Match analyze_session-signaturen: (rider_weight_kg, bike_weight_kg)
pub fn total_mass(rider_weight_kg: f64, bike_weight_kg: f64) -> f64 {
    let rw = if rider_weight_kg.is_finite() {
        rider_weight_kg
    } else {
        70.0
    };
    let bw = if bike_weight_kg.is_finite() {
        bike_weight_kg
    } else {
        9.0
    };
    (rw + bw).max(40.0)
}

// Rounding-trait som ofte importeres fra physics
pub trait RoundTo {
    fn round_to(self, decimals: u32) -> f64;
}
impl RoundTo for f64 {
    fn round_to(self, decimals: u32) -> f64 {
        let p = 10f64.powi(decimals as i32);
        (self * p).round() / p
    }
}

// -------------------------------
// Tester (syntetisk vind sanity)
// -------------------------------
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn relative_air_speed_tail_vs_headwind() {
        let v = 10.0;
        let wind = 5.0;
        let heading = 90.0; // øst

        let v_air_tail = cg_relative_air_speed(v, heading, heading + 180.0, wind);
        let v_air_head = cg_relative_air_speed(v, heading, heading, wind);

        assert!((v_air_tail - 5.0).abs() < 1e-9);
        assert!((v_air_head - 15.0).abs() < 1e-9);

        let along_tail = cg_along_wind_component(heading, heading + 180.0, wind);
        let along_head = cg_along_wind_component(heading, heading, wind);
        assert!(along_tail > 0.0 && (along_tail - 5.0).abs() < 1e-9);
        assert!(along_head < 0.0 && (along_head + 5.0).abs() < 1e-9);
    }

    #[test]
    fn test_apparent_air_speed_sign() {
        let v = 10.0;
        let w = 5.0;
        let h = 90.0; // øst

        let v_air_med = super::apparent_air_speed(v, h, 270.0, w);
        assert!((v_air_med - 5.0).abs() < 1e-6);

        let v_air_mot = super::apparent_air_speed(v, h, 90.0, w);
        assert!((v_air_mot - 15.0).abs() < 1e-6);
    }
}
