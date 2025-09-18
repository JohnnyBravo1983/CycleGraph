use crate::physics::compute_power;
use crate::smoothing::smooth_altitude;
use crate::models::{Sample, Profile, Weather};

pub fn print_power_report(samples: &[Sample], profile: &Profile, weather: &Weather) {
    let power_raw = compute_power(samples, profile, weather);
    let power_smooth = smooth_power(&power_raw, 5);

    let avg = power_raw.iter().copied().sum::<f64>() / power_raw.len() as f64;
    let np = compute_np(&power_raw);

    println!("--- Power Report ---");
    println!("Sample watt: {:?}", &power_raw[..5.min(power_raw.len())]);
    println!("Smoothed watt (5s): {:?}", &power_smooth[..5.min(power_smooth.len())]);
    println!("Avg watt: {:.1}", avg);
    println!("NP watt: {:.1}", np);
}

fn smooth_power(power: &[f64], window: usize) -> Vec<f64> {
    let mut smoothed = Vec::with_capacity(power.len());

    for i in 0..power.len() {
        let start = i.saturating_sub(window / 2);
        let end = (i + window / 2).min(power.len() - 1);
        let slice = &power[start..=end];
        let avg = slice.iter().copied().sum::<f64>() / slice.len() as f64;
        smoothed.push(avg);
    }

    smoothed

    
    fn compute_np(power: &[f64]) -> f64 {
    let avg_4th = power.iter().map(|p| p.powi(4)).sum::<f64>() / power.len() as f64;
    avg_4th.powf(0.25)
}