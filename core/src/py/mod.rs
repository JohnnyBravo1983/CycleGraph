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

use serde::Deserialize;
use serde::de::IntoDeserializer; // for Value::into_deserializer()
use serde_json::{self as json, Map as JsonMap, Value};
use serde_path_to_error as spte;

use crate::Weather as CoreWeather;

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
// KONVERTERINGER (tolerant → kjerne-typer)
// ──────────────────────────────────────────────────────────────────────────────

fn to_core_profile_tol(p: ProfileInTol, estimat_present: bool) -> Result<crate::Profile, String> {
    let mut m = JsonMap::new();

    // Sett verdier eller Null hvis None
    m.insert("cda".into(), match p.cda { Some(x) => Value::from(x), None => Value::Null });
    m.insert("crr".into(), match p.crr { Some(x) => Value::from(x), None => Value::Null });
    m.insert("weight_kg".into(), match p.weight_kg { Some(x) => Value::from(x), None => Value::Null });

    m.insert("device".into(), Value::from(p.device));
    m.insert("calibrated".into(), Value::from(p.calibrated));

    // Repeter til kjerneprofilen: et boolsk hint om estimat-tilstedeværelse
    m.insert("estimat".into(), Value::from(estimat_present));

    // valgfrie mulige kjernefelt
    if !m.contains_key("total_weight") { m.insert("total_weight".into(), Value::Null); }
    if !m.contains_key("bike_type") { m.insert("bike_type".into(), Value::Null); }
    if !m.contains_key("calibration_mae") { m.insert("calibration_mae".into(), Value::Null); }

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
        Some(w) => { m.insert("device_watts".into(), Value::from(w)); }
        None => { m.insert("device_watts".into(), Value::Null); }
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
            obj.entry("source").or_insert_with(|| Value::from("rust_binding"));
            let dbg = obj.entry("debug").or_insert_with(|| Value::Object(JsonMap::new()));
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
                for k in ["precision_watt","drag_watt","rolling_watt","total_watt"].iter() {
                    if let Some(val) = obj.remove(*k) { m.insert((*k).into(), val); }
                }
                if !m.is_empty() { obj.insert("metrics".into(), Value::Object(m)); }
            }
            obj.entry("source").or_insert(Value::from("rust_1arg"));
            obj.entry("weather_applied").or_insert(Value::from(false));
            if let Ok(s) = serde_json::to_string(&v) { out_json = s; }
        }
    }
    out_json
}

// ──────────────────────────────────────────────────────────────────────────────
// STEG 1 (A): Skalar-metrics og diagnostikk-arrays (vind av)
// ──────────────────────────────────────────────────────────────────────────────

fn mean(xs: &[f64]) -> f64 {
    if xs.is_empty() { 0.0 } else { xs.iter().copied().sum::<f64>() / (xs.len() as f64) }
}

fn compute_scalar_metrics(
    samples: &[crate::Sample],
    profile: &ProfileInTol,
) -> (Vec<f64>, Vec<f64>, Vec<f64>, f64, f64, f64, f64) {
    let cda = profile.cda.unwrap_or(0.25);
    let crr = profile.crr.unwrap_or(0.004);
    let weight = profile.weight_kg.unwrap_or(85.0);
    let rho = RHO_DEFAULT;

    let mut w_drag = Vec::with_capacity(samples.len());
    let mut w_roll = Vec::with_capacity(samples.len());
    let mut w_model = Vec::with_capacity(samples.len());
    let mut device_watts = Vec::new();

    for s in samples {
        let v = s.v_ms.max(0.0);
        let w_d = 0.5 * rho * cda * v * v * v;
        let w_r = crr * weight * G * v;
        let w_m = w_d + w_r;

        w_drag.push(w_d);
        w_roll.push(w_r);
        w_model.push(w_m);

        // Bruk målt effekt om tilgjengelig
        if let Some(w) = s.device_watts {
            if w.is_finite() {
                device_watts.push(w);
            }
        }
    }

    let drag_watt = mean(&w_drag);
    let rolling_watt = mean(&w_roll);
    let precision_watt = drag_watt + rolling_watt;
    let total_watt = if !device_watts.is_empty() { mean(&device_watts) } else { precision_watt };

    (w_drag, w_roll, w_model, drag_watt, rolling_watt, precision_watt, total_watt)
}

