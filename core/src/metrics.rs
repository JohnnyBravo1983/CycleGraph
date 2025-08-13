use crate::types::{Meta, Sample};

/// Normalized Power:
/// 1) 30s rullende snitt av kraft
/// 2) ^4-middel
/// 3) fjerderot
pub fn normalized_power(samples: &[Sample]) -> Option<f32> {
    let w: Vec<f32> = samples.iter().filter_map(|s| s.watts).collect();
    if w.len() < 30 { return None; }

    let window = 30usize;
    let mut smooth = Vec::with_capacity(w.len().saturating_sub(window) + 1);
    let mut sum = 0.0f32;

    for i in 0..w.len() {
        sum += w[i];
        if i >= window {
            sum -= w[i - window];
        }
        if i + 1 >= window {
            smooth.push(sum / window as f32);
        }
    }
    if smooth.is_empty() { return None; }

    let mut fourth_power_avg = 0.0f64;
    for v in &smooth {
        let x = *v as f64;
        fourth_power_avg += x.powi(4);
    }
    fourth_power_avg /= smooth.len() as f64;

    Some(fourth_power_avg.powf(0.25) as f32)
}

pub fn avg_power(samples: &[Sample]) -> Option<f32> {
    let mut sum = 0.0f32;
    let mut cnt = 0usize;
    for s in samples {
        if let Some(w) = s.watts {
            sum += w;
            cnt += 1;
        }
    }
    if cnt == 0 { None } else { Some(sum / cnt as f32) }
}

pub fn avg_hr(samples: &[Sample]) -> Option<f32> {
    let mut sum = 0.0f32;
    let mut cnt = 0usize;
    for s in samples {
        if let Some(h) = s.hr {
            sum += h;
            cnt += 1;
        }
    }
    if cnt == 0 { None } else { Some(sum / cnt as f32) }
}

/// IF = NP/FTP
pub fn intensity_factor(np: Option<f32>, ftp: Option<f32>) -> Option<f32> {
    match (np, ftp) {
        (Some(n), Some(f)) if f > 0.0 => Some(n / f),
        _ => None,
    }
}

/// VI = NP / AvgPower
pub fn variability_index(np: Option<f32>, avg_p: Option<f32>) -> Option<f32> {
    match (np, avg_p) {
        (Some(n), Some(a)) if a > 0.0 => Some(n / a),
        _ => None,
    }
}

/// Pa:Hr (%) – del økt i to like deler, beregn (AvgPower/AvgHR) pr del og relativ endring i %.
pub fn pa_hr_pct(samples: &[Sample]) -> Option<f32> {
    let n = samples.len();
    if n < 120 { return None; } // krever litt lengde

    let mid = n / 2;
    let (a, b) = samples.split_at(mid);

    let (avg_p_a, avg_hr_a) = (avg_power(a)?, avg_hr(a)?);
    let (avg_p_b, avg_hr_b) = (avg_power(b)?, avg_hr(b)?);

    if avg_hr_a <= 0.0 || avg_hr_b <= 0.0 { return None; }

    let r_a = avg_p_a / avg_hr_a;
    let r_b = avg_p_b / avg_hr_b;

    if r_a <= 0.0 { return None; }

    let drift = ((r_b - r_a) / r_a) * 100.0;
    Some(drift)
}

/// W/beat = AvgPower / AvgHR
pub fn w_per_beat(avg_p: Option<f32>, avg_hr: Option<f32>) -> Option<f32> {
    match (avg_p, avg_hr) {
        (Some(p), Some(h)) if h > 0.0 => Some(p / h),
        _ => None,
    }
}

/// Velg FTP: meta.ftp hvis finnes (auto-estimat kommer i batch senere)
pub fn resolve_ftp(meta: &Meta) -> Option<f32> {
    meta.ftp
}
