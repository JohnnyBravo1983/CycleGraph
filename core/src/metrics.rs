//! Trenings- og værrelaterte metrics brukt i CycleGraph

use once_cell::sync::Lazy;
use prometheus::{IntCounter, Registry};
use std::sync::atomic::AtomicUsize;

/// 🌤️ Værkontekst brukt for å justere effektivitet (bevisst f32 for konsistens)
#[derive(Debug, Clone, Copy, Default)]
pub struct WeatherContext {
    pub temperature: f32,    // °C
    pub humidity: f32,       // %
    pub wind_speed: f32,     // m/s
    pub wind_direction: f32, // grader (0–360)
    pub pressure: f32,       // hPa
}

/// Intern helper: samlet justeringsfaktor fra vær
#[inline]
pub fn weather_adjustment_factor(weather: &WeatherContext) -> f32 {
    let humidity_factor = if weather.humidity > 80.0 { 0.95 } else { 1.0 };
    let temp_factor = if weather.temperature > 25.0 {
        0.97
    } else {
        1.0
    };
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

pub fn weather_cache_hit_total(metrics: &Metrics) -> &IntCounter {
    &metrics.weather_cache_hit_total
}

pub fn weather_cache_miss_total(metrics: &Metrics) -> &IntCounter {
    &metrics.weather_cache_miss_total
}

pub static SESSIONS_NO_POWER_TOTAL: Lazy<AtomicUsize> = Lazy::new(|| AtomicUsize::new(0));
pub static SESSIONS_DEVICE_WATTS_FALSE_TOTAL: Lazy<AtomicUsize> = Lazy::new(|| AtomicUsize::new(0));

#[inline]
fn mean(xs: &[f32]) -> f32 {
    if xs.is_empty() {
        0.0
    } else {
        xs.iter().copied().sum::<f32>() / xs.len() as f32
    }
}

fn median_f32(xs: &mut [f32]) -> f32 {
    if xs.is_empty() {
        return 0.0;
    }
    xs.sort_by(|a, b| a.partial_cmp(b).unwrap_or(std::cmp::Ordering::Equal));
    let n = xs.len();
    if n % 2 == 1 {
        xs[n / 2]
    } else {
        0.5 * (xs[n / 2 - 1] + xs[n / 2])
    }
}

#[inline]
pub fn avg_power(p: &[f32]) -> f32 {
    mean(p)
}

pub fn np(p: &[f32], hz: f32) -> f32 {
    if p.is_empty() {
        return 0.0;
    }
    let hz = if hz.is_finite() && hz > 0.0 { hz } else { 1.0 };
    let win = (30.0 * hz).floor() as usize;
    let window = win.max(1);

    if p.len() < window {
        return avg_power(p);
    }

    let mut rolling: Vec<f64> = Vec::with_capacity(p.len());
    let mut sum: f64 = 0.0;
    for i in 0..p.len() {
        sum += p[i] as f64;
        if i >= window {
            sum -= p[i - window] as f64;
        }
        let avg = if i + 1 >= window {
            sum / window as f64
        } else {
            sum / (i + 1) as f64
        };
        rolling.push(avg);
    }

    let m4 = rolling.iter().map(|x| x.powi(4)).sum::<f64>() / rolling.len() as f64;
    m4.powf(0.25) as f32
}

pub fn compute_np(power: &[f64]) -> f64 {
    if power.is_empty() {
        return 0.0;
    }
    let window = 30usize;

    if power.len() < window {
        return power.iter().copied().sum::<f64>() / power.len() as f64;
    }

    let mut rolling: Vec<f64> = Vec::with_capacity(power.len());
    let mut sum = 0.0;
    for i in 0..power.len() {
        sum += power[i];
        if i >= window {
            sum -= power[i - window];
        }
        let avg = if i + 1 >= window {
            sum / window as f64
        } else {
            sum / (i + 1) as f64
        };
        rolling.push(avg);
    }
    let m4 = rolling.iter().map(|x| x.powi(4)).sum::<f64>() / rolling.len() as f64;
    m4.powf(0.25)
}

#[inline]
pub fn intensity_factor(np: f32, ftp: f32) -> f32 {
    if ftp > 0.0 {
        np / ftp
    } else {
        0.0
    }
}

#[inline]
pub fn variability_index(np: f32, avg_power: f32) -> f32 {
    if avg_power > 0.0 {
        np / avg_power
    } else {
        0.0
    }
}

pub fn pa_hr(hr: &[f32], power: &[f32], _hz: f32) -> f32 {
    if hr.is_empty() || power.is_empty() {
        return 0.0;
    }

    let avg_hr = mean(hr);
    if avg_hr <= 0.0 {
        return 0.0;
    }

    let avg_p = avg_power(power);
    let w_per_beat_session = avg_p / avg_hr;

    let n = hr.len().min(power.len());
    let mut wpb_series: Vec<f32> = Vec::with_capacity(n);
    for i in 0..n {
        let h = hr[i];
        let p = power[i];
        if h > 0.0 && p.is_finite() {
            wpb_series.push(p / h);
        }
    }

    let baseline = if !wpb_series.is_empty() {
        median_f32(&mut wpb_series)
    } else {
        w_per_beat_session
    };

    if baseline > 0.0 {
        w_per_beat_session / baseline
    } else {
        0.0
    }
}

pub fn w_per_beat(power: &[f32], hr: &[f32]) -> f32 {
    if power.is_empty() || hr.is_empty() {
        return 0.0;
    }

    let avg_p = avg_power(power);
    let avg_hr = mean(hr);

    if avg_hr > 0.0 {
        avg_p / avg_hr
    } else {
        0.0
    }
}

pub fn precision_watt(power: &[f32], hz: f32) -> f32 {
    if power.is_empty() {
        return 0.0;
    }
    let hz = if hz.is_finite() && hz > 0.0 { hz } else { 1.0 };
    let win = (30.0 * hz).floor() as usize;
    let window = win.max(1).min(power.len());

    let mut rolling: Vec<f32> = Vec::with_capacity(power.len());
    let mut sum: f64 = 0.0;
    for i in 0..power.len() {
        sum += power[i] as f64;
        if i >= window {
            sum -= power[i - window] as f64;
        }
        let avg = if i + 1 >= window {
            sum / window as f64
        } else {
            sum / (i + 1) as f64
        };
        rolling.push(avg as f32);
    }

    let mut resid: Vec<f32> = power
        .iter()
        .zip(rolling.iter())
        .map(|(p, m)| *p - *m)
        .collect();

    if resid.is_empty() {
        return 0.0;
    }

    resid.sort_by(|a, b| a.partial_cmp(b).unwrap_or(std::cmp::Ordering::Equal));

    let q = |v: &[f32], q: f32| -> f32 {
        if v.is_empty() {
            return 0.0;
        }
        let n = v.len() as f32;
        let idx = (q * (n - 1.0)).clamp(0.0, n - 1.0);
        let lo = idx.floor() as usize;
        let hi = idx.ceil() as usize;
        if lo == hi {
            v[lo]
        } else {
            let w = idx - lo as f32;
            v[lo] * (1.0 - w) + v[hi] * w
        }
    };

    let q1 = q(&resid, 0.25);
    let q3 = q(&resid, 0.75);
    let iqr = (q3 - q1).abs();
    let sigma = if iqr > 0.0 { iqr / 1.349 } else { 0.0 };

    if window > 0 {
        sigma / (window as f32).sqrt()
    } else {
        sigma
    }
}

pub fn format_precision_watt(pw: f32) -> String {
    if !pw.is_finite() {
        return "±0.0 W".to_string();
    }
    format!("±{:.1} W", pw.max(0.0))
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
    fn test_avg_power_basic() {
        let result = avg_power(&[100.0, 200.0, 300.0]);
        assert!((result - 200.0).abs() < 1e-6);
    }

    #[test]
    fn test_np_basic_matches_compute_np_for_1hz() {
        let p32 = [100.0f32, 200.0f32];
        let p64 = [100.0f64, 200.0f64];
        let np_f32 = np(&p32, 1.0);
        let np_f64 = compute_np(&p64) as f32;
        assert!((np_f32 - np_f64).abs() < 1e-4);
    }

    #[test]
    fn test_compute_np_smoke() {
        let power = vec![200.0f64; 60];
        let npv = compute_np(&power);
        assert!(npv.is_finite());
        assert!((npv - 200.0).abs() < 1e-6);
    }

    #[test]
    fn test_intensity_factor() {
        let result = intensity_factor(200.0, 100.0);
        assert_eq!(result, 2.0);
    }

    #[test]
    fn test_variability_index() {
        let vi = variability_index(200.0, 100.0);
        assert_eq!(vi, 2.0);
    }

    #[test]
    fn test_pa_hr() {
        let hr = [150.0, 150.0, 150.0];
        let p = [100.0, 200.0, 165.0];
        let v = pa_hr(&hr, &p, 1.0);
        let expected = (155.0 / 150.0) / 1.1;
        assert!((v - expected).abs() < 1e-6);
    }

    #[test]
    fn test_weather_adjustment_factor_and_adjusted_efficiency() {
        let weather = WeatherContext {
            temperature: 26.0,
            humidity: 85.0,
            pressure: 995.0,
            wind_speed: 3.0,
            wind_direction: 180.0,
        };
        let factor = weather_adjustment_factor(&weather);
        let expected_factor = 0.95 * 0.97 * 0.98;
        assert!((factor - expected_factor).abs() < 1e-6);

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
            temperature: 10.0,
            humidity: 50.0,
            pressure: 1005.0,
            wind_speed: 5.0,
            wind_direction: 90.0,
        };
        let adj = w_per_beat_adjusted(&power, &hr, &weather);
        assert!((adj - base).abs() < 1e-6);
    }

    #[test]
    fn test_precision_watt_constant_series() {
        // Helt jevnt signal → usikkerhet ~ 0
        let p = vec![200.0f32; 120];
        let pw = precision_watt(&p, 1.0);
        assert!((0.0..0.01).contains(&pw));
        let s = format_precision_watt(pw);
        assert_eq!(s, "±0.0 W");
    }

    #[test]
    fn test_precision_watt_small_variation() {
        let mut p: Vec<f32> = Vec::with_capacity(120);
        for i in 0..120 {
            let delta = if i % 4 == 0 { 2.0 } else { -2.0 };
            p.push(200.0 + delta);
        }
        let pw = precision_watt(&p, 1.0);
        assert!(pw.is_finite() && pw > 0.0);
        assert!(pw < 5.0);
    }
}
