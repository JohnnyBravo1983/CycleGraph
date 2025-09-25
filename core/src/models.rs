// core/src/models.rs
use serde::{Serialize, Deserialize};

#[derive(Debug, Clone, Copy, Serialize, Deserialize, Default)]
pub struct Sample {
    pub t: f64,           // sek
    pub v_ms: f64,        // m/s
    pub altitude_m: f64,  // meter

    /// Statisk heading (grader). Brukes som fallback hvis GPS mangler.
    pub heading_deg: f64, // grader
    pub moving: bool,

    // --- S5: Indoor/GPS utvidelser ---
    /// Effekt fra rulle/powermeter (hvis tilgjengelig)
    #[serde(default)]
    pub device_watts: Option<f64>,

    /// GPS-posisjon (grader). Valgfritt; hvis satt kan vi beregne heading mellom punkter.
    #[serde(default)]
    pub latitude: Option<f64>,
    #[serde(default)]
    pub longitude: Option<f64>,
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize, Default)]
pub struct Weather {
    pub wind_ms: f64,         // m/s
    pub wind_dir_deg: f64,    // grader (vinden KOMMER FRA)
    pub air_temp_c: f64,      // °C
    pub air_pressure_hpa: f64 // hPa
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Profile {
    pub total_weight: Option<f64>,
    pub bike_type: Option<String>,
    pub crr: Option<f64>,
    pub cda: Option<f64>,
    pub calibrated: bool,
    pub calibration_mae: Option<f64>,
    pub estimat: bool,
}

// Gi fornuftige defaults for å støtte Profile::default()
impl Default for Profile {
    fn default() -> Self {
        Self {
            total_weight: None,
            bike_type: None,
            crr: None,
            cda: None,
            calibrated: false,
            calibration_mae: None,
            estimat: true,
        }
    }
}

impl Sample {
    /// Beregn heading (0–360°, der 0 = nord) fra dette punktet til `next` basert på GPS.
    /// Returnerer None hvis noen av koordinatene mangler.
    pub fn heading_to(&self, next: &Sample) -> Option<f64> {
        let (lat1, lon1, lat2, lon2) = match (
            self.latitude, self.longitude, next.latitude, next.longitude
        ) {
            (Some(a), Some(b), Some(c), Some(d)) => (a, b, c, d),
            _ => return None,
        };

        // Konverter til radianer
        let phi1 = lat1.to_radians();
        let phi2 = lat2.to_radians();
        let dlam = (lon2 - lon1).to_radians();

        // Storcirkel-azimuth (initial bearing)
        let y = dlam.sin() * phi2.cos();
        let x = phi1.cos() * phi2.sin() - phi1.sin() * phi2.cos() * dlam.cos();
        let mut theta = y.atan2(x).to_degrees(); // [-180, 180]
        if theta < 0.0 {
            theta += 360.0;
        }
        Some(theta)
    }
}

impl Weather {
    /// Komponent av vinden langs bevegelsesretningen (positiv = motvind).
    /// Bruker meteorologisk konvensjon: `wind_dir_deg` er retningen vinden KOMMER FRA.
    pub fn headwind_component(&self, heading_deg: f64) -> f64 {
        let rel_angle = (heading_deg - self.wind_dir_deg).rem_euclid(360.0).to_radians();
        self.wind_ms * rel_angle.cos()
    }
}