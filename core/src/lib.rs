
// core/src/lib.rs

// Rust-kjernen (alltid tilgjengelig)
pub mod metrics;

// -------- PYTHON BINDINGS (kun når --features python) --------
#[cfg(feature = "python")]
mod pybindings {
    use pyo3::exceptions::PyValueError;
    use pyo3::prelude::*;        // Bound, PyModule, PyResult, Python, etc.
    use pyo3::wrap_pyfunction;   // makroen må importeres i samme modul

    #[pyfunction]
    pub fn calculate_efficiency_series(
        watts: Vec<f64>,
        pulses: Vec<f64>,
    ) -> PyResult<(f64, String, Vec<f64>, Vec<String>)> {
        if watts.is_empty() || pulses.is_empty() || watts.len() != pulses.len() {
            return Err(PyErr::new::<PyValueError, _>(
                "Watt og puls-lister må ha samme lengde og ikke være tomme.",
            ));
        }

        // Beregn snittverdier
        let avg_watt: f64 = watts.iter().sum::<f64>() / watts.len() as f64;
        let avg_pulse: f64 = pulses.iter().sum::<f64>() / pulses.len() as f64;
        let avg_eff = if avg_pulse == 0.0 { 0.0 } else { avg_watt / avg_pulse };

        // Status for hele økten
        let session_status = if avg_eff < 1.0 {
            "Lav effekt – vurder å øke tråkkfrekvens eller intensitet.".to_string()
        } else if avg_pulse > 170.0 {
            "Høy puls – vurder lengre restitusjon.".to_string()
        } else {
            "OK – treningen ser balansert ut.".to_string()
        };

        // Per-datapunkt effektivitet + status
        let mut per_point_eff = Vec::with_capacity(watts.len());
        let mut per_point_status = Vec::with_capacity(watts.len());

        for (w, p) in watts.iter().zip(pulses.iter()) {
            let eff = if *p == 0.0 { 0.0 } else { w / p };
            per_point_eff.push(eff);

            let status = if eff < 1.0 {
                "Lav effekt"
            } else if *p > 170.0 {
                "Høy puls"
            } else {
                "OK"
            }
            .to_string();
            per_point_status.push(status);
        }

        Ok((avg_eff, session_status, per_point_eff, per_point_status))
    }

    // PyO3 0.22: Bound<'_, PyModule>
    #[pymodule]
    fn cyclegraph_core(m: &Bound<'_, PyModule>) -> PyResult<()> {
        m.add_function(wrap_pyfunction!(calculate_efficiency_series, m)?)?;
        Ok(())
    }
}
// -------- END PYTHON BINDINGS --------




// -----------------------------------------------------------------------------
// TESTS (M7) – unit + golden + perf-guard
// (uendret – kjører uten python-feature)
// -----------------------------------------------------------------------------
#[cfg(test)]
mod m7_tests {
    use std::{iter, path::PathBuf, time::Instant};
    use crate::metrics;

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

    use serde::Deserialize;
    #[derive(Deserialize)]
    struct Row {
        #[serde(rename = "time")]
        _time: f32,
        hr: Option<f32>,
        watts: Option<f32>,
    }

    #[derive(Deserialize)]
    struct ExpField { value: f32, tol: f32 }

    #[derive(Deserialize)]
    struct Expected {
        #[serde(default)]
        ftp: Option<f32>,
        #[serde(default)]
        np: Option<ExpField>,
        #[serde(rename = "if", default)]
        i_f: Option<ExpField>,
        #[serde(default)]
        vi: Option<ExpField>,
        #[serde(default)]
        pa_hr: Option<ExpField>,
        #[serde(default)]
        w_per_beat: Option<ExpField>,
    }

    fn manifest_path(p: &str) -> PathBuf {
        PathBuf::from(env!("CARGO_MANIFEST_DIR")).join(p)
    }

