//! CycleGraph core library.
//!
//! Viktig: Denne fila skal **ikke** ha pyo3-imports. All Python-binding
//! ligger i `crate::py`, som kun bygges når `--features python` er aktiv.

#![deny(unsafe_code)]
#![cfg_attr(not(debug_assertions), deny(warnings))]

// ───────── Moduler (pure Rust) ─────────
pub mod analyze_session;
pub mod calibration;
pub mod metrics;
pub mod models;
pub mod physics;
pub mod smoothing;
pub mod storage;
pub mod weather;
pub mod weather_api;

// Interne moduler
mod defaults;

// ───────── Imports (pure Rust) ─────────
use serde_json::json;

// ───────── Re-exports (pure Rust) ─────────
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

// ───────── Feature-gated Python-modul (innhold lages senere) ─────────
// Merk: `core/src/py/mod.rs` implementeres i en egen oppgave/chat.
#[cfg(feature = "python")]
pub mod py;

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

// ───────── TODO(next) ─────────
// Flytt alle PyO3-wrappere til `core/src/py/mod.rs` og eksponer dem derfra.
// Denne fila skal ikke bli “smittet” av pyo3.
