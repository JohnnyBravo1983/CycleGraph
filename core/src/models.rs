use serde::{Serialize, Deserialize};

#[derive(Debug, Clone, Copy)]
pub struct Sample {
    pub t: f64,           // sek
    pub v_ms: f64,        // m/s
    pub altitude_m: f64,  // meter
    pub heading_deg: f64, // grader
    pub moving: bool,
}

#[derive(Debug, Clone, Copy)]
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
    pub estimat: bool,
}

impl Default for Profile {
    fn default() -> Self {
        Self {
            total_weight: None,
            bike_type: None,
            crr: None,
            estimat: true,
        }
    }
}