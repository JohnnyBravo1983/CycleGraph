use cyclegraph_core::analyze_session;
use serde_json::Value;

#[test]
fn test_fallback_to_hr_only() {
    let watts = vec![]; // Ingen wattdata
    let pulses = vec![120.0, 125.0, 130.0];
    let device_watts = Some(true);

    let result_json = analyze_session(watts, pulses, device_watts)
        .expect("Expected analyze_session to return Ok");

    let result: Value = serde_json::from_str(&result_json)
        .expect("Expected valid JSON output");

    assert_eq!(result["mode"], "hr_only");
    assert_eq!(result["no_power_reason"], "no_power_stream");
}

#[test]
fn test_analyze_session_basic() {
    let watts = vec![150.0, 160.0];
    let pulses = vec![120.0, 122.0];
    let device_watts = Some(true);

    let result = analyze_session(watts, pulses, device_watts);
    assert!(result.is_ok(), "Expected analyze_session to succeed");

    let json = result.unwrap();
    let parsed: Value = serde_json::from_str(&json).expect("Expected valid JSON");

    assert!(parsed.get("NP").is_some() || parsed.get("avg").is_some(), "Expected key 'NP' or 'avg' in output");
}