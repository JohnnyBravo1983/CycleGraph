#![allow(unused_imports)]

// ───────── Moduler ─────────
pub mod analyze_session;
pub mod calibration;
pub mod metrics;
pub mod models;
pub mod physics;
pub mod smoothing;
pub mod storage;
pub mod weather;
pub mod weather_api;

mod defaults;
use defaults::*;
use serde::{Deserialize, Serialize};
use serde_json::json;

// ───────── Re-exports (beholdt) ─────────
use crate::weather::{normalize_rho, normalize_wind_angle_deg};
pub use crate::calibration::{fit_cda_crr, CalibrationResult};
pub use crate::metrics::{compute_np, w_per_beat};
pub use crate::models::{Profile, Sample, Weather};
pub use crate::physics::{
    compute_indoor_power, compute_power, compute_power_with_wind, estimate_crr, total_mass,
    PowerOutputs, RoundTo,
};
pub use crate::storage::{load_profile, save_profile};

// ───────── Rust-only helper (ingen PyO3) ─────────
pub fn compute_power_with_wind_json(
    samples: &[Sample],
    profile: &Profile,
    weather: &Weather,
) -> String {
    let out = physics::compute_power_with_wind(samples, profile, weather);
    serde_json::json!({
        "watts": out.power,
        "wind_rel": out.wind_rel,
        "v_rel": out.v_rel,
        "calibrated": profile.calibrated,
    })
    .to_string()
}

// ───────── analyze_session_core ─────────
fn analyze_session_core(
    watts: Vec<f64>,
    pulses: Vec<f64>,
    device_watts: Option<bool>,
    wind_angle_deg: Option<f64>,
    air_density_kg_per_m3: Option<f64>,
) -> Result<serde_json::Value, String> {
    if pulses.is_empty() || (!watts.is_empty() && pulses.len() != watts.len()) {
        return Err("Watt og puls må ha samme lengde (dersom watt er tilstede) og puls-listen kan ikke være tom.".to_string());
    }

    let angle_deg = normalize_wind_angle_deg(wind_angle_deg.unwrap_or(30.0));
    let rho = normalize_rho(air_density_kg_per_m3.unwrap_or(1.225));
    let weather_applied = true;

    let no_power_stream = watts.is_empty();
    let device_watts_false = device_watts == Some(false);

    if no_power_stream || device_watts_false {
        let reason = if no_power_stream { "no_power_stream" } else { "device_watts_false" };
        let avg_pulse = pulses.iter().sum::<f64>() / pulses.len() as f64;

        return Ok(json!({
            "mode": "hr_only",
            "no_power_reason": reason,
            "avg_pulse": avg_pulse,
            "avg": 0.0,
            "NP": 0.0,
            "calibrated": "Nei",
            "cda": 0.30,
            "crr": 0.005,
            "mae": 0.0,
            "reason": "hr_only_mode",
            "weather_applied": weather_applied,
            "wind_angle_deg": angle_deg,
            "air_density_kg_per_m3": rho,
            "precision_watt": 0.0,
            "precision_watt_ci": 0.0
        }));
    }

    let avg_watt = watts.iter().copied().sum::<f64>() / watts.len() as f64;
    let avg_pulse = pulses.iter().copied().sum::<f64>() / pulses.len() as f64;
    let np = compute_np(&watts);
    let eff = if avg_pulse == 0.0 { 0.0 } else { avg_watt / avg_pulse };
    let status = if eff < 1.0 { "Lav effekt" } else if avg_pulse > 170.0 { "Høy puls" } else { "OK" };

    let calibration = CalibrationResult {
        cda: 0.30,
        crr: 0.005,
        mae: 0.0,
        calibrated: false,
        reason: Some("calibration_context_missing".to_string()),
    };

    let aero_frac = 0.60_f64;
    let angle_factor = 1.0 + 0.5 * (angle_deg / 180.0);
    let non_aero = (1.0 - aero_frac) * avg_watt;
    let aero_scaled = aero_frac * avg_watt * (rho / 1.225) * angle_factor;
    let pw_adjusted = non_aero + aero_scaled;
    let precision_ci = (avg_watt * 0.055).abs();

    Ok(json!({
        "mode": "normal",
        "effektivitet": eff,
        "status": status,
        "avg_watt": avg_watt,
        "avg_pulse": avg_pulse,
        "avg": avg_watt,
        "NP": np,
        "calibrated": if calibration.calibrated { "Ja" } else { "Nei" },
        "cda": calibration.cda,
        "crr": calibration.crr,
        "mae": calibration.mae,
        "reason": calibration.reason.unwrap_or_default(),
        "weather_applied": weather_applied,
        "wind_angle_deg": angle_deg,
        "air_density_kg_per_m3": rho,
        "precision_watt": pw_adjusted,
        "precision_watt_ci": precision_ci
    }))
}

