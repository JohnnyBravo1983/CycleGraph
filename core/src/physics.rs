// core/src/physics.rs
use crate::Profile;
use crate::models::{Sample, Weather};

pub fn compute_power(samples: &[Sample], profile: &Profile, weather: &Weather) -> Vec<f64> {
    let g: f64 = 9.80665;

    // Lufttetthet (fallback til standard sjø-nivå)
    let rho: f64 = compute_air_density(weather).unwrap_or(1.225);

    // Hent verdier fra Profile med sikre defaults
    let mass_total_kg: f64 = profile.total_weight.unwrap_or(78.0);
    let crr: f64 = profile.crr.unwrap_or(0.005);
    let drivetrain_loss: f64 = 0.03;

    // En enkel CdA-default etter sykkeltype (Profile har ikke cda_m2-felt)
    let cda: f64 = match profile.bike_type.as_deref() {
        Some("tt") | Some("tri") => 0.23,
        Some("mtb")              => 0.40,
        Some("gravel")           => 0.33,
        _ /* road/ukjent */      => 0.30,
    };

    let mut power = Vec::with_capacity(samples.len());

    for i in 0..samples.len() {
        let s = &samples[i];

        // Hastighet: nullstill hvis ikke i bevegelse
        let v = if s.moving { s.v_ms } else { 0.0 };

        // Slope-estimat fra nabopunkt (robust mot deltider = 0)
        let (dz, dt) = if i + 1 < samples.len() {
            let next = &samples[i + 1];
            (next.altitude_m - s.altitude_m, (next.t - s.t).max(1e-3))
        } else {
            (0.0, 1.0)
        };
        let dx = (v * dt).max(0.1);
        let slope = dz / dx; // liten-vinkel-approksimasjon

        // Gravitasjon og rulling
        let f_gravity = mass_total_kg * g * slope;
        let f_roll    = mass_total_kg * g * crr;

        // Aero: relativ vind mot heading
        let wind_angle_rad = (weather.wind_dir_deg - s.heading_deg).to_radians();
        let wind_component = weather.wind_ms * wind_angle_rad.cos();
        let v_rel = (v - wind_component).max(0.0);
        let f_aero = 0.5 * rho * cda * v_rel * v_rel;

        // Total effekt (tap i drivverk)
        let f_total = f_gravity + f_roll + f_aero;
        let p_total = f_total * v * (1.0 - drivetrain_loss);

        power.push(p_total);
    }

    power
}

fn compute_air_density(weather: &Weather) -> Option<f64> {
    let temp_k = weather.air_temp_c + 273.15;
    let pressure_pa = weather.air_pressure_hpa * 100.0;
    if temp_k > 0.0 {
        Some(pressure_pa / (287.05 * temp_k))
    } else {
        None
    }
}