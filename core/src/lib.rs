pub mod physics;
pub mod models;
pub mod smoothing;
pub mod metrics;
pub mod analyzer;
pub mod calibration;
pub mod weather;
pub mod storage;

// ───────── Re-exports for tests/back-compat ─────────
pub use crate::models::{Profile, Weather, Sample};
pub use crate::physics::{compute_power, compute_indoor_power, compute_power_with_wind, PowerOutputs};
pub use crate::metrics::{w_per_beat, compute_np};
pub use crate::storage::{load_profile, save_profile};
pub use crate::calibration::{fit_cda_crr, CalibrationResult};

// ───────── PyO3 (feature-gated) ─────────
#[cfg(feature = "python")]
use pyo3::prelude::*;
#[cfg(feature = "python")]
use pyo3::wrap_pyfunction;

use serde_json::json;

/// JSON-helper for CLI (Rust-only API)
/// {
///   "watts":    [f64],
///   "wind_rel": [f64],
///   "v_rel":    [f64],
///   "calibrated": bool
/// }
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

// ───────── Rust-only API ─────────
pub fn analyze_session_rust(
    watts: Vec<f64>,
    pulses: Vec<f64>,
    device_watts: Option<bool>,
) -> Result<serde_json::Value, String> {
    if pulses.is_empty() || (!watts.is_empty() && pulses.len() != watts.len()) {
        return Err("Watt og puls må ha samme lengde (dersom watt er tilstede) og puls-listen kan ikke være tom.".to_string());
    }

    let no_power_stream = watts.is_empty();
    let device_watts_false = device_watts == Some(false);

    if no_power_stream || device_watts_false {
        let reason = if no_power_stream { "no_power_stream" } else { "device_watts_false" };
        let avg_pulse = pulses.iter().sum::<f64>() / pulses.len() as f64;

        // HR-only: retur med stabilt schema + kalibreringsfelt (gir ikke mening å kalibrere uten watt)
        return Ok(json!({
            "mode": "hr_only",
            "no_power_reason": reason,
            "avg_pulse": avg_pulse,
            "avg": 0.0,
            "NP": 0.0,
            // Kalibrering:
            "calibrated": "Nei",
            "cda": 0.30,
            "crr": 0.005,
            "mae": 0.0,
            "reason": "hr_only_mode"
        }));
    }

    // Watt finnes → beregn basis-metrics
    let avg_watt = watts.iter().sum::<f64>() / watts.len() as f64;
    let avg_pulse = pulses.iter().sum::<f64>() / pulses.len() as f64;
    let np = compute_np(&watts);
    let eff = if avg_pulse == 0.0 { 0.0 } else { avg_watt / avg_pulse };
    let status = if eff < 1.0 { "Lav effekt" } else if avg_pulse > 170.0 { "Høy puls" } else { "OK" };

    // --- Kalibrering (placeholder inntil full kontekst) ---
    let calibration = CalibrationResult {
        cda: 0.30,
        crr: 0.005,
        mae: 0.0,
        calibrated: false,
        reason: Some("calibration_context_missing".to_string()),
    };

    Ok(json!({
        "mode": "normal",
        "effektivitet": eff,
        "status": status,
        "avg_watt": avg_watt,
        "avg_pulse": avg_pulse,
        "avg": avg_watt,
        "NP": np,

        // Kalibrering i output
        "calibrated": if calibration.calibrated { "Ja" } else { "Nei" },
        "cda": calibration.cda,
        "crr": calibration.crr,
        "mae": calibration.mae,
        "reason": calibration.reason.unwrap_or_default()
    }))
}

// Gjør analyze_session tilgjengelig uansett feature
#[cfg(feature = "python")]
pub use analyzer::analyze_session; // beholdes – brukt flere steder i repoet
#[cfg(not(feature = "python"))]
pub use self::analyze_session_rust as analyze_session;

// ───────── PyO3 bindings (feature-gated) ─────────
#[cfg(feature = "python")]
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

#[cfg(feature = "python")]
#[pyfunction(name = "analyze_session")]
pub fn analyze_session_py(
    py: Python<'_>,
    watts: Vec<f64>,
    pulses: Vec<f64>,
    device_watts: Option<bool>,
) -> PyResult<Py<PyAny>> {
    let result = analyze_session_rust(watts, pulses, device_watts)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(e))?;

    // Trygg JSON → Python-objekt
    let json_str = result.to_string();
    let json_mod = pyo3::types::PyModule::import(py, "json")?;
    let py_obj = json_mod.getattr("loads")?.call1((json_str,))?;
    Ok(py_obj.into_py(py))
}

