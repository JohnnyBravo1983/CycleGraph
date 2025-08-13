use crate::types::CgsWeights;

/// Intensitetsscore – klokkeform rundt IF≈0.90 iht. DOD. 0–100.
pub fn score_intensity(r_if: Option<f32>) -> f32 {
    if let Some(ifv) = r_if {
        let val = 100.0f32 * (-(((ifv - 0.90f32) / 0.10f32).powi(2))).exp();
        val.clamp(0.0, 100.0)
    } else { 50.0 }
}

/// Varighetsscore – log-skalert (0–100).
pub fn score_duration(min: f32) -> f32 {
    if min <= 0.0 { return 0.0; }
    let num = (1.0f32 + (min / 30.0f32)).ln();
    let den = (1.0f32 + (180.0f32 / 30.0f32)).ln();
    let val = 100.0f32 * (num / den).min(1.0f32);
    val.clamp(0.0, 100.0)
}

/// Kvalitet – stykkevise skalaer for Pa:Hr, VI og W/beat vs baseline.
pub fn score_quality(pa_hr_pct: Option<f32>, vi: Option<f32>, wpb: Option<f32>, wpb_baseline: Option<f32>) -> f32 {
    // Drift (Pa:Hr): best nær 0 % eller ≤ 2 %
    let drift_score = match pa_hr_pct {
        Some(d) if d.abs() <= 2.0 => 100.0,
        Some(d) if d.abs() <= 5.0 => 80.0,
        Some(d) if d.abs() <= 8.0 => 60.0,
        Some(_) => 40.0,
        None => 50.0,
    };

    // VI: best når nær 1.00
    let vi_score = match vi {
        Some(v) if v <= 1.03 => 100.0,
        Some(v) if v <= 1.08 => 80.0,
        Some(v) if v <= 1.15 => 60.0,
        Some(_) => 40.0,
        None => 50.0,
    };

    // W/beat relativt til baseline
    let wpb_score = match (wpb, wpb_baseline) {
        (Some(w), Some(b)) if b > 0.0 => {
            let delta = (w - b) / b;
            if delta >= 0.10 { 100.0 }
            else if delta >= 0.05 { 85.0 }
            else if delta >= 0.00 { 70.0 }
            else if delta >= -0.05 { 55.0 }
            else { 40.0 }
        }
        _ => 50.0,
    };

    // 0.4 Drift + 0.3 VI + 0.3 WpB
    0.4 * drift_score + 0.3 * vi_score + 0.3 * wpb_score
}

/// Kombiner CGS ut fra vekter, re-vekt ved behov.
pub fn combine_cgs(intensity: f32, duration: f32, quality: f32, weights: Option<&CgsWeights>) -> (f32, (f32,f32,f32)) {
    let (mut wi, mut wd, mut wq) = if let Some(w) = weights {
        (w.intensity, w.duration, w.quality)
    } else {
        (0.4f32, 0.3f32, 0.3f32)
    };
    let sum = wi + wd + wq;
    if sum > 0.0 {
        wi /= sum; wd /= sum; wq /= sum;
    } else {
        wi = 0.4; wd = 0.3; wq = 0.3;
    }
    let cgs = wi*intensity + wd*duration + wq*quality;
    (cgs, (wi, wd, wq))
}
