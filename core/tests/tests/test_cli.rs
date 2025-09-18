#[test]
fn test_np_computation() {
    let power = vec![100.0, 200.0, 300.0, 400.0];
    let np = compute_np(&power);
    assert!(np > 250.0);
}