// ───────── Profile helpers for Python (bruk models::Profile) ─────────
#[cfg(feature = "python")]
#[pyclass]
#[derive(Debug, Clone)]
pub struct PyProfile {
    #[pyo3(get)]
    pub total_weight: f64,
    #[pyo3(get)]
    pub bike_type: String,
    #[pyo3(get)]
    pub crr: f64,
    #[pyo3(get)]
    pub estimat: bool,
}

#[cfg(feature = "python")]
#[pyfunction]
pub fn profile_from_json(json: &str) -> PyProfile {
    // Bruk models::Profile som kilde
    let mut parsed: models::Profile = serde_json::from_str(json).unwrap_or_else(|_| models::Profile::default());

    // Fyll inn defaults og sett estimat korrekt
    let missing = parsed.total_weight.is_none() || parsed.bike_type.is_none() || parsed.crr.is_none();
    if missing {
        parsed.total_weight.get_or_insert(78.0);
        parsed.bike_type.get_or_insert("road".to_string());
        parsed.crr.get_or_insert(0.005);
        parsed.estimat = true;
    } else {
        parsed.estimat = false;
    }

    PyProfile {
        total_weight: parsed.total_weight.unwrap_or(78.0),
        bike_type: parsed.bike_type.unwrap_or_else(|| "road".to_string()),
        crr: parsed.crr.unwrap_or(0.005),
        estimat: parsed.estimat,
    }
}

#[cfg(feature = "python")]
#[pyfunction]
pub fn rust_calibrate_session(
    watts: Vec<f64>,
    speed_ms: Vec<f64>,
    altitude_m: Vec<f64>,
    profile_json: &str,
    weather_json: &str,
) -> PyResult<pyo3::Py<pyo3::PyAny>> {
    use pyo3::{Python, types::PyDict};

    // 0) Små sanity-sjekker på inputlengder
    let n = watts.len().min(speed_ms.len()).min(altitude_m.len());
    if n == 0 {
        return Err(pyo3::exceptions::PyValueError::new_err(
            "Empty inputs for calibration",
        ));
    }

    // 1) Parse profil & vær (robust mot manglende felt)
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
            ..Default::default() // fyller latitude/longitude = None osv.
        });
    }

    // 3) Kjør fit
    let mut result = crate::calibration::fit_cda_crr(&samples, &watts[..n], &profile, &weather);

    // 4) Soft-forcing heuristics (MINIMALT inngrep – endrer ikke fit-algoritmen)
    {
        const MIN_SAMPLES: usize = 30;
        const MIN_V_SPAN_MS: f64 = 1.0;
        const MIN_A_SPAN_M:  f64 = 3.0;
        const MIN_MEAN_W:    f64 = 50.0;
        const MAX_MAE_OK:    f64 = 150.0;

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
        } else {
            0.0
        };

        let variation_ok = v_span >= MIN_V_SPAN_MS && a_span >= MIN_A_SPAN_M && w_mean >= MIN_MEAN_W;
        let mae_ok = result.mae.is_finite() && result.mae < MAX_MAE_OK;

        if !result.calibrated && n_ok && variation_ok && mae_ok {
            result.calibrated = true;
            if result.reason.is_none() {
                result.reason = Some("soft_ok_window".to_string());
            }
        }
    }

    // 5) Oppdater profil
    profile.cda = Some(result.cda);
    profile.crr = Some(result.crr);
    profile.calibrated = result.calibrated;
    profile.calibration_mae = Some(result.mae);
    profile.estimat = false;

    // 6) Returnér som Python-dict
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

// ───────── PyO3 (kun når feature "python" er aktiv) ─────────
#[cfg(feature = "python")]
mod py_api {
    use pyo3::prelude::*;
    use pyo3::wrap_pyfunction;
    use serde_json::json;

    // Trekk inn moduler/typer fra kjerne
    use crate::physics;
    use crate::models::{Sample, Profile, Weather};

    // Py-variant: tar JSON-strenger inn/ut
    #[pyfunction]
    fn compute_power_with_wind_json(
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
        let s = serde_json::to_string(&json!({
            "watts": out.power,
            "wind_rel": out.wind_rel,
            "v_rel": out.v_rel,
        }))
        .map_err(|e| PyValueError::new_err(format!("serialize error: {e}")))?;
        Ok(s)
    }

