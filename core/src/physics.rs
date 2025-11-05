// core/src/physics.rs
// ---------- øverst i physics.rs (rett under use-linjene) ----------
use crate::models::{Metrics, Profile, Sample};
use crate::Weather;

pub const G: f64 = 9.80665;        // gravitasjon (m/s²)
pub const RHO: f64 = 1.225;        // lufttetthet (kg/m³)
pub const MIN_V_MS: f64 = 1.0;     // min. gyldig hastighet (m/s)
pub const MIN_DT_S: f64 = 0.2;     // min. tidssteg (sek)
pub const GRADE_MA_WIN: usize = 5; 
pub const ETA_DEFAULT: f64 = 0.955; // standard drivverkseffektivitet crank→hjul
// --- RoundTo trait (offentlig, brukt av lib.rs) ---
pub trait RoundTo {
    fn round_to(self, dp: u32) -> f64;
}

impl RoundTo for f64 {
    #[inline]
    fn round_to(self, dp: u32) -> f64 {
        if dp == 0 { return self.round(); }
        let factor = 10_f64.powi(dp as i32);
        (self * factor).round() / factor
    }
}

#[cfg(any(test, debug_assertions))]
#[derive(Debug, Clone, Copy, Default)]
struct PerSample {
    w_drag: f64,
    w_roll: f64,
    w_gravity: f64,
    w_precision: f64,
    w_total: f64,
}

#[cfg(any(test, debug_assertions))]
fn clamp_nonneg(x: f64) -> f64 {
    if x.is_finite() && x > 0.0 { x } else { 0.0 }
}

#[cfg(any(test, debug_assertions))]
fn ma_vec(xs: &[f64], win: usize) -> Vec<f64> {
    if win <= 1 || xs.is_empty() { return xs.to_vec(); }
    let mut out = Vec::with_capacity(xs.len());
    let mut sum = 0.0;
    for i in 0..xs.len() {
        sum += xs[i];
        if i >= win { sum -= xs[i - win]; }
        let denom = (i + 1).min(win) as f64;
        out.push(sum / denom);
    }
    out
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

/// Total masse (kg) = rytter + sykkel.
#[inline]
pub fn total_mass(rider_weight_kg: f64, bike_weight_kg: f64) -> f64 {
    (rider_weight_kg + bike_weight_kg).round_to(5)
}

/// CdA ut fra sykkeltype (fallback hvis profile.cda ikke er satt)
fn cda_for(bike_type: Option<&str>) -> f64 {
    match bike_type.unwrap_or("road").to_lowercase().as_str() {
        "tt" | "tri" => 0.25,
        "mtb" | "gravel" => 0.40,
        _ => 0.30,
    }
}

#[allow(dead_code)]
fn air_density(air_temp_c: f64, air_pressure_hpa: f64) -> f64 {
    let p_pa = (air_pressure_hpa * 100.0).max(1.0);
    let t_k = (air_temp_c + 273.15).max(150.0);
    (p_pa / (287.05 * t_k)).clamp(0.9, 1.4)
}

/// ----- Kraft-komponent helpers -----

#[inline]
fn drag_watt(rho: f64, cda: f64, v_rel_ms: f64) -> f64 {
    let v = v_rel_ms.max(0.0);
    let p = 0.5 * rho * cda * v.powi(3);
    if p.is_finite() { p.max(0.0) } else { 0.0 }
}

#[inline]
fn rolling_watt(crr: f64, mass_kg: f64, v_ms: f64) -> f64 {
    let v = v_ms.max(0.0);
    let p = mass_kg * G * crr * v;
    if p.is_finite() { p.max(0.0) } else { 0.0 }
}

/// Rå gravitasjonseffekt fra høydeendring (signert).
/// Kompiler kun i debug/test for å unngå dead_code i release.
#[cfg(any(test, debug_assertions))]
#[inline]
fn gravity_watt_from_alt_raw(mass_kg: f64, dh_m: f64, dt_s: f64) -> f64 {
    if dt_s <= 1e-6 {
        return 0.0;
    }
    let v_vert = dh_m / dt_s; // m/s opp (+) / ned (-)
    mass_kg * G * v_vert
}

/// Utdata fra kraftberegning med vind.
#[derive(Debug, Clone)]
pub struct PowerOutputs {
    pub power: Vec<f64>,
    pub wind_rel: Vec<f64>,
    pub v_rel: Vec<f64>,
}

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

    let mass = profile.total_weight.unwrap_or(75.0);
    let crr = profile.crr.unwrap_or(0.005);
    let cda = profile.cda.unwrap_or_else(|| cda_for(profile.bike_type.as_deref()));

    let alt = crate::smoothing::smooth_altitude(samples);

    let mut power_out = Vec::with_capacity(n);
    let mut wind_rel_out = Vec::with_capacity(n);
    let mut v_rel_out = Vec::with_capacity(n);

    for i in 0..n {
        let s = samples[i];

        let (dt, v_prev, alt_prev) = if i == 0 {
            (1.0, s.v_ms.max(0.0), alt[0])
        } else {
            let sp = samples[i - 1];
            (((s.t - sp.t).abs()).max(1e-3), sp.v_ms.max(0.0), alt[i - 1])
        };

        let v = s.v_ms.max(0.0);
        let v_mid = 0.5 * (v + v_prev);
        let a = (v - v_prev) / dt;

        let ds = (v_mid * dt).max(1e-3);
        let slope = if i == 0 { 0.0 } else { ((alt[i] - alt_prev) / ds).clamp(-0.3, 0.3) };

        let heading = if i + 1 < n { samples[i].heading_to(&samples[i + 1]) } else { None };
        let heading_deg = heading.unwrap_or(0.0);

        let wind_rel = weather.headwind_component(heading_deg);
        let v_rel = (v_mid - wind_rel).max(0.0);

        let p_roll = rolling_watt(crr, mass, v_mid);
        let p_aero = drag_watt(RHO, cda, v_rel);
        let p_grav = (mass * G * v_mid * slope).max(0.0);
        let p_acc = (mass * a * v_mid).max(0.0);

        let p = p_roll + p_aero + p_grav + p_acc;
        power_out.push(if p.is_finite() { p.max(0.0) } else { 0.0 });
        wind_rel_out.push(wind_rel);
        v_rel_out.push(v_rel);
    }

    PowerOutputs { power: power_out, wind_rel: wind_rel_out, v_rel: v_rel_out }
}

