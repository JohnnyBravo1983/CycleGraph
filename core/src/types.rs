use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Sample {
    pub t: f32,                  // sekunder fra start (0..N, gjerne 1 Hz)
    pub hr: Option<f32>,         // bpm
    pub watts: Option<f32>,      // watt
    pub moving: Option<bool>,
    pub altitude: Option<f32>,   // meter
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Meta {
    pub session_id: String,
    pub duration_sec: f32,
    pub ftp: Option<f32>,
    pub hr_max: Option<f32>,
    pub start_time_utc: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct Cfg {
    pub ftp_auto_estimate: Option<bool>,
    pub cgs_weights: Option<CgsWeights>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CgsWeights {
    pub intensity: f32, // typ 0.4
    pub duration: f32,  // typ 0.3
    pub quality: f32,   // typ 0.3
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct SessionScores {
    pub intensity: f32,
    pub duration: f32,
    pub quality: f32,
    pub cgs: f32,
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct TrendInfo {
    pub cgs_last3_avg: Option<f32>,
    pub cgs_delta_vs_last3: Option<f32>,
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct SessionReport {
    pub session_id: String,
    pub duration_min: f32,
    pub avg_power: Option<f32>,
    pub avg_hr: Option<f32>,
    pub np: Option<f32>,
    pub r#if: Option<f32>,
    pub vi: Option<f32>,
    pub pa_hr_pct: Option<f32>,
    pub w_per_beat: Option<f32>,
    pub w_per_beat_baseline: Option<f32>,
    pub scores: SessionScores,
    pub badges: Vec<String>,
    pub trend: TrendInfo,
}
