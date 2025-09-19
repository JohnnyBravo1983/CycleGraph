// core/tests/test_calibration.rs
use cyclegraph_core::calibration::fit_cda_crr;
use cyclegraph_core::compute_power; // re-eksportert i lib.rs via `pub use physics::compute_power;`
use cyclegraph_core::models::{Profile, Sample, Weather};

fn make_weather() -> Weather {
    Weather {
        wind_ms: 2.0,
        wind_dir_deg: 180.0,
        air_temp_c: 15.0,
        air_pressure_hpa: 1013.0,
    }
}

fn make_samples(n: usize) -> Vec<Sample> {
    // 1 Hz, svak økning i fart, “bakke” via høydeøkning (0.5 m/s ~ ca 5 % hvis ~10 m/s horisontal)
    (0..n)
        .map(|i| Sample {
            t: i as f64,
            v_ms: 6.0 + (i as f64 * 0.01),
            altitude_m: 100.0 + i as f64 * 0.5,
            heading_deg: 0.0,
            moving: true,
        })
        .collect()
}

#[test]
fn test_fit_cda_crr_recovers_known_crr_with_noise() {
    let weather = make_weather();

    // Ground-truth profil for å lage “målt” data
    let mut gt_profile = Profile::default();
    let gt_crr = 0.0055;
    gt_profile.crr = Some(gt_crr);

    // 300 samples ≈ 5 min @ 1 Hz
    let samples = make_samples(300);

    // Lag “målt” kraft fra modellen (ground truth) + liten deterministisk støy
    let mut measured_power_w = compute_power(&samples, &gt_profile, &weather);
    for (i, w) in measured_power_w.iter_mut().enumerate() {
        // ±1.5 W deterministisk “sagtann”-støy
        let noise = if i % 2 == 0 { 1.5 } else { -1.5 };
        *w += noise;
    }

    // Startprofil for fit (bevisst litt feil startverdi)
    let mut start_profile = Profile::default();
    start_profile.crr = Some(0.005); // nær, men ikke lik

    let result = fit_cda_crr(&samples, &measured_power_w, &start_profile, &weather);
    eprintln!("FIT RESULT: {:?}", result);

    assert!(result.mae.is_finite());
    assert!(result.calibrated, "Forventet calibrated=true når MAE < 10% av snitteffekt");
    // Crr må treffe innen rimelig margin (grid: 0.003–0.008 i steg 0.001)
    assert!(
        (result.crr - gt_crr).abs() <= 0.001,
        "CRR mismatch: got {}, expected ~{}",
        result.crr,
        gt_crr
    );

    // Ekstra sanity: MAE < 10% av snitteffekt (samme terskel som i fit)
    let avg_measured = measured_power_w.iter().copied().sum::<f64>() / measured_power_w.len() as f64;
    assert!(
        result.mae < 0.10 * avg_measured,
        "MAE too high: {} vs 10% of avg {}",
        result.mae,
        0.10 * avg_measured
    );
}

#[test]
fn test_fit_cda_crr_insufficient_segment() {
    let weather = make_weather();
    let samples = make_samples(120); // < 300 → skal gi insufficient_segment
    let measured_power_w = vec![250.0; samples.len()];

    let mut profile = Profile::default();
    profile.crr = Some(0.005);

    let result = fit_cda_crr(&samples, &measured_power_w, &profile, &weather);
    // forventet false og reason satt
    assert!(!result.calibrated);
    assert!(result.mae == 0.0);
    assert_eq!(result.reason.as_deref(), Some("insufficient_segment"));
}