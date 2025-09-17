// tests/test_physics.rs
use cyclegraph_core::{compute_power, Profile};
use cyclegraph_core::models::{Sample, Weather};

#[test]
fn test_gravity_power() {
    let samples = vec![
        Sample { t: 0.0, v_ms: 5.0, altitude_m: 100.0, heading_deg: 0.0, moving: true },
        Sample { t: 1.0, v_ms: 5.0, altitude_m: 101.0, heading_deg: 0.0, moving: true },
    ];
    let profile = Profile {
        mass_total_kg: 75.0,
        cda_m2: 0.3,
        crr: 0.005,
        drivetrain_loss: 0.03,
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