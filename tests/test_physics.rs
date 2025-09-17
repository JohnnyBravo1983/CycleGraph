// tests/test_physics.rs
use cyclegraph_core::{compute_power, Profile};
use cyclegraph_core::models::{Sample, Weather};

#[test]
fn test_gravity_power() {
    let samples = vec![
        Sample { t: 0.0, v_ms: 5.0,  altitude_m: 100.0, heading_deg: 0.0, moving: true },
        Sample { t: 1.0, v_ms: 5.0,  altitude_m: 101.0, heading_deg: 0.0, moving: true },
    ];

    // Profile matcher lib.rs: total_weight, bike_type, crr, estimat
    let profile = Profile {
        total_weight: Some(75.0),
        bike_type: Some("road".to_string()), // CdA hentes i physics.rs basert på bike_type
        crr: Some(0.005),
        estimat: false, // alle felter er satt
    };

    let weather = Weather {
        wind_ms: 0.0,
        wind_dir_deg: 0.0,
        air_temp_c: 15.0,
        air_pressure_hpa: 1013.0,
    };

    let power = compute_power(&samples, &profile, &weather);
    assert!(power[0] > 0.0);
}

#[test]
fn test_aero_power() {
    let samples = vec![
        Sample { t: 0.0, v_ms: 10.0, altitude_m: 100.0, heading_deg: 0.0, moving: true },
        Sample { t: 1.0, v_ms: 10.0, altitude_m: 100.0, heading_deg: 0.0, moving: true },
    ];

    let profile = Profile {
        total_weight: Some(75.0),
        bike_type: Some("road".to_string()), // "road" ⇒ CdA≈0.30 i physics.rs
        crr: Some(0.005),
        estimat: false,
    };

    let weather = Weather {
        wind_ms: 2.0,
        wind_dir_deg: 180.0, // motvind
        air_temp_c: 15.0,
        air_pressure_hpa: 1013.0,
    };

    let power = compute_power(&samples, &profile, &weather);
    assert!(power[0] > 0.0);
}