fn enrich_metrics_on_object(
    mut resp: serde_json::Value,
    samples: &[crate::Sample],
    profile: &ProfileInTol,
) -> serde_json::Value {
    use serde_json::{json, Value};

    let (w_drag, w_roll, w_model, drag_watt, rolling_watt, precision_watt, total_watt)
        = compute_scalar_metrics(samples, profile);

    if let Some(obj) = resp.as_object_mut() {
        // metrics
        match obj.get_mut("metrics") {
            Some(mv) if mv.is_object() => {
                let m = mv.as_object_mut().unwrap();
                m.entry("drag_watt").or_insert(json!(drag_watt));
                m.entry("rolling_watt").or_insert(json!(rolling_watt));
                m.entry("precision_watt").or_insert(json!(precision_watt));
                m.entry("total_watt").or_insert(json!(total_watt));

                // profile_used
                let mut prof = serde_json::Map::new();
                if let Some(v) = profile.cda { prof.insert("cda".into(), json!(v)); }
                if let Some(v) = profile.crr { prof.insert("crr".into(), json!(v)); }
                if let Some(v) = profile.weight_kg { prof.insert("weight_kg".into(), json!(v)); }
                prof.insert("calibrated".into(), json!(profile.calibrated));
                m.entry("profile_used").or_insert(Value::Object(prof));
            }
            _ => {
                let mut prof = serde_json::Map::new();
                if let Some(v) = profile.cda { prof.insert("cda".into(), json!(v)); }
                if let Some(v) = profile.crr { prof.insert("crr".into(), json!(v)); }
                if let Some(v) = profile.weight_kg { prof.insert("weight_kg".into(), json!(v)); }
                prof.insert("calibrated".into(), json!(profile.calibrated));

                obj.insert("metrics".into(), json!({
                    "drag_watt": drag_watt,
                    "rolling_watt": rolling_watt,
                    "precision_watt": precision_watt,
                    "total_watt": total_watt,
                    "profile_used": prof
                }));
            }
        }

        // arrays
        match obj.get_mut("arrays") {
            Some(av) if av.is_object() => {
                let a = av.as_object_mut().unwrap();
                if !a.contains_key("w_drag") { a.insert("w_drag".into(), json!(w_drag)); }
                if !a.contains_key("w_roll") { a.insert("w_roll".into(), json!(w_roll)); }
                if !a.contains_key("w_model") { a.insert("w_model".into(), json!(w_model)); }
            }
            _ => {
                obj.insert("arrays".into(), json!({
                    "w_drag": w_drag,
                    "w_roll": w_roll,
                    "w_model": w_model
                }));
            }
        }

        // toppnivå standardfelt
        obj.entry("source").or_insert(json!("rust_1arg"));
        obj.entry("weather_applied").or_insert(json!(false));

        // debug.reason = "ok" hvis ikke satt
        let dbg = obj.entry("debug").or_insert(json!({}));
        if let Some(d) = dbg.as_object() {
            if !d.contains_key("reason") {
                if let Some(d_mut) = obj.get_mut("debug").and_then(|v| v.as_object_mut()) {
                    d_mut.insert("reason".into(), json!("ok"));
                }
            }
        }
    }

    resp
}

// ──────────────────────────────────────────────────────────────────────────────
// TOLERANT PARSER
// ──────────────────────────────────────────────────────────────────────────────

fn parse_tolerant(json_str: &str) -> Result<(Vec<crate::Sample>, crate::Profile, CoreWeather, bool, &'static str, bool), String> {
    let mut de = json::Deserializer::from_str(json_str);
    let repr: InReprTol = spte::deserialize(&mut de)
        .map_err(|e| format!("parse error (ComputePowerIn tolerant) at {}: {}", e.path(), e))?;

    match repr {
        InReprTol::Object(o) => {
            let estimat_present = o._ignore_estimat.as_ref().map(|v| !v.is_null()).unwrap_or(false);

            let core_samples = o.samples
                .into_iter()
                .map(to_core_sample_tol)
                .collect::<Result<Vec<_>, _>>()?;

            let core_profile = to_core_profile_tol(o.profile, estimat_present)?;
            let w = neutral_weather();

            Ok((core_samples, core_profile, w, estimat_present, "legacy_tolerant", true))
        }
        InReprTol::Triple(TripleTol(samples, p, third)) => {
            let estimat_present = !third.is_null();

            let core_samples = samples
                .into_iter()
                .map(to_core_sample_tol)
                .collect::<Result<Vec<_>, _>>()?;

            let core_profile = to_core_profile_tol(p, estimat_present)?;
            let w = neutral_weather();

            Ok((core_samples, core_profile, w, estimat_present, "legacy_tolerant", true))
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
                let core_samples = obj.samples
                    .into_iter()
                    .map(to_core_sample_tol)
                    .collect::<Result<Vec<_>, _>>()?;

                let mut out = crate::compute_power_with_wind_json(&core_samples, &core_profile, &w);

                let mut dbg = JsonMap::new();
                dbg.insert("repr_kind".into(), Value::from("object"));
                dbg.insert("used_fallback".into(), Value::from(false));
                dbg.insert("estimat_present".into(), Value::from(estimat_present));
                dbg.insert(
                    "weather_source".into(),
                    Value::from(if w.air_temp_c != 0.0 || w.wind_ms != 0.0 || w.air_pressure_hpa != 0.0 || w.wind_dir_deg != 0.0 { "object_weather" } else { "neutral" }),
                );
                dbg.insert("binding".into(), Value::from("py_mod"));

                out = with_debug(out, &dbg);
                out = ensure_metrics_shape(out);

                // berik OBJECT-svar
                if let Ok(resp_val) = serde_json::from_str::<serde_json::Value>(&out) {
                    let enriched = enrich_metrics_on_object(resp_val, &core_samples, &obj.profile);
                    if let Ok(s) = serde_json::to_string(&enriched) { out = s; }
                }

                return Ok(out);
            }
            Err(e) => {
                eprintln!("[OBJ-DEBUG] failed at path {}: {}", track.path().to_string(), e);
            }
        }
    }

    // 1) Prøv untagged enum (OBJECT → Legacy)
    let parsed_primary: Result<(Vec<crate::Sample>, crate::Profile, CoreWeather, bool, &'static str, bool, Option<(Vec<crate::Sample>, ProfileInTol)>) , String> = {
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
                let core_samples = obj.samples
                    .clone()
                    .into_iter()
                    .map(to_core_sample_tol)
                    .collect::<Result<Vec<_>, _>>()?;

                Ok((core_samples.clone(), core_profile, w, estimat_present, "object", false, Some((core_samples, obj.profile.clone()))))
            }
            ComputePowerIn::Legacy(ComputePowerLegacy(samples, profile, third)) => {
                let estimat_present = !third.is_null();
                let w = neutral_weather();
                Ok((samples, profile, w, estimat_present, "triple", true, None))
            }
        }
    };

    // 2) Tolerant fallback ved full feil
    let (samples, profile, weather, estimat_present, repr_kind, used_fallback, obj_opt) = match parsed_primary {
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
            "object" => if weather.air_temp_c != 0.0 || weather.wind_ms != 0.0 || weather.air_pressure_hpa != 0.0 || weather.wind_dir_deg != 0.0 { "object_weather" } else { "neutral" },
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
                let enriched = enrich_metrics_on_object(resp_val, &core_samples_obj, &profile_tol);
                if let Ok(s) = serde_json::to_string(&enriched) { out = s; }
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
    let parsed: ComputePowerInV3StrictRaw = spte::deserialize(&mut de)
        .map_err(|e| format!("parse error (ComputePowerIn v3 strict raw) at {}: {}", e.path(), e))?;

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

    let out = crate::compute_power_with_wind_json(&parsed.samples, &profile, &parsed.weather);
    Ok(out)
}

