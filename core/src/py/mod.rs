use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::{PyAny, PyDict, PyString, PyTuple};
use pyo3::wrap_pyfunction;

use serde::Deserialize;
use serde::de::IntoDeserializer; // for Value::into_deserializer()
use serde_json::{self as json, Map as JsonMap, Value};
use serde_path_to_error as spte;

use crate::Weather as CoreWeather;

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
#[derive(Debug, Deserialize)]
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
    estimat: Option<Value>,
}

// OBJECT v3 form: { samples, profile (tolerant), weather?, estimat? }
#[derive(Debug, Deserialize)]
struct ComputePowerObjectV3 {
    samples: Vec<crate::Sample>,
    profile: ProfileInTol, // ← tolerant

    // Valgfritt værfelt – tillates men kan være None
    #[serde(default)]
    weather: Option<crate::Weather>,

    // Aksepter både "estimat" og "estimate", tolerant type
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

#[derive(Debug, Deserialize)]
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
    watts: f64,
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

// Hjelper for triple-varianten i tolerant parser (kan annotere #[serde(default)])
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
    m.insert("watts".into(), Value::from(s.watts));
    m.insert("rho".into(), Value::from(s.rho));
    m.insert("wind_ms".into(), Value::from(s.wind_speed));
    m.insert("wind_dir_deg".into(), Value::from(s.wind_dir_deg));
    m.insert("air_temp_c".into(), Value::from(s.air_temp_c));
    m.insert("air_pressure_hpa".into(), Value::from(s.pressure_hpa));
    m.insert("humidity".into(), Value::from(s.humidity));

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

// Garanter metrics-shape + sikre toppnivånøkler
fn ensure_metrics_shape(mut out_json: String) -> String {
    if let Ok(mut v) = serde_json::from_str::<Value>(&out_json) {
        if let Value::Object(ref mut obj) = v {
            if !obj.contains_key("metrics") {
                let mut m = JsonMap::new();
                for k in ["precision_watt","drag_watt","rolling_watt","total_watt"].iter() {
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
            if let Ok(s) = serde_json::to_string(&v) { out_json = s; }
        }
    }
    out_json
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
/* PRIMÆR PARSING (OBJECT → LEGACY) MED OBJ-DEBUG */
// ──────────────────────────────────────────────────────────────────────────────

fn call_compute_from_json(json_in: &str) -> Result<String, String> {
    // 0) OBJ-DEBUG: prøv ren OBJECT først, med path-forklaring ved feil
    let val: Value = json::from_str(json_in).unwrap_or(Value::Null);
    {
        let mut track = spte::Track::new();
        let de = spte::Deserializer::new(val.clone().into_deserializer(), &mut track);
        let try_obj: Result<ComputePowerObjectV3, _> = Deserialize::deserialize(de);
        match try_obj {
            Ok(obj) => {
                // OBJECT parsed — konverter tolerant profil → kjerneprofil
                let estimat_present = !obj.estimat.is_null();
                let core_profile = to_core_profile_tol(obj.profile, estimat_present)
                    .map_err(|e| format!("profile convert error: {}", e))?;
                let w = obj.weather.unwrap_or_else(neutral_weather);

                let mut out = crate::compute_power_with_wind_json(&obj.samples, &core_profile, &w);

                // debug: OBJECT-path, ikke fallback
                let mut dbg = JsonMap::new();
                dbg.insert("repr_kind".into(), Value::from("object"));
                dbg.insert("used_fallback".into(), Value::from(false));
                dbg.insert("estimat_present".into(), Value::from(estimat_present));
                dbg.insert(
                    "weather_source".into(),
                    Value::from(if w.air_temp_c != 0.0 || w.wind_ms != 0.0 || w.air_pressure_hpa != 0.0 || w.wind_dir_deg != 0.0 {
                        "object_weather"
                    } else {
                        "neutral"
                    }),
                );
                dbg.insert("binding".into(), Value::from("py_mod"));

                out = with_debug(out, &dbg);
                out = ensure_metrics_shape(out);
                return Ok(out);
            }
            Err(e) => {
                eprintln!("[OBJ-DEBUG] failed at path {}: {}", track.path().to_string(), e);
                // faller videre til untagged + tolerant
            }
        }
    }

    // 1) Prøv untagged enum (OBJECT først, deretter Legacy)
    let parsed_primary: Result<(Vec<crate::Sample>, crate::Profile, CoreWeather, bool, &'static str, bool), String> = {
        let mut de = json::Deserializer::from_str(json_in);
        let repr_res: Result<ComputePowerIn, _> = spte::deserialize(&mut de)
            .map_err(|e| format!("parse error (ComputePowerIn primary) at {}: {}", e.path(), e));

        match repr_res? {
            ComputePowerIn::Object(obj) => {
                let estimat_present = !obj.estimat.is_null();
                let core_profile = to_core_profile_tol(obj.profile, estimat_present)
                    .map_err(|e| format!("profile convert error: {}", e))?;
                let w = obj.weather.unwrap_or_else(neutral_weather);
                Ok((obj.samples, core_profile, w, estimat_present, "object", false))
            }
            ComputePowerIn::Legacy(ComputePowerLegacy(samples, profile, third)) => {
                let estimat_present = !third.is_null();
                let w = neutral_weather();
                Ok((samples, profile, w, estimat_present, "triple", true))
            }
        }
    };

    // 2) Hvis primær feiler helt, gjør tolerant fallback
    let (samples, profile, weather, estimat_present, repr_kind, used_fallback) = match parsed_primary {
        Ok(ok) => ok,
        Err(e_primary) => {
            eprintln!("[PRIMARY] parse failed → trying tolerant: {}", e_primary);
            // Tolerant: godtar weightKg/v_mps/alias/ekstrafelt
            let (s, p, w, est, kind, used) = parse_tolerant(json_in)?;
            (s, p, w, est, kind, used)
        }
    };

    let mut out = crate::compute_power_with_wind_json(&samples, &profile, &weather);

    // legg på nyttig debug
    let mut dbg = JsonMap::new();
    dbg.insert("repr_kind".into(), Value::from(repr_kind));
    dbg.insert("used_fallback".into(), Value::from(used_fallback));
    dbg.insert("estimat_present".into(), Value::from(estimat_present));
    dbg.insert(
        "weather_source".into(),
        Value::from(match repr_kind {
            "object" => if weather.air_temp_c != 0.0 || weather.wind_ms != 0.0 || weather.air_pressure_hpa != 0.0 || weather.wind_dir_deg != 0.0 {
                "object_weather"
            } else {
                "neutral"
            },
            "triple" => "neutral",
            "legacy_tolerant" => "neutral",
            _ => "neutral",
        }),
    );
    dbg.insert("binding".into(), Value::from("py_mod"));

    out = with_debug(out, &dbg);
    out = ensure_metrics_shape(out);
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
// PyO3-FUNKSJONER
// ──────────────────────────────────────────────────────────────────────────────

/// Overload-vennlig binding:
///  - 1 arg: JSON-streng ELLER vilkårlig Py-objekt (vi bruker json.dumps(obj) hvis ikke str)
///  - 3 arg: (samples, profile, third) – serialiseres med json.dumps(args) → TRIPLE
#[pyfunction]
#[pyo3(name = "compute_power_with_wind_json", signature = (*args, **_kwargs))]
pub fn compute_power_with_wind_json_py(
    py: Python<'_>,
    args: &PyTuple,
    _kwargs: Option<&PyDict>,
) -> PyResult<String> {
    match args.len() {
        1 => {
            let any: &PyAny = args.get_item(0)?;
            let json_str: String = if any.downcast::<PyString>().is_ok() {
                any.extract::<String>()?
            } else {
                // sikre gyldig JSON selv om det er et dict/list/tuple
                let json_mod = py.import("json")?;
                json_mod.getattr("dumps")?.call1((any,))?.extract()?
            };
            call_compute_from_json(&json_str).map_err(PyValueError::new_err)
        }
        3 => {
            let json_mod = py.import("json")?;
            // dumps(args) → JSON-array [samples, profile, third] (TRIPLE-sti)
            let json_str: String = json_mod.getattr("dumps")?.call1((args,))?.extract()?;
            call_compute_from_json(&json_str).map_err(PyValueError::new_err)
        }
        n => Err(PyValueError::new_err(format!(
            "compute_power_with_wind_json: expected 1 or 3 args, got {n}"
        ))),
    }
}

/// Rå V3-inngang med streng JSON (eksplisitt weather)
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
    // Standard: tolerant/overload-varianten
    m.add_function(wrap_pyfunction!(compute_power_with_wind_json_py, m)?)?;

    // Eksplicit V3 (strict) for testing
    m.add_function(wrap_pyfunction!(compute_power_with_wind_json_v3, m)?)?;

    // Analyze helper
    m.add_function(wrap_pyfunction!(call_analyze_session_rust_from_json, m)?)?;
    Ok(())
}
