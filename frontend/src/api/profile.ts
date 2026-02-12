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
