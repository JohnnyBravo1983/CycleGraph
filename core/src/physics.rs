// core/src/physics.rs
use crate::models::{Profile, Sample, Weather};

const G: f64 = 9.80665;

/// Hjelpetrait for avrunding til N desimaler.
pub trait RoundTo {
    fn round_to(self, dp: u32) -> f64;
}

impl RoundTo for f64 {
    #[inline]
    fn round_to(self, dp: u32) -> f64 {
        if dp == 0 {
            return self.round();
        }
        let factor = 10_f64.powi(dp as i32);
        (self * factor).round() / factor
    }
}

/// Estimer Crr basert på dekkbredde og kvalitetsnivå.
/// Merk: `bike_type` tas inn for ev. fremtidig justering (ikke brukt nå).
/// - `tire_width` i millimeter (mm)
/// - `tire_quality` i {"Trening", "Vanlig", "Ritt"} (ukjent -> 1.0)
pub fn estimate_crr(bike_type: &str, tire_width: f64, tire_quality: &str) -> f64 {
    let _ = bike_type; // reservert for fremtidig bruk

    // Guard: sikre fornuftige grenser og finitte verdier
    let width_mm = if tire_width.is_finite() && tire_width > 10.0 {
        tire_width
    } else {
        25.0
    };

    let quality_factor = match tire_quality {
        "Trening" => 1.2,
        "Vanlig" => 1.0,
        "Ritt" => 0.85,
        _ => 1.0, // fallback
    };

    // Spesifisert baseformel + 5 desimalers avrunding
    let base = (28.0 / width_mm).powf(0.3);
    (base * quality_factor).round_to(5)
}

/// Total masse (kg) = rytter + sykkel, rundet til 5 desimaler.
#[inline]
pub fn total_mass(rider_weight_kg: f64, bike_weight_kg: f64) -> f64 {
    (rider_weight_kg + bike_weight_kg).round_to(5)
}

/// CdA ut fra sykkeltype (fallback hvis profile.cda ikke er satt)
fn cda_for(bike_type: Option<&str>) -> f64 {
    match bike_type.unwrap_or("road").to_lowercase().as_str() {
        "tt" | "tri" => 0.25,
        "mtb" | "gravel" => 0.40,
        _ => 0.30, // road default
    }
}

#[allow(dead_code)] // behold for mulig senere bruk
fn air_density(air_temp_c: f64, air_pressure_hpa: f64) -> f64 {
    // ρ = p / (R * T) ~ 1.225 kg/m^3 @ 15°C, 1013 hPa
    let p_pa = (air_pressure_hpa * 100.0).max(1.0);
    let t_k = (air_temp_c + 273.15).max(150.0);
    (p_pa / (287.05 * t_k)).clamp(0.9, 1.4)
}

/// Utdata fra kraftberegning med vind. Gjør vind-data tilgjengelig for CLI.
#[derive(Debug, Clone)]
pub struct PowerOutputs {
    pub power: Vec<f64>,    // W per sample
    pub wind_rel: Vec<f64>, // m/s (positiv = motvind langs heading)
    pub v_rel: Vec<f64>,    // m/s (relativ lufthastighet brukt i aero)
}

/// Full beregning med v_rel/wind_rel tilgjengelig.
pub fn compute_power_with_wind(
    samples: &[Sample],
    profile: &Profile,
    weather: &Weather,
) -> PowerOutputs {
    let n = samples.len();
    if n == 0 {
        return PowerOutputs {
            power: Vec::new(),
            wind_rel: Vec::new(),
            v_rel: Vec::new(),
        };
    }

    // Parametre (med fornuftige defaults).
    // OBS: crr og total_weight hentes fortsatt fra Profile for bakoverkompatibilitet.
    // Hvis du har beregnet estimate_crr/total_mass tidligere i flyten:
    // sett profile.crr og profile.total_weight før du kaller hit.
    let mass = profile.total_weight.unwrap_or(75.0);
    let crr = profile.crr.unwrap_or(0.005);
    let cda = profile
        .cda
        .unwrap_or_else(|| cda_for(profile.bike_type.as_deref()));

    // Glatt høyde for mer robust stigningsestim
    let alt = crate::smoothing::smooth_altitude(samples);

    let mut power_out = Vec::with_capacity(n);
    let mut wind_rel_out = Vec::with_capacity(n);
    let mut v_rel_out = Vec::with_capacity(n);

    for i in 0..n {
        let s = samples[i];

        // Tid og forrige punkt
        let (dt, v_prev, alt_prev) = if i == 0 {
            (1.0, s.v_ms.max(0.0), alt[0])
        } else {
            let sp = samples[i - 1];
            (((s.t - sp.t).abs()).max(1e-3), sp.v_ms.max(0.0), alt[i - 1])
        };

        // Midtfart og akselerasjon
        let v = s.v_ms.max(0.0);
        let v_mid = 0.5 * (v + v_prev); // m/s
        let a = (v - v_prev) / dt; // m/s^2

        // Stigning dh/ds (bruk midtfart for ds)
        let ds = (v_mid * dt).max(1e-3);
        let slope = if i == 0 {
            0.0
        } else {
            ((alt[i] - alt_prev) / ds).clamp(-0.3, 0.3)
        };

        // Heading fra påfølgende punkt, fallback 0.0
        let heading = if i + 1 < n {
            samples[i].heading_to(&samples[i + 1])
        } else {
            None
        };
        let heading_deg = heading.unwrap_or(0.0);

        // Vindkomponent langs bevegelsesretningen + relativ lufthastighet
        let wind_rel = weather.headwind_component(heading_deg);
        let v_rel = (v_mid - wind_rel).max(0.0); // sikrer ikke-negativ aero

        // Effektkomponenter
        let p_roll = mass * G * crr * v_mid;

        // Aero iht. spes: fast rho=1.225
        let p_aero = 0.5 * 1.225 * cda * v_rel.powi(3);

        let p_grav = (mass * G * v_mid * slope).max(0.0);
        let p_acc = (mass * a * v_mid).max(0.0);

        let p = p_roll + p_aero + p_grav + p_acc;
        power_out.push(if p.is_finite() { p.max(0.0) } else { 0.0 });
        wind_rel_out.push(wind_rel);
        v_rel_out.push(v_rel);
    }

    PowerOutputs {
        power: power_out,
        wind_rel: wind_rel_out,
        v_rel: v_rel_out,
    }
}

/// Bakoverkompatibel wrapper: returnerer kun watt, som før.
pub fn compute_power(samples: &[Sample], profile: &Profile, weather: &Weather) -> Vec<f64> {
    compute_power_with_wind(samples, profile, weather).power
}

/// Indoor-beregning:
/// 1) Hvis `device_watts` finnes på sample, returneres den (pass-through).
/// 2) Ellers: enkel aero + rullemotstand basert på v_ms og profil.
pub fn compute_indoor_power(sample: &Sample, profile: &Profile) -> f64 {
    if let Some(watts) = sample.device_watts {
        return watts;
    }

    // Fallback – enkel modell uten GPS/høyde
    let v = sample.v_ms.max(0.0); // m/s
    let cda = profile
        .cda
        .unwrap_or_else(|| cda_for(profile.bike_type.as_deref()));
    let crr = profile.crr.unwrap_or(0.004);
    let mass = profile.total_weight.unwrap_or(75.0);

    // Indoor: anta standard lufttetthet
    let rho = 1.225;

    let p_aero = 0.5 * rho * cda * v * v * v;
    let p_roll = mass * G * crr * v;

    (p_aero + p_roll).max(0.0)
}
