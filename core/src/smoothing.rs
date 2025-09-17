use crate::models::Sample;

pub fn smooth_altitude(samples: &[Sample]) -> Vec<f64> {
    let mut smoothed = Vec::with_capacity(samples.len());

    for i in 0usize..samples.len() {
        let mut sum = 0.0;
        let mut count = 0;

        for j in i.saturating_sub(1)..=(i + 1).min(samples.len() - 1) {
            let dz = (samples[j].altitude_m - samples[i].altitude_m).abs();
            let dt = (samples[j].t - samples[i].t).abs();
            if dt > 0.0 && dz / dt < 10.0 {
                sum += samples[j].altitude_m;
                count += 1;
            }
        }

        let avg = if count > 0 { sum / count as f64 } else { samples[i].altitude_m };
        smoothed.push(avg);
    }

    smoothed
}