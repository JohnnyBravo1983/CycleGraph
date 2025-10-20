// core/src/weather_api.rs
use std::time::Duration;

use chrono::{DateTime, Utc};
use reqwest::blocking::Client as Agent;
use serde::Deserialize;

use crate::weather::{WeatherProvider, WeatherSummary};

#[derive(Debug, Clone, Deserialize)]
struct OpenMeteoResp {
    // Open-Meteo har både eldre `current_weather` og nyere `current`-nøkkel.
    // Vi støtter begge via alias.
    #[serde(alias = "current", alias = "current_weather")]
    current: CurrentWeather,
}

#[derive(Debug, Clone, Deserialize)]
struct CurrentWeather {
    // Eldre `current_weather`: temperature, windspeed, winddirection, pressure (varierer)
    // Nyere `current`: *_2m, *_10m, surface_pressure
    #[serde(alias = "temperature", alias = "temperature_2m")]
    temperature_2m: f64,
    #[serde(alias = "windspeed", alias = "wind_speed_10m")]
    wind_speed_10m: f64,
    #[serde(alias = "winddirection", alias = "wind_direction_10m")]
    wind_direction_10m: f64,
    #[serde(alias = "pressure", alias = "surface_pressure")]
    surface_pressure: f64,
}

/// Open-Meteo klient – blocking (reqwest)
pub struct OpenMeteoClient {
    agent: Agent,
}

impl OpenMeteoClient {
    pub fn new() -> Self {
        // Kort timeout for å unngå heng ved nettproblemer
        let agent = reqwest::blocking::Client::builder()
            .timeout(Duration::from_secs(5))
            .build()
            .expect("Failed to build reqwest blocking client");

        Self { agent }
    }
}

impl Default for OpenMeteoClient {
    fn default() -> Self {
        Self::new()
    }
}

impl WeatherProvider for OpenMeteoClient {
    fn get_weather_for_session(
        &self,
        _start_time: DateTime<Utc>,
        lat: f64,
        lon: f64,
        _duration_secs: u32,
    ) -> Option<WeatherSummary> {
        // NB: holder oss nettverks-agnostisk i test (funksjonen returnerer Option).
        let url = format!(
            "https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,wind_speed_10m,wind_direction_10m,surface_pressure"
        );

        let resp = self.agent.get(&url).send().ok()?;
        let body: OpenMeteoResp = resp.json().ok()?;

        // Enkel logging for debugging
        println!(
            "[OpenMeteo] lat={:.3}, lon={:.3} => {:.1}°C, {:.1} m/s @ {:.0}°, {:.0} hPa",
            lat,
            lon,
            body.current.temperature_2m,
            body.current.wind_speed_10m,
            body.current.wind_direction_10m,
            body.current.surface_pressure
        );

        Some(WeatherSummary {
            wind_speed_ms: body.current.wind_speed_10m,
            wind_dir_deg: body.current.wind_direction_10m,
            temperature_c: body.current.temperature_2m,
            pressure_hpa: body.current.surface_pressure,
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    // Denne testen ringer faktisk nettet → vi ignorerer den i CI.
    #[ignore]
    #[test]
    fn test_openmeteo_fetch() {
        // Oslo sentrum
        let client = OpenMeteoClient::new();
        let result = client.get_weather_for_session(Utc::now(), 59.91, 10.75, 60);
        assert!(result.is_some(), "OpenMeteo returned None");
        let w = result.unwrap();
        assert!(w.temperature_c > -40.0 && w.temperature_c < 50.0);
    }
}
