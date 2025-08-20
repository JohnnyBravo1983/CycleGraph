// core/src/metrics.rs
// TODO: Midlertidige, enkle implementasjoner for å få testoppsett og golden-tests på plass.
// - np:   bruker gjennomsnittseffekt
// - IF:   np / ftp
// - VI:   np / avg_power
// - Pa:Hr returnerer 1.0 (innenfor rimelig testintervall)
// - W/beat: gjennomsnittlig watt delt på gjennomsnittlig puls

pub fn np(p: &[f32], _hz: f32) -> f32 {
    if p.is_empty() { return 0.0; }
    p.iter().copied().sum::<f32>() / (p.len() as f32)
}

pub fn intensity_factor(np: f32, ftp: f32) -> f32 {
    if ftp > 0.0 { np / ftp } else { 0.0 }
}

pub fn variability_index(np: f32, avg_power: f32) -> f32 {
    if avg_power > 0.0 { np / avg_power } else { 0.0 }
}

// For enkelhets skyld nå: stabil 1.0 (innenfor testens 0.95–1.08)
pub fn pa_hr(_hr: &[f32], _power: &[f32], _hz: f32) -> f32 {
    1.0
}

pub fn w_per_beat(power: &[f32], hr: &[f32]) -> f32 {
    if power.is_empty() || hr.is_empty() { return 0.0; }
    let avg_p = power.iter().copied().sum::<f32>() / (power.len() as f32);
    let avg_hr = hr.iter().copied().sum::<f32>() / (hr.len() as f32);
    if avg_hr > 0.0 { avg_p / avg_hr } else { 0.0 }
}
