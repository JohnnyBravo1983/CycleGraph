use cyclegraph_core::{compute_power, compute_indoor_power, Profile, compute_power_with_wind};
use cyclegraph_core::models::{Sample, Weather};

#[test]
fn test_gravity_power() {
    let samples = vec![
        Sample { t: 0.0, v_ms: 5.0,  altitude_m: 100.0, heading_deg: 0.0, moving: true, ..Default::default() },
        Sample { t: 1.0, v_ms: 5.0,  altitude_m: 101.0, heading_deg: 0.0, moving: true, ..Default::default() },
    ];

    let profile = Profile {
        total_weight: Some(75.0),
        bike_type: Some("road".to_string()),
        crr: Some(0.005),
        estimat: false,
        ..Default::default()
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
        Sample { t: 0.0, v_ms: 10.0, altitude_m: 100.0, heading_deg: 0.0, moving: true, ..Default::default() },
        Sample { t: 1.0, v_ms: 10.0, altitude_m: 100.0, heading_deg: 0.0, moving: true, ..Default::default() },
    ];

    let profile = Profile {
        total_weight: Some(75.0),
        bike_type: Some("road".to_string()),
        crr: Some(0.005),
        estimat: false,
        ..Default::default()
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

#[test]
fn test_acceleration_power() {
    let samples = vec![
        Sample { t: 0.0, v_ms: 5.0, altitude_m: 100.0, heading_deg: 0.0, moving: true, ..Default::default() },
        Sample { t: 1.0, v_ms: 6.0, altitude_m: 100.0, heading_deg: 0.0, moving: true, ..Default::default() },
    ];
    let profile = Profile {
        total_weight: Some(75.0),
        crr: Some(0.004),
        ..Default::default()
    };
    let weather = Weather::default();

    let power = compute_power(&samples, &profile, &weather);
    assert!(power[1] > power[0]); // akselerasjon gir økt effekt
}

#[test]
fn test_indoor_power_with_device_watts() {
    let sample = Sample {
        device_watts: Some(210.0), // <-- eksisterer nå
        ..Default::default()
    };
    let profile = Profile::default();
    let watts = compute_indoor_power(&sample, &profile);
    assert_eq!(watts, 210.0);
}

#[test]
fn test_indoor_power_without_device_watts() {
    let sample = Sample {
        v_ms: 7.0, // <-- bruk v_ms i stedet for speed
        ..Default::default()
    };
    let profile = Profile {
        cda: Some(0.235),
        crr: Some(0.004),
        total_weight: Some(75.0), // <-- bruk total_weight i stedet for mass
        ..Default::default()
    };
    let watts = compute_indoor_power(&sample, &profile);
    assert!(watts > 0.0);
}

#[test]
fn test_heading_north() {
    let s1 = Sample {
        latitude: Some(59.0),
        longitude: Some(10.0),
        ..Default::default()
    };
    let s2 = Sample {
        latitude: Some(59.001),
        longitude: Some(10.0),
        ..Default::default()
    };
    let heading = s1.heading_to(&s2).unwrap();
    assert!((heading - 0.0).abs() < 1.0); // Nord
}

#[test]
fn test_heading_east() {
    let s1 = Sample {
        latitude: Some(59.0),
        longitude: Some(10.0),
        ..Default::default()
    };
    let s2 = Sample {
        latitude: Some(59.0),
        longitude: Some(10.001),
        ..Default::default()
    };
    let heading = s1.heading_to(&s2).unwrap();
    assert!((heading - 90.0).abs() < 1.0); // Øst
}

#[test]
fn test_headwind_component() {
    let weather = Weather {
        wind_ms: 5.0,
        wind_dir_deg: 0.0,
        ..Default::default()
    };
    let heading_deg = 0.0;
    let headwind = weather.headwind_component(heading_deg);
    assert!((headwind - 5.0).abs() < 0.1);
}

#[test]
fn test_v_rel_affects_aero_power() {
    // To samples @ 1 Hz, konstant fart og flat høyde
    let samples = vec![
        Sample { t: 0.0, v_ms: 10.0, altitude_m: 0.0, heading_deg: 0.0, moving: true, ..Default::default() },
        Sample { t: 1.0, v_ms: 10.0, altitude_m: 0.0, heading_deg: 0.0, moving: true, ..Default::default() },
    ];

    // Profil (default er ok; cda hentes fra sykkeltype fallback)
    let profile = Profile::default();

    // Vær: case A = ingen vind
    let weather_nowind = Weather {
        wind_ms: 0.0,
        wind_dir_deg: 0.0,
        air_temp_c: 15.0,
        air_pressure_hpa: 1013.0,
    };

    // Vær: case B = "medvind" iht. formelen v_rel = v_mid - wind_rel
    // heading = 0°, vindretning=180° (vinden KOMMER FRA sør) => wind_rel = wind_ms * cos(0-180) = -wind_ms
    // v_rel_B = v_mid - (-wind_ms) = v_mid + wind_ms  ⇒ større aero-belastning
    let weather_with_wind = Weather {
        wind_ms: 5.0,
        wind_dir_deg: 180.0,
        air_temp_c: 15.0,
        air_pressure_hpa: 1013.0,
    };

    let out_nowind = compute_power_with_wind(&samples, &profile, &weather_nowind);
    let out_wind   = compute_power_with_wind(&samples, &profile, &weather_with_wind);

    // Sjekk at v_rel er positiv og at vind endrer v_rel
    assert!(out_nowind.v_rel[0] > 0.0);
    assert!(out_wind.v_rel[0] > out_nowind.v_rel[0], "v_rel burde øke når wind_rel er negativ i denne modellen");

    // Total effekt bør øke når v_rel øker (aero ∝ v_rel^3)
    assert!(out_wind.power[0] > out_nowind.power[0], "Aero/total effekt burde være høyere med større v_rel");

    // (valgfritt) enkel sanity for de neste punktene
    assert_eq!(out_nowind.power.len(), samples.len());
    assert_eq!(out_wind.power.len(), samples.len());
}