pub fn analyze_session_rust(
    watts: Vec<f64>,
    pulses: Vec<f64>,
    device_watts: Option<bool>,
) -> Result<serde_json::Value, String> {
    analyze_session_core(watts, pulses, device_watts, None, None)
}
pub use self::analyze_session_rust as analyze_session;

// ───────── PyO3-seksjon ─────────
#[cfg(feature = "python")]
pub(crate) mod pybridge {
    use super::*;
    use pyo3::prelude::*;
    use pyo3::types::{PyAny, PyDict, PyList, PyModule};

    // ---------- Helpers (idiomatisk Option/Result-håndtering) ----------
    fn dict_f64(d: &PyDict, key: &str) -> PyResult<Option<f64>> {
        Ok(d.get_item(key)?.and_then(|a| a.extract::<f64>().ok()))
    }
    fn dict_string(d: &PyDict, key: &str) -> PyResult<Option<String>> {
        Ok(d.get_item(key)?.and_then(|a| a.extract::<String>().ok()))
    }
    fn dict_dict<'py>(d: &'py PyDict, key: &str) -> PyResult<Option<&'py PyDict>> {
        match d.get_item(key)? {
            Some(a) => Ok(Some(a.downcast::<PyDict>()?)),
            None => Ok(None),
        }
    }
    /// Henter stream som liste av f64 (tom vektor hvis ikke finnes)
    fn dict_stream_f64(d: &PyDict, key: &str) -> PyResult<Vec<f64>> {
        match d.get_item(key)? {
            Some(a) => {
                if let Ok(v) = a.extract::<Vec<f64>>() {
                    return Ok(v);
                }
                let list = a.downcast::<PyList>()?;
                let mut out = Vec::with_capacity(list.len());
                for item in list.iter() {
                    if let Ok(v) = item.extract::<f64>() {
                        out.push(v);
                    } else if let Ok(i) = item.extract::<i64>() {
                        out.push(i as f64);
                    }
                }
                Ok(out)
            }
            None => Ok(vec![]),
        }
    }

    #[pyfunction]
    pub fn calculate_efficiency_series(
        watts: Vec<f64>,
        pulses: Vec<f64>,
    ) -> PyResult<(f64, String, Vec<f64>, Vec<String>)> {
        if watts.is_empty() || pulses.is_empty() || watts.len() != pulses.len() {
            return Err(pyo3::exceptions::PyValueError::new_err(
                "Watt og puls-lister må ha samme lengde og ikke være tomme.",
            ));
        }
        let avg_watt = watts.iter().sum::<f64>() / watts.len() as f64;
        let avg_pulse = pulses.iter().sum::<f64>() / pulses.len() as f64;
        let avg_eff = if avg_pulse == 0.0 { 0.0 } else { avg_watt / avg_pulse };

        let session_status = if avg_eff < 1.0 {
            "Lav effekt – vurder å øke tråkkfrekvens eller intensitet.".to_string()
        } else if avg_pulse > 170.0 {
            "Høy puls – vurder lengre restitusjon.".to_string()
        } else {
            "OK – treningen ser balansert ut.".to_string()
        };

        let mut per_point_eff = Vec::with_capacity(watts.len());
        let mut per_point_status = Vec::with_capacity(watts.len());
        for (w, p) in watts.iter().zip(pulses.iter()) {
            let eff = if *p == 0.0 { 0.0 } else { w / p };
            per_point_eff.push(eff);
            let status = if eff < 1.0 { "Lav effekt" } else if *p > 170.0 { "Høy puls" } else { "OK" };
            per_point_status.push(status.to_string());
        }

        Ok((avg_eff, session_status, per_point_eff, per_point_status))
    }

    /// Hjelpefunksjon: konverterer en Python-sekvens til Vec<f64>
    fn py_seq_to_vec_f64(seq: &PyAny) -> PyResult<Vec<f64>> {
        let list = seq.downcast::<PyList>()?;
        list.iter().map(|x| x.extract::<f64>()).collect()
    }

    /// Nytt, høynivå API: tar et `session`-dict fra Python
    #[pyfunction]
    pub fn analyze_session(py: Python<'_>, session: &PyAny) -> PyResult<PyObject> {
        // Forvent et dict-lignende Python-objekt
        let sess_dict = session.downcast::<PyDict>().map_err(|_| {
            pyo3::exceptions::PyValueError::new_err("Forventet et dict-lignende 'session'-objekt")
        })?;

        // streams
        let streams_any = match sess_dict.get_item("streams")? {
            Some(v) => v,
            None => {
                return Err(pyo3::exceptions::PyValueError::new_err(
                    "Fant ikke serier i økta. Forventet 'session[\"streams\"]' med 'watts' og 'hr'.",
                ))
            }
        };
        let streams = streams_any.downcast::<PyDict>().map_err(|_| {
            pyo3::exceptions::PyValueError::new_err("'session[\"streams\"]' må være et dict")
        })?;

        // watts
        let watts_any = match streams.get_item("watts")? {
            Some(v) => v,
            None => {
                return Err(pyo3::exceptions::PyValueError::new_err(
                    "Mangler 'watts' i session['streams'] (forventet session['streams']['watts'])",
                ))
            }
        };
        let watts = py_seq_to_vec_f64(watts_any).map_err(|_| {
            pyo3::exceptions::PyValueError::new_err(
                "'session[\"streams\"][\"watts\"]' må være en liste av tall (f64)",
            )
        })?;

        // pulses/hr
        let pulses_any = if let Some(v) = streams.get_item("pulses")? {
            v
        } else if let Some(v) = streams.get_item("hr")? {
            v
        } else {
            return Err(pyo3::exceptions::PyValueError::new_err(
                "Mangler 'pulses' eller 'hr' i session['streams']",
            ));
        };
        let pulses = py_seq_to_vec_f64(pulses_any).map_err(|_| {
            pyo3::exceptions::PyValueError::new_err(
                "'session[\"streams\"][\"pulses\"/\"hr\"]' må være en liste av tall (f64)",
            )
        })?;

        // device_watts (Option<bool>)
        let device_watts: Option<bool> = match sess_dict.get_item("device_watts")? {
            Some(x) => Some(x.extract::<bool>()?),
            None => None,
        };

        // Vindvinkel (Option<f64>) – toppnivå eller under weather.wind_rel_angle_deg
        let wind_angle_deg: Option<f64> = if let Some(x) = sess_dict.get_item("wind_angle_deg")? {
            Some(x.extract::<f64>()?)
        } else if let Some(w) = sess_dict.get_item("weather")? {
            let wd = w.downcast::<PyDict>()?;
            if let Some(a) = wd.get_item("wind_rel_angle_deg")? {
                Some(a.extract::<f64>()?)
            } else {
                None
            }
        } else {
            None
        };

        // Lufttetthet (Option<f64>) – toppnivå eller under weather.air_density_kg_per_m3
        let air_density_kg_per_m3: Option<f64> =
            if let Some(x) = sess_dict.get_item("air_density_kg_per_m3")? {
                Some(x.extract::<f64>()?)
            } else if let Some(w) = sess_dict.get_item("weather")? {
                let wd = w.downcast::<PyDict>()?;
                if let Some(a) = wd.get_item("air_density_kg_per_m3")? {
                    Some(a.extract::<f64>()?)
                } else {
                    None
                }
            } else {
                None
            };

        // Kjør kjernelogikk
        let result = super::analyze_session_core(
            watts,
            pulses,
            device_watts,
            wind_angle_deg,
            air_density_kg_per_m3,
        )
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(e))?;

        // Returner JSON-resultatet som et Python-dict
        let json_str = result.to_string();
        let obj = PyModule::import(py, "json")?
            .getattr("loads")?
            .call1((json_str,))?;
        Ok(obj.into_py(py))
    }

    /// Bakoverkompatibel test-hook med den gamle signaturen
    #[pyfunction]
    #[pyo3(signature = (watts, pulses, device_watts=None, wind_angle_deg=None, air_density_kg_per_m3=None))]
    pub fn analyze_session_py(
        py: Python<'_>,
        watts: Vec<f64>,
        pulses: Vec<f64>,
        device_watts: Option<bool>,
        wind_angle_deg: Option<f64>,
        air_density_kg_per_m3: Option<f64>,
    ) -> PyResult<PyObject> {
        let result = super::analyze_session_core(
            watts,
            pulses,
            device_watts,
            wind_angle_deg,
            air_density_kg_per_m3,
        )
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(e))?;
        let json_str = result.to_string();
        let obj = PyModule::import(py, "json")?
            .getattr("loads")?
            .call1((json_str,))?;
        Ok(obj.into_py(py))
    }

    #[pyclass]
    #[derive(Debug, Clone, Serialize, Deserialize)]
    pub struct PyProfile {
        #[pyo3(get)]
        #[serde(alias = "totalWeight", alias = "TotalWeight", alias = "weight_kg", alias = "WeightKg")]
        pub total_weight: f64,

        #[pyo3(get)]
        #[serde(alias = "bikeType", alias = "BikeType")]
        pub bike_type: String,

        #[pyo3(get)]
        #[serde(alias = "Crr", alias = "crr_used", alias = "crr")]
        pub crr: f64,

        #[pyo3(get)]
        pub estimat: bool,
    }

    impl Default for PyProfile {
        fn default() -> Self {
            Self {
                total_weight: 78.0,
                bike_type: "road".to_string(),
                crr: 0.005,
                estimat: true,
            }
        }
    }

    #[pyfunction]
    pub fn profile_from_json(json: &str) -> PyProfile {
        if let Ok(mut parsed) = serde_json::from_str::<crate::models::Profile>(json) {
            let mut used_default = false;

            let total_weight = match parsed.total_weight.take() {
                Some(v) if v > 0.0 => v,
                _ => { used_default = true; 78.0 }
            };
            let bike_type = match parsed.bike_type.take() {
                Some(s) if !s.trim().is_empty() => s,
                _ => { used_default = true; "road".to_string() }
            };
            let crr = match parsed.crr.take() {
                Some(v) if v > 0.0 => v,
                _ => { used_default = true; 0.005 }
            };

            return PyProfile {
                total_weight,
                bike_type,
                crr,
                estimat: parsed.estimat || used_default,
            };
        }

        if let Ok(mut p) = serde_json::from_str::<PyProfile>(json) {
            let mut used_default = false;
            if p.total_weight <= 0.0 { p.total_weight = 78.0; used_default = true; }
            if p.bike_type.trim().is_empty() { p.bike_type = "road".to_string(); used_default = true; }
            if p.crr <= 0.0 { p.crr = 0.005; used_default = true; }
            p.estimat = p.estimat || used_default;
            return p;
        }

        PyProfile::default()
    }

    #[pyfunction]
    pub fn analyze_session_with_profile(
        py: Python<'_>,
        session: &PyDict,
        profile: Option<&PyDict>
    ) -> PyResult<PyObject> {
        // 1) parse profil
        let prof = profile.unwrap_or_else(|| PyDict::new(py));
        let cda    = dict_f64(prof, "CdA")?.unwrap_or(0.30);
        let crr    = dict_f64(prof, "Crr")?.unwrap_or(0.005);
        let weight = dict_f64(prof, "weight_kg")?.unwrap_or(80.0);
        let _device = dict_string(prof, "device")?.unwrap_or_else(|| "unknown".to_string());

        // 2) parse weather ρ (fallback 1.225)
        let weather = dict_dict(session, "weather")?;
        let rho = match weather {
            Some(w) => dict_f64(w, "air_density_kg_per_m3")?.unwrap_or(1.225),
            None => 1.225,
        };

        // 3) trekk ut serier
        let streams = dict_dict(session, "streams")?;
        let (vel, alt): (Vec<f64>, Vec<f64>) = match streams {
            Some(s) => (
                dict_stream_f64(s, "velocity_smooth")?,
                dict_stream_f64(s, "altitude")?
            ),
            None => (vec![], vec![]),
        };

        // 4) beregn komponenter over tid
        let comp = physics::compute_components(&vel, &alt, cda, crr, weight, rho);

        // 5) aggreger (forutsetter metrics f64 + pub)
        // NB: Du legger til mean_f64 / robust_ci_f64 i metrics.rs i parallell-oppgaven.
        let mean_total = metrics::mean_f64(&comp.total);      // precision_watt
        let ci         = metrics::robust_ci_f64(&comp.total); // precision_watt_ci (1.4826*MAD)
        let mean_drag  = metrics::mean_f64(&comp.drag);
        let mean_roll  = metrics::mean_f64(&comp.rolling);
        let aero_fraction = if mean_total > 0.0 { mean_drag / mean_total } else { 0.0 };

        // 6) bygg resultat
        let out = PyDict::new(py);
        out.set_item("precision_watt", mean_total)?;
        out.set_item("precision_watt_ci", ci)?;
        out.set_item("total_watt", mean_total)?;
        out.set_item("drag_watt", mean_drag)?;
        out.set_item("rolling_watt", mean_roll)?;
        out.set_item("aero_fraction", aero_fraction)?;
        out.set_item("profile", prof)?;
        out.set_item("weather_applied", true)?;
        out.set_item("reason", "ok_profile_driven")?;
        Ok(out.to_object(py))
    }

    #[pyfunction]
    pub fn rust_calibrate_session(
        watts: Vec<f64>,
        speed_ms: Vec<f64>,
        altitude_m: Vec<f64>,
        profile_json: &str,
        weather_json: &str,
    ) -> PyResult<pyo3::Py<pyo3::PyAny>> {
        use pyo3::{types::PyDict, Python};

        let n = watts.len().min(speed_ms.len()).min(altitude_m.len());
        if n == 0 {
            return Err(pyo3::exceptions::PyValueError::new_err("Empty inputs for calibration"));
        }

        let mut profile: crate::models::Profile =
            serde_json::from_str(profile_json).unwrap_or_default();

        let weather: crate::models::Weather =
            serde_json::from_str(weather_json).unwrap_or(crate::models::Weather {
                wind_ms: 0.0,
                wind_dir_deg: 0.0,
                air_temp_c: 15.0,
                air_pressure_hpa: 1013.0,
            });

        let mut samples = Vec::with_capacity(n);
        for i in 0..n {
            samples.push(crate::models::Sample {
                t: i as f64,
                v_ms: speed_ms[i],
                altitude_m: altitude_m[i],
                heading_deg: 0.0,
                moving: true,
                device_watts: Some(watts[i]),
                ..Default::default()
            });
        }

        let mut result = crate::calibration::fit_cda_crr(&samples, &watts[..n], &profile, &weather);

        // Soft heuristics (beholdt)
        {
            const MIN_SAMPLES: usize = 30;
            const MIN_V_SPAN_MS: f64 = 1.0;
            const MIN_A_SPAN_M: f64 = 3.0;
            const MIN_MEAN_W: f64 = 50.0;
            const MAX_MAE_OK: f64 = 150.0;

            let n_ok = n >= MIN_SAMPLES;

            let (v_min, v_max) = speed_ms[..n]
                .iter()
                .fold((f64::INFINITY, f64::NEG_INFINITY), |(mn, mx), &v| (mn.min(v), mx.max(v)));
            let v_span = if v_min.is_finite() && v_max.is_finite() { v_max - v_min } else { 0.0 };

            let (a_min, a_max) = altitude_m[..n]
                .iter()
                .fold((f64::INFINITY, f64::NEG_INFINITY), |(mn, mx), &a| (mn.min(a), mx.max(a)));
            let a_span = if a_min.is_finite() && a_max.is_finite() { a_max - a_min } else { 0.0 };

            let w_mean = if n > 0 {
                watts[..n].iter().copied().sum::<f64>() / (n as f64)
            } else { 0.0 };

            let variation_ok = v_span >= MIN_V_SPAN_MS && a_span >= MIN_A_SPAN_M && w_mean >= MIN_MEAN_W;
            let mae_ok = result.mae.is_finite() && result.mae < MAX_MAE_OK;

            if !result.calibrated && n_ok && variation_ok && mae_ok {
                result.calibrated = true;
                if result.reason.is_none() {
                    result.reason = Some("soft_ok_window".to_string());
                }
            }
        }

        profile.cda = Some(result.cda);
        profile.crr = Some(result.crr);
        profile.calibrated = result.calibrated;
        profile.calibration_mae = Some(result.mae);
        profile.estimat = false;

        Python::with_gil(|py| {
            let out = PyDict::new(py);
            out.set_item("calibrated", result.calibrated)?;
            out.set_item("cda", result.cda)?;
            out.set_item("crr", result.crr)?;
            out.set_item("mae", result.mae)?;
            if let Some(r) = result.reason {
                out.set_item("reason", r)?;
            } else {
                out.set_item("reason", py.None())?;
            }
            out.set_item("profile", serde_json::to_string(&profile).unwrap())?;
            Ok(out.into())
        })
    }

    #[pyfunction(name = "compute_power_with_wind_json")]
    pub fn compute_power_with_wind_json_py(
        samples_json: &str,
        profile_json: &str,
        weather_json: &str,
    ) -> PyResult<String> {
        use pyo3::exceptions::PyValueError;

        let samples: Vec<Sample> = serde_json::from_str(samples_json)
            .map_err(|e| PyValueError::new_err(format!("samples parse error: {e}")))?;
        let profile: Profile = serde_json::from_str(profile_json)
            .map_err(|e| PyValueError::new_err(format!("profile parse error: {e}")))?;
        let weather: Weather = serde_json::from_str(weather_json)
            .map_err(|e| PyValueError::new_err(format!("weather parse error: {e}")))?;

        let out = physics::compute_power_with_wind(&samples, &profile, &weather);
        let s = serde_json::to_string(&serde_json::json!({
            "watts": out.power,
            "wind_rel": out.wind_rel,
            "v_rel": out.v_rel,
        }))
        .map_err(|e| PyValueError::new_err(format!("serialize error: {e}")))?;
        Ok(s)
    }
}

