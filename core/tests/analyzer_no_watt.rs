use cyclegraph_core::analyze_session; // aliaser til analyze_session_rust uten python-feature
use serde_json::Value;

#[test]
fn analyzer_no_watt_hr_only() {
    let watts = vec![];
    let pulses = vec![120.0, 125.0, 130.0];
    let device_watts = Some(true);

    // analyze_session(...) -> Result<Value, String>
    let result: Value = analyze_session(watts, pulses, device_watts).unwrap();

    assert_eq!(result.get("mode").and_then(|v| v.as_str()), Some("hr_only"));
    assert_eq!(result.get("no_power_reason").and_then(|v| v.as_str()), Some("no_power_stream"));
}
#[test]
fn test_analyze_session_basic() {
    let watts = vec![150.0, 160.0];
    let pulses = vec![120.0, 122.0];
    let device_watts = Some(true);

    let result = analyze_session(watts, pulses, device_watts);
    assert!(result.is_ok(), "Expected analyze_session to succeed");

    let parsed: Value = result.unwrap(); // ferdig, allerede en Value

    assert!(parsed.get("NP").is_some() || parsed.get("avg").is_some(), "Expected key 'NP' or 'avg' in output");
}