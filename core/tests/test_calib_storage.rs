use cyclegraph_core::{
    models::{Profile, Sample, Weather},
    calibration::fit_cda_crr,
    storage::{load_profile, save_profile},
};

#[test]
fn calib_updates_and_saves_profile_json() {
    // 1) Syntetiske samples (≈5 min @1Hz, 4% stigning)
    let samples: Vec<Sample> = (0..300).map(|i| Sample {
        t: i as f64,
        v_ms: 6.0 + (i as f64 * 0.01),
        altitude_m: 100.0 + i as f64 * 0.5,
        heading_deg: 0.0,
        moving: true,
    }).collect();

    // 2) “Målt” effekt (dummy)
    let measured_power_w: Vec<f64> = vec![250.0; samples.len()];

    // 3) Weather og profile
    let weather = Weather { wind_ms: 2.0, wind_dir_deg: 180.0, air_temp_c: 15.0, air_pressure_hpa: 1013.0 };
    let mut profile = Profile::default();
    profile.bike_type = Some("gravel".to_string());
    profile.total_weight = Some(78.0);
    profile.crr = Some(0.004);      // startantakelse
    profile.cda = Some(0.30);       // startantakelse

    // 4) Kjør kalibrering
    let result = fit_cda_crr(&samples, &measured_power_w, &profile, &weather);

    // 5) Oppdater profil
    profile.cda = Some(result.cda);
    profile.crr = Some(result.crr);
    profile.calibrated = result.calibrated;
    profile.calibration_mae = Some(result.mae);
    profile.estimat = false;

    // 6) Lagre og les tilbake
    let path = "profile.json";
    save_profile(&profile, path).expect("save_profile");
    let loaded = load_profile(path).expect("load_profile");

    // 7) Enkle asserts
    assert_eq!(loaded.calibrated, result.calibrated);
    assert!(loaded.crr.is_some());
    assert!(loaded.cda.is_some());
    assert!(loaded.calibration_mae.unwrap_or(1.0) >= 0.0);
}

use cyclegraph_core::{Profile, save_profile, load_profile};
use std::fs;

#[test]
fn test_roundtrip_profile_save_and_load() {
    let tmpfile = "tests/tmp_profile.json";

    // Lag et testprofil
    let profile = Profile {
        total_weight: Some(78.0),
        bike_type: Some("gravel".to_string()),
        crr: Some(0.004),
        cda: Some(0.29),
        calibrated: true,
        calibration_mae: Some(0.015),
        estimat: false,
    };

    // Lagre
    save_profile(&profile, tmpfile).expect("save_profile feilet");

    // Lese inn igjen
    let loaded = load_profile(tmpfile).expect("load_profile feilet");

    // Sammenlign
    assert_eq!(profile.total_weight, loaded.total_weight);
    assert_eq!(profile.bike_type, loaded.bike_type);
    assert_eq!(profile.crr, loaded.crr);
    assert_eq!(profile.cda, loaded.cda);
    assert_eq!(profile.calibrated, loaded.calibrated);
    assert_eq!(profile.calibration_mae, loaded.calibration_mae);
    assert_eq!(profile.estimat, loaded.estimat);

    // Rydd opp
    fs::remove_file(tmpfile).ok();
}