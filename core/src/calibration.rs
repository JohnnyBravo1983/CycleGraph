// core/src/calibration.rs
use crate::models::{Profile, Sample, Weather};
use crate::physics::compute_power;

#[derive(Debug)]
pub struct CalibrationResult {
    pub cda: f64,        // holdes konstant inntil Profile får CdA-felt
    pub crr: f64,        // beste kandidat fra grid-search
    pub mae: f64,        // mean absolute error mot målt effekt
    pub calibrated: bool,
    pub reason: Option<String>,
}

// Hent Crr fra profile med fornuftig default
fn profile_crr(profile: &Profile) -> f64 {
    profile.crr.unwrap_or(0.005)
}

// Inntil Profile får CdA: bruk en konservativ konstant
const DEFAULT_CDA: f64 = 0.30;

pub fn fit_cda_crr(
    samples: &[Sample],
    measured_power_w: &[f64], // målt effekt per sample (powermeter) for segmentet
    profile: &Profile,
    weather: &Weather,
) -> CalibrationResult {
    // Grunnleggende validering av input
    if samples.len() < 300 {
        return CalibrationResult {
            cda: DEFAULT_CDA,
            crr: profile_crr(profile),
            mae: 0.0,
            calibrated: false,
            reason: Some("insufficient_segment".into()),
        };
    }
    if measured_power_w.len() != samples.len() {
        return CalibrationResult {
            cda: DEFAULT_CDA,
            crr: profile_crr(profile),
            mae: 0.0,
            calibrated: false,
            reason: Some("length_mismatch_model_vs_measured".into()),
        };
    }
    if measured_power_w.iter().any(|x| !x.is_finite()) {
        return CalibrationResult {
            cda: DEFAULT_CDA,
            crr: profile_crr(profile),
            mae: 0.0,
            calibrated: false,
            reason: Some("non_finite_measured_power".into()),
        };
    }

    // Grid-search på Crr (CdA holdes konstant inntil vi har felt for den)
    let mut best_crr = profile_crr(profile);
    let mut best_mae = f64::INFINITY;

    for crr in (3..=8).map(|x| x as f64 / 1000.0) {
        // Overstyr Crr i en midlertidig profil
        let mut p = profile.clone();
        p.crr = Some(crr);

        // Modellkraft for HELE segmentet
        let model_w: Vec<f64> = compute_power(samples, &p, weather);

        // Sikkerhetsvakt (skulle være samme lengde, men verifiser)
        if model_w.len() != measured_power_w.len() {
            return CalibrationResult {
                cda: DEFAULT_CDA,
                crr: profile_crr(profile),
                mae: 0.0,
                calibrated: false,
                reason: Some("length_mismatch_model_vs_measured".into()),
            };
        }

        // MAE = gjennomsnittlig absoluttavvik
        let mut total_err = 0.0;
        let mut n = 0usize;
        for (m, y) in model_w.iter().zip(measured_power_w.iter()) {
            // hopp over ikke-finite verdier i modell (burde ikke skje, men defensivt)
            if m.is_finite() && y.is_finite() {
                total_err += (m - y).abs();
                n += 1;
            }
        }

        // Hvis alt ble filtrert vekk (uvanlig), hopp kandidat
        if n == 0 {
            continue;
        }

        let mae = total_err / n as f64;
        if mae < best_mae {
            best_mae = mae;
            best_crr = crr;
        }
    }

    // 10% terskel relativt til snitteffekten i segmentet
    let avg_measured = measured_power_w.iter().copied().sum::<f64>() / measured_power_w.len() as f64;
    let calibrated = avg_measured.is_finite() && best_mae < 0.10 * avg_measured;

    CalibrationResult {
        cda: DEFAULT_CDA, // TODO: utvid med CdA-fit når Profile har felt for dette
        crr: best_crr,
        mae: best_mae,
        calibrated,
        reason: None,
    }
}