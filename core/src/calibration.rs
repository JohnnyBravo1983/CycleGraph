// core/src/calibration.rs
use crate::models::{Profile, Sample, Weather};
use crate::physics::compute_power;

// Hvis du vil kunne persistere direkte fra her:
use crate::storage::{load_profile, save_profile};
use std::error::Error;

#[derive(Debug, Clone)]
pub struct CalibrationResult {
    pub cda: f64,        // CdA brukt i modellen under fit (fra profile eller default)
    pub crr: f64,        // beste kandidat fra grid-search
    pub mae: f64,        // mean absolute error mot målt effekt
    pub calibrated: bool,
    pub reason: Option<String>,
}

#[inline]
fn profile_crr(profile: &Profile) -> f64 {
    profile.crr.unwrap_or(0.005)
}

#[inline]
fn profile_cda(profile: &Profile) -> f64 {
    profile.cda.unwrap_or(0.30) // konservativ default
}

/// Fit Crr (grid-search) gitt samples + målt effekt. CdA holdes konstant.
/// Returnerer MAE og flagg om kalibrering anses gyldig (<10% av snittwatt).
pub fn fit_cda_crr(
    samples: &[Sample],
    measured_power_w: &[f64],
    profile: &Profile,
    weather: &Weather,
) -> CalibrationResult {
    // Grunnleggende validering av input
    if samples.len() < 300 {
        return CalibrationResult {
            cda: profile_cda(profile),
            crr: profile_crr(profile),
            mae: 0.0,
            calibrated: false,
            reason: Some("insufficient_segment".into()),
        };
    }
    if measured_power_w.len() != samples.len() {
        return CalibrationResult {
            cda: profile_cda(profile),
            crr: profile_crr(profile),
            mae: 0.0,
            calibrated: false,
            reason: Some("length_mismatch_model_vs_measured".into()),
        };
    }
    if measured_power_w.iter().any(|x| !x.is_finite()) {
        return CalibrationResult {
            cda: profile_cda(profile),
            crr: profile_crr(profile),
            mae: 0.0,
            calibrated: false,
            reason: Some("non_finite_measured_power".into()),
        };
    }

    // Hold CdA konstant (fra profil eller default) inntil vi støtter 2D-fit
    let fixed_cda = profile_cda(profile);

    // Grid-search på Crr
    let mut best_crr = profile_crr(profile);
    let mut best_mae = f64::INFINITY;

    for crr in (3..=8).map(|x| x as f64 / 1000.0) {
        // Overstyr Crr i en midlertidig profil, hold CdA konstant
        let mut p = profile.clone();
        p.crr = Some(crr);
        p.cda = Some(fixed_cda);

        // Modellkraft for HELE segmentet
        let model_w: Vec<f64> = compute_power(samples, &p, weather);

        // Sikkerhetsvakt
        if model_w.len() != measured_power_w.len() {
            return CalibrationResult {
                cda: fixed_cda,
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
            if m.is_finite() && y.is_finite() {
                total_err += (m - y).abs();
                n += 1;
            }
        }
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
        cda: fixed_cda,
        crr: best_crr,
        mae: best_mae,
        calibrated,
        reason: None,
    }
}

/// Oppdaterer Profile med resultatet av kalibreringen.
pub fn apply_calibration_to_profile(profile: &mut Profile, result: &CalibrationResult) {
    profile.cda = Some(result.cda);
    profile.crr = Some(result.crr);
    profile.calibrated = result.calibrated;
    profile.calibration_mae = Some(result.mae);
    // Når vi har eksplisitt kalibrerte verdier er dette ikke lenger et estimat
    if result.calibrated {
        profile.estimat = false;
    }
}

/// (Valgfritt) Full flyt: last profil → fit → oppdater → lagre.
/// Praktisk for CLI/testing.
pub fn calibrate_and_persist(
    profile_path: &str,
    samples: &[Sample],
    measured_power_w: &[f64],
    weather: &Weather,
) -> Result<CalibrationResult, Box<dyn Error>> {
    let mut profile = load_profile(profile_path)?;
    let result = fit_cda_crr(samples, measured_power_w, &profile, weather);
    apply_calibration_to_profile(&mut profile, &result);
    save_profile(&profile, profile_path)?;
    Ok(result)
}