// ───── Python-eksport (PyO3) ─────
#[cfg(feature = "python")]
use pyo3::prelude::*;
#[cfg(feature = "python")]
use pyo3::wrap_pyfunction;

#[cfg(feature = "python")]
#[pymodule]
fn cyclegraph_core(_py: Python<'_>, m: &PyModule) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(pybridge::compute_power_with_wind_json_py, m)?)?;
    m.add_function(wrap_pyfunction!(pybridge::calculate_efficiency_series, m)?)?;
    m.add_function(wrap_pyfunction!(pybridge::analyze_session_py, m)?)?;
    m.add_function(wrap_pyfunction!(pybridge::profile_from_json, m)?)?;
    m.add_function(wrap_pyfunction!(pybridge::rust_calibrate_session, m)?)?;
    m.add_class::<pybridge::PyProfile>()?;
    m.add_function(wrap_pyfunction!(pybridge::analyze_session, m)?)?;
    m.add_function(wrap_pyfunction!(crate::pybridge::analyze_session_with_profile, m)?)?;

    Ok(())
}

// ================== Tests (Rust-only) ==================
#[cfg(test)]
mod m7_tests {
    use crate::metrics;
    use std::{iter, path::PathBuf, time::Instant};

    fn const_series(val: f32, n: usize) -> Vec<f32> { iter::repeat(val).take(n).collect() }
    fn ramp_series(start: f32, step: f32, n: usize) -> Vec<f32> { (0..n).map(|i| start + step * (i as f32)).collect() }

