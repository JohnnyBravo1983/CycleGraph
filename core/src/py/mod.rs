use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::{PyAny, PyDict, PyString, PyTuple};
use pyo3::wrap_pyfunction;

use crate::Weather as CoreWeather;

use serde::Deserialize;
use serde_json::{self as json, Value};
use serde_path_to_error as spte;

// ---------- INPUT TYPES (tolerante) ----------

#[derive(Debug, Deserialize)]
struct ProfileIn {
    #[serde(alias = "CdA", alias = "cda")]
    cda: f64,
    #[serde(alias = "Crr", alias = "crr")]
    crr: f64,
    #[serde(alias = "weightKg", alias = "weight_kg")]
    weight_kg: f64,
    #[serde(default)]
    device: String,
    #[serde(default)]
    calibrated: bool,
}

#[derive(Debug, Deserialize)]
#[allow(dead_code)]
struct EstimatIn {
    #[serde(default)]
    mode: String,
    #[serde(default)]
    version: u32,
    #[serde(default)]
    force: bool,
    #[serde(default)]
    notes: Option<String>,
}

#[derive(Debug, Deserialize)]
struct SampleIn {
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
    // Normaliser vind til ÉN nøkkel (aksepter alias inn)
    #[serde(default, alias = "wind_ms", alias = "wind_speed")]
    wind_speed: f64,
    #[serde(default)]
    wind_dir_deg: f64,
    #[serde(default)]
    air_temp_c: f64,
    #[serde(default, alias = "air_pressure_hpa", alias = "pressure_hpa")]
    air_pressure_hpa: f64,
    #[serde(default)]
    humidity: f64,
}

#[derive(Debug, Deserialize)]
struct WeatherIn {
    #[serde(default, alias = "wind_ms", alias = "wind_speed")]
    wind_ms: f64,
    #[serde(default)]
    wind_dir_deg: f64,
    #[serde(default)]
    air_temp_c: f64,
    #[serde(default, alias = "air_pressure_hpa", alias = "pressure_hpa")]
    air_pressure_hpa: f64,
}

#[derive(Debug, Deserialize)]
struct ObjectIn {
    #[serde(default)]
    samples: Vec<SampleIn>,
    profile: ProfileIn,

    // Ekte vær hvis tilstede i objekt-stil
    #[serde(default)]
    weather: Option<WeatherIn>,

    // Estimat-konfig – aksepter flere alias
    #[serde(
        default,
        alias = "estimat",
        alias = "estimate",
        alias = "estimat_cfg",
        alias = "estimate_cfg"
    )]
    estimat_cfg: Option<EstimatIn>,
}

#[derive(Debug, Deserialize)]
#[serde(untagged)]
enum ThirdIn {
    Weather(WeatherIn),
    Estimat(EstimatIn),
}

#[derive(Debug, Deserialize)]
#[serde(untagged)]
enum InRepr {
    // TRIPLE/tuple: (samples, profile, third) – third kan være Weather ELLER Estimat
    Triple((Vec<SampleIn>, ProfileIn, ThirdIn)),
    // Objektstil
    Object(ObjectIn),
}

impl From<(Vec<SampleIn>, ProfileIn, ThirdIn)> for ObjectIn {
    fn from(t: (Vec<SampleIn>, ProfileIn, ThirdIn)) -> Self {
        let (samples, profile, third) = t;
        match third {
            ThirdIn::Weather(w) => ObjectIn {
                samples,
                profile,
                weather: Some(w),
                estimat_cfg: None,
            },
            ThirdIn::Estimat(e) => ObjectIn {
                samples,
                profile,
                weather: None,
                estimat_cfg: Some(e),
            },
        }
    }
}

// ---------- SAFE MAP TIL KJERNETYPER VIA JSON ----------

