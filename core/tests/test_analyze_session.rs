// core/tests/test_analyze_session.rs

use chrono::Utc;

// Importer fra modulen (ikke via crate-roten)
use cyclegraph_core::analyze_session::{analyze_session, AnalyzeInputs, AnalyzeOutputs};
use cyclegraph_core::physics::{estimate_crr, total_mass, RoundTo};

#[test]
fn analyze_session_without_weather_or_headings_returns_zeros_and_sets_crr_and_mass() {
    // Arrange
    let duration_secs = 10u32;

    let inputs = AnalyzeInputs {
        start_time: Utc::now(),
        lat: 59.4,
        lon: 10.5,
        headings_deg: &[], // tom: tvinger v_rel=0 uten vær/headings
        duration_secs,
        weather: None,

        // Bike Setup / profil
        bike_type: "Road",
        tire_width_mm: 28.0,
        tire_quality: "Vanlig",
        rider_weight_kg: 80.0,
        bike_weight_kg: 8.5,
    };

    // Act (modul-funksjonen tar 1 argument: AnalyzeInputs)
    let out: AnalyzeOutputs = analyze_session(inputs);

    // Assert: v_rel_ms skal ha length == duration_secs og være nuller
    assert_eq!(out.v_rel_ms.len(), duration_secs as usize, "v_rel_ms len");
    assert!(
        out.v_rel_ms.iter().all(|v| v.abs() < 1e-12),
        "v_rel_ms should be all zeros when no weather/headings"
    );

    // Sammendragsvinkel = 0 når vær/headings mangler
    assert!((out.wind_rel_deg - 0.0).abs() < 1e-12);

    // Crr brukt samsvarer med estimate_crr(...)
    let expected_crr = estimate_crr("Road", 28.0, "Vanlig").round_to(5);
    assert!(
        (out.crr_used - expected_crr).abs() < 1e-12,
        "crr_used mismatch: got {}, expected {}",
        out.crr_used,
        expected_crr
    );

    // Total masse samsvarer med total_mass(...)
    let expected_mass = total_mass(80.0, 8.5);
    assert!(
        (out.total_mass_kg - expected_mass).abs() < 1e-12,
        "total_mass_kg mismatch"
    );
}

#[test]
fn analyze_session_crr_quality_affects_value() {
    // Samme bredde/type – kvalitet skal påvirke Crr: Trening (1.2) > Vanlig (1.0) > Ritt (0.85)
    let trening = estimate_crr("Road", 28.0, "Trening");
    let vanlig = estimate_crr("Road", 28.0, "Vanlig");
    let ritt = estimate_crr("Road", 28.0, "Ritt");

    assert!(trening > vanlig, "Trening skal gi høyere Crr enn Vanlig");
    assert!(vanlig > ritt, "Vanlig skal gi høyere Crr enn Ritt");
}

#[test]
fn analyze_session_total_mass_rounding_is_5dp() {
    let rider = 82.34567_f64;
    let bike = 8.12345_f64;
    let tot = total_mass(rider, bike);
    assert!(
        (tot - (rider + bike).round_to(5)).abs() < 1e-12,
        "total_mass rounding to 5dp failed"
    );
}
