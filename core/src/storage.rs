// core/src/storage.rs
use crate::models::Profile;
use serde::{Deserialize, Serialize};
use std::error::Error;
use std::fs;
use std::path::{Path, PathBuf};

/// Leser inn profil fra disk (JSON).
/// Hvis filen ikke finnes, returneres en default-profil.
pub fn load_profile(path: &str) -> Result<Profile, Box<dyn Error>> {
    if Path::new(path).exists() {
        let contents = fs::read_to_string(path)?;
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
    ensure_parent_dir(path)?;
    let json = serde_json::to_string_pretty(profile)?;
    fs::write(path, json)?;
    println!(
        "✅ Profil lagret til {} (calibrated={})",
        path, profile.calibrated
    );
    Ok(())
}

fn ensure_parent_dir(path: &str) -> Result<(), Box<dyn Error>> {
    if let Some(parent) = Path::new(path).parent() {
        if !parent.as_os_str().is_empty() {
            fs::create_dir_all(parent)?;
        }
    }
    Ok(())
}

/// --- Session metrics persistens -----------------------------------------------------
///
/// Minimalt, fremtidssikkert datasett for metrics vi ønsker å persistere pr. økt.
/// Trådsikkert å utvide senere uten å knekke lagret format (serde er tolerant for ekstra felt).
#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct SessionMetrics {
    /// Estimert rullemotstand (Crr) brukt i beregningene
    pub crr_used: Option<f64>,
    /// Ryttervekt i kg
    pub rider_weight: Option<f64>,
    /// Sykkelvekt i kg
    pub bike_weight: Option<f64>,
    /// Total masse i kg (= rytter + sykkel)
    pub total_mass: Option<f64>,

    /// (Valgfritt) Økt-ID eller nøkkel hvis du har det tilgjengelig
    #[serde(skip_serializing_if = "Option::is_none")]
    pub session_id: Option<String>,

    /// (Valgfritt) Ekstra nøkkel->verdi felt du vil lagre uten å endre structen
    #[serde(skip_serializing_if = "Option::is_none")]
    pub extra: Option<serde_json::Map<String, serde_json::Value>>,
}

/// Lagre metrics som en enkelt JSON-fil (pretty).
/// NB: Denne funksjonen **overskriver** path. Hvis du ønsker historikk, se `append_session_metrics_jsonl`.
pub fn save_session_metrics(metrics: &SessionMetrics, path: &str) -> Result<(), Box<dyn Error>> {
    ensure_parent_dir(path)?;
    let json = serde_json::to_string_pretty(metrics)?;
    fs::write(path, json)?;
    println!(
        "✅ Session metrics lagret til {} (crr_used={:?}, total_mass={:?})",
        path, metrics.crr_used, metrics.total_mass
    );
    Ok(())
}

/// Les metrics fra JSON-fil. Returnerer Ok(None) hvis fila ikke finnes.
pub fn load_session_metrics(path: &str) -> Result<Option<SessionMetrics>, Box<dyn Error>> {
    if Path::new(path).exists() {
        let contents = fs::read_to_string(path)?;
        let metrics: SessionMetrics = serde_json::from_str(&contents)?;
        println!(
            "📂 Session metrics lastet fra {} (crr_used={:?}, total_mass={:?})",
            path, metrics.crr_used, metrics.total_mass
        );
        Ok(Some(metrics))
    } else {
        println!("ℹ️ Fant ikke session metrics på {}, returnerer None", path);
        Ok(None)
    }
}

/// Alternativ: Append som JSONL (én økt per linje) for historikk/logg.
pub fn append_session_metrics_jsonl(
    metrics: &SessionMetrics,
    path: &str,
) -> Result<(), Box<dyn Error>> {
    ensure_parent_dir(path)?;
    let mut line = serde_json::to_string(metrics)?;
    line.push('\n');
    use std::io::Write;
    let mut file = open_append(path)?;
    file.write_all(line.as_bytes())?;
    println!("🧾 Session metrics appendet til {} (jsonl)", path);
    Ok(())
}

fn open_append(path: &str) -> Result<fs::File, Box<dyn Error>> {
    use std::fs::OpenOptions;
    let file = OpenOptions::new()
        .create(true)
        .append(true)
        .open(PathBuf::from(path))?;
    Ok(file)
}
