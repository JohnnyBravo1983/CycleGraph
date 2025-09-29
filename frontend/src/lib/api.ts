import type { SessionReport } from "../types/session";
import { mockSession } from "./mockSession";

// Bruk Vite-typene fra env.d.ts
const USE_MOCK = import.meta.env.VITE_USE_MOCK !== "0";     // default: mock på
const API_BASE = import.meta.env.VITE_API_BASE ?? "/api";   // default: /api

// Litt ventetid for realisme i mock
const delay = (ms: number) => new Promise((res) => setTimeout(res, ms));

export async function fetchSession(id: string): Promise<SessionReport> {
  if (USE_MOCK) {
    await delay(150);
    return { ...mockSession };
  }

  const url = `${API_BASE}/session/${encodeURIComponent(id)}`;
  const res = await fetch(url);
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(
      `HTTP ${res.status} ${res.statusText}${text ? ` – ${text}` : ""}`
    );
  }
  const data = (await res.json()) as SessionReport;
  return data;
}