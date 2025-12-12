import React from "react";
import type { SessionHoverSummary } from "../types/sessionHover";
import {
  fmtWatt,
  fmtKm,
  fmtStartTime,
  fmtWeather,
  fmtProfile,
} from "../types/sessionHover";

type Props = {
  data: SessionHoverSummary;
};

const SessionHoverCard: React.FC<Props> = ({ data }) => {
  return (
    <div
      style={{
        position: "absolute",
        zIndex: 50,
        right: 12,
        top: "50%",
        transform: "translateY(-50%)",
        width: 320,
        background: "white",
        border: "1px solid rgba(0,0,0,0.12)",
        borderRadius: 12,
        padding: 12,
        boxShadow: "0 10px 30px rgba(0,0,0,0.15)",
      }}
      role="tooltip"
      aria-label="Session summary"
    >
      <div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
        <div style={{ fontSize: 12, opacity: 0.7 }}>Precision Watt (avg)</div>
        <div style={{ fontWeight: 800, fontSize: 16 }}>{fmtWatt(data.precision_watt_avg)}</div>
      </div>

      <div style={{ marginTop: 8, display: "grid", gap: 6 }}>
        <Row label="Start" value={fmtStartTime(data.start_time)} />
        <Row label="Distanse" value={fmtKm(data.distance_km)} />
        <Row label="Weather" value={fmtWeather(data.weather_source)} />
        <Row label="Profile" value={fmtProfile(data.profile_label)} />
      </div>

      <div style={{ marginTop: 10, fontSize: 11, opacity: 0.6 }}>
        Kilde: sessions-list (ikke re-analyse)
      </div>
    </div>
  );
};

const Row: React.FC<{ label: string; value: string }> = ({ label, value }) => (
  <div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
    <div style={{ fontSize: 12, opacity: 0.7 }}>{label}</div>
    <div style={{ fontSize: 12, fontWeight: 600, textAlign: "right" }}>{value}</div>
  </div>
);

export default SessionHoverCard;
