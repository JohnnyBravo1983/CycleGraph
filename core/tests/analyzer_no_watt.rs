use crate::analyze_session;
#[test]
fn test_fallback_to_hr_only() {
    let watts = vec![];  // Ingen wattdata
    let pulses = vec![120.0, 125.0, 130.0];
    let device_watts = Some(true);

    let result_json = analyze_session(watts, pulses, device_watts).unwrap();
    let result: serde_json::Value = serde_json::from_str(&result_json).unwrap();

    assert_eq!(result["mode"], "hr_only");
    assert_eq!(result["no_power_reason"], "no_power_stream");
}
