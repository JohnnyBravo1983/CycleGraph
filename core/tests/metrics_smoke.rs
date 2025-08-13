use cyclegraph_core::*;
use serde_json::json;

#[test]
fn smoke_constant_series() {
    // 120 sek, 1 Hz, konstant 220W/135bpm
    let samples: Vec<_> = (0..120).map(|i| json!({
        "t": i as f32, "hr": 135.0, "watts": 220.0, "moving": true, "altitude": 100.0
    })).collect();

    let meta = json!({
        "session_id": "t1",
        "duration_sec": 120.0,
        "ftp": 260.0,
        "hr_max": 190.0,
        "start_time_utc": null
    });

    let cfg = json!({
        "ftp_auto_estimate": false,
        "cgs_weights": {"intensity":0.4,"duration":0.3,"quality":0.3}
    });

    let out = analyze_session_json(
        &serde_json::to_string(&samples).unwrap(),
        &serde_json::to_string(&meta).unwrap(),
        Some(&serde_json::to_string(&cfg).unwrap()),
    ).unwrap();

    let v: serde_json::Value = serde_json::from_str(&out).unwrap();
    assert_eq!(v["session_id"], "t1");
    assert!(v["np"].as_f64().unwrap() > 200.0);
    let vi = v["vi"].as_f64().unwrap();
    assert!(vi > 0.95 && vi < 1.05);
}
