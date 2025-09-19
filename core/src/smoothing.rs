use crate::models::Sample;

/// Robust 3-punkts medianfilter for høyde.
/// Endepunkter bruker seg selv som nabov erdi (repeteres) for å holde lengden.
pub fn smooth_altitude(samples: &[Sample]) -> Vec<f64> {
    if samples.is_empty() {
        return Vec::new();
    }
    let n = samples.len();
    let mut out = Vec::with_capacity(n);

    for i in 0..n {
        let a0 = if i > 0 { samples[i - 1].altitude_m } else { samples[i].altitude_m };
        let a1 = samples[i].altitude_m;
        let a2 = if i + 1 < n { samples[i + 1].altitude_m } else { samples[i].altitude_m };

        let mut win = [a0, a1, a2];
        win.sort_by(|x, y| x.partial_cmp(y).unwrap());
        out.push(win[1]); // median
    }

    out
}