    #[test]
    fn np_if_vi_constant_power() {
        let hz = 1.0;
        let p = const_series(200.0, 1800);
        let np = metrics::np(&p, hz);
        let avg = 200.0;
        let ftp = 250.0;
        let iff = metrics::intensity_factor(np, ftp);
        let vi = metrics::variability_index(np, avg);
        assert!((np - avg).abs() < 1.0);
        assert!((vi - 1.0).abs() < 0.02);
        assert!(iff > 0.0 && iff < 2.0);
    }

    #[test]
    fn pa_hr_monotone_effort_reasonable() {
        let hz = 1.0;
        let p = ramp_series(120.0, 0.05, 3600);
        let hr = ramp_series(120.0, 0.03, 3600);
        let pa = metrics::pa_hr(&hr, &p, hz);
        assert!(pa > 0.95 && pa < 1.08);
    }

    #[test]
    fn w_per_beat_defined_when_hr_power_present() {
        let p = const_series(210.0, 600);
        let hr = const_series(150.0, 600);
        let wpb = metrics::w_per_beat(&p, &hr);
        assert!(wpb > 1.0 && wpb < 2.0);
    }

    // ---------- IO structs for golden (Uten serde_derive) ----------
    #[derive(Debug, Clone, Copy)]
    struct ExpField { value: f32, tol: f32 }

