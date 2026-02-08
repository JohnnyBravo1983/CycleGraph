// In release builds we deny(warnings) at crate level. This module contains
// tolerant parsers and helpers that may be intentionally unused during
// incremental integration. Allow them in release to avoid breaking the build.
#![cfg_attr(
    not(debug_assertions),
    allow(dead_code, unused_imports, unused_variables, unused_mut, unused_macros)
)]

use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::wrap_pyfunction;

use serde::de::IntoDeserializer; // for Value::into_deserializer()
use serde::Deserialize;
use serde_json::{self as json, Map as JsonMap, Value};
use serde_path_to_error as spte;

use crate::Sample;
use crate::Weather as CoreWeather; // Added import for Sample type

// ──────────────────────────────────────────────────────────────────────────────
// Konstanter for fysikk
// ──────────────────────────────────────────────────────────────────────────────
const G: f64 = 9.80665;
const RHO_DEFAULT: f64 = 1.225;
const WIND_EFFECT: f64 = 0.55; // Hvor mye av modellen-vinden som faktisk "treffer" rytteren

// ──────────────────────────────────────────────────────────────────────────────
// Build-konstant for å verifisere at riktig Rust kjører
// ──────────────────────────────────────────────────────────────────────────────
const CG_BUILD: &str = "T15-cg_build-20251216";

// ──────────────────────────────────────────────────────────────────────────────
// INPUT-REPR (untagged): PRØV OBJECT FØRST, SÅ LEGACY (TRIPLE)
// ──────────────────────────────────────────────────────────────────────────────

// TRIPLE/legacy form: [samples, profile, estimat?]
#[derive(Debug, Deserialize)]
struct ComputePowerLegacy(
    Vec<crate::Sample>,
    crate::Profile,
    #[serde(default)] Value, // estimat (optional)
);

// Tolerant profil-inngang
#[derive(Debug, Deserialize, Clone)]
struct ProfileInTol {
    #[serde(default, alias = "CdA", alias = "cda")]
    cda: Option<f64>,
    #[serde(default, alias = "Crr", alias = "crr")]
    crr: Option<f64>,
    #[serde(default, alias = "weightKg", alias = "weight_kg")]
    weight_kg: Option<f64>,

    // Additiv: drivetrain / crank efficiency i prosent (0-100)
    // Aliaser for å tåle ulike klientnavn
    #[serde(
        default,
        alias = "crank_eff_pct",
        alias = "crank_efficiency",
        alias = "crank_eff"
    )]
    crank_eff_pct: Option<f64>,

    #[serde(default)]
    device: String,
    #[serde(default)]
    calibrated: bool,

    // Viktig – aksepter valgfritt estimat i profile-inngangen
    #[serde(default)]
    #[allow(dead_code)] // feltet aksepteres fra JSON men brukes ikke direkte her
    estimat: Option<Value>,
}

// OBJECT v3: { samples (tolerant), profile (tolerant), weather?, estimat? }
#[derive(Debug, Deserialize, Clone)]
struct ComputePowerObjectV3 {
    // Viktig: tolerant samples → konverteres til kjerne før kall
    samples: Vec<SampleInTol>,
    profile: ProfileInTol,

    #[serde(default)]
    weather: Option<crate::Weather>,

    #[serde(default)]
    #[serde(alias = "estimate")]
    estimat: serde_json::Value,
}

// Prøv OBJECT først, deretter Legacy
#[derive(Debug, Deserialize)]
#[serde(untagged)]
enum ComputePowerIn {
    Object(ComputePowerObjectV3),
    Legacy(ComputePowerLegacy),
}

// ──────────────────────────────────────────────────────────────────────────────
// TOLERANT FALLBACK-PARSER (for eldre/avvikende feltnavn)
// ──────────────────────────────────────────────────────────────────────────────

#[derive(Debug, Deserialize, Clone)]
struct SampleInTol {
    t: f64,
    #[serde(alias = "v_mps", alias = "v")]
    v_ms: f64,
    #[serde(alias = "alt", alias = "elev")]
    altitude_m: f64,
    #[serde(default)]
    heading_deg: f64,
    #[serde(default)]
    moving: bool,
    #[serde(default)]
    rho: f64,
    // Normaliser vind: aksepter wind_ms / wind_speed
    #[serde(default, alias = "wind_ms", alias = "wind_speed")]
    wind_speed: f64,
    #[serde(default)]
    wind_dir_deg: f64,
    #[serde(default)]
    air_temp_c: f64,
    // aksepter air_pressure_hpa alias som pressure_hpa
    #[serde(default, alias = "air_pressure_hpa")]
    pressure_hpa: f64,
    #[serde(default)]
    humidity: f64,

    // Målt effekt — aliaser for legacy klienter
    #[serde(default)]
    #[serde(alias = "watts")]
    #[serde(alias = "power")]
    #[serde(alias = "power_w")]
    device_watts: Option<f64>,
}

#[derive(Debug, Deserialize)]
struct ObjectTol {
    #[serde(default)]
    samples: Vec<SampleInTol>,
    profile: ProfileInTol,

    // tillat at klient har brukt estimat/estimate på toppnivå (vi ignorerer her)
    #[serde(default, alias = "estimat", alias = "estimate")]
    _ignore_estimat: Option<Value>,

    #[serde(flatten)]
    _extra: Option<Value>,
}

