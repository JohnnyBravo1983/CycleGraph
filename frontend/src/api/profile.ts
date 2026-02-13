// frontend/src/api/profile.ts
import { cgApi } from "../lib/cgApi";

export async function getProfile(): Promise<any | null> {
  const res = await fetch(`${cgApi.baseUrl()}/api/profile/get`, {
    method: "GET",
    credentials: "include",
  });

  if (res.status === 204 || res.status === 404) return null;

  if (!res.ok) {
    let msg = `API-feil (${res.status})`;
    try {
      const j = await res.json();
      if (typeof j?.detail === "string") msg = j.detail;
      if (typeof j?.error === "string") msg = j.error;
    } catch {
      // ignore
    }
    throw new Error(msg);
  }

  try {
    const data = await res.json();
    if (!data || (typeof data === "object" && Object.keys(data).length === 0)) return null;
    return data;
  } catch {
    return null;
  }
}

// Minimal payload-type (ikke stram inn mer enn nødvendig nå)
export type SaveProfilePayload = {
  name?: string | null;
  weight?: number | null;
  ftp?: number | null;
  bike_type?: string | null;
  bike_weight?: number | null;
};

export async function saveProfile(payload: SaveProfilePayload): Promise<any> {
  const res = await fetch(`${cgApi.baseUrl()}/api/profile/save`, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
    },
    credentials: "include",
    body: JSON.stringify(payload ?? {}),
  });

  if (!res.ok) {
    let msg = `API-feil (${res.status})`;
    try {
      const j = await res.json();
      if (typeof j?.detail === "string") msg = j.detail;
      if (typeof j?.error === "string") msg = j.error;
    } catch {
      // ignore
    }
    throw new Error(msg);
  }

  // Noen backends returnerer 204 på save – håndter begge
  if (res.status === 204) return { ok: true };

  try {
    return await res.json();
  } catch {
    return { ok: true };
  }
}

/**
 * UI wrapper: mapper feltnavn fra ProfilePeekCard (rider_weight_kg, ftp_watts, bike_weight_kg)
 * til API-feltene backend forventer (weight, ftp, bike_weight).
 *
 * Dette lar oss holde UI-modellen stabil uten å endre backend.
 */
export type SaveProfileUiPayload = {
  name?: string | null;
  rider_weight_kg?: number | null;
  ftp_watts?: number | null;
  bike_type?: string | null;
  bike_weight_kg?: number | null;
};

export async function saveProfileFromUi(ui: SaveProfileUiPayload): Promise<any> {
  const mapped: SaveProfilePayload = {
    name: ui.name ?? null,
    weight: ui.rider_weight_kg ?? null,
    ftp: ui.ftp_watts ?? null,
    bike_type: ui.bike_type ?? null,
    bike_weight: ui.bike_weight_kg ?? null,
  };
  return saveProfile(mapped);
}