    #[derive(Debug, Clone)]
    struct Expected {
        #[allow(dead_code)]
        ftp: Option<f32>,
        np: Option<ExpField>,
        i_f: Option<ExpField>,
        vi: Option<ExpField>,
        pa_hr: Option<ExpField>,
        w_per_beat: Option<ExpField>,
    }

    fn manifest_path(p: &str) -> PathBuf { PathBuf::from(env!("CARGO_MANIFEST_DIR")).join(p) }

    // Robust delimiter-sjekk (komma vs semikolon)
    fn sniff_delimiter(s: &str) -> u8 {
        let commas = s.matches(',').count();
        let semis = s.matches(';').count();
        if semis > commas { b';' } else { b',' }
    }

    // Robust tall-parser (1,23 / 1.23 / "200 W")
    fn parse_num(s: &str) -> Option<f32> {
        let t = s.trim();
        if t.is_empty() { return None; }
        let t = t.trim_matches(|c| c == '"' || c == '\'').replace(',', ".");
        let mut buf = String::new();
        let mut seen_digit = false;
        for ch in t.chars() {
            if ch.is_ascii_digit() || ch == '.' || ch == '-' || ch == '+' || ch == 'e' || ch == 'E' {
                buf.push(ch);
                if ch.is_ascii_digit() { seen_digit = true; }
            } else if seen_digit { break; }
        }
        if buf.is_empty() { return None; }
        buf.parse::<f32>().ok()
    }