/// Bakoverkompatibel wrapper
pub fn compute_power(samples: &[Sample], profile: &Profile, weather: &Weather) -> Vec<f64> {
    compute_power_with_wind(samples, profile, weather).power
}

/// Indoor-beregning (pass-through av device_watts eller enkel modell)
pub fn compute_indoor_power(sample: &Sample, profile: &Profile) -> f64 {
    if let Some(watts) = sample.device_watts { return watts; }

    let v = sample.v_ms.max(0.0);
    let cda = profile.cda.unwrap_or_else(|| cda_for(profile.bike_type.as_deref()));
    let crr = profile.crr.unwrap_or(0.004);
    let mass = profile.total_weight.unwrap_or(75.0);

    let p_aero = drag_watt(RHO, cda, v);
    let p_roll = rolling_watt(crr, mass, v);
    (p_aero + p_roll).max(0.0)
}

/* -------------------------------------------------------------------------
   (Eksisterende) komponent-beregninger for tidsserier (drag/rolling/climb).
   ------------------------------------------------------------------------- */

#[derive(Debug, Clone)]
pub struct Components {
    pub total: Vec<f64>,
    pub drag: Vec<f64>,
    pub rolling: Vec<f64>,
}

fn gradient_from_alt(alt: &Vec<f64>, vel_len: usize, vel: &Vec<f64>) -> Vec<f64> {
    let n = vel_len.min(alt.len());
    if n == 0 { return Vec::new(); }
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
        let p_drag = drag_watt(rho, cda, v);
        let p_roll = crr * mass * G * v * (1.0 - 0.5 * grad[i] * grad[i]);
        let p_climb = (mass * G * v * grad[i]).max(0.0);
        let p = p_drag + p_roll + p_climb;

        drag.push(if p_drag.is_finite() { p_drag.max(0.0) } else { 0.0 });
        rolling.push(if p_roll.is_finite() { p_roll.max(0.0) } else { 0.0 });
        total.push(if p.is_finite() { p.max(0.0) } else { 0.0 });
    }

    Components { total, drag, rolling }
}

/* -------------------------------------------------------------------------
   DT-vektet gjennomsnitt (eksisterende API, renavnet for å unngå kollisjon)
   ------------------------------------------------------------------------- */

#[inline]
fn clamp(x: f64, lo: f64, hi: f64) -> f64 { x.max(lo).min(hi) }

#[derive(Debug, Clone, Copy, Default)]
pub struct PhysProfile {
    pub cda: f64,       // m^2
    pub crr: f64,       // -
    pub weight_kg: f64, // rytter+sykkel
}

