use std::collections::HashMap;
use std::sync::{Arc, Mutex};
use ordered_float::OrderedFloat;
use crate::metrics::{weather_cache_hit_total, weather_cache_miss_total, Metrics};

#[derive(Debug, Clone)]
pub struct WeatherData {
    pub temperature: f64,
    pub wind_speed: f64,
    pub pressure: f64,
}

#[derive(Debug, Default)]
pub struct WeatherClient {
    cache: Arc<Mutex<HashMap<(OrderedFloat<f64>, OrderedFloat<f64>, i64), WeatherData>>>,
}

impl WeatherClient {
    pub fn new() -> Self {
        Self {
            cache: Arc::new(Mutex::new(HashMap::new())),
        }
    }

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