    fn find_col(headers: &csv::StringRecord, candidates: &[&str]) -> Option<usize> {
        let lower: Vec<String> = headers.iter().map(|h| h.trim().to_ascii_lowercase()).collect();
        for key in candidates {
            let k = key.to_ascii_lowercase();
            if let Some((idx, _)) = lower.iter().enumerate().find(|(_, h)| **h == k) { return Some(idx); }
        }
        for key in candidates {
            let k = key.to_ascii_lowercase();
            if let Some((idx, _)) = lower.iter().enumerate().find(|(_, h)| h.contains(&k)) { return Some(idx); }
        }
        None
    }

    fn read_streams(csv_path: &str) -> (Vec<f32>, Vec<f32>) {
        let full = manifest_path(csv_path);
        let content = std::fs::read_to_string(&full).expect("open csv text");
        let delim = sniff_delimiter(&content);
        let mut rdr = csv::ReaderBuilder::new()
            .delimiter(delim)
            .has_headers(true)
            .flexible(true)
            .from_reader(content.as_bytes());
        let headers = rdr.headers().expect("headers").clone();
        let i_hr = find_col(&headers, &["hr","heartrate","heart_rate","bpm","pulse"]).expect("no HR column in golden csv");
        let i_pw = find_col(&headers, &["device_watts","watts","power","power_w","pwr"]).expect("no power column in golden csv");
        let i_mask = find_col(&headers, &["moving","in_segment","valid","ok"]);
        let mut hr = Vec::<f32>::new();
        let mut p = Vec::<f32>::new();
        for rec in rdr.records() {
            let r = rec.expect("row");
            if let Some(mi) = i_mask {
                if let Some(mv) = r.get(mi) {
                    let t = mv.trim().to_ascii_lowercase();
                    if !matches!(t.as_str(),"1"|"true"|"yes"|"y"|"ok") { continue; }
                }
            }
            let hr_opt = r.get(i_hr).and_then(parse_num);
            let pw_opt = r.get(i_pw).and_then(parse_num);
            let (Some(h), Some(w)) = (hr_opt, pw_opt) else { continue };
            if w <= 0.0 { continue; }
            hr.push(h);
            p.push(w);
        }
        (p, hr)
    }

