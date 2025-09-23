// core/src/models.rs
use serde::{Serialize, Deserialize};

#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
pub struct Sample {
    pub t: f64,           // sek
    pub v_ms: f64,        // m/s
    pub altitude_m: f64,  // meter
    pub heading_deg: f64, // grader
    pub moving: bool,
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
pub struct Weather {
    pub wind_ms: f64,         // m/s
    pub wind_dir_deg: f64,    // grader
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