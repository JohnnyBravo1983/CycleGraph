use serde_json::{json, Value};

/// Midlertidig implementasjon av analyze_session for testing og golden-tests.
///
/// Returnerer en JSON-respons som `Value`. Hvis `watts` er tom,
/// antas det at økten mangler kraftdata og fallback til pulsmodus brukes.
pub fn analyze_session(
    watts: Vec<f32>,
    pulses: Vec<f32>,
    device_watts: Option<bool>,
) -> Result<Value, String> {
    if watts.is_empty() || device_watts == Some(false) {
        Ok(json!({
            "mode": "hr_only",
            "no_power_reason": "no_power_stream"
        }))
    } else {
        Ok(json!({
            "mode": "normal",
            "NP": 150,
            "avg": 145,
            "pulses": pulses.len()
        }))
    }
}