fn to_core_profile(p: ProfileIn, estimat_present: bool) -> Result<crate::Profile, String> {
    let mut m = serde_json::Map::new();

    // Vanlige felt (snake_case)
    m.insert("cda".into(), Value::from(p.cda));
    m.insert("crr".into(), Value::from(p.crr));
    m.insert("weight_kg".into(), Value::from(p.weight_kg));
    m.insert("device".into(), Value::from(p.device));
    m.insert("calibrated".into(), Value::from(p.calibrated));

    // Viktig: aldri null – sett bool for estimat
    m.insert("estimat".into(), Value::from(estimat_present));

    // Øvrige ev. felter i kjernen (hold null hvis ikke relevante)
    if !m.contains_key("total_weight")    { m.insert("total_weight".into(), Value::Null); }
    if !m.contains_key("bike_type")       { m.insert("bike_type".into(), Value::Null); }
    if !m.contains_key("calibration_mae") { m.insert("calibration_mae".into(), Value::Null); }

    let txt = Value::Object(m).to_string();
    let mut de = json::Deserializer::from_str(&txt);
    spte::deserialize(&mut de).map_err(|e| format!("profile parse at {}: {}", e.path(), e))
}

fn to_core_sample(s: SampleIn) -> Result<crate::Sample, String> {
    let mut m = serde_json::Map::new();

    // Pålagte/vanlige felt
    m.insert("t".into(), Value::from(s.t));
    m.insert("v_ms".into(), Value::from(s.v_ms));
    m.insert("altitude_m".into(), Value::from(s.altitude_m));

    // Opsjonelle felt
    m.insert("heading_deg".into(), Value::from(s.heading_deg));
    m.insert("moving".into(), Value::from(s.moving));
    m.insert("watts".into(), Value::from(s.watts));
    m.insert("rho".into(), Value::from(s.rho));
    m.insert("wind_ms".into(), Value::from(s.wind_speed)); // normalisert
    m.insert("wind_dir_deg".into(), Value::from(s.wind_dir_deg));
    m.insert("air_temp_c".into(), Value::from(s.air_temp_c));
    m.insert("air_pressure_hpa".into(), Value::from(s.air_pressure_hpa));
    m.insert("humidity".into(), Value::from(s.humidity));

    let txt = Value::Object(m).to_string();
    let mut de = json::Deserializer::from_str(&txt);
    spte::deserialize(&mut de).map_err(|e| format!("sample parse at {}: {}", e.path(), e))
}

fn to_core_weather(w: WeatherIn) -> CoreWeather {
    CoreWeather {
        wind_ms: w.wind_ms,
        wind_dir_deg: w.wind_dir_deg,
        air_temp_c: w.air_temp_c,
        air_pressure_hpa: w.air_pressure_hpa,
    }
}

// Les EstimatIn-feltene én gang (stilner “never read”), og lever nøytral weather.
fn to_core_weather_from_estimat(e: EstimatIn) -> CoreWeather {
    let _ = (&e.mode, e.version, e.force, e.notes.as_ref());
    CoreWeather {
        wind_ms: 0.0,
        wind_dir_deg: 0.0,
        air_temp_c: 0.0,
        air_pressure_hpa: 0.0,
    }
}

// ---------- Parsing ----------

fn parse_in_repr(json_str: &str) -> PyResult<ObjectIn> {
    let mut de = json::Deserializer::from_str(json_str);
    let repr: InRepr = spte::deserialize(&mut de).map_err(|e| {
        let path = e.path().to_string();
        PyValueError::new_err(format!("parse error (ComputePowerIn) at {}: {}", path, e))
    })?;

    Ok(match repr {
        InRepr::Object(o) => o,
        InRepr::Triple(t) => ObjectIn::from(t),
    })
}

// ---------- V3 (eksplisitt, for testing) ----------

#[derive(Debug, Deserialize)]
struct ComputePowerInV3 {
    samples: Vec<crate::Sample>,
    profile: crate::Profile,
    weather: crate::Weather,
    #[serde(default)]
    #[allow(dead_code)]
    estimat: serde_json::Value,
}

fn call_compute_power_with_wind_from_json_v3(json_in: &str) -> Result<String, String> {
    let mut de = serde_json::Deserializer::from_str(json_in);
    let parsed: ComputePowerInV3 = spte::deserialize(&mut de)
        .map_err(|e| format!("parse error (ComputePowerIn v3) at {}: {}", e.path(), e))?;

    let out = crate::compute_power_with_wind_json(
        &parsed.samples,
        &parsed.profile,
        &parsed.weather,
    );
    Ok(out)
}