    fn parse_expected(json_text: &str) -> Expected {
        let v: serde_json::Value = serde_json::from_str(json_text).unwrap();
        let gf = |obj: &serde_json::Value, key: &str| -> Option<ExpField> {
            let o = obj.get(key)?; let val = o.get("value")?.as_f64()? as f32; let tol = o.get("tol")?.as_f64()? as f32;
            Some(ExpField { value: val, tol })
        };
        Expected {
            ftp: v.get("ftp").and_then(|x| x.as_f64()).map(|x| x as f32),
            np: gf(&v, "np"),
            i_f: gf(&v, "if"),
            vi: gf(&v, "vi"),
            pa_hr: gf(&v, "pa_hr"),
            w_per_beat: gf(&v, "w_per_beat"),
        }
    }

    #[test]
    fn golden_sessions_match_with_tolerance() {
        let cases = [
            ("tests/golden/data/sess01_streams.csv","tests/golden/expected/sess01_expected.json"),
            ("tests/golden/data/sess02_streams.csv","tests/golden/expected/sess02_expected.json"),
            ("tests/golden/data/sess03_streams.csv","tests/golden/expected/sess03_expected.json"),
        ];
        for (csv_path, json_path) in cases {
            let (p, hr) = read_streams(csv_path);
            assert!(!p.is_empty(), "empty power series for {}", csv_path);

            let hz = 1.0;
            let np = crate::metrics::np(&p, hz);
            let avg = p.iter().copied().sum::<f32>() / (p.len() as f32).max(1.0);
            let ftp = 250.0;
            let iff = crate::metrics::intensity_factor(np, ftp);
            let vi = crate::metrics::variability_index(np, avg);
            let pa = crate::metrics::pa_hr(&hr, &p, hz);
            let wpb = crate::metrics::w_per_beat(&p, &hr);

            let expected: Expected = parse_expected(&std::fs::read_to_string(manifest_path(json_path)).unwrap());

            let f = expected.w_per_beat.as_ref().unwrap();
            assert!((wpb - f.value).abs() <= f.tol, "WpB {} vs {}±{} ({})", wpb, f.value, f.tol, csv_path);

            let f = expected.np.as_ref().unwrap();
            assert!((np - f.value).abs() <= f.tol, "NP {} vs {}±{} ({})", np, f.value, f.tol, csv_path);

            let f = expected.i_f.as_ref().unwrap();
            assert!((iff - f.value).abs() <= f.tol, "IF {} vs {}±{} ({})", iff, f.value, f.tol, csv_path);

            let f = expected.vi.as_ref().unwrap();
            assert!((vi - f.value).abs() <= f.tol, "VI {} vs {}±{} ({})", vi, f.value, f.tol, csv_path);

            let f = expected.pa_hr.as_ref().unwrap();
            assert!((pa - f.value).abs() <= f.tol, "PaHR {} vs {}±{} ({})", pa, f.value, f.tol, csv_path);
        }
    }