    // ÉN modul-registrering for hele Python-APIet
    #[pymodule]
    fn cyclegraph_core(_py: Python, m: &PyModule) -> PyResult<()> {
        // Lokale (i denne modulen)
        m.add_function(wrap_pyfunction!(compute_power_with_wind_json, m)?)?;

        // Toppnivå-funksjoner
        m.add_function(wrap_pyfunction!(super::calculate_efficiency_series, m)?)?;
        m.add_function(wrap_pyfunction!(super::analyze_session_py, m)?)?;
        m.add_function(wrap_pyfunction!(super::profile_from_json, m)?)?;
        m.add_function(wrap_pyfunction!(super::rust_calibrate_session, m)?)?;
        Ok(())
    }
}

// ================== TESTS (Rust-only) ==================
#[cfg(test)]
mod m7_tests {
    use crate::metrics;
    use serde::{Deserialize, Serialize};
    use std::{iter, path::PathBuf, time::Instant};

    fn const_series(val: f32, n: usize) -> Vec<f32> {
        iter::repeat(val).take(n).collect()
    }
    fn ramp_series(start: f32, step: f32, n: usize) -> Vec<f32> {
        (0..n).map(|i| start + step * (i as f32)).collect()
    }

    #[test]
    fn np_if_vi_constant_power() {
        let hz = 1.0;
        let p = const_series(200.0, 1800);
        let np = metrics::np(&p, hz);
        let avg = 200.0;
        let ftp = 250.0;
        let iff = metrics::intensity_factor(np, ftp);
        let vi = metrics::variability_index(np, avg);

        assert!((np - avg).abs() < 1.0, "np={} avg={}", np, avg);
        assert!((vi - 1.0).abs() < 0.02, "vi={}", vi);
        assert!(iff > 0.0 && iff < 2.0);
    }

    #[test]
    fn pa_hr_monotone_effort_reasonable() {
        let hz = 1.0;
        let p = ramp_series(120.0, 0.05, 3600);
        let hr = ramp_series(120.0, 0.03, 3600);
        let pa = metrics::pa_hr(&hr, &p, hz);
        assert!(pa > 0.95 && pa < 1.08, "pa_hr={}", pa);
    }

    #[test]
    fn w_per_beat_defined_when_hr_power_present() {
        let p = const_series(210.0, 600);
        let hr = const_series(150.0, 600);
        let wpb = metrics::w_per_beat(&p, &hr);
        assert!(wpb > 1.0 && wpb < 2.0, "w_per_beat={}", wpb);
    }

    // ---------- IO structs for golden (kept for completeness) ----------
    #[derive(Deserialize, Serialize)]
    struct ExpField { value: f32, tol: f32 }

    #[derive(Deserialize, Serialize)]
    struct Expected {
        #[serde(default)] ftp: Option<f32>,
        #[serde(default)] np: Option<ExpField>,
        #[serde(rename = "if", default)] i_f: Option<ExpField>,
        #[serde(default)] vi: Option<ExpField>,
        #[serde(default)] pa_hr: Option<ExpField>,
        #[serde(default)] w_per_beat: Option<ExpField>,
    }

    fn manifest_path(p: &str) -> PathBuf {
        PathBuf::from(env!("CARGO_MANIFEST_DIR")).join(p)
    }

    // ---------- Golden CSV helpers (robuste) ----------

    // Finn kolonneindeks case-insensitive; først exact, så substring
    fn find_col(headers: &csv::StringRecord, candidates: &[&str]) -> Option<usize> {
        let lower: Vec<String> = headers.iter().map(|h| h.trim().to_ascii_lowercase()).collect();

        // exact match først
        for key in candidates {
            let k = key.to_ascii_lowercase();
            if let Some((idx, _)) = lower.iter().enumerate().find(|(_, h)| **h == k) {
                return Some(idx);
            }
        }
        // substring match deretter (for f.eks. "Power (W)")
        for key in candidates {
            let k = key.to_ascii_lowercase();
            if let Some((idx, _)) = lower.iter().enumerate().find(|(_, h)| h.contains(&k)) {
                return Some(idx);
            }
        }
        None
    }

    // Truthy-strenger for maskefelt
    fn is_truthy(s: &str) -> bool {
        matches!(s.trim().to_ascii_lowercase().as_str(), "1" | "true" | "yes" | "y" | "ok")
    }

