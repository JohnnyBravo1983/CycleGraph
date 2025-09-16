//! Trenings- og værrelaterte metrics brukt i CycleGraph

use once_cell::sync::Lazy;
use prometheus::{IntCounter, Registry};
use std::sync::atomic::AtomicUsize;

/// 🌤️ Værkontekst brukt for å justere effektivitet (bevisst f32 for konsistens)
#[derive(Debug, Clone, Copy, Default)]
pub struct WeatherContext {
    pub temperature: f32,     // °C
    pub humidity: f32,        // %
    pub wind_speed: f32,      // m/s
    pub wind_direction: f32,  // grader (0–360)
    pub pressure: f32,        // hPa
}

/// Intern helper: samlet justeringsfaktor fra vær
#[inline]
pub fn weather_adjustment_factor(weather: &WeatherContext) -> f32 {
    let humidity_factor = if weather.humidity > 80.0 { 0.95 } else { 1.0 };
    let temp_factor = if weather.temperature > 25.0 { 0.97 } else { 1.0 };
    let pressure_factor = if weather.pressure < 1000.0 { 0.98 } else { 1.0 };
    humidity_factor * temp_factor * pressure_factor
}

/// 1️⃣ Justert effektivitet for ett datapunkt (watt per hjerteslag) med værfaktor
#[inline]
pub fn adjusted_efficiency(watt: f32, hr: f32, weather: &WeatherContext) -> f32 {
    if hr <= 0.0 {
        0.0
    } else {
        (watt / hr) * weather_adjustment_factor(weather)
    }
}

/// 2️⃣ Sesjonsnivå: justert watt per hjerteslag basert på gjennomsnitt og vær
///
/// Merk: siden værfaktoren her er konstant for økten, justerer vi den
/// gjennomsnittlige w/beat direkte. Hvis du i fremtiden vil støtte
/// tidsvarierende vær, kan du iterere per sample med `adjusted_efficiency`.
#[inline]
pub fn w_per_beat_adjusted(power: &[f32], hr: &[f32], weather: &WeatherContext) -> f32 {
    let base = w_per_beat(power, hr);
    if base == 0.0 {
        0.0
    } else {
        base * weather_adjustment_factor(weather)
    }
}

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

    #[test]
    fn test_weather_adjustment_factor_and_adjusted_efficiency() {
        let weather = WeatherContext {
            temperature: 26.0, // -> 0.97
            humidity: 85.0,    // -> 0.95
            pressure: 995.0,   // -> 0.98
            wind_speed: 3.0,
            wind_direction: 180.0,
        };
        let factor = weather_adjustment_factor(&weather);
        // Forventet faktor: 0.95 * 0.97 * 0.98
        let expected_factor = 0.95 * 0.97 * 0.98;
        assert!((factor - expected_factor).abs() < 1e-6);

        // Ett datapunkt: 300W / 150bpm = 2.0 w/beat * faktor
        let adj = adjusted_efficiency(300.0, 150.0, &weather);
        let expected = 2.0 * expected_factor;
        assert!((adj - expected).abs() < 1e-6);
    }

    #[test]
    fn test_w_per_beat_adjusted() {
        let power = [200.0, 220.0, 180.0, 210.0];
        let hr = [150.0, 152.0, 148.0, 151.0];
        let base = w_per_beat(&power, &hr);

        let weather = WeatherContext {
            temperature: 10.0, // ingen temp-reduksjon
            humidity: 50.0,    // ingen humidity-reduksjon
            pressure: 1005.0,  // ingen pressure-reduksjon
            wind_speed: 5.0,
            wind_direction: 90.0,
        };
        let adj = w_per_beat_adjusted(&power, &hr, &weather);
        // Siden faktor = 1.0, forventer vi at adj == base
        assert!((adj - base).abs() < 1e-6);
    }
}