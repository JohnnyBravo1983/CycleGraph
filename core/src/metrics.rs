//! Trenings- og værrelaterte metrics brukt i CycleGraph

use once_cell::sync::Lazy;
use prometheus::{IntCounter, Registry};
use std::sync::atomic::AtomicUsize;

/// 🌦️ Metrics for vær-cache (brukes i WeatherClient)
#[derive(Debug)]
pub struct Metrics {
    pub weather_cache_hit_total: IntCounter,
    pub weather_cache_miss_total: IntCounter,
}

impl Metrics {
    pub fn new(registry: &Registry) -> Self {
        let hit = IntCounter::new("weather_cache_hit_total", "Total cache hits").unwrap();
        let miss = IntCounter::new("weather_cache_miss_total", "Total cache misses").unwrap();

        registry.register(Box::new(hit.clone())).unwrap();
        registry.register(Box::new(miss.clone())).unwrap();

        Metrics {
            weather_cache_hit_total: hit,
            weather_cache_miss_total: miss,
        }
    }
}

/// 🔧 Hjelpefunksjoner for å hente vær-metrics
pub fn weather_cache_hit_total(metrics: &Metrics) -> &IntCounter {
    &metrics.weather_cache_hit_total
}

pub fn weather_cache_miss_total(metrics: &Metrics) -> &IntCounter {
    &metrics.weather_cache_miss_total
}

/// 📊 Globale tellere for sessions uten kraftdata (én definisjon hver)
pub static SESSIONS_NO_POWER_TOTAL: Lazy<AtomicUsize> = Lazy::new(|| AtomicUsize::new(0));
pub static SESSIONS_DEVICE_WATTS_FALSE_TOTAL: Lazy<AtomicUsize> = Lazy::new(|| AtomicUsize::new(0));

/// 🔢 Normalized Power (NP) – her bare gjennomsnittseffekt for enkelhet
pub fn np(p: &[f32], _hz: f32) -> f32 {
    if p.is_empty() {
        0.0
    } else {
        p.iter().copied().sum::<f32>() / p.len() as f32
    }
}

/// Intensity Factor (IF) = NP / FTP
pub fn intensity_factor(np: f32, ftp: f32) -> f32 {
    if ftp > 0.0 {
        np / ftp
    } else {
        0.0
    }
}

/// Variability Index (VI) = NP / gjennomsnittseffekt
pub fn variability_index(np: f32, avg_power: f32) -> f32 {
    if avg_power > 0.0 {
        np / avg_power
    } else {
        0.0
    }
}

/// Pa:Hr – placeholder som returnerer 1.0
pub fn pa_hr(_hr: &[f32], _power: &[f32], _hz: f32) -> f32 {
    1.0
}

/// Watt per hjerteslag – gjennomsnittlig watt delt på gjennomsnittlig puls.
/// Returnerer 0.0 hvis input er tom eller gjennomsnittlig puls er null.
pub fn w_per_beat(power: &[f32], hr: &[f32]) -> f32 {
    if power.is_empty() || hr.is_empty() {
        return 0.0;
    }

    let avg_p = power.iter().copied().sum::<f32>() / power.len() as f32;
    let avg_hr = hr.iter().copied().sum::<f32>() / hr.len() as f32;

    if avg_hr > 0.0 {
        avg_p / avg_hr
    } else {
        0.0
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_w_per_beat_empty() {
        assert_eq!(w_per_beat(&[], &[]), 0.0);
    }

    #[test]
    fn test_w_per_beat_valid() {
        let result = w_per_beat(&[100.0, 200.0], &[150.0, 150.0]);
        let expected = 150.0 / 150.0;
        assert!((result - expected).abs() < 0.01);
    }

    #[test]
    fn test_np_basic() {
        let result = np(&[100.0, 200.0], 1.0);
        assert_eq!(result, 150.0);
    }

    #[test]
    fn test_intensity_factor() {
        let result = intensity_factor(200.0, 100.0);
        assert_eq!(result, 2.0);
    }

    #[test]
    fn test_variability_index() {
        let result = variability_index(200.0, 100.0);
        assert_eq!(result, 2.0);
    }

    #[test]
    fn test_pa_hr_constant() {
        let result = pa_hr(&[120.0, 125.0], &[150.0, 160.0], 1.0);
        assert_eq!(result, 1.0);
    }
}