    #[test]
    fn perf_guard_two_hours_one_hz() {
        let n = 2 * 60 * 60;
        let hz = 1.0;
        let p: Vec<f32> = (0..n).map(|i| 180.0 + ((i % 60) as f32) * 0.5).collect();
        let hr: Vec<f32> = (0..n).map(|i| 140.0 + ((i % 90) as f32) * 0.3).collect();
        let t0 = Instant::now();
        let np = crate::metrics::np(&p, hz);
        let _if = crate::metrics::intensity_factor(np, 250.0);
        let _vi = crate::metrics::variability_index(np, 200.0);
        let _pa = crate::metrics::pa_hr(&hr, &p, hz);
        let _wb = crate::metrics::w_per_beat(&p, &hr);
        let dt = t0.elapsed();
        let limit_ms: u128 = std::env::var("CG_PERF_MS").ok().and_then(|s| s.parse::<u128>().ok()).unwrap_or(200);
        assert!(dt.as_millis() <= limit_ms, "perf guard: {} ms > {} ms", dt.as_millis(), limit_ms);
    }
}

// ================== Python-avhengig test ==================
#[cfg(all(test, feature = "python"))]
mod py_tests {
    use super::*;
    use pyo3::prelude::*;
    #[test]
    fn test_fallback_to_hr_only() {
        pyo3::prepare_freethreaded_python();
        let watts = vec![];
        let pulses = vec![120.0, 125.0, 130.0];
        let device_watts = Some(true);
        pyo3::Python::with_gil(|py| -> pyo3::PyResult<()> {
            let result = crate::pybridge::analyze_session_py(py, watts.clone(), pulses.clone(), device_watts, None, None).unwrap();
            let result_ref = result.as_ref(py);
            let mode: &str = result_ref.get_item("mode")?.extract()?;
            let reason: &str = result_ref.get_item("no_power_reason")?.extract()?;
            assert_eq!(mode, "hr_only");
            assert_eq!(reason, "no_power_stream");
            Ok(())
        }).unwrap();
    }
}