    fn read_streams(csv_path: &str) -> (Vec<f32>, Vec<f32>) {
        let mut rdr = csv::Reader::from_path(manifest_path(csv_path)).expect("open csv");
        let mut hr = Vec::<f32>::new();
        let mut p = Vec::<f32>::new();
        for rec in rdr.deserialize::<Row>() {
            let r = rec.expect("row");
            hr.push(r.hr.unwrap_or(0.0));
            p.push(r.watts.unwrap_or(0.0));
        }
        (p, hr)
    }

    fn read_expected(json_path: &str) -> Expected {
        let f = std::fs::File::open(manifest_path(json_path)).expect("open json");
        serde_json::from_reader::<_, Expected>(std::io::BufReader::new(f)).expect("parse expected")
    }

    fn approx(val: f32, exp: f32, tol: f32) -> bool {
        (val - exp).abs() <= tol
    }

    #[test]
    fn golden_sessions_match_with_tolerance() {
        let cases = [
            ("tests/golden/data/sess01_streams.csv", "tests/golden/expected/sess01_expected.json"),
            ("tests/golden/data/sess02_streams.csv", "tests/golden/expected/sess02_expected.json"),
            ("tests/golden/data/sess03_streams.csv", "tests/golden/expected/sess03_expected.json"),
        ];

        for (csv_path, json_path) in cases {
            let (p, hr) = read_streams(csv_path);
            assert!(!p.is_empty(), "empty power series for {}", csv_path);

            let exp = read_expected(json_path);
            let hz = 1.0;

            let np  = metrics::np(&p, hz);
            let avg = p.iter().copied().sum::<f32>() / (p.len() as f32).max(1.0);
            let ftp = exp.ftp.unwrap_or(250.0);
            let iff = metrics::intensity_factor(np, ftp);
            let vi  = metrics::variability_index(np, avg);
            let pa  = metrics::pa_hr(&hr, &p, hz);
            let wpb = metrics::w_per_beat(&p, &hr);

            if let Some(f) = exp.np.as_ref()         { assert!(approx(np,  f.value, f.tol),   "NP {} vs {}±{} ({})",  np,  f.value, f.tol,  csv_path); }
            if let Some(f) = exp.i_f.as_ref()        { assert!(approx(iff, f.value, f.tol),   "IF {} vs {}±{} ({})",  iff, f.value, f.tol,  csv_path); }
            if let Some(f) = exp.vi.as_ref()         { assert!(approx(vi,  f.value, f.tol),   "VI {} vs {}±{} ({})",  vi,  f.value, f.tol,  csv_path); }
            if let Some(f) = exp.pa_hr.as_ref()      { assert!(approx(pa,  f.value, f.tol),   "Pa:Hr {} vs {}±{} ({})", pa, f.value, f.tol, csv_path); }
            if let Some(f) = exp.w_per_beat.as_ref() { assert!(approx(wpb, f.value, f.tol),   "WpB {} vs {}±{} ({})", wpb, f.value, f.tol,  csv_path); }
        }
    }

    #[test]
    fn perf_guard_two_hours_one_hz() {
        let n = 2 * 60 * 60; // 7200 samples
        let hz = 1.0;
        let p: Vec<f32>  = (0..n).map(|i| 180.0 + ((i % 60) as f32) * 0.5).collect();
        let hr: Vec<f32> = (0..n).map(|i| 140.0 + ((i % 90) as f32) * 0.3).collect();

        let t0 = Instant::now();
        let np  = metrics::np(&p, hz);
        let _if = metrics::intensity_factor(np, 250.0);
        let _vi = metrics::variability_index(np, 200.0);
        let _pa = metrics::pa_hr(&hr, &p, hz);
        let _wb = metrics::w_per_beat(&p, &hr);
        let dt = t0.elapsed();

        let limit_ms: u128 = std::env::var("CG_PERF_MS").ok()
            .and_then(|s| s.parse::<u128>().ok()).unwrap_or(200);

    assert!(
    dt.as_millis() <= limit_ms,
    "perf guard: {} ms > {} ms",
    dt.as_millis(),
    limit_ms
);

    }
}
