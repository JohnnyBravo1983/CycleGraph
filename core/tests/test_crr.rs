// tests/test_crr.rs

use cyclegraph_core::physics::{estimate_crr, total_mass, RoundTo};

#[test]
fn crr_known_qualities_and_rounding() {
    // 3 x 3 x 3 kombinasjoner (bike_type brukes ikke ennå, men API-stabilitet)
    let bike_types = ["Road", "Gravel", "MTB"];
    let widths_mm = [23.0_f64, 28.0_f64, 40.0_f64];
    let qualities = ["Trening", "Vanlig", "Ritt"];

    for bt in bike_types {
        for w in widths_mm {
            for q in qualities {
                let crr = estimate_crr(bt, w, q);
                // 5 desimaler
                assert!(
                    (crr - crr.round_to(5)).abs() < 1e-12,
                    "Crr ikke rundet til 5 desimaler: bt={bt}, w={w}, q={q}, crr={crr}"
                );
                // Forventet “rimelig” område for Crr
                assert!(
                    crr.is_finite() && crr > 0.0005 && crr < 0.02,
                    "Crr utenfor forventet intervall: {crr} (bt={bt}, w={w}, q={q})"
                );
            }
        }
    }
}

#[test]
fn crr_quality_ordering_for_same_width() {
    // For samme bredde bør Trening (1.2) > Vanlig (1.0) > Ritt (0.85)
    let w = 28.0;
    let trening = estimate_crr("Road", w, "Trening");
    let vanlig = estimate_crr("Road", w, "Vanlig");
    let ritt = estimate_crr("Road", w, "Ritt");

    assert!(trening > vanlig, "Trening skal gi større Crr enn Vanlig");
    assert!(vanlig > ritt, "Vanlig skal gi større Crr enn Ritt");
}

#[test]
fn crr_extreme_widths_and_unknown_quality_fallback() {
    // Ekstremt smalt/bredt skal gi finitte verdier
    let crr_narrow = estimate_crr("Road", 18.0, "Vanlig");
    assert!(crr_narrow.is_finite() && crr_narrow > 0.0);

    let crr_wide = estimate_crr("Gravel", 55.0, "Vanlig");
    assert!(crr_wide.is_finite() && crr_wide > 0.0);

    // Ukjent kvalitet -> faktor 1.0 (samme som "Vanlig")
    let crr_unknown = estimate_crr("Road", 28.0, "UkjentEtikett");
    let crr_vanlig = estimate_crr("Road", 28.0, "Vanlig");
    assert!(
        (crr_unknown - crr_vanlig).abs() < 1e-12,
        "Ukjent kvalitet bør falle tilbake til 1.0 (Vanlig)"
    );
}

#[test]
fn crr_width_guard_falls_back_to_25mm_when_too_small() {
    // I implementasjonen: width <= 10.0 eller ikke-finit → fallback til 25.0
    let crr_tiny = estimate_crr("Road", 8.0, "Vanlig");
    let crr_fallback = estimate_crr("Road", 25.0, "Vanlig");
    assert!(
        (crr_tiny - crr_fallback).abs() < 1e-12,
        "Bredde <= 10mm skal falle tilbake til 25mm-beregning"
    );
}

#[test]
fn total_mass_is_sum_and_rounded_to_5dp() {
    let rider = 82.34567_f64;
    let bike = 8.12345_f64;
    let expected = (rider + bike).round_to(5);
    let tot = total_mass(rider, bike);
    assert!(
        (tot - expected).abs() < 1e-12,
        "Total masse feil: fikk {tot}, forventet {expected}"
    );
}

#[test]
fn crr_and_mass_are_ready_for_pw() {
    // Sanity: verdiene skal være >0 og finitte slik at PW-formelen kan bruke dem
    let crr = estimate_crr("Road", 28.0, "Ritt");
    let m = total_mass(80.0, 8.5);
    assert!(crr.is_finite() && crr > 0.0, "Crr må være > 0 og finite");
    assert!(
        m.is_finite() && m > 0.0,
        "Total masse må være > 0 og finite"
    );
}