// ──────────────────────────────────────────────────────────────────────────────
// PyO3-FUNKSJONER — 1-ARG EXPORT (OBJECT → core → enrich → JSON)
// ──────────────────────────────────────────────────────────────────────────────
#[pyfunction]
fn compute_power_with_wind_json(_py: Python<'_>, payload_json: &str) -> PyResult<String> {
    use serde_json::Value as J;

    // --- 1) Parse rå JSON ---
    let raw_val: J = serde_json::from_str(payload_json)
        .map_err(|e| PyValueError::new_err(format!("parse error (raw json): {e}")))?;

    // --- 2) Deserialiser tolerant OBJECT med path-sporing ---
    let obj: ComputePowerObjectV3 = {
        let mut track = spte::Track::new();
        let de = spte::Deserializer::new(raw_val.clone().into_deserializer(), &mut track);
        match Deserialize::deserialize(de) {
            Ok(v) => v,
            Err(e) => {
                let path = track.path().to_string();
                return Err(PyValueError::new_err(
                    format!("parse error (OBJECT tolerant) at {path}: {e}")
                ));
            }
        }
    };

    // --- 3) Konverter felt til kjerneformater ---
    let estimat_present = !obj.estimat.is_null();
    let core_profile = to_core_profile_tol(obj.profile.clone(), estimat_present)
        .map_err(|e| PyValueError::new_err(format!("profile convert error: {e}")))?;
    let weather = obj.weather.unwrap_or_else(neutral_weather);

    let core_samples = obj.samples
        .into_iter()
        .map(to_core_sample_tol)
        .collect::<Result<Vec<_>, _>>()
        .map_err(PyValueError::new_err)?;

    // --- 4) Kall Rust-kjernen (lib.rs) ---
    let core_out_str = crate::compute_power_with_wind_json(&core_samples, &core_profile, &weather);

    // --- 5) Legg til src før retur ---
    let mut val: J = serde_json::from_str(&core_out_str)
        .map_err(|e| PyValueError::new_err(format!("reparse error: {e}")))?;
    val["src"] = J::String("rust_1arg".to_string());

    // --- 6) Returner gyldig JSON-streng ---
    Ok(val.to_string())
}

#[pyfunction]
pub fn compute_power_with_wind_json_v3(_py: Python<'_>, json_str: &str) -> PyResult<String> {
    let mut val: serde_json::Value = call_compute_power_with_wind_from_json_v3(json_str)
        .map_err(PyValueError::new_err)
        .and_then(|s| {
            serde_json::from_str(&s)
                .map_err(|e| PyValueError::new_err(format!("reparse error: {e}")))
        })?;
    val["src"] = serde_json::json!("rust_1arg");
    Ok(val.to_string())
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

    // Eksplicit V3 (strict) for testing
    m.add_function(wrap_pyfunction!(compute_power_with_wind_json_v3, m)?)?;

    // Analyze helper
    m.add_function(wrap_pyfunction!(call_analyze_session_rust_from_json, m)?)?;
    Ok(())
}
