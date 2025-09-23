use crate::models::Profile;
use std::error::Error;
use std::path::Path;

/// Leser inn profil fra disk (JSON).
/// Hvis filen ikke finnes, returneres en default-profil.
pub fn load_profile(path: &str) -> Result<Profile, Box<dyn Error>> {
    if Path::new(path).exists() {
        let contents = std::fs::read_to_string(path)?;
        let profile: Profile = serde_json::from_str(&contents)?;
        println!(
            "📂 Profil lastet fra {} (calibrated={})",
            path, profile.calibrated
        );
        Ok(profile)
    } else {
        println!(
            "⚠️ Fant ikke profil på {}, returnerer default (calibrated=false)",
            path
        );
        Ok(Profile::default())
    }
}

/// Lagrer profil til disk som JSON (pretty-print).
pub fn save_profile(profile: &Profile, path: &str) -> Result<(), Box<dyn Error>> {
    let json = serde_json::to_string_pretty(profile)?;
    std::fs::write(path, json)?;
    println!(
        "✅ Profil lagret til {} (calibrated={})",
        path, profile.calibrated
    );
    Ok(())
}