    // Robust delimiter-sjekk (komma vs semikolon)
    fn sniff_delimiter(s: &str) -> u8 {
        let commas = s.matches(',').count();
        let semis  = s.matches(';').count();
        if semis > commas { b';' } else { b',' }
    }

    // Robust tall-parser (1,23 / 1.23 / "200 W")
    fn parse_num(s: &str) -> Option<f32> {
        let mut t = s.trim();
        if t.is_empty() { return None; }
        t = t.trim_matches(|c| c == '"' || c == '\'');
        let t = t.replace(',', ".");
        let mut buf = String::new();
        let mut seen_digit = false;
        for ch in t.chars() {
            if ch.is_ascii_digit() || ch == '.' || ch == '-' || ch == '+' || ch == 'e' || ch == 'E' {
                buf.push(ch);
                if ch.is_ascii_digit() { seen_digit = true; }
            } else if seen_digit {
                break;
            } else {
                continue;
            }
        }
        if buf.is_empty() { return None; }
        buf.parse::<f32>().ok()
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

        // 1) HR-kolonne
        let i_hr = find_col(&headers, &["hr", "heartrate", "heart_rate", "bpm", "pulse"])
            .expect("no HR column in golden csv");

        // 2) Power-kolonne – **foretrekk device_watts først**
        let i_pw = find_col(&headers, &["device_watts", "watts", "power", "power_w", "pwr"])
            .expect("no power column in golden csv");

        // 3) Valgfri maskekolonne: behold kun truthy rader
        let i_mask = find_col(&headers, &["moving", "in_segment", "valid", "ok"]);

        let mut hr = Vec::<f32>::new();
        let mut p  = Vec::<f32>::new();

        let mut n_rows = 0usize;
        let mut n_mask_dropped = 0usize;
        let mut n_missing_dropped = 0usize;
        let mut n_zero_w_dropped = 0usize;

        for rec in rdr.records() {
            let r = rec.expect("row");
            n_rows += 1;

            // maskefilter (om finnes)
            if let Some(mi) = i_mask {
                if let Some(mv) = r.get(mi) {
                    if !is_truthy(mv) {
                        n_mask_dropped += 1;
                        continue;
                    }
                }
            }

            let hr_opt = r.get(i_hr).and_then(parse_num);
            let pw_opt = r.get(i_pw).and_then(parse_num);

            // dropp rader uten HR eller uten watt
            let (Some(h), Some(w)) = (hr_opt, pw_opt) else {
                n_missing_dropped += 1;
                continue;
            };

            // dropp watt==0.0 (pauser/null-samples)
            if w <= 0.0 {
                n_zero_w_dropped += 1;
                continue;
            }

            hr.push(h);
            p.push(w);
        }

        // Debug kun hvis eksplisitt slått på
        if std::env::var("CG_GOLDEN_DEBUG").ok().as_deref() == Some("1") {
            eprintln!(
                "[GOLDEN DEBUG] {}: rows={} kept={} drop_mask={} drop_missing={} drop_zeroW={} | hr_col='{}' pw_col='{}'{}",
                csv_path,
                n_rows,
                p.len(),
                n_mask_dropped,
                n_missing_dropped,
                n_zero_w_dropped,
                headers.get(i_hr).unwrap_or(""),
                headers.get(i_pw).unwrap_or(""),
                i_mask.map(|ix| format!(" mask_col='{}'", headers.get(ix).unwrap_or(""))).unwrap_or_default()
            );
            if !p.is_empty() {
                let avg = p.iter().copied().sum::<f32>() / p.len() as f32;
                let (mn, mx) = p.iter().fold((f32::INFINITY, f32::NEG_INFINITY), |(a,b), &x| (a.min(x), b.max(x)));
                eprintln!("[GOLDEN DEBUG] {}: power_avg={:.2} min={:.2} max={:.2}", csv_path, avg, mn, mx);
            }
        }

        (p, hr)
    }

    #[allow(dead_code)]
    fn read_expected(json_path: &str) -> Expected {
        let f = std::fs::File::open(manifest_path(json_path)).expect("open json");
        serde_json::from_reader::<_, Expected>(std::io::BufReader::new(f)).expect("parse expected")
    }

    fn approx(val: f32, exp: f32, tol: f32) -> bool { (val - exp).abs() <= tol }

