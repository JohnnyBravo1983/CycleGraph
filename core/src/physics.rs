// core/src/physics.rs
use crate::Profile;
use crate::models::{Sample, Weather};

pub fn compute_power(samples: &[Sample], profile: &Profile, _weather: &Weather) -> Vec<f64> {
    // Faste konstanter
    let g: f64 = 9.80665;

    // Robust uthenting av opsjonelle felter (fungerer for Option<f64> og Option<&f64>)
    let mass_total_kg: f64 = profile.total_weight.as_ref().copied().unwrap_or(78.0);
    let crr: f64 = profile.crr.as_ref().copied().unwrap_or(0.005);

    // Midlertidig drivverkstap til vi legger dette i Profile
    let drivetrain_loss: f64 = 0.03;

    let mut power = Vec::with_capacity(samples.len());

    for s in samples {
        let v = s.v_ms;

        // TODO: bytt ut med faktisk stigning ut fra høydeserie når smoothing er på plass
        let slope = 0.0_f64;

        // Krefter
        let f_gravity = mass_total_kg * g * slope;
        let f_roll    = mass_total_kg * g * crr;

        // Effekt (instantan)
        let p = (f_gravity + f_roll) * v * (1.0 - drivetrain_loss);

        power.push(p);
    }

    power
}
