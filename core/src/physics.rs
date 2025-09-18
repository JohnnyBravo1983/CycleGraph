use crate::models::{Profile, Sample, Weather};

const G: f64 = 9.80665;

fn cda_for(bike_type: Option<&str>) -> f64 {
    match bike_type.unwrap_or("road").to_lowercase().as_str() {
        "tt" | "tri" => 0.25,
        "mtb" | "gravel" => 0.40,
        _ => 0.30, // road default
    }
}

fn air_density(air_temp_c: f64, air_pressure_hpa: f64) -> f64 {
    // ρ = p / (R * T) – tørr luft, ca 1.225 kg/m^3 @ 15°C, 1013 hPa
    let p_pa = air_pressure_hpa * 100.0;
    let t_k = air_temp_c + 273.15;
    (p_pa / (287.05 * t_k)).clamp(0.9, 1.4)
}

fn headwind_component(heading_deg: f64, wind_ms: f64, wind_dir_deg: f64) -> f64 {
    // Vind kommer FRA wind_dir_deg. Positivt ⇒ motvind i bevegelsesretning.
    let phi = (heading_deg - wind_dir_deg).to_radians();
    wind_ms * phi.cos()
}

pub fn compute_power(samples: &[Sample], profile: &Profile, weather: &Weather) -> Vec<f64> {
    let n = samples.len();
    if n == 0 {
        return Vec::new();
    }

    // Parametre
    let mass = profile.total_weight.unwrap_or(75.0);
    let crr = profile.crr.unwrap_or(0.005);
    let cda = cda_for(profile.bike_type.as_deref());
    let rho = air_density(weather.air_temp_c, weather.air_pressure_hpa);

    // Glatt høyde for stigning
    let alt = crate::smoothing::smooth_altitude(samples);

    let mut out = Vec::with_capacity(n);

    for i in 0..n {
        let s = &samples[i];

        // Tid og hastigheter
        let (dt, v_prev, alt_prev) = if i == 0 {
            (1.0, s.v_ms.max(0.0), alt[0])
        } else {
            let sp = &samples[i - 1];
            (((s.t - sp.t).abs()).max(1e-3), sp.v_ms.max(0.0), alt[i - 1])
        };

        let v = s.v_ms.max(0.0);
        let v_mid = 0.5 * (v + v_prev);        // dynamisk midtfart
        let a = (v - v_prev) / dt;             // m/s^2

        // Stigning via dh/ds, bruk midtfart for ds
        let ds = (v_mid * dt).max(1e-3);
        let slope = if i == 0 {
            0.0
        } else {
            ((alt[i] - alt_prev) / ds).clamp(-0.3, 0.3)
        };

        // Relativ vind ved midtfart
        let head = headwind_component(s.heading_deg, weather.wind_ms, weather.wind_dir_deg);
        let v_rel = (v_mid + head).max(0.0);

        // Komponenter (alle ved midtfart)
        let p_roll = mass * G * crr * v_mid;
        let p_aero = 0.5 * rho * cda * v_rel * v_rel * v_rel;
        let p_grav = mass * G * v_mid * slope.max(0.0);
        let p_acc = (mass * a * v_mid).max(0.0); // ← sikrer høyere effekt ved akselerasjon

        let p = p_roll + p_aero + p_grav + p_acc;
        out.push(if p.is_finite() { p.max(0.0) } else { 0.0 });
    }

    out
}