/// Nye tweak-parametre for finjustering
#[derive(Debug, Clone, Copy, Default)]
pub struct PhysTweak {
    pub include_gravity: bool,
    pub drivetrain_eta: f64,
    pub alt_smooth_secs: f64,
    pub cd_a_scale: f64,
    pub crr_scale: f64,
}

/// Smooth en serie verdier med et glidende gjennomsnitt
pub fn smooth_series(values: &[f64], window: usize) -> Vec<f64> {
    if window <= 1 || values.len() < 3 {
        return values.to_vec();
    }

    // sørg for at vinduet er oddetall, slik at midtpunktet er veldefinert
    let w = if window % 2 == 0 { window + 1 } else { window };
    let k = w / 2;
    let mut out = vec![0.0; values.len()];

    for i in 0..values.len() {
        let a = i.saturating_sub(k);
        let b = (i + k + 1).min(values.len());
        let n = (b - a) as f64;

        let mut s = 0.0;
        for j in a..b {
            s += values[j];
        }
        out[i] = s / n;
    }

    out
}
/// 1) Fyll distance fra v*dt hvis distance mangler
pub fn fill_distance_if_missing(samples: &mut [Sample]) {
    let mut have_any = false;
    for s in samples.iter() {
        if s.distance_m.is_some() { have_any = true; break; }
    }
    if have_any || samples.is_empty() { return; }

    let mut dist = 0.0;
    for i in 0..samples.len() {
        let dt = if i == 0 { 0.0 } else { (samples[i].t - samples[i - 1].t).max(0.0) };
        dist += samples[i].v_ms.max(0.0) * dt;
        samples[i].distance_m = Some(dist);
    }
}

/// 2) Derivér/smooth grade fra altitude/dist med tid-basert smoothing
pub fn derive_or_smooth_grade(samples: &mut [Sample], alt_smooth_secs: f64) {
    if samples.len() < 3 { return; }

    // Beregn median dt
    let dt_med = {
        let mut dts = Vec::with_capacity(samples.len().saturating_sub(1));
        for w in samples.windows(2) {
            let dt = (w[1].t - w[0].t).max(0.0);
            if dt > 0.0 { dts.push(dt); }
        }
        if dts.is_empty() {
            1.0
        } else {
            let mid = dts.len() / 2;
            let mut tmp = dts.clone();
            tmp.sort_by(|a, b| a.partial_cmp(b).unwrap());
            tmp[mid]
        }
    };

    let window_n = ((alt_smooth_secs / dt_med).round() as usize).max(3);

    // Smooth altitude først
    let alt_raw: Vec<f64> = samples.iter().map(|s| s.altitude_m).collect();
    let alt_s = smooth_series(&alt_raw, window_n);

    let mut dists: Vec<f64> = Vec::with_capacity(samples.len());
    for s in samples.iter() { dists.push(s.distance_m.unwrap_or(0.0)); }

    let mut out: Vec<Option<f64>> = vec![None; samples.len()];
    let half = alt_smooth_secs * 0.5;

    for i in 0..samples.len() {
        if let Some(g) = samples[i].grade {
            out[i] = Some(g);
            continue;
        }
        let xi = dists[i];

        let mut j0 = i;
        while j0 > 0 && (xi - dists[j0]).abs() < half { j0 -= 1; }
        let mut j1 = i;
        while j1 + 1 < samples.len() && (dists[j1 + 1] - xi) < half { j1 += 1; }

        let start_alt = alt_s[j0];
        let end_alt   = alt_s[j1];
        let d_alt = end_alt - start_alt;
        let d_dist = (dists[j1] - dists[j0]).abs();

        let grade = if d_dist > 1e-6 { d_alt / d_dist } else { 0.0 };
        out[i] = Some(grade);
    }

    for i in 0..samples.len() {
        let v = samples[i].v_ms.max(0.0);
        let g = out[i].unwrap_or(0.0);
        let g = if v < 1.0 { 0.0 } else { clamp(g, -0.15, 0.15) };
        samples[i].grade = Some(g);
    }
}

