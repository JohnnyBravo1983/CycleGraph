use pyo3::prelude::*;

mod types;
mod metrics;
mod cgs;

use types::{Cfg, Meta, Sample, SessionReport, SessionScores, TrendInfo};
use metrics::{
    avg_hr, avg_power, normalized_power, intensity_factor, variability_index,
    pa_hr_pct, w_per_beat, /* w_per_beat_baseline, */ resolve_ftp
};
use cgs::{score_intensity, score_duration, score_quality, combine_cgs};

#[pyclass]
struct Api;

#[pymethods]
impl Api {
    /// Enkel ping for røyk-test fra Python
    #[staticmethod]
    pub fn ping() -> &'static str { "pong" }

    /// Din eksisterende funksjon – effektivitet fra watt/puls-arrays
    #[staticmethod]
    pub fn calculate_efficiency_series(watts: Vec<f64>, pulses: Vec<f64>)
        -> PyResult<(f64, String, Vec<f64>, Vec<String>)>
    {
        if watts.is_empty() || pulses.is_empty() || watts.len() != pulses.len() {
            return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
                "Watt og puls-lister må ha samme lengde og ikke være tomme.",
            ));
        }

        // Beregn snittverdier (manuelt)
        let avg_watt: f64 = watts.iter().copied().sum::<f64>() / watts.len() as f64;
        let avg_pulse: f64 = pulses.iter().copied().sum::<f64>() / pulses.len() as f64;
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
                "Lav effekt".to_string()
            } else if *p > 170.0 {
                "Høy puls".to_string()
            } else {
                "OK".to_string()
            };
            per_point_status.push(status);
        }

        Ok((avg_eff, session_status, per_point_eff, per_point_status))
    }

    /// analyze_session_json(samples_json, meta_json, cfg_json=None) -> JSON-string av SessionReport
    #[staticmethod]
    #[pyo3(signature = (samples_json, meta_json, cfg_json=None))]
    pub fn analyze_session_json(samples_json: &str, meta_json: &str, cfg_json: Option<&str>) -> PyResult<String> {
        // Parse input
        let samples: Vec<Sample> = serde_json::from_str(samples_json)
            .map_err(|e| pyo3::exceptions::PyValueError::new_err(format!("Invalid samples JSON: {e}")))?;
        let meta: Meta = serde_json::from_str(meta_json)
            .map_err(|e| pyo3::exceptions::PyValueError::new_err(format!("Invalid meta JSON: {e}")))?;
        let cfg: Cfg = match cfg_json {
            Some(s) => serde_json::from_str(s)
                .map_err(|e| pyo3::exceptions::PyValueError::new_err(format!("Invalid cfg JSON: {e}")))?,
            None => Cfg::default(),
        };

        // Grunnleggende aggregeringer
        let duration_min = meta.duration_sec / 60.0;
        let ap  = avg_power(&samples);
        let ahr = avg_hr(&samples);
        let np  = normalized_power(&samples);

        // Avledede nøkkeltall
        let ftp = resolve_ftp(&meta);                 // auto-estimat kommer i batch senere
        let ifv = intensity_factor(np, ftp);          // IF = NP/FTP
        let vi  = variability_index(np, ap);          // VI = NP/AvgPower
        let pa  = pa_hr_pct(&samples);                // Pa:Hr (%)
        let wpb = w_per_beat(ap, ahr);                // Watt per slag

        // Placeholder baseline for W/beat – settes i batch/trend senere
        let wpb_baseline = None;

        // Del-scorer
        let s_int = score_intensity(ifv);             // 0..100
        let s_dur = score_duration(duration_min);     // 0..100
        let s_qual = score_quality(pa, vi, wpb, wpb_baseline); // 0..100

        // Samlet CGS (m/vekter fra cfg om satt)
        let (cgs, _weights_used) = combine_cgs(s_int, s_dur, s_qual, cfg.cgs_weights.as_ref());

        // Badges v1
        let mut badges = vec![];
        if let Some(drift) = pa {
            if drift.abs() <= 2.0 && duration_min >= 90.0 { badges.push("Iron Lungs".to_string()); }
        }
        if let Some(vi_v) = vi {
            if vi_v <= 1.03 && duration_min >= 60.0 { badges.push("Metronome".to_string()); }
        }
        if let (Some(w), Some(b)) = (wpb, wpb_baseline) {
            if b > 0.0 && (w - b)/b >= 0.10 { badges.push("Big Engine".to_string()); }
        }

        // Bygg rapport
        let report = SessionReport {
            session_id: meta.session_id.clone(),
            duration_min,
            avg_power: ap,
            avg_hr: ahr,
            np,
            r#if: ifv,
            vi,
            pa_hr_pct: pa,
            w_per_beat: wpb,
            w_per_beat_baseline: wpb_baseline,
            scores: SessionScores { intensity: s_int, duration: s_dur, quality: s_qual, cgs },
            badges,
            trend: TrendInfo::default(), // fylles i analyze_batch senere
        };

        Ok(serde_json::to_string_pretty(&report).unwrap())
    }
}

#[pymodule]
fn cyclegraph_core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    // Eksponer klassen med statiske metoder
    m.add_class::<Api>()?;
    Ok(())
}
