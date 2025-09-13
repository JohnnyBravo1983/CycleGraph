use cyclegraph_core::analyze_session;
use serde_json::Value;

#[test]
fn test_fallback_to_hr_only() {
    let watts = vec![];  // Ingen wattdata
    let pulses = vec![120.0, 125.0, 130.0];
    let device_watts = Some(true);

    let result_json = analyze_session(watts, pulses, device_watts).unwrap();
    let result: Value = serde_json::from_str(&result_json).unwrap();

    assert_eq!(result["mode"], "hr_only");
    assert_eq!(result["no_power_reason"], "no_power_stream");
}

#[test]
fn test_analyze_session_basic() {
    let watts = vec![150.0, 160.0];
    let pulses = vec![120.0, 122.0];
    let result = analyze_session(watts, pulses, Some(true));
    assert!(result.is_ok());
}