/// DT-vektet gjennomsnittskraft (energi/T) – med tweak-parametre.
/// Renavnet fra `compute_metrics` for å unngå navnekollisjon.
pub fn compute_metrics_phys(samples: &[Sample], profile: PhysProfile, tweak: PhysTweak) -> Metrics {
    if samples.is_empty() {
        return Metrics::default();
    }

    let w    = profile.weight_kg;
    let cd_a = profile.cda * tweak.cd_a_scale;   // (snake_case)
    let crr  = profile.crr * tweak.crr_scale;

    let mut e_drag   = 0.0;
    let mut e_roll   = 0.0;
    let mut e_grav   = 0.0;
    let mut total_dt = 0.0;
    let mut active_dt= 0.0;

    // Beregn median dt
    let dt_med = {
        let mut dts = Vec::with_capacity(samples.len().saturating_sub(1));
        for w2 in samples.windows(2) {
            let dt = (w2[1].t - w2[0].t).max(0.0);
            if dt > 0.0 { dts.push(dt); }
        }
        if dts.is_empty() {
            1.0
        } else {
            let mid = dts.len() / 2;
            let mut tmp = dts.clone();
            tmp.sort_by(|a, b| a.partial_cmp(b).unwrap());
            tmp[mid]
        }
    };

    let window_n = ((tweak.alt_smooth_secs / dt_med).round() as usize).max(3);
    let alt_raw: Vec<f64> = samples.iter().map(|s| s.altitude_m).collect();
    let alt_s = smooth_series(&alt_raw, window_n);

    for i in 0..samples.len() {
        let s  = samples[i];
        let dt = if i == 0 { 0.0 } else { (s.t - samples[i - 1].t).max(0.0) };
        if dt <= 0.0 { continue; }

        let v = s.v_ms.max(0.0);

        // Beregn grade fra smooth altitude med sikkerhetsgrenser
        let min_dt = MIN_DT_S;
        let min_v  = MIN_V_MS;
        let g = if i > 0 && dt >= min_dt && v >= min_v {
            let dh   = alt_s[i] - alt_s[i - 1];
            let dhdt = dh / dt;
            let grade = if v > 0.0 { dhdt / v } else { 0.0 };
            clamp(grade, -0.15, 0.15)
        } else {
            0.0
        };

        let cos_theta = (1.0 + g * g).powf(-0.5);
        let sin_theta = g * cos_theta;

        // NB: bruker RHO-konstanten
        let p_drag = 0.5 * RHO * cd_a * v * v * v;
        let p_roll = crr * w * G * v * cos_theta;
        let p_grav = if tweak.include_gravity { w * G * v * sin_theta } else { 0.0 };

        // Tidsvektet aggregering med aktivitetsfilter
        total_dt += dt;
        if dt >= MIN_DT_S && v >= MIN_V_MS {
            active_dt += dt;
            e_drag  += p_drag * dt;
            e_roll  += p_roll * dt;
            e_grav  += p_grav * dt; // kan være negativ (summeres algebraisk)
        }
    }

    // Snitt over AKTIV tid
    let d_avg = if active_dt > 0.0 { e_drag / active_dt } else { 0.0 };
    let r_avg = if active_dt > 0.0 { e_roll / active_dt } else { 0.0 };
    let g_avg = if active_dt > 0.0 { e_grav / active_dt } else { 0.0 };

    // Beregn precision med drivetrain efficiency
    let base_power     = d_avg + r_avg + g_avg;
    let precision_watt = if tweak.drivetrain_eta > 0.0 {
        base_power / tweak.drivetrain_eta
    } else {
        base_power
    };

    let _active_ratio = if total_dt > 0.0 { active_dt / total_dt } else { 0.0 };

    Metrics {
        drag_watt: d_avg,
        rolling_watt: r_avg,
        gravity_watt: g_avg,
        precision_watt,
    }
}

/// Hjelpefunksjon for å beregne kraftkomponenter per sample (for timeserie)
pub fn compute_metrics_for_sample(
    sample: &Sample,
    profile: PhysProfile,
    tweak: PhysTweak,
) -> (f64, f64, f64, f64) {
    let v = sample.v_ms.max(0.0);
    let g = sample.grade.unwrap_or(0.0);

    let cd_a = profile.cda * tweak.cd_a_scale;
    let crr  = profile.crr * tweak.crr_scale;

    let cos_theta = (1.0 + g * g).powf(-0.5);
    let sin_theta = g * cos_theta;

    // Bruk cd_a her i stedet for cdA
    let drag_watt     = 0.5 * RHO * cd_a * v * v * v;
    let rolling_watt  = crr * profile.weight_kg * G * v * cos_theta;
    let gravity_watt  = if tweak.include_gravity {
        profile.weight_kg * G * v * sin_theta
    } else {
        0.0
    };

    let base_power     = drag_watt + rolling_watt + gravity_watt;
    let precision_watt = if tweak.drivetrain_eta > 0.0 {
        base_power / tweak.drivetrain_eta
    } else {
        base_power
    };

    (drag_watt, rolling_watt, gravity_watt, precision_watt)
}