// Hjelper for triple-varianten i tolerant parser
#[derive(Debug, Deserialize)]
struct TripleTol(Vec<SampleInTol>, ProfileInTol, #[serde(default)] Value);

#[derive(Debug, Deserialize)]
#[serde(untagged)]
enum InReprTol {
    Triple(TripleTol),
    Object(ObjectTol),
}

// ──────────────────────────────────────────────────────────────────────────────
// KONVERTERINGER (tolerant → kjerne-typer)
// ──────────────────────────────────────────────────────────────────────────────

fn to_core_profile_tol(p: ProfileInTol, estimat_present: bool) -> Result<crate::Profile, String> {
    let mut m = JsonMap::new();

    // Sett verdier eller Null hvis None
    m.insert(
        "cda".into(),
        match p.cda {
            Some(x) => Value::from(x),
            None => Value::Null,
        },
    );
    m.insert(
        "crr".into(),
        match p.crr {
            Some(x) => Value::from(x),
            None => Value::Null,
        },
    );
    m.insert(
        "weight_kg".into(),
        match p.weight_kg {
            Some(x) => Value::from(x),
            None => Value::Null,
        },
    );

    // Additiv: speil inn crank_eff_pct i core-profil-json hvis klient sendte det
    // (core kan ignorere, men vi bevarer feltet i pipeline)
    m.insert(
        "crank_eff_pct".into(),
        match p.crank_eff_pct {
            Some(x) => Value::from(x),
            None => Value::Null,
        },
    );

    m.insert("device".into(), Value::from(p.device));
    m.insert("calibrated".into(), Value::from(p.calibrated));

    // Repeter til kjerneprofilen: et boolsk hint om estimat-tilstedeværelse
    m.insert("estimat".into(), Value::from(estimat_present));

    // valgfrie mulige kjernefelt
    if !m.contains_key("total_weight") {
        m.insert("total_weight".into(), Value::Null);
    }
    if !m.contains_key("bike_type") {
        m.insert("bike_type".into(), Value::Null);
    }
    if !m.contains_key("calibration_mae") {
        m.insert("calibration_mae".into(), Value::Null);
    }

    let txt = Value::Object(m).to_string();
    let mut de = json::Deserializer::from_str(&txt);
    spte::deserialize(&mut de).map_err(|e| format!("profile parse at {}: {}", e.path(), e))
}

fn to_core_sample_tol(s: SampleInTol) -> Result<crate::Sample, String> {
    let mut m = JsonMap::new();
    m.insert("t".into(), Value::from(s.t));
    m.insert("v_ms".into(), Value::from(s.v_ms));
    m.insert("altitude_m".into(), Value::from(s.altitude_m));
    m.insert("heading_deg".into(), Value::from(s.heading_deg));
    m.insert("moving".into(), Value::from(s.moving));
    m.insert("rho".into(), Value::from(s.rho));
    m.insert("wind_ms".into(), Value::from(s.wind_speed));
    m.insert("wind_dir_deg".into(), Value::from(s.wind_dir_deg));
    m.insert("air_temp_c".into(), Value::from(s.air_temp_c));
    m.insert("air_pressure_hpa".into(), Value::from(s.pressure_hpa));
    m.insert("humidity".into(), Value::from(s.humidity));

    // Viderefør målt effekt til kjernefeltet device_watts (Null hvis None)
    match s.device_watts {
        Some(w) => {
            m.insert("device_watts".into(), Value::from(w));
        }
        None => {
            m.insert("device_watts".into(), Value::Null);
        }
    }

    let txt = Value::Object(m).to_string();
    let mut de = json::Deserializer::from_str(&txt);
    spte::deserialize(&mut de).map_err(|e| format!("sample parse at {}: {}", e.path(), e))
}

// ──────────────────────────────────────────────────────────────────────────────
// HJELPERE
// ──────────────────────────────────────────────────────────────────────────────

fn neutral_weather() -> CoreWeather {
    CoreWeather {
        wind_ms: 0.0,
        wind_dir_deg: 0.0,
        air_temp_c: 0.0,
        air_pressure_hpa: 0.0,
    }
}

fn with_debug(mut out_json: String, extra: &JsonMap<String, Value>) -> String {
    if let Ok(mut v) = serde_json::from_str::<Value>(&out_json) {
        if let Value::Object(ref mut obj) = v {
            obj.entry("source")
                .or_insert_with(|| Value::from("rust_binding"));
            let dbg = obj
                .entry("debug")
                .or_insert_with(|| Value::Object(JsonMap::new()));
            if let Value::Object(ref mut dbg_map) = dbg {
                for (k, val) in extra.iter() {
                    dbg_map.insert(k.clone(), val.clone());
                }
            } else {
                obj.insert("debug".into(), Value::Object(extra.clone()));
            }
            if let Ok(s) = serde_json::to_string(&v) {
                out_json = s;
            }
        }
    }
    out_json
}

// Sørger for metrics-blokk + toppnivåfelt dersom kjerne svarer "flatt"
fn ensure_metrics_shape(mut out_json: String) -> String {
    if let Ok(mut v) = serde_json::from_str::<Value>(&out_json) {
        if let Value::Object(ref mut obj) = v {
            if !obj.contains_key("metrics") {
                let mut m = JsonMap::new();
                for k in ["precision_watt", "drag_watt", "rolling_watt", "total_watt"].iter() {
                    if let Some(val) = obj.remove(*k) {
                        m.insert((*k).into(), val);
                    }
                }
                if !m.is_empty() {
                    obj.insert("metrics".into(), Value::Object(m));
                }
            }
            obj.entry("source").or_insert(Value::from("rust_1arg"));
            obj.entry("weather_applied").or_insert(Value::from(false));
            if let Ok(s) = serde_json::to_string(&v) {
                out_json = s;
            }
        }
    }
    out_json
}

// ──────────────────────────────────────────────────────────────────────────────
// STEG 1 (A): Skalar-metrics og diagnostikk-arrays (vind av)
// ──────────────────────────────────────────────────────────────────────────────

fn mean(xs: &[f64]) -> f64 {
    if xs.is_empty() {
        0.0
    } else {
        xs.iter().copied().sum::<f64>() / (xs.len() as f64)
    }
}

// Time-weighted mean for skalarer - konsekvent bruk i compute_scalar_metrics
fn tw_mean_f64(power: &[f64], samples: &Vec<crate::Sample>) -> f64 {
    if power.is_empty() || samples.is_empty() || power.len() != samples.len() {
        return 0.0;
    }
    let mut sum = 0.0f64;
    let mut tsum = 0.0f64;
    for i in 0..samples.len() {
        let t_cur = samples[i].t;
        let t_prev = if i > 0 { samples[i - 1].t } else { t_cur };
        let dt = (t_cur - t_prev).max(0.0);
        if dt > 0.0 {
            sum += power[i] * dt;
            tsum += dt;
        }
    }
    if tsum > 0.0 { sum / tsum } else { 0.0 }
}

// Time-weighted mean, men bare for perioder hvor rytteren beveger seg (moving==true)
fn tw_mean_f64_moving_only(values: &Vec<f64>, samples: &Vec<crate::Sample>) -> f64 {
    if values.is_empty() || samples.is_empty() {
        return 0.0;
    }

    let mut sum = 0.0_f64;
    let mut wsum = 0.0_f64;

    let n = values.len().min(samples.len());
    for i in 0..n {
        let s = &samples[i];

        // samme moving-def som i loop
        let moving = s.moving && s.v_ms.is_finite() && s.v_ms > 0.5;
        if !moving {
            continue;
        }

        // dt fra t-serien (fallback 1s)
        let dt = if i == 0 {
            1.0
        } else {
            let prev_t = samples[i - 1].t;
            let this_t = s.t;
            let d = (this_t - prev_t).max(0.01);
            if d.is_finite() { d } else { 1.0 }
        };

        let v = values[i];
        if v.is_finite() {
            sum += v * dt;
            wsum += dt;
        }
    }

    if wsum > 0.0 { sum / wsum } else { 0.0 }
}

fn clamp_eff_pct_from_profile_tol(p: &ProfileInTol) -> f64 {
    // prefer pct, fallback 95.5
    let raw = p.crank_eff_pct.unwrap_or(95.5);

    // Hvis noen sender ratio (0.96), normaliser til prosent
    let pct = if raw <= 1.5 { raw * 100.0 } else { raw };

    // clamp pct til [50, 100]
    pct.clamp(50.0, 100.0)
}

/// Fallback/beriking: regn skalarer når core ikke leverer alt.
/// Nå med vær slik at drag bruker relativ luftfart (v_air^3) basert på langs-komponent modell.
///
/// Return:
/// (w_drag, w_roll, w_grav, w_model, drag_watt, rolling_watt, gravity_watt, precision_watt, total_watt,
///  avg_grav_pedal, avg_model_pedal, precision_watt_pedal)
fn compute_scalar_metrics(
    samples: &Vec<crate::Sample>,
    profile: &ProfileInTol,
    weather: &CoreWeather,
) -> (
    Vec<f64>,
    Vec<f64>,
    Vec<f64>,
    Vec<f64>,
    f64,
    f64,
    f64,
    f64,
    f64,
    f64,
    f64,
    f64,
    f64,
    f64,
    f64,
) {
    let cda = profile.cda.unwrap_or(0.30);
    let crr = profile.crr.unwrap_or(0.004);
    let weight = profile.weight_kg.unwrap_or(85.0);

    // NB: vi bruker fortsatt RHO_DEFAULT her som før (evt. kan du bytte til weather-ρ senere)
    let rho = RHO_DEFAULT;

    let n = samples.len();
    let mut w_drag: Vec<f64> = Vec::with_capacity(n);
    let mut w_roll: Vec<f64> = Vec::with_capacity(n);
    let mut w_grav: Vec<f64> = Vec::with_capacity(n);
    let mut w_model: Vec<f64> = Vec::with_capacity(n);

    // PATCH: additive "pedal" vectors
    let mut w_grav_pedal: Vec<f64> = Vec::with_capacity(n);
    let mut w_model_pedal: Vec<f64> = Vec::with_capacity(n);

    let mut device_watts: Vec<f64> = Vec::new();

    // ───────────────────────────────────────────────
    // 1) Precompute dt-serie og gravity per sample fra SMOOTHED altitude + dt
    //    Bruk smooth_altitude for å redusere GPS-jitter/drift
    // ───────────────────────────────────────────────
    let altitude_series = crate::smoothing::smooth_altitude(samples);
    let mut dt_series: Vec<f64> = Vec::with_capacity(n);

    for (i, s) in samples.iter().enumerate() {
        // dt: differanse i tid mellom samples (sekunder)
        let dt = if i == 0 {
            1.0
        } else {
            let prev_t = samples[i - 1].t;
            let this_t = s.t;
            let d = (this_t - prev_t).max(0.01);
            if d.is_finite() { d } else { 1.0 }
        };

        dt_series.push(dt);
    }

    // Bruk din physics.rs (Sprint 14.7) gravity-funksjon med smoothed altitude
    let grav_vec = crate::physics::compute_gravity_component(weight, &altitude_series, &dt_series);

    // ───────────────────────────────────────────────
    // 2) Vind: wind_dir_deg er "fra"; konverter til "til"
    // ───────────────────────────────────────────────
    let wind_ms = weather.wind_ms.max(0.0);
    let wind_from_deg = weather.wind_dir_deg % 360.0;
    let wind_to_deg = (wind_from_deg + 180.0) % 360.0;

    // ───────────────────────────────────────────────
    // 3) Per-sample watt-komponenter
    // ───────────────────────────────────────────────
    for (i, s) in samples.iter().enumerate() {
        let v = s.v_ms.max(0.0);

        // Relativ vinkel mellom sykkel-heading og vindens "til"-retning
        // NB: normaliser til [-180,180] for stabilitet rundt 0/360 wrap.
        let mut d = (wind_to_deg - s.heading_deg) % 360.0;
        if d < -180.0 { d += 360.0; }
        if d > 180.0 { d -= 360.0; }
        let delta_rad = d.to_radians();

        // Vind langs bevegelsesretning (+ = tailwind, - = headwind)
        let wind_along = wind_ms * delta_rad.cos();
        
        // Reduser vindens effekt med WIND_EFFECT faktor for reliability
        let wind_along_eff = wind_along * WIND_EFFECT;

        // Bruk kun langs-komponent for relativ luftfart (stabil, realistisk for road-bikes uten yaw-modell)
        let v_air = (v - wind_along_eff).max(0.0);

        // Aerodynamisk drag ~ v_air^3
        let w_d = 0.5 * rho * cda * v_air.powi(3);

        // Rullemotstand
        let w_r = crr * weight * G * v;

        // Gravity per sample fra smoothed altitude+dt (kan være negativ ved nedover)
        let raw_g = *grav_vec.get(i).unwrap_or(&0.0);

        // Hvis vi ikke beveger oss: sett gravity=0 for å unngå alt-jitter -> fake dh/dt power.
        // (moving-flagget + en liten v-threshold som ekstra sikkerhet)
        let moving = s.moving && s.v_ms.is_finite() && s.v_ms > 0.5;
        let w_g = if moving { raw_g } else { 0.0 };

        // Modellert total (signert grav)
        let w_m = w_d + w_r + w_g;

        w_drag.push(w_d);
        w_roll.push(w_r);
        w_grav.push(w_g);
        w_model.push(w_m);

        // PATCH: pedal-gravity og pedal-model på hjul (negativ grav klippes til 0)
        let w_g_pedal = if w_g > 0.0 { w_g } else { 0.0 };
        w_grav_pedal.push(w_g_pedal);

        let w_pedal = w_d + w_r + w_g_pedal;
        w_model_pedal.push(w_pedal);
    }

    // ───────────────────────────────────────────────
    // 4) Scalar (time-weighted mean) metrics (PATCH G1)
    // ───────────────────────────────────────────────
    let drag_watt = tw_mean_f64(&w_drag, samples);
    let rolling_watt = tw_mean_f64(&w_roll, samples);
    let gravity_watt = tw_mean_f64(&w_grav, samples);

    // eksisterende "precision" fallback (wheel, signert grav)
    let precision_watt = drag_watt + rolling_watt + gravity_watt;

    let total_watt = precision_watt; // Bruk modell når vi ikke har device_watts

    // ───────────────────────────────────────────────
    // 5) PATCH C2: elapsed vs moving averages (time-weighted) for pedal model
    // ───────────────────────────────────────────────
    let avg_grav_pedal = tw_mean_f64_moving_only(&w_grav_pedal, samples);
    
    // Beregn BÅDE elapsed og moving for pedal-model
    let avg_model_pedal_elapsed = tw_mean_f64(&w_model_pedal, samples);
    let avg_model_pedal_moving = tw_mean_f64_moving_only(&w_model_pedal, samples);
    
    // Ratio for debug
    let pedal_ratio_elapsed_over_moving = if avg_model_pedal_moving > 0.0 {
        avg_model_pedal_elapsed / avg_model_pedal_moving
    } else {
        0.0
    };

    let crank_eff_pct = clamp_eff_pct_from_profile_tol(profile);
    let eff = (crank_eff_pct / 100.0).clamp(0.50, 1.0);
    let precision_watt_pedal = if eff > 0.0 { avg_model_pedal_moving / eff } else { 0.0 };

    (
        w_drag,
        w_roll,
        w_grav,
        w_model,
        drag_watt,
        rolling_watt,
        gravity_watt,
        precision_watt,
        total_watt,
        avg_grav_pedal,
        avg_model_pedal_moving, // bruk moving for eksisterende bruk
        precision_watt_pedal,
        avg_model_pedal_elapsed, // ny: for debug
        avg_model_pedal_moving,  // ny: for debug (samme som over)
        pedal_ratio_elapsed_over_moving, // ny: ratio for debug
    )
}

// UI-definisjon:
// - metrics.precision_watt_avg   = wheel (rå fysikk)
// - metrics.precision_watt_pedal = hovedverdi for bruker
// - metrics.precision_watt_crank = avansert (wheel / eff)
// - resp.precision_watt_avg      = pedal (brukes i UI)
// Ingen fysikk endres her – kun mapping.

fn compute_device_watts_avg(samples: &Vec<crate::Sample>) -> (Option<f64>, &'static str, usize) {
    // --- core_watts_avg: ONLY from device_watts (powermeter) ---
    let mut core_n: usize = 0;
    let mut device: Vec<f64> = Vec::new();

    for s in samples.iter() {
        if let Some(w) = s.device_watts {
            // ignore zeros / bogus
            if w.is_finite() && w > 0.0 {
                device.push(w);
                core_n += 1;
            }
        }
    }

    // If we have device watts, report them. If not, that's fine — model still runs elsewhere.
    let (core_watts_avg, core_watts_source) = if !device.is_empty() {
        (Some(mean(&device)), "device_watts")
    } else {
        (None, "no_powermeter")
    };

    // Debug logging for å bevise at device_watts faktisk finnes
    println!(
        "[CORE] core_watts_avg={:?} source={} n_device={} total_samples={}",
        core_watts_avg,
        core_watts_source,
        core_n,
        samples.len()
    );

    (core_watts_avg, core_watts_source, core_n)
}

fn enrich_metrics_on_object(
    mut resp: serde_json::Value,
    samples: &Vec<crate::Sample>,
    profile: &ProfileInTol,
    repr_kind: &str,
    weather: &CoreWeather,
) -> serde_json::Value {
    use serde_json::{json, Value};

    // helper for drivetrain efficiency (crank_eff_pct) from profile_used map
    fn clamp_eff_from_profile(profile_used: &serde_json::Map<String, Value>) -> f64 {
        // Prefer crank_eff_pct (0–100). Fallback til 95.5 hvis mangler.
        let eff_pct = profile_used
            .get("crank_eff_pct")
            .and_then(|v| v.as_f64())
            .unwrap_or(95.5);

        let eff = eff_pct / 100.0;

        // Robust clamp: vi nekter ekstremverdier som kan sprenge watt
        eff.clamp(0.50, 1.0)
    }

    // Time-weighted mean fra samples[].t
    fn tw_mean(power: &[f64], samples: &Vec<crate::Sample>) -> Option<f64> {
        if power.is_empty() || samples.is_empty() || power.len() != samples.len() {
            return None;
        }
        let mut sum = 0.0f64;
        let mut tsum = 0.0f64;
        for i in 0..samples.len() {
            let t_cur = samples[i].t;
            let t_prev = if i > 0 { samples[i - 1].t } else { t_cur };
            let dt = (t_cur - t_prev).max(0.0);
            if dt > 0.0 {
                sum += power[i] * dt;
                tsum += dt;
            }
        }
        if tsum > 0.0 { Some(sum / tsum) } else { None }
    }

    // 1) Skalarer (fallback når core-power mangler).
    // Bruk faktisk vær om repr_kind tilsier objekt-vær, ellers nøytral.
    let neutral = neutral_weather();
    let wx_for_scalar = if repr_kind == "object" { weather } else { &neutral };

    // ─────────────────────────────────────────────────────────────────────────
    // PATCH 2: Prefer authoritative profile from resp["profile_used"] (core output)
    // ─────────────────────────────────────────────────────────────────────────
    let mut prof_for_scalar = profile.clone();

    if let Some(obj) = resp.as_object() {
        if let Some(pu) = obj.get("profile_used").and_then(|v| v.as_object()) {
            if prof_for_scalar.weight_kg.is_none() {
                prof_for_scalar.weight_kg = pu.get("weight_kg").and_then(|v| v.as_f64());
            }
            if prof_for_scalar.cda.is_none() {
                prof_for_scalar.cda = pu.get("cda").and_then(|v| v.as_f64());
            }
            if prof_for_scalar.crr.is_none() {
                prof_for_scalar.crr = pu.get("crr").and_then(|v| v.as_f64());
            }
            if prof_for_scalar.crank_eff_pct.is_none() {
                prof_for_scalar.crank_eff_pct =
                    pu.get("crank_eff_pct").and_then(|v| v.as_f64());
            }
        }
    }

    let (
        _w_drag,
        _w_roll,
        _w_grav,
        _w_model,
        drag_watt,
        rolling_watt,
        gravity_watt_scalar,
        _precision_watt_fb,
        _total_watt_fb,
        avg_grav_pedal,
        avg_model_pedal_moving, // NOTE: bruker moving-versionen her
        precision_watt_pedal,
        avg_model_pedal_elapsed, // PATCH C2: elapsed version
        _avg_model_pedal_moving_debug, // PATCH C2: moving (samme som ovenfor)
        pedal_ratio_elapsed_over_moving, // PATCH C2: ratio
    ) = compute_scalar_metrics(samples, &prof_for_scalar, wx_for_scalar);

    // 2) core_watts_avg: KUN fra device_watts i samples (powermeter)
    // PATCH 1+2: Få tuple med 3 verdier og force-disable
    let (core_watts_avg, core_watts_source, core_n) = compute_device_watts_avg(samples);

    // 3) IKKE backsolve gravity. Bruk scalar gravity fra smoothed altitude+dt.
    let gravity_watt = gravity_watt_scalar;

    // 4) Merge inn i resp
    if let Some(obj) = resp.as_object_mut() {
        match obj.get_mut("metrics") {
            Some(mv) if mv.is_object() => {
                let m = mv.as_object_mut().unwrap();

                // build-stempel for å bekrefte at riktig Rust kjører
                m.insert("cg_build".into(), json!(CG_BUILD));

                // components (fallback hvis core ikke leverer)
                m.entry("drag_watt").or_insert(json!(drag_watt));
                m.entry("rolling_watt").or_insert(json!(rolling_watt));
                m.entry("gravity_watt").or_insert(json!(gravity_watt));

                // wheel model (bruk gravity som faktisk ligger i metrics hvis satt)
                let gravity_used = m
                    .get("gravity_watt")
                    .and_then(|v| v.as_f64())
                    .unwrap_or(gravity_watt);

                let model_watt_wheel = drag_watt + rolling_watt + gravity_used;
                m.insert("model_watt_wheel".into(), json!(model_watt_wheel));

                // profile_used (for eff)
                let mut prof = serde_json::Map::new();
                if let Some(v) = profile.cda {
                    prof.insert("cda".into(), json!(v));
                }
                if let Some(v) = profile.crr {
                    prof.insert("crr".into(), json!(v));
                }
                if let Some(v) = profile.weight_kg {
                    prof.insert("weight_kg".into(), json!(v));
                }
                if let Some(v) = profile.crank_eff_pct {
                    prof.insert("crank_eff_pct".into(), json!(v));
                }
                prof.insert("calibrated".into(), json!(profile.calibrated));

                // NB: ikke overskriv hvis core allerede har komplett profile_used
                let prof_used_val = m.entry("profile_used").or_insert(Value::Object(prof));
                let eff = prof_used_val
                    .as_object()
                    .map(clamp_eff_from_profile)
                    .unwrap_or(0.955);

                // total_watt: PATCH 3: Bruk alltid wheel model når vi ikke har powermeter
                // IKKE bruk core_watts_avg da den alltid er None
                let total_watt_ui = model_watt_wheel;
                m.insert("total_watt".into(), json!(total_watt_ui));

                // diagnose / transparens
                m.insert("precision_watt_crank".into(), json!(model_watt_wheel / eff));
                m.insert("eff_used".into(), json!(eff));
                m.insert("model_watt_crank".into(), json!(model_watt_wheel / eff));

                // wind_effect faktor i debug info
                m.insert("wind_effect".into(), json!(WIND_EFFECT));

                // PATCH 3: core_watts_avg KUN fra device_watts - sett kun hvis vi har data
                // PATCH 2: core_watts_avg er alltid None, så vi setter ikke denne
                m.insert("core_watts_source".into(), json!(core_watts_source));
                m.insert("core_n_device_samples".into(), json!(core_n));
                // PATCH 3: Ikke sett "core_watts_avg" i JSON hvis den er None
                // Dette sikrer at with_has_core_key=False i testene

                // pedal (positive-only) behold
                m.insert("gravity_watt_pedal".into(), json!(avg_grav_pedal));
                m.insert("model_watt_wheel_pedal".into(), json!(avg_model_pedal_moving));
                m.insert("total_watt_pedal".into(), json!(avg_model_pedal_moving));
                m.insert("precision_watt_pedal".into(), json!(precision_watt_pedal));
                
                // PATCH C2: Legg til debug-felt for elapsed vs moving
                m.insert("model_watt_wheel_pedal_elapsed".into(), json!(avg_model_pedal_elapsed));
                m.insert("model_watt_wheel_pedal_moving".into(), json!(avg_model_pedal_moving));
                m.insert("pedal_ratio_elapsed_over_moving".into(), json!(pedal_ratio_elapsed_over_moving));
            }
            _ => {
                // Opprett metrics-blokk
                let model_watt_wheel = drag_watt + rolling_watt + gravity_watt;

                let mut prof = serde_json::Map::new();
                if let Some(v) = profile.cda {
                    prof.insert("cda".into(), json!(v));
                }
                if let Some(v) = profile.crr {
                    prof.insert("crr".into(), json!(v));
                }
                if let Some(v) = profile.weight_kg {
                    prof.insert("weight_kg".into(), json!(v));
                }
                if let Some(v) = profile.crank_eff_pct {
                    prof.insert("crank_eff_pct".into(), json!(v));
                }
                prof.insert("calibrated".into(), json!(profile.calibrated));

                let eff = clamp_eff_from_profile(&prof);
                // PATCH 3: Bruk alltid wheel model når vi ikke har powermeter
                let total_watt_ui = model_watt_wheel;

                let mut metrics_obj = serde_json::Map::new();
                metrics_obj.insert("cg_build".into(), json!(CG_BUILD));
                metrics_obj.insert("drag_watt".into(), json!(drag_watt));
                metrics_obj.insert("rolling_watt".into(), json!(rolling_watt));
                metrics_obj.insert("gravity_watt".into(), json!(gravity_watt));
                metrics_obj.insert("model_watt_wheel".into(), json!(model_watt_wheel));
                metrics_obj.insert("total_watt".into(), json!(total_watt_ui));
                metrics_obj.insert("precision_watt_crank".into(), json!(model_watt_wheel / eff));
                metrics_obj.insert("eff_used".into(), json!(eff));
                metrics_obj.insert("model_watt_crank".into(), json!(model_watt_wheel / eff));
                metrics_obj.insert("core_watts_source".into(), json!(core_watts_source));
                metrics_obj.insert("core_n_device_samples".into(), json!(core_n));
                // wind_effect faktor i debug info
                metrics_obj.insert("wind_effect".into(), json!(WIND_EFFECT));
                // PATCH 3: Ikke sett "core_watts_avg" i JSON hvis den er None

                metrics_obj.insert("profile_used".into(), Value::Object(prof));
                metrics_obj.insert("gravity_watt_pedal".into(), json!(avg_grav_pedal));
                metrics_obj.insert("total_watt_pedal".into(), json!(avg_model_pedal_moving));
                metrics_obj.insert("precision_watt_pedal".into(), json!(precision_watt_pedal));
                metrics_obj.insert("model_watt_wheel_pedal".into(), json!(avg_model_pedal_moving));
                
                // PATCH C2: Legg til debug-felt for elapsed vs moving
                metrics_obj.insert("model_watt_wheel_pedal_elapsed".into(), json!(avg_model_pedal_elapsed));
                metrics_obj.insert("model_watt_wheel_pedal_moving".into(), json!(avg_model_pedal_moving));
                metrics_obj.insert("pedal_ratio_elapsed_over_moving".into(), json!(pedal_ratio_elapsed_over_moving));

                obj.insert("metrics".into(), Value::Object(metrics_obj));
            }
        }

        // ── HARD OVERRIDE (siste ord): sørg for definisjonene vi vil ha i UI ─────────
        if let Some(mv) = obj.get_mut("metrics") {
            if let Some(m) = mv.as_object_mut() {
                // wheel = model_watt_wheel hvis den finnes, ellers fallback til komponent-sum
                let wheel = m
                    .get("model_watt_wheel")
                    .and_then(|v| v.as_f64())
                    .unwrap_or(drag_watt + rolling_watt + gravity_watt);

                // eff fra profile_used (samme clamp som ellers)
                let eff = m
                    .get("profile_used")
                    .and_then(|v| v.as_object())
                    .map(clamp_eff_from_profile)
                    .unwrap_or(0.955);

                // UI: precision_watt = wheel
                m.insert("precision_watt".into(), json!(wheel));

                // Diagnose: crank = wheel/eff
                m.insert("precision_watt_crank".into(), json!(wheel / eff));
                m.insert("eff_used".into(), json!(eff));
                m.insert("model_watt_crank".into(), json!(wheel / eff));

                // ✅ NYTT: metrics.precision_watt_avg skal være WHEEL (rå fysikk)
                m.insert("precision_watt_avg".into(), json!(wheel));

                // ✅ Sikkerhet: behold pedal i metrics (hoved for bruker)
                // (den settes allerede over, men dette gjør hard-override robust)
                m.insert("precision_watt_pedal".into(), json!(precision_watt_pedal));
            }
        }

        // ✅ NYTT: Top-level avg for list/UI = PEDAL (brukerfelt)
        obj.insert("precision_watt_avg".into(), json!(precision_watt_pedal));

        // Sett metadata om de mangler (ikke overskriv core)
        obj.entry("source").or_insert(Value::from("rust_1arg"));
        obj.entry("weather_applied").or_insert(Value::from(false));

        // DEBUG: build-stamp for å verifisere at ny .pyd faktisk kjører
        obj.insert("cg_build".into(), Value::from(CG_BUILD));
    }

    resp
}




fn parse_tolerant(
    json_str: &str,
) -> Result<
    (
        Vec<crate::Sample>,
        crate::Profile,
        CoreWeather,
        bool,
        &'static str,
        bool,
    ),
    String,
> {
    let mut de = json::Deserializer::from_str(json_str);
    let repr: InReprTol = spte::deserialize(&mut de).map_err(|e| {
        format!(
            "parse error (ComputePowerIn tolerant) at {}: {}",
            e.path(),
            e
        )
    })?;

    match repr {
        InReprTol::Object(o) => {
            let estimat_present = o
                ._ignore_estimat
                .as_ref()
                .map(|v| !v.is_null())
                .unwrap_or(false);

            let core_samples = o
                .samples
                .into_iter()
                .map(to_core_sample_tol)
                .collect::<Result<Vec<_>, _>>()?;

            let core_profile = to_core_profile_tol(o.profile, estimat_present)?;
            let w = neutral_weather();

            Ok((
                core_samples,
                core_profile,
                w,
                estimat_present,
                "legacy_tolerant",
                true,
            ))
        }
        InReprTol::Triple(TripleTol(samples, p, third)) => {
            let estimat_present = !third.is_null();

            let core_samples = samples
                .into_iter()
                .map(to_core_sample_tol)
                .collect::<Result<Vec<_>, _>>()?;

            let core_profile = to_core_profile_tol(p, estimat_present)?;
            let w = neutral_weather();

            Ok((
                core_samples,
                core_profile,
                w,
                estimat_present,
                "legacy_tolerant",
                true,
            ))
        }
    }
}

// ──────────────────────────────────────────────────────────────────────────────
// PRIMÆR PARSING (OBJECT → LEGACY) MED OBJ-DEBUG
// ──────────────────────────────────────────────────────────────────────────────


fn call_compute_from_json(json_in: &str) -> Result<String, String> {
    // 0) OBJ-DEBUG: prøv ren OBJECT først
    let val: Value = json::from_str(json_in).unwrap_or(Value::Null);
    {
        let mut track = spte::Track::new();
        let de = spte::Deserializer::new(val.clone().into_deserializer(), &mut track);
        let try_obj: Result<ComputePowerObjectV3, _> = Deserialize::deserialize(de);
        match try_obj {
            Ok(obj) => {
                let estimat_present = !obj.estimat.is_null();
                let core_profile = to_core_profile_tol(obj.profile.clone(), estimat_present)
                    .map_err(|e| format!("profile convert error: {}", e))?;
                let w = obj.weather.unwrap_or_else(neutral_weather);

                // KONVERTER tolerant samples → kjerne
                let core_samples = obj
                    .samples
                    .into_iter()
                    .map(to_core_sample_tol)
                    .collect::<Result<Vec<_>, _>>()?;

                // ✅ FIX: compute_power_with_wind_json tar 3 args (samples, profile, weather)
                let mut out =
                    crate::compute_power_with_wind_json(&core_samples, &core_profile, &w);

                let mut dbg = JsonMap::new();
                dbg.insert("repr_kind".into(), Value::from("object"));
                dbg.insert("used_fallback".into(), Value::from(false));
                dbg.insert("estimat_present".into(), Value::from(estimat_present));
                dbg.insert(
                    "weather_source".into(),
                    Value::from(
                        if w.air_temp_c != 0.0
                            || w.wind_ms != 0.0
                            || w.air_pressure_hpa != 0.0
                            || w.wind_dir_deg != 0.0
                        {
                            "object_weather"
                        } else {
                            "neutral"
                        },
                    ),
                );
                dbg.insert("binding".into(), Value::from("py_mod"));

                out = with_debug(out, &dbg);
                out = ensure_metrics_shape(out);

                // berik OBJECT-svar
                if let Ok(resp_val) = serde_json::from_str::<serde_json::Value>(&out) {
                    let repr_kind = "object";
                    let enriched =
                        enrich_metrics_on_object(resp_val, &core_samples, &obj.profile, repr_kind, &w);
                    if let Ok(s) = serde_json::to_string(&enriched) {
                        out = s;
                    }
                }

                return Ok(out);
            }
            Err(e) => {
                eprintln!(
                    "[OBJ-DEBUG] failed at path {}: {}",
                    track.path().to_string(),
                    e
                );
            }
        }
    }

    // 1) Prøv untagged enum (OBJECT → Legacy)
    let parsed_primary: Result<
        (
            Vec<crate::Sample>,
            crate::Profile,
            CoreWeather,
            bool,
            &'static str,
            bool,
            Option<(Vec<crate::Sample>, ProfileInTol)>,
        ),
        String,
    > = {
        let mut de = json::Deserializer::from_str(json_in);
        let repr_res: Result<ComputePowerIn, _> = spte::deserialize(&mut de).map_err(|e| {
            format!(
                "parse error (ComputePowerIn primary) at {}: {}",
                e.path(),
                e
            )
        });

        match repr_res? {
            ComputePowerIn::Object(obj) => {
                let estimat_present = !obj.estimat.is_null();
                let core_profile = to_core_profile_tol(obj.profile.clone(), estimat_present)
                    .map_err(|e| format!("profile convert error: {}", e))?;
                let w = obj.weather.unwrap_or_else(neutral_weather);

                // konverter tolerant samples
                let core_samples = obj
                    .samples
                    .clone()
                    .into_iter()
                    .map(to_core_sample_tol)
                    .collect::<Result<Vec<_>, _>>()?;

                Ok((
                    core_samples.clone(),
                    core_profile,
                    w,
                    estimat_present,
                    "object",
                    false,
                    Some((core_samples, obj.profile.clone())),
                ))
            }
            ComputePowerIn::Legacy(ComputePowerLegacy(samples, profile, third)) => {
                let estimat_present = !third.is_null();
                let w = neutral_weather();
                Ok((samples, profile, w, estimat_present, "triple", true, None))
            }
        }
    };

    // 2) Tolerant fallback ved full feil
    let (samples, profile, weather, estimat_present, repr_kind, used_fallback, obj_opt) =
        match parsed_primary {
            Ok(ok) => ok,
            Err(e_primary) => {
                eprintln!("[PRIMARY] parse failed → trying tolerant: {}", e_primary);
                let (s, p, w, est, kind, used) = parse_tolerant(json_in)?;
                (s, p, w, est, kind, used, None)
            }
        };

    // ✅ FIX: 3 args (samples, profile, weather)
    let mut out = crate::compute_power_with_wind_json(&samples, &profile, &weather);

    let mut dbg = JsonMap::new();
    dbg.insert("repr_kind".into(), Value::from(repr_kind));
    dbg.insert("used_fallback".into(), Value::from(used_fallback));
    dbg.insert("estimat_present".into(), Value::from(estimat_present));
    dbg.insert(
        "weather_source".into(),
        Value::from(match repr_kind {
            "object" => {
                if weather.air_temp_c != 0.0
                    || weather.wind_ms != 0.0
                    || weather.air_pressure_hpa != 0.0
                    || weather.wind_dir_deg != 0.0
                {
                    "object_weather"
                } else {
                    "neutral"
                }
            }
            "triple" | "legacy_tolerant" => "neutral",
            _ => "neutral",
        }),
    );
    dbg.insert("binding".into(), Value::from("py_mod"));

    out = with_debug(out, &dbg);
    out = ensure_metrics_shape(out);

    if repr_kind == "object" {
        if let Some((core_samples_obj, profile_tol)) = obj_opt {
            if let Ok(resp_val) = serde_json::from_str::<serde_json::Value>(&out) {
                let repr_kind = "object";
                let enriched = enrich_metrics_on_object(
                    resp_val,
                    &core_samples_obj,
                    &profile_tol,
                    repr_kind,
                    &weather,
                );
                if let Ok(s) = serde_json::to_string(&enriched) {
                    out = s;
                }
            }
        }
    }

    Ok(out)
}

// ──────────────────────────────────────────────────────────────────────────────
// STRICT V3 (med weather) – beholdt for eksplisitt testing
// ──────────────────────────────────────────────────────────────────────────────

#[derive(Debug, Deserialize)]
struct ComputePowerInV3StrictRaw {
    samples: Vec<crate::Sample>,
    profile: Value, // les som Value for ev. injeksjon
    weather: crate::Weather,
    #[serde(default)]
    estimat: Value, // topp-nivå; kan være Null
}

fn call_compute_power_with_wind_from_json_v3(json_in: &str) -> Result<String, String> {
    let mut de = serde_json::Deserializer::from_str(json_in);
    let parsed: ComputePowerInV3StrictRaw = spte::deserialize(&mut de).map_err(|e| {
        format!(
            "parse error (ComputePowerIn v3 strict raw) at {}: {}",
            e.path(),
            e
        )
    })?;

    // Sørg for at profile har en "estimat"-nøkkel (null hvis ikke satt),
    // eller speil toppnivå `estimat` for maksimal kompatibilitet.
    let mut profile_val = parsed.profile.clone();
    if let Value::Object(ref mut pm) = profile_val {
        if !pm.contains_key("estimat") {
            pm.insert("estimat".into(), parsed.estimat.clone());
        }
    }

    // Deserialiser så til kjerne-typene
    let profile: crate::Profile = {
        let txt = profile_val.to_string();
        let mut de = json::Deserializer::from_str(&txt);
        spte::deserialize(&mut de)
            .map_err(|e| format!("parse error (Profile in v3 strict) at {}: {}", e.path(), e))?
    };

    // ✅ FIX: 3 args (samples, profile, weather)
    let out = crate::compute_power_with_wind_json(&parsed.samples, &profile, &parsed.weather);
    Ok(out)
}

// ──────────────────────────────────────────────────────────────────────────────
// PyO3-FUNKSJONER — 1-ARG EXPORT (OBJECT → core → enrich → JSON)
// ──────────────────────────────────────────────────────────────────────────────

#[pyfunction]
fn compute_power_with_wind_json(_py: Python<'_>, payload_json: &str) -> PyResult<String> {
    use serde_json::Value as J;

    // 1) Parse rå JSON
    let raw_val: J = serde_json::from_str(payload_json)
        .map_err(|e| PyValueError::new_err(format!("parse error (raw json): {e}")))?;

    // 2) Deserialiser tolerant OBJECT med path-sporing
    let obj: ComputePowerObjectV3 = {
        let mut track = spte::Track::new();
        let de = spte::Deserializer::new(raw_val.clone().into_deserializer(), &mut track);
        match Deserialize::deserialize(de) {
            Ok(v) => v,
            Err(e) => {
                let path = track.path().to_string();
                return Err(PyValueError::new_err(format!(
                    "parse error (OBJECT tolerant) at {path}: {e}"
                )));
            }
        }
    };

    // 3) Kall kjernen (via eksisterende 3-arg-funksjon)
    let estimat_present = !obj.estimat.is_null();
    let core_profile = to_core_profile_tol(obj.profile.clone(), estimat_present)
        .map_err(|e| PyValueError::new_err(format!("profile convert error: {e}")))?;
    let weather = obj.weather.unwrap_or_else(neutral_weather);

    // KONVERTER tolerant samples → kjerne
    let core_samples = obj
        .samples
        .into_iter()
        .map(to_core_sample_tol)
        .collect::<Result<Vec<_>, _>>()
        .map_err(|e| PyValueError::new_err(e))?;

    // ✅ FIX: 3 args (samples, profile, weather)
    let core_out_str = crate::compute_power_with_wind_json(&core_samples, &core_profile, &weather);
    let core_resp_val: serde_json::Value = serde_json::from_str(&core_out_str)
        .unwrap_or_else(|_| serde_json::json!({ "debug": { "reason": "decode_error" } }));

    // 4) Berik svaret med skalarer, arrays, source/weather_applied
    let repr_kind: &str = "object";

    let enriched = enrich_metrics_on_object(
        core_resp_val,
        &core_samples,
        &obj.profile,
        repr_kind,
        &weather,
    );

    // 5) Returnér som JSON-streng
    serde_json::to_string(&enriched)
        .map_err(|e| PyValueError::new_err(format!("json encode error: {e}")))
}



#[pyfunction]
pub fn compute_power_with_wind_json_v3(_py: Python<'_>, json_str: &str) -> PyResult<String> {
    call_compute_power_with_wind_from_json_v3(json_str).map_err(PyValueError::new_err)
}

#[pyfunction]
fn call_analyze_session_rust_from_json(json_in: &str) -> PyResult<String> {
    #[derive(Deserialize)]
    struct AnalyzeRustIn {
        watts: Vec<f64>,
        pulses: Vec<f64>,
        #[serde(default)]
        device_watts: Option<bool>,
    }

    let mut de = json::Deserializer::from_str(json_in);
    let parsed: AnalyzeRustIn = spte::deserialize(&mut de).map_err(|e| {
        let path = e.path().to_string();
        PyValueError::new_err(format!("parse error (AnalyzeRustIn) at {}: {}", path, e))
    })?;

    let out_val = crate::analyze_session_rust(parsed.watts, parsed.pulses, parsed.device_watts)
        .map_err(|e| PyValueError::new_err(e.to_string()))?;

    Ok(out_val.to_string())
}

// ──────────────────────────────────────────────────────────────────────────────
// PyO3-MODUL
// ──────────────────────────────────────────────────────────────────────────────

#[pymodule]
fn cyclegraph_core(_py: Python, m: &PyModule) -> PyResult<()> {
    // 1-arg: OBJECT → core → enrich → JSON
    m.add_function(wrap_pyfunction!(compute_power_with_wind_json, m)?)?;

    // Eksplisitt V3 (strict) for testing
    m.add_function(wrap_pyfunction!(compute_power_with_wind_json_v3, m)?)?;

    // Analyze helper
    m.add_function(wrap_pyfunction!(call_analyze_session_rust_from_json, m)?)?;
    Ok(())
}