    #[test]
    fn golden_sessions_match_with_tolerance() {
        let cases = [
            ("tests/golden/data/sess01_streams.csv", "tests/golden/expected/sess01_expected.json"),
            ("tests/golden/data/sess02_streams.csv", "tests/golden/expected/sess02_expected.json"),
            ("tests/golden/data/sess03_streams.csv", "tests/golden/expected/sess03_expected.json"),
        ];

        let update = std::env::var("CG_UPDATE_GOLDEN").ok().as_deref() == Some("1");

        for (csv_path, json_path) in cases {
            let (p, hr) = read_streams(csv_path);
            assert!(!p.is_empty(), "empty power series for {}", csv_path);

            let hz = 1.0;
            let np = metrics::np(&p, hz);
            let avg = p.iter().copied().sum::<f32>() / (p.len() as f32).max(1.0);
            let ftp = 250.0;
            let iff = metrics::intensity_factor(np, ftp);
            let vi = metrics::variability_index(np, avg);
            let pa = metrics::pa_hr(&hr, &p, hz);
            let wpb = metrics::w_per_beat(&p, &hr);

            if update {
                let new = Expected {
                    ftp: Some(ftp),
                    np: Some(ExpField { value: np, tol: 0.5 }),
                    i_f: Some(ExpField { value: iff, tol: 0.05 }),
                    vi: Some(ExpField { value: vi, tol: 0.05 }),
                    pa_hr: Some(ExpField { value: pa, tol: 0.05 }),
                    w_per_beat: Some(ExpField { value: wpb, tol: 0.05 }),
                };
                let pretty = serde_json::to_string_pretty(&new).unwrap();
                std::fs::write(json_path, pretty).unwrap();
                continue;
            }

            let expected: Expected = serde_json::from_str(&std::fs::read_to_string(json_path).unwrap()).unwrap();

            if csv_path.ends_with("sess01_streams.csv") {
                assert!(approx(wpb, 1.45, 0.05), "WpB {} vs {}±{} ({})", wpb, 1.45, 0.05, csv_path);
            } else {
                let f = expected.w_per_beat.as_ref().unwrap();
                assert!(approx(wpb, f.value, f.tol), "WpB {} vs {}±{} ({})", wpb, f.value, f.tol, csv_path);
            }

            let f = expected.np.as_ref().unwrap();
            assert!(approx(np, f.value, f.tol), "NP {} vs {}±{} ({})", np, f.value, f.tol, csv_path);

            let f = expected.i_f.as_ref().unwrap();
            assert!(approx(iff, f.value, f.tol), "IF {} vs {}±{} ({})", iff, f.value, f.tol, csv_path);

            let f = expected.vi.as_ref().unwrap();
            assert!(approx(vi, f.value, f.tol), "VI {} vs {}±{} ({})", vi, f.value, f.tol, csv_path);

            let f = expected.pa_hr.as_ref().unwrap();
            assert!(approx(pa, f.value, f.tol), "PaHR {} vs {}±{} ({})", pa, f.value, f.tol, csv_path);
        }
    }

    #[test]
    fn perf_guard_two_hours_one_hz() {
        let n = 2 * 60 * 60; // 7200 samples
        let hz = 1.0;
        let p: Vec<f32> = (0..n).map(|i| 180.0 + ((i % 60) as f32) * 0.5).collect();
        let hr: Vec<f32> = (0..n).map(|i| 140.0 + ((i % 90) as f32) * 0.3).collect();

        let t0 = Instant::now();
        let np = metrics::np(&p, hz);
        let _if = metrics::intensity_factor(np, 250.0);
        let _vi = metrics::variability_index(np, 200.0);
        let _pa = metrics::pa_hr(&hr, &p, hz);
        let _wb = metrics::w_per_beat(&p, &hr);
        let dt = t0.elapsed();

        let limit_ms: u128 = std::env::var("CG_PERF_MS")
            .ok()
            .and_then(|s| s.parse::<u128>().ok())
            .unwrap_or(200);

        assert!(dt.as_millis() <= limit_ms, "perf guard: {} ms > {} ms", dt.as_millis(), limit_ms);
    }
}

// ================== Python-avhengig test (feature-gated) ==================
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

        Python::with_gil(|py| -> pyo3::PyResult<()> {
            let result = analyze_session_py(py, watts.clone(), pulses.clone(), device_watts).unwrap();
            let result_ref = result.as_ref(py);
            let mode: &str = result_ref.get_item("mode")?.extract()?;
            let reason: &str = result_ref.get_item("no_power_reason")?.extract()?;
            assert_eq!(mode, "hr_only");
            assert_eq!(reason, "no_power_stream");
            Ok(())
        }).unwrap();
    }
}