// MetricsSeries struct og implementasjon (hvis den ikke allerede eksisterer)
#[derive(Debug, Clone, Default)]
pub struct MetricsSeries {
    pub d_avg: f64,
    pub r_avg: f64,
    pub g_avg: f64,
    pub total_dt: f64,
    pub active_dt: f64,
}

impl MetricsSeries {
    #[inline] pub fn drag_watt(&self)    -> f64 { self.d_avg }
    #[inline] pub fn rolling_watt(&self) -> f64 { self.r_avg }
    #[inline] pub fn gravity_watt(&self) -> f64 { self.g_avg }
    #[inline] pub fn active_ratio(&self) -> f64 {
        if self.total_dt > 0.0 { self.active_dt / self.total_dt } else { 0.0 }
    }
}

/* -------------------------------------------------------------------------
   PATCH A+B+C — ny per-sample pipeline: required gravity + drivetrain eta
   ------------------------------------------------------------------------- */

/// Per-sample metrics (drag, rolling, gravity(required), precision) → public `Metrics`.
pub fn compute_metrics_for_series(
    samples: &[Sample],
    profile: &Profile,
    rho: f64,
) -> Vec<Metrics> {
    let mut out = Vec::with_capacity(samples.len());
    if samples.is_empty() {
        return out;
    }

    // Profildata med trygge defaults
    let eta = ETA_DEFAULT;   // crank→hjul effektivitet
    let cda  = profile.cda.unwrap_or_else(|| cda_for(profile.bike_type.as_deref()));
    let crr  = profile.crr.unwrap_or(0.005);
    let mass = profile.total_weight.unwrap_or(75.0);

    // første sample: 0 vertikalhastighet
    let mut prev_alt = samples[0].altitude_m;
    let mut prev_t   = samples[0].t;

    for (i, s) in samples.iter().enumerate() {
        let v = s.v_ms.max(0.0);

        // hopp over stillstand/lav fart for mer robuste tall
        if v < MIN_V_MS {
            // push et "null-sample" for å bevare indeks hvis ønskelig
            out.push(Metrics {
                drag_watt: 0.0,
                rolling_watt: 0.0,
                gravity_watt: 0.0,
                precision_watt: 0.0,
               });
            prev_alt = s.altitude_m;
            prev_t   = s.t;
            continue;
        }

        // tidssteg og høydeendring
        let (dh, dt) = if i == 0 {
            (0.0, 0.0)
        } else {
            (s.altitude_m - prev_alt, s.t - prev_t)
        };
        let dt = dt.max(MIN_DT_S);

        // dersom grade finnes, bruk den til å estimere dh (mindre støy enn rå alt)
        let dh_by_grade = s.grade.map(|g| (v * dt) * g);
        let dh_effective = dh_by_grade.unwrap_or(dh);

        // komponenter (wheel-side)
        let w_drag = 0.5 * rho * cda * v * v * v;
        let w_roll = crr * mass * G * v;

        // rå gravitasjon (kan være ±)
        let w_grav_raw = mass * G * (dh_effective / dt);

        // required gravitasjon: kun oppover bidrar
        let w_gravity_req = w_grav_raw.max(0.0);

        // summering wheel-side og over til crank-side via eta
        let w_total_wheel    = w_drag + w_roll + w_gravity_req;
        let w_precision_crank = if eta > 0.0 { w_total_wheel / eta } else { w_total_wheel };

        out.push(Metrics {
            drag_watt:      if w_drag.is_finite() { w_drag.max(0.0) } else { 0.0 },
            rolling_watt:   if w_roll.is_finite() { w_roll.max(0.0) } else { 0.0 },
            gravity_watt:   if w_gravity_req.is_finite() { w_gravity_req.max(0.0) } else { 0.0 },
            precision_watt: if w_precision_crank.is_finite() { w_precision_crank.max(0.0) } else { 0.0 },
        });

        prev_alt = s.altitude_m;
        prev_t   = s.t;
    }

    out
}

/// Tynn wrapper: bruk modulens standard RHO
pub fn compute_metrics(samples: &[Sample], profile: Profile) -> Vec<Metrics> {
    compute_metrics_for_series(samples, &profile, RHO)
}
