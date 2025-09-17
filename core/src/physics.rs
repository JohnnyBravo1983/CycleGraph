// core/src/physics.rs
use crate::smoothing::smooth_altitude;
use crate::Profile;
use crate::models::{Sample, Weather};

fn compute_air_density(weather: &Weather) -> Option<f64> {
    let temp_k = weather.air_temp_c + 273.15;
    let pressure_pa = weather.air_pressure_hpa * 100.0;
    if temp_k > 0.0 {
        Some(pressure_pa / (287.05 * temp_k))
    } else {
        None
    }
}

pub fn compute_power(samples: &[Sample], profile: &Profile, weather: &Weather) -> Vec<f64> {
    let g = 9.80665;
    let rho = compute_air_density(weather).unwrap_or(1.225);

    // 🔧 Nytt: smoothet høyde-profil
    let altitudes = smooth_altitude(samples);

    let mut power = Vec::with_capacity(samples.len());

    for i in 0..samples.len() {
        let s = &samples[i];
        let v = if s.moving { s.v_ms } else { 0.0 };

        // Slope estimation (bruk smoothet høyde)
        let slope = if i + 1 < samples.len() {
            let dz = altitudes[i + 1] - altitudes[i];
            let dx = v.max(0.1);
            (dz / dx).atan()
        } else {
            0.0
        };

        let mass_total_kg = profile.total_weight.unwrap_or(78.0);
        let crr = profile.crr.unwrap_or(0.005);
        let cda = 0.3; // midlertidig CdA
        let drivetrain_loss = 0.03;

        // Gravitasjon
        let f_gravity = mass_total_kg * g * slope;

        // Rulling
        let f_roll = mass_total_kg * g * crr;

        // Aero
        let wind_angle_rad = (weather.wind_dir_deg - s.heading_deg).to_radians();
        let wind_component = weather.wind_ms * wind_angle_rad.cos();
        let v_rel = (v - wind_component).max(0.0);
        let f_aero = 0.5 * rho * cda * v_rel * v_rel;

        // Akselerasjon
        let dv_dt = if i > 0 {
            let dv = s.v_ms - samples[i - 1].v_ms;
            let dt = s.t - samples[i - 1].t;
            if dt > 0.0 { dv / dt } else { 0.0 }
        } else {
            0.0
        };
        let f_acc = mass_total_kg * dv_dt;

        // Total kraft
        let f_total = f_gravity + f_roll + f_aero + f_acc;
        let p_total = f_total * v * (1.0 - drivetrain_loss);
        power.push(p_total);
    }

    power
}