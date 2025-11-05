// In release builds we deny(warnings) at crate level. This module contains
// tolerant parsers and helpers that may be intentionally unused during
// incremental integration. Allow them in release to avoid breaking the build.
#![cfg_attr(
    not(debug_assertions),
    allow(
        dead_code,
        unused_imports,
        unused_variables,
        unused_mut,
        unused_macros
    )
)]

use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::wrap_pyfunction;

use serde::de::IntoDeserializer; // for Value::into_deserializer()
use serde::Deserialize;
use serde_json::{self as json, Map as JsonMap, Value};
use serde_path_to_error as spte;
use crate::physics::{
    PhysProfile,
    PhysTweak,
    fill_distance_if_missing,
    derive_or_smooth_grade,
    MetricsSeries,
};

use crate::Weather as CoreWeather;
use crate::physics::compute_metrics_for_series;
// ──────────────────────────────────────────────────────────────────────────────
// Konstanter for fysikk
// ──────────────────────────────────────────────────────────────────────────────
const G: f64 = 9.80665;
const RHO_DEFAULT: f64 = 1.225;

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
    heading_deg: Option<f64>,
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
struct TripleTol(
    Vec<SampleInTol>,
    ProfileInTol,
    #[serde(default)] Value,
);

#[derive(Debug, Deserialize)]
#[serde(untagged)]
enum InReprTol {
    Triple(TripleTol),
    Object(ObjectTol),
}

