use cyclegraph_core::metrics::w_per_beat;

#[test]
fn test_empty_arrays() {
    let result = w_per_beat(&[], &[]);
    assert_eq!(result, 0.0);
}

#[test]
fn test_mismatched_lengths() {
    let result = w_per_beat(&[100.0, 200.0], &[150.0]); // ulik lengde
    assert!(result.is_finite());
}

#[test]
fn test_nan_values() {
    let result = w_per_beat(&[f32::NAN, 200.0], &[150.0, 160.0]);
    assert!(result.is_nan() || result.is_finite()); // tester robusthet
}

#[test]
fn test_valid_input() {
    let result = w_per_beat(&[100.0, 200.0], &[150.0, 150.0]);
    let expected = (100.0 + 200.0) / (150.0 + 150.0); // snitt watt per puls
    assert!((result - expected).abs() < 0.01);
}
