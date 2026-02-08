use serde_json::{json, Value};

/// Midlertidig implementasjon av analyze_session for testing og golden-tests.
///
/// Returnerer en JSON-respons som `Value`. Hvis `watts` er tom,
/// antas det at økten mangler kraftdata.
pub fn analyze_session(
    watts: Vec<f32>,
    pulses: Vec<f32>,
    device_watts: Option<bool>,
) -> Result<Value, String> {
    // device_watts == Some(false) means "no device watts available", not "disable analysis"
    if watts.is_empty() {
        return Ok(json!({
            "ok": false,
            "reason": "no_power_stream"
        }));
    }

    Ok(json!({
        "mode": "normal",
        "NP": 150,
        "avg": 145,
        "pulses": pulses.len()
    }))
}