// ──────────────────────────────────────────────────────────────────────────────
/* KONVERTERINGER (tolerant → kjerne-typer) */
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
    m.insert(
    "heading_deg".into(),
    match s.heading_deg {
        Some(h) => serde_json::Value::from(h),
        None => serde_json::Value::Null,
    },
);

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
                for k in [
                    "precision_watt",
                    "drag_watt",
                    "rolling_watt",
                    "gravity_watt",
                    "total_watt",
                ]
                .iter()
                {
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

#[inline]
fn mean(xs: &[f64]) -> f64 {
    if xs.is_empty() {
        0.0
    } else {
        xs.iter().copied().sum::<f64>() / (xs.len() as f64)
    }
}

/// Beregn timeserie-metrics via fysikk-kjernen og returnér også skalar-gjennomsnitt.
/// NB: `total_watt` er *lik* `precision_watt` for bakoverkompatibilitet.
fn compute_series_metrics_with_gravity(
    samples: &[crate::Sample],
    core_profile: &crate::Profile,
    estimat_cfg: &serde_json::Value,
) -> (
    Vec<f64>, // w_drag
    Vec<f64>, // w_roll
    Vec<f64>, // w_gravity
    Vec<f64>, // w_precision (crank = wheel / eta)
    Vec<f64>, // w_total (== w_precision for back-compat)
    f64,      // drag_watt (mean)
    f64,      // rolling_watt (mean)
    f64,      // gravity_watt (mean)
    f64,      // precision_watt (mean)
    f64,      // total_watt (== precision_watt)
    f64,      // active_ratio
) {
    // --- Toggles / skaleringsparametre ---
    let include_gravity = estimat_cfg
        .as_object()
        .and_then(|m| m.get("include_gravity"))
        .and_then(|v| v.as_bool())
        .unwrap_or(true);

    let drivetrain_eta = estimat_cfg
        .as_object()
        .and_then(|m| m.get("drivetrain_eta"))
        .and_then(|v| v.as_f64())
        .map(|x| x.clamp(0.90, 1.0))
        .unwrap_or(0.97);

    let alt_smooth_secs = estimat_cfg
        .as_object()
        .and_then(|m| m.get("alt_smooth_secs"))
        .and_then(|v| v.as_f64())
        .map(|x| x.clamp(0.0, 10.0))
        .unwrap_or(4.0);

    let cd_a_scale = estimat_cfg
        .as_object()
        .and_then(|m| m.get("cdA_scale"))
        .and_then(|v| v.as_f64())
        .map(|x| x.clamp(0.8, 1.2))
        .unwrap_or(1.0);

    let crr_scale = estimat_cfg
        .as_object()
        .and_then(|m| m.get("crr_scale"))
        .and_then(|v| v.as_f64())
        .map(|x| x.clamp(0.8, 1.2))
        .unwrap_or(1.0);

    // --- Preprosessering av samples ---
    let mut processed_samples = samples.to_vec();
    // Disse antas å eksistere i modulen din:
    // - fill_distance_if_missing
    // - derive_or_smooth_grade (bruker alt_smooth_secs)
    fill_distance_if_missing(&mut processed_samples);
    derive_or_smooth_grade(&mut processed_samples, alt_smooth_secs);

    // --- Effektive koeffisienter ---
    // NB: behold felt-navn slik du allerede bruker i Profile
    let base_cda = core_profile.cda.unwrap_or(0.30);
    let base_crr = core_profile.crr.unwrap_or(0.005);
    let mass_kg  = core_profile.total_weight.unwrap_or(75.0);

    let eff_cda = base_cda * cd_a_scale;
    let eff_crr = base_crr * crr_scale;

    // --- Tidsserier ---
    let n = processed_samples.len();
    let mut w_drag = Vec::with_capacity(n);
    let mut w_roll = Vec::with_capacity(n);
    let mut w_grav = Vec::with_capacity(n);
    let mut w_prec = Vec::with_capacity(n);
    let mut w_tot  = Vec::with_capacity(n);

    // --- Aggregater (mean) ---
    let mut sum_drag = 0.0;
    let mut sum_roll = 0.0;
    let mut sum_grav = 0.0;
    let mut sum_prec = 0.0;
    let mut count    = 0usize;

    // Aktiv andel (enkelt estimat: v >= 1.0 m/s)
    let mut active_cnt = 0usize;

    for s in &processed_samples {
        let v = s.v_ms.max(0.0);
        if v >= 1.0 {
            active_cnt += 1;
        }

        // grade som brøk (0.05 = 5 %). Bygg tolerant:
        // - hvis du har s.grade: Option<f64>, bruk den
        // - ev. legg til s.grade_frac / s.grade_pct i din Sample-modell
        let grade = s.grade.unwrap_or(0.0);

        // Geometri
        let cos_theta = (1.0 + grade * grade).powf(-0.5);
        let sin_theta = grade * cos_theta;

        // Kraftkomponenter (W)
        let drag_watt    = 0.5 * crate::physics::RHO * eff_cda * v * v * v;
        let rolling_watt = eff_crr * mass_kg * G * v * cos_theta;
        let gravity_watt = if include_gravity {
            mass_kg * G * v * sin_theta
        } else {
            0.0
        };

        // Crank power (precision) = wheel / eta
        let base_power     = drag_watt + rolling_watt + gravity_watt;
        let precision_watt = base_power / drivetrain_eta;

        // Push tidsserier
        w_drag.push(drag_watt);
        w_roll.push(rolling_watt);
        w_grav.push(gravity_watt);
        w_prec.push(precision_watt);
        w_tot.push(precision_watt); // back-compat

        // Aggreger
        if precision_watt.is_finite() {
            sum_drag += drag_watt;
            sum_roll += rolling_watt;
            sum_grav += gravity_watt;
            sum_prec += precision_watt;
            count    += 1;
        }
    }

    let inv = if count > 0 { 1.0 / count as f64 } else { 0.0 };
    let drag_watt      = sum_drag * inv;
    let rolling_watt   = sum_roll * inv;
    let gravity_watt   = sum_grav * inv;
    let precision_watt = sum_prec * inv;
    let total_watt     = precision_watt; // definert lik precision for bakoverkomp.

    let active_ratio = if n > 0 {
        active_cnt as f64 / n as f64
    } else {
        0.0
    };

    (
        w_drag,
        w_roll,
        w_grav,
        w_prec,
        w_tot,
        drag_watt,
        rolling_watt,
        gravity_watt,
        precision_watt,
        total_watt,
        active_ratio,
    )
}


fn enrich_metrics_on_object(
    mut resp: serde_json::Value,
    samples: &[crate::Sample],
    core_profile: &crate::Profile,
    profile_tol_for_echo: &ProfileInTol,
    estimat_cfg: &Value,
) -> serde_json::Value {
    use serde_json::{json, Value};

    let (
        w_drag,
        w_roll,
        w_grav,
        w_prec,
        w_tot,
        drag_watt,
        rolling_watt,
        gravity_watt,
        precision_watt,
        total_watt,
        active_ratio,
    ) = compute_series_metrics_with_gravity(samples, core_profile, estimat_cfg);

    // ---- METRICS (D, R, G, P) + DEBUG FELT ----
    // Aggregert (snitt) fra serien:
    let d = drag_watt;
    let r = rolling_watt;
    let g = gravity_watt;

    // Precision før/drivverk
    let mut p_no_eta = if estimat_cfg
        .as_object()
        .and_then(|m| m.get("include_gravity"))
        .and_then(|v| v.as_bool())
        .unwrap_or(true) 
    { 
        d + r + g 
    } else { 
        d + r 
    };
    
    // Drivverkskorrigert precision (rytterkraft)
    let drivetrain_eta = estimat_cfg
        .as_object()
        .and_then(|m| m.get("drivetrain_eta"))
        .and_then(|v| v.as_f64())
        .map(|x| x.clamp(0.90, 1.0))
        .unwrap_or(0.97);
    let p = p_no_eta / drivetrain_eta;

    // Sørg for at w_precision bruker samme logikk som aggregatet:
    let include_gravity = estimat_cfg
        .as_object()
        .and_then(|m| m.get("include_gravity"))
        .and_then(|v| v.as_bool())
        .unwrap_or(true);
    
    let w_precision: Vec<f64> = if include_gravity {
      w_drag.iter().zip(&w_roll).zip(&w_grav).map(|((dd, rr), gg)| (dd + rr + gg) / drivetrain_eta).collect()
    } else {
        w_drag.iter().zip(&w_roll).map(|(dd, rr)| (dd + rr) / drivetrain_eta).collect()
    };

    if let Some(obj) = resp.as_object_mut() {
        // metrics
        match obj.get_mut("metrics") {
            Some(mv) if mv.is_object() => {
                let m = mv.as_object_mut().unwrap();
                m.insert("drag_watt".into(), json!(d));
                m.insert("rolling_watt".into(), json!(r));
                m.insert("gravity_watt".into(), json!(g));
                m.insert("precision_watt".into(), json!(p));

                // Back-compat: total_watt speiler precision_watt
                m.entry("total_watt").or_insert(json!(p));

                // profile_used: gjenspeil det klient ga (tolerant), slik at UI ser konkrete tall
                let mut prof = serde_json::Map::new();
                if let Some(v) = profile_tol_for_echo.cda {
                    prof.insert("cda".into(), json!(v));
                }
                if let Some(v) = profile_tol_for_echo.crr {
                    prof.insert("crr".into(), json!(v));
                }
                if let Some(v) = profile_tol_for_echo.weight_kg {
                    prof.insert("weight_kg".into(), json!(v));
                }
                prof.insert("calibrated".into(), json!(profile_tol_for_echo.calibrated));
                m.entry("profile_used").or_insert(Value::Object(prof));
            }
            _ => {
                let mut prof = serde_json::Map::new();
                if let Some(v) = profile_tol_for_echo.cda {
                    prof.insert("cda".into(), json!(v));
                }
                if let Some(v) = profile_tol_for_echo.crr {
                    prof.insert("crr".into(), json!(v));
                }
                if let Some(v) = profile_tol_for_echo.weight_kg {
                    prof.insert("weight_kg".into(), json!(v));
                }
                prof.insert("calibrated".into(), json!(profile_tol_for_echo.calibrated));

                obj.insert(
                    "metrics".into(),
                    json!({
                        "drag_watt": d,
                        "rolling_watt": r,
                        "gravity_watt": g,
                        "precision_watt": p,
                        // Back-compat: total_watt speiler precision_watt
                        "total_watt": p,
                        "profile_used": prof
                    }),
                );
            }
        }

        // arrays
        match obj.get_mut("arrays") {
            Some(av) if av.is_object() => {
                let a = av.as_object_mut().unwrap();
                a.insert("w_drag".into(), json!(w_drag));
                a.insert("w_roll".into(), json!(w_roll));
                a.insert("w_gravity".into(), json!(w_grav));
                a.insert("w_precision".into(), json!(w_precision));
                // Back-compat: w_total speiler w_precision
                a.insert("w_total".into(), json!(w_precision));
            }
            _ => {
                obj.insert(
                    "arrays".into(),
                    json!({
                        "w_drag": w_drag,
                        "w_roll": w_roll,
                        "w_gravity": w_grav,
                        "w_precision": w_precision,
                        // Back-compat: w_total speiler w_precision
                        "w_total": w_precision
                    }),
                );
            }
        }

        // toppnivå standardfelt
        obj.entry("source").or_insert(json!("rust_1arg"));
        obj.entry("weather_applied").or_insert(json!(false));

        // DEBUG-felter (må bli med i rot-svaret):
        let mut debug = json::Map::new();
        debug.insert("include_gravity".into(), json!(include_gravity));
        debug.insert("drivetrain_eta".into(), json!(drivetrain_eta));
        debug.insert("rho_used".into(), json!(RHO_DEFAULT));
        
        let cd_a_scale = estimat_cfg
            .as_object()
            .and_then(|m| m.get("cdA_scale"))
            .and_then(|v| v.as_f64())
            .map(|x| x.clamp(0.8, 1.2))
            .unwrap_or(1.0);
        let crr_scale = estimat_cfg
            .as_object()
            .and_then(|m| m.get("crr_scale"))
            .and_then(|v| v.as_f64())
            .map(|x| x.clamp(0.8, 1.2))
            .unwrap_or(1.0);
        
        debug.insert("cdA_effective".into(), json!(core_profile.cda.unwrap_or(0.3) * cd_a_scale));
        debug.insert("crr_effective".into(), json!(core_profile.crr.unwrap_or(0.005) * crr_scale));
        
        let alt_smooth_secs = estimat_cfg
            .as_object()
            .and_then(|m| m.get("alt_smooth_secs"))
            .and_then(|v| v.as_f64())
            .map(|x| x.clamp(0.0, 10.0))
            .unwrap_or(4.0);
        debug.insert("alt_smooth_secs".into(), json!(alt_smooth_secs));
        debug.insert("p_no_eta".into(), json!(p_no_eta));
        
        // Nytt: eksponer aktivitetsstatistikk fra series
        debug.insert("active_ratio".into(), json!(active_ratio));
        debug.insert("min_speed_ms".into(), json!(1.0));
        debug.insert("min_dt_s".into(), json!(0.2));

        obj.insert("debug".into(), json::Value::from(debug));
    }

    resp
}

// ──────────────────────────────────────────────────────────────────────────────
// TOLERANT PARSER
// ──────────────────────────────────────────────────────────────────────────────

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
    let repr: InReprTol = spte::deserialize(&mut de)
        .map_err(|e| format!("parse error (ComputePowerIn tolerant) at {}: {}", e.path(), e))?;

    match repr {
        InReprTol::Object(o) => {
            let estimat_present = o._ignore_estimat.as_ref().map(|v| !v.is_null()).unwrap_or(false);

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
                    .clone()
                    .into_iter()
                    .map(to_core_sample_tol)
                    .collect::<Result<Vec<_>, _>>()?;

                // Kall kjernen
                let mut out =
                    crate::compute_power_with_wind_json(&core_samples, &core_profile, &w);

                // Debug
                let mut dbg = JsonMap::new();
                dbg.insert("repr_kind".into(), Value::from("object"));
                dbg.insert("used_fallback".into(), Value::from(false));
                dbg.insert("estimat_present".into(), Value::from(estimat_present));
                dbg.insert(
                    "weather_source".into(),
                    Value::from(if w.air_temp_c != 0.0
                        || w.wind_ms != 0.0
                        || w.air_pressure_hpa != 0.0
                        || w.wind_dir_deg != 0.0
                    {
                        "object_weather"
                    } else {
                        "neutral"
                    }),
                );
                dbg.insert("binding".into(), Value::from("py_mod"));

                out = with_debug(out, &dbg);
                out = ensure_metrics_shape(out);

                // Berik med timeserier/aggregater fra fysikk-kjernen (inkl. nye toggles)
                if let Ok(resp_val) = serde_json::from_str::<serde_json::Value>(&out) {
                    let enriched = enrich_metrics_on_object(
                        resp_val,
                        &core_samples,
                        &core_profile,
                        &obj.profile,
                        &obj.estimat,
                    );
                    if let Ok(s) = serde_json::to_string(&enriched) {
                        out = s;
                    }
                }

                return Ok(out);
            }
            Err(e) => {
                eprintln!("[OBJ-DEBUG] failed at path {}: {}", track.path().to_string(), e);
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
            Option<(Vec<crate::Sample>, ProfileInTol, Value)>,
        ),
        String,
    > = {
        let mut de = json::Deserializer::from_str(json_in);
        let repr_res: Result<ComputePowerIn, _> = spte::deserialize(&mut de)
            .map_err(|e| format!("parse error (ComputePowerIn primary) at {}: {}", e.path(), e));

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
                    Some((core_samples, obj.profile.clone(), obj.estimat.clone())),
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

    // Berik også i denne stien
    if repr_kind == "object" {
        if let Some((core_samples_obj, profile_tol, estimat)) = obj_opt {
            if let Ok(resp_val) = serde_json::from_str::<serde_json::Value>(&out) {
                let enriched = enrich_metrics_on_object(
                    resp_val,
                    &core_samples_obj,
                    &profile,
                    &profile_tol,
                    &estimat,
                );
                if let Ok(s) = serde_json::to_string(&enriched) {
                    out = s;
                }
            }
        }
    } else {
        if let Ok(resp_val) = serde_json::from_str::<serde_json::Value>(&out) {
            let enriched =
                enrich_metrics_on_object(resp_val, &samples, &profile, &ProfileInTol {
                    cda: None,
                    crr: None,
                    weight_kg: None,
                    device: String::new(),
                    calibrated: false,
                    estimat: None,
                }, &Value::Null);
            if let Ok(s) = serde_json::to_string(&enriched) {
                out = s;
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



// ──────────────────────────────────────────────────────────────────────────────
// PyO3-FUNKSJONER — 1-ARG EXPORT (OBJECT → core → enrich → JSON)
// ──────────────────────────────────────────────────────────────────────────────

fn call_compute_power_with_wind_from_json_v3(json_in: &str) -> Result<String, String> {
    // 1) Parse raw v3 payload
    let mut de = serde_json::Deserializer::from_str(json_in);
    let parsed: ComputePowerInV3StrictRaw = spte::deserialize(&mut de)
        .map_err(|e| format!("parse error (ComputePowerIn v3 strict raw) at {}: {}", e.path(), e))?;

    // 2) Sikre 'estimat' i profile (bakoverkompatibilitet)
    let mut profile_val = parsed.profile.clone();
    if let Value::Object(ref mut pm) = profile_val {
        if !pm.contains_key("estimat") {
            pm.insert("estimat".into(), parsed.estimat.clone());
        }
    }

    // 3) Profile → core
    let profile: crate::Profile = {
        let txt = profile_val.to_string();
        let mut de = json::Deserializer::from_str(&txt);
        spte::deserialize(&mut de)
            .map_err(|e| format!("parse error (Profile in v3 strict) at {}: {}", e.path(), e))?
    };

    // 4) Samples: ta direkte og pre-prosesser
    let mut samples: Vec<crate::Sample> = parsed.samples;
    let total_samples_in = samples.len();

    fill_distance_if_missing(&mut samples);
    // bruk 5 s jevning – robust mot støy
    derive_or_smooth_grade(&mut samples, 5.0);

    // 5) Lufttetthet (ρ): tolerant beregning fra Weather, ellers safe default
    //    NB: Weather hos deg har f64-felt (ikke Option). Om felt mangler i payload,
    //    forventer vi at de defaultes (serde default) – men vi gjør sanity-check uansett.
    let (rho, weather_applied) = {
        let w: &crate::Weather = &parsed.weather;
        let p_hpa = w.air_pressure_hpa; // f64
        let t_c   = w.air_temp_c;       // f64
        let p_ok = p_hpa.is_finite() && (100.0..1100.0).contains(&p_hpa);
        let t_ok = t_c.is_finite()   && (-60.0..60.0).contains(&t_c);
        if p_ok && t_ok {
            let p_pa  = p_hpa * 100.0;
            let t_k   = t_c + 273.15;
            if t_k > 0.0 {
                let r_air = 287.05_f64;
                let r = p_pa / (r_air * t_k);
                // sanity: kast NaN/inf
                if r.is_finite() && r > 0.8 && r < 1.6 {
                    (r, (r - RHO_DEFAULT).abs() > 1e-6)
                } else {
                    (RHO_DEFAULT, false)
                }
            } else {
                (RHO_DEFAULT, false)
            }
        } else {
            (RHO_DEFAULT, false)
        }
    };

    // 6) Beregn via SERIES-banen (per-sample Metrics)
    let series: Vec<crate::models::Metrics> = compute_metrics_for_series(&samples, &profile, rho);

    // 7) Hvis serien er tom, returnér tydelig debug i JSON så vi ser hvorfor i PS
    if series.is_empty() {
        let mut dbg = json::Map::new();
        dbg.insert("reason".into(),        json::Value::from("empty_series"));
        dbg.insert("total_samples_in".into(), json::Value::from(total_samples_in as i64));
        // plukk ut noen første samples for inspeksjon
        let preview: Vec<_> = samples.iter().take(3).map(|s| {
            json::json!({
                "t": s.t, "v_ms": s.v_ms, "alt": s.altitude_m,
                "grade": s.grade, "moving": s.moving
            })
        }).collect();
        dbg.insert("samples_preview".into(), json::Value::from(preview));
        dbg.insert("rho_used".into(), json::Value::from(rho));

        let mut resp = json::Map::new();
        resp.insert("source".into(),          json::Value::from("series_empty"));
        resp.insert("weather_applied".into(), json::Value::from(weather_applied));
        resp.insert("metrics".into(), json::Value::Object({
            let mut m = json::Map::new();
            m.insert("drag_watt".into(),      json::Value::from(0.0));
            m.insert("rolling_watt".into(),   json::Value::from(0.0));
            m.insert("gravity_watt".into(),   json::Value::from(0.0));
            m.insert("precision_watt".into(), json::Value::from(0.0));
            m.insert("total_watt".into(),     json::Value::from(0.0));
            m.insert("profile_used".into(),   serde_json::to_value(&profile).unwrap());
            m
        }));
        resp.insert("debug".into(),            json::Value::Object(dbg));
        return Ok(serde_json::Value::Object(resp).to_string());
    }

    // 8) Aggreger til snitt
    let n = series.len() as f64;
    let mut d = 0.0;
    let mut r = 0.0;
    let mut g = 0.0;
    let mut p = 0.0;
    for m in &series {
        d += m.drag_watt;
        r += m.rolling_watt;
        g += m.gravity_watt;    // "required" (>= 0)
        p += m.precision_watt;  // crank-side (etter eta)
    }
    let drag_watt      = d / n;
    let rolling_watt   = r / n;
    let gravity_watt   = g / n;
    let precision_watt = p / n;
    let total_watt     = drag_watt + rolling_watt + gravity_watt; // wheel-side

    // 9) Bygg JSON-respons
    let mut metrics = json::Map::new();
    metrics.insert("drag_watt".into(),      json::Value::from(drag_watt));
    metrics.insert("rolling_watt".into(),   json::Value::from(rolling_watt));
    metrics.insert("gravity_watt".into(),   json::Value::from(gravity_watt));
    metrics.insert("precision_watt".into(), json::Value::from(precision_watt));
    metrics.insert("total_watt".into(),     json::Value::from(total_watt));
    metrics.insert("profile_used".into(),   serde_json::to_value(&profile).unwrap());

    let mut debug = json::Map::new();
    debug.insert("used_fallback".into(), json::Value::from(false));
    debug.insert("series_len".into(),    json::Value::from(series.len() as i64));
    debug.insert("rho_used".into(),      json::Value::from(rho));

    let mut resp = json::Map::new();
    resp.insert("source".into(),           json::Value::from("series_v2"));
    resp.insert("weather_applied".into(),  json::Value::from(weather_applied));
    resp.insert("metrics".into(),          json::Value::Object(metrics));
    resp.insert("debug".into(),            json::Value::Object(debug));

    Ok(serde_json::Value::Object(resp).to_string())
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

#[pyfunction]
fn compute_power_with_wind_json(py: Python<'_>, payload: &PyAny) -> PyResult<PyObject> {
    // 1) Få inn JSON-string fra payload (tillater både str og dict/objekt)
    let json_in: String = if let Ok(s) = payload.extract::<&str>() {
        s.to_owned()
    } else {
        // Bruk Python sin json.dumps for å serialisere hvilket som helst Python-objekt
        let json_mod = py.import("json")
            .map_err(|e| PyValueError::new_err(format!("failed to import json: {e}")))?;
        json_mod
            .call_method1("dumps", (payload,))
            .and_then(|o| o.extract::<String>())
            .map_err(|e| PyValueError::new_err(format!("failed to serialize payload with json.dumps: {e}")))?
    };

    // 2) Kjør v3-ruten som bygger korrekt metrics (med gravity_watt osv.)
    let out = match call_compute_power_with_wind_from_json_v3(&json_in) {
        Ok(s) => s,
        Err(e) => return Err(PyValueError::new_err(e)),
    };

    // 3) Returnér som Python-objekt (dict) via Python's json.loads (unngår pyo3 serde-feature)
    let json_mod = py.import("json")
    .map_err(|e| PyValueError::new_err(format!("failed to import json: {e}")))?;
    let obj = json_mod
     .call_method1("loads", (out.as_str(),))
     .map_err(|e| PyValueError::new_err(format!("internal JSON parse error via json.loads: {e}")))?;
      Ok(obj.into_py(py))
}




#[pymodule]
fn cyclegraph_core(_py: Python, m: &PyModule) -> PyResult<()> {
    // 1-arg: OBJECT → core → enrich → JSON
    m.add_function(wrap_pyfunction!(compute_power_with_wind_json, m)?)?;

    // Eksplicit V3 (strict) for testing
    m.add_function(wrap_pyfunction!(compute_power_with_wind_json_v3, m)?)?;

    // Analyze helper
    m.add_function(wrap_pyfunction!(call_analyze_session_rust_from_json, m)?)?;
    Ok(())
}