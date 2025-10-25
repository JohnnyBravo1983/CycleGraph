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

/// ─────────────────────────────────────────────────────────────────────────────
/// NYE HJELPERE (brukes av lib.rs / fysikkmotoren)
/// ─────────────────────────────────────────────────────────────────────────────

/// Klem (clamp) et tall til [lo, hi]
pub fn clamp_f64(x: f64, lo: f64, hi: f64) -> f64 {
    if x < lo {
        lo
    } else if x > hi {
        hi
    } else {
        x
    }
}

/// Normaliser lufttetthet til fornuftig område (fail-safe)
pub fn normalize_rho(rho: f64) -> f64 {
    // Ca. 0.9–1.5 dekker høyde/temperatur-variasjoner
    clamp_f64(rho, 0.9, 1.5)
}

/// Normaliser relativ vindvinkel (0..180°). >90° ~ motvind-komponent.
pub fn normalize_wind_angle_deg(angle: f64) -> f64 {
    if !angle.is_finite() {
        return 30.0; // trygg default
    }
    clamp_f64(angle, 0.0, 180.0)
}

/// Beregn relativ vinkel mellom kurs (heading_deg) og vindretning.
/// `wind_dir_deg` er *hvor vinden kommer fra* (meteorologisk, 0..360).
/// Relativ vinkel = vinkel mellom heading og vindens *retning mot* (wind_dir+180).
pub fn wind_rel_angle_deg(wind_dir_deg: f64, heading_deg: f64) -> f64 {
    // Normaliser begge vinkler til [0, 360)
    let hd = heading_deg.rem_euclid(360.0);
    let wd = wind_dir_deg.rem_euclid(360.0);

    // Vind blåser FRA wd, altså TIL (wd + 180)
    let wind_towards = (wd + 180.0).rem_euclid(360.0);

    // Absolutt vinkelavvik mellom retning du sykler og retning vinden blåser TIL
    let mut diff = (wind_towards - hd).abs();
    if diff > 180.0 {
        diff = 360.0 - diff;
    }

    // Sikrer 0..180 i henhold til din helper
    normalize_wind_angle_deg(diff)
}

/// Standard lufttetthet fra T (°C) og p (hPa): ρ = p / (R*T), R=287.05
pub fn air_density_from(temp_c: f64, pressure_hpa: f64) -> f64 {
    let p_pa = pressure_hpa * 100.0;
    let t_k = (temp_c + 273.15).max(1.0);
    normalize_rho(p_pa / (287.05 * t_k))
}