// ---------- PyO3-funksjoner ----------

/// Overload-vennlig binding: aksepterer enten:
/// - 1 arg: JSON-streng / vilkårlig objekt (bruker str(obj))
/// - 3 arg: (samples, profile, third) – serialiseres til JSON, så samme løype.
///
/// Eksporteres under standardnavnet som CLI forventer.
#[pyfunction(name = "compute_power_with_wind_json", signature = (*args, **_kwargs))]
pub fn compute_power_with_wind_json_py(py: Python<'_>, args: &PyTuple, _kwargs: Option<&PyDict>) -> PyResult<String> {
    match args.len() {
        // 1-arg: json string / vilkårlig py-objekt -> str(json)
        1 => {
            let json_in: &PyAny = args.get_item(0)?; // <-- FIX: get_item() returnerer PyResult<&PyAny>
            let json_str: &str = if let Ok(s) = json_in.downcast::<PyString>() {
                s.to_str()?
            } else {
                json_in.str()?.to_str()?
            };

            let obj = parse_in_repr(json_str)?;
            let estimat_present = obj.estimat_cfg.is_some();

            let core_samples = obj.samples.into_iter()
                .map(to_core_sample)
                .collect::<Result<Vec<_>, _>>()
                .map_err(PyValueError::new_err)?;

            let core_profile = to_core_profile(obj.profile, estimat_present)
                .map_err(PyValueError::new_err)?;

            let core_weather: CoreWeather = match (obj.weather, obj.estimat_cfg) {
                (Some(w), _)    => to_core_weather(w),
                (None, Some(e)) => to_core_weather_from_estimat(e),
                (None, None)    => CoreWeather { wind_ms: 0.0, wind_dir_deg: 0.0, air_temp_c: 0.0, air_pressure_hpa: 0.0 },
            };

            Ok(crate::compute_power_with_wind_json(&core_samples, &core_profile, &core_weather))
        }

        // 3-arg: (samples, profile, third) -> bygg JSON via Python json.dumps og kjør samme løype
        3 => {
            let json_mod = py.import("json")?;
            let dumped: Py<PyAny> = json_mod.getattr("dumps")?.call1((args,))?.into();
            let json_str: String = dumped.extract(py)?;

            let obj = parse_in_repr(&json_str)?;
            let estimat_present = obj.estimat_cfg.is_some();

            let core_samples = obj.samples.into_iter()
                .map(to_core_sample)
                .collect::<Result<Vec<_>, _>>()
                .map_err(PyValueError::new_err)?;

            let core_profile = to_core_profile(obj.profile, estimat_present)
                .map_err(PyValueError::new_err)?;

            let core_weather: CoreWeather = match (obj.weather, obj.estimat_cfg) {
                (Some(w), _)    => to_core_weather(w),
                (None, Some(e)) => to_core_weather_from_estimat(e),
                (None, None)    => CoreWeather { wind_ms: 0.0, wind_dir_deg: 0.0, air_temp_c: 0.0, air_pressure_hpa: 0.0 },
            };

            Ok(crate::compute_power_with_wind_json(&core_samples, &core_profile, &core_weather))
        }

        n => Err(PyValueError::new_err(format!(
            "compute_power_with_wind_json: expected 1 or 3 args, got {n}"
        ))),
    }
}

/// V3: eksplisitt JSON-streng med weather (for test/debug, annet navn)
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

// ---------- PyO3-modul ----------

#[pymodule]
fn cyclegraph_core(_py: Python, m: &PyModule) -> PyResult<()> {
    // Eksporter *kun* overload-varianten under standardnavnet
    m.add_function(wrap_pyfunction!(compute_power_with_wind_json_py, m)?)?;

    // V3 tilgjengelig for eksplisitt testing (annet navn)
    m.add_function(wrap_pyfunction!(compute_power_with_wind_json_v3, m)?)?;

    m.add_function(wrap_pyfunction!(call_analyze_session_rust_from_json, m)?)?;
    Ok(())
}
