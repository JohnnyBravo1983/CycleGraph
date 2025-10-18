use cyclegraph_core::{load_profile, save_profile, Profile};
use std::fs;

#[test]
fn test_save_and_load_profile() {
    let path = "tests/tmp_profile.json";

    // lag en dummy-profil
    let profile = Profile {
        total_weight: Some(78.0),
        bike_type: Some("gravel".to_string()),
        crr: Some(0.004),
        cda: Some(0.29),
        calibrated: true,
        calibration_mae: Some(0.015),
        estimat: false,
    };

    // lagre til disk
    save_profile(&profile, path).expect("kunne ikke lagre profil");

    // les tilbake
    let loaded = load_profile(path).expect("kunne ikke laste profil");

    assert_eq!(loaded.total_weight, Some(78.0));
    assert_eq!(loaded.bike_type, Some("gravel".to_string()));
    assert!(loaded.calibrated);

    // rydde opp
    fs::remove_file(path).ok();
}
