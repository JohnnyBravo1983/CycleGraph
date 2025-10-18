use chrono::{DateTime, Utc};
use ordered_float::OrderedFloat;
use prometheus::Registry;
use std::collections::HashMap;
use std::sync::{Arc, Mutex};

use crate::metrics::{weather_cache_hit_total, weather_cache_miss_total, Metrics};

/// ─────────────────────────────────────────────────────────────────────────────
/// Strukturer for konsistent værdata og vindinformasjon
/// ─────────────────────────────────────────────────────────────────────────────
#[derive(Debug, Clone)]
pub struct WeatherData {
    pub temperature: f64, // °C
    pub wind_speed: f64,  // m/s
    pub pressure: f64,    // hPa
}

/// Utvidet sammendragsstruktur (brukes av analyze_session)
#[derive(Debug, Clone)]
pub struct WeatherSummary {
    pub wind_speed_ms: f64, // m/s
    pub wind_dir_deg: f64,  // 0–360 (fra hvor vinden blåser)
    pub temperature_c: f64,
    pub pressure_hpa: f64,
}

/// ─────────────────────────────────────────────────────────────────────────────
/// Trait-grensesnitt for å hente værdata
/// ─────────────────────────────────────────────────────────────────────────────
pub trait WeatherProvider: Send + Sync {
    fn get_weather_for_session(
        &self,
        start_time: DateTime<Utc>,
        lat: f64,
        lon: f64,
        duration_secs: u32,
    ) -> Option<WeatherSummary>;
}

/// ─────────────────────────────────────────────────────────────────────────────
/// WeatherClient med enkel cache og simulerte data (kan senere byttes til API)
/// ─────────────────────────────────────────────────────────────────────────────
#[derive(Debug, Default)]
pub struct WeatherClient {
    #[allow(clippy::type_complexity)]
    cache: Arc<Mutex<HashMap<(OrderedFloat<f64>, OrderedFloat<f64>, i64), WeatherData>>>,
}

impl WeatherClient {
    pub fn new() -> Self {
        Self {
            cache: Arc::new(Mutex::new(HashMap::new())),
        }
    }

    /// Henter grunnleggende værdata (brukes internt)
    pub fn get_weather(
        &self,
        lat: f64,
        lon: f64,
        timestamp: i64,
        metrics: &Metrics,
    ) -> WeatherData {
        let key = (OrderedFloat(lat), OrderedFloat(lon), timestamp);
        let mut cache = self.cache.lock().unwrap();

        if let Some(data) = cache.get(&key) {
            weather_cache_hit_total(metrics).inc();
            return data.clone();
        }

        // Simulert API-kall (erstatt med ekte kall senere)
        let fetched = WeatherData {
            temperature: 17.5,
            wind_speed: 3.2,
            pressure: 1012.0,
        };

        cache.insert(key, fetched.clone());
        weather_cache_miss_total(metrics).inc();
        fetched
    }
}

/// ─────────────────────────────────────────────────────────────────────────────
/// Implementasjon av WeatherProvider for analyze_session
/// ─────────────────────────────────────────────────────────────────────────────
impl WeatherProvider for WeatherClient {
    fn get_weather_for_session(
        &self,
        start_time: DateTime<Utc>,
        lat: f64,
        lon: f64,
        _duration_secs: u32,
    ) -> Option<WeatherSummary> {
        // Bruk Unix-tid som nøkkel
        let timestamp = start_time.timestamp();

        // Henter grunnverdier fra cache eller mock-kall
        let registry = Registry::new();
        let dummy_metrics = Metrics::new(&registry);
        let base = self.get_weather(lat, lon, timestamp, &dummy_metrics);

        // Hvis vi ikke har vindretning fra kilden, default til 0.0 (vindstille/ukjent)
        Some(WeatherSummary {
            wind_speed_ms: base.wind_speed,
            wind_dir_deg: 0.0,
            temperature_c: base.temperature,
            pressure_hpa: base.pressure,
        })
    }
}

/// ─────────────────────────────────────────────────────────────────────────────
/// StaticWeatherProvider – brukes i tester for deterministisk output
/// ─────────────────────────────────────────────────────────────────────────────

#[derive(Clone)]
pub struct StaticWeatherProvider {
    pub summary: Option<WeatherSummary>,
}

impl WeatherProvider for StaticWeatherProvider {
    fn get_weather_for_session(
        &self,
        _start_time: DateTime<Utc>,
        _lat: f64,
        _lon: f64,
        _duration_secs: u32,
    ) -> Option<WeatherSummary> {
        self.summary.clone()
    }
}
