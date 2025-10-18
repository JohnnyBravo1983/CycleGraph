use cyclegraph_core::models::Sample;
use cyclegraph_core::smoothing::smooth_altitude;

#[test]
fn test_smooth_altitude() {
    let samples = vec![
        Sample {
            t: 0.0,
            v_ms: 0.0,
            altitude_m: 100.0,
            moving: true,
            ..Default::default()
        },
        Sample {
            t: 1.0,
            v_ms: 0.0,
            altitude_m: 200.0,
            moving: true,
            ..Default::default()
        }, // outlier
        Sample {
            t: 2.0,
            v_ms: 0.0,
            altitude_m: 102.0,
            moving: true,
            ..Default::default()
        },
    ];

    let smoothed = smooth_altitude(&samples);
    assert!(smoothed[1] < 150.0); // outlier dempet
}
