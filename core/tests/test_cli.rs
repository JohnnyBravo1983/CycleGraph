use cyclegraph_core::metrics::compute_np;

#[test]
fn test_np_computation() {
    let power = vec![100.0, 200.0, 300.0, 400.0];
    let np = compute_np(&power);
    let avg = power.iter().sum::<f64>() / power.len() as f64;

    // For korte serier (<30s) bruker vi kortere vindu → NP kan være <= avg.
    assert!(np.is_finite());
    assert!(np <= avg + 1e-9);
}

#[test]
fn test_np_smoke() {
    let power = vec![200.0f64; 60];
    let np = compute_np(&power);
    let avg = 200.0;
    // Med ≥30 samples og konstant effekt skal NP≈avg
    assert!((np - avg).abs() < 1e-6);
}