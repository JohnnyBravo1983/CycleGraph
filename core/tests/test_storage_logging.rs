// tests/test_storage_logging.rs
use cyclegraph_core::{load_profile, save_profile, Profile};
use std::fs;

#[test]
fn test_storage_logging() {
    let path = "tests/tmp_profile.json";

    // Sørg for ren start (slett hvis filen finnes)
    let _ = fs::remove_file(path);

    let profile = Profile {
        total_weight: Some(78.0),
        bike_type: Some("gravel".to_string()),
        crr: Some(0.004),
        cda: Some(0.29),
        calibrated: true,
        calibration_mae: Some(0.015),
        estimat: false,
    };

    // Save
    save_profile(&profile, path).expect("save_profile failed");

    // Load
    let loaded = load_profile(path).expect("load_profile failed");

    // Assertions
    assert_eq!(loaded.total_weight, Some(78.0));
    assert_eq!(loaded.bike_type, Some("gravel".to_string()));
    assert_eq!(loaded.crr, Some(0.004));
    assert_eq!(loaded.cda, Some(0.29));
    assert!(loaded.calibrated);
    assert_eq!(loaded.calibration_mae, Some(0.015));
    assert!(!loaded.estimat);

    // Clean up
    let _ = fs::remove_file(path);
}
