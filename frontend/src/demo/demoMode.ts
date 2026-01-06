// frontend/src/demo/demoMode.ts
export const DEMO_KEY = "cg_demo";
export const DEMO_EVENT = "cg_demo_changed";

export function setDemoMode(on: boolean) {
  if (typeof window === "undefined") return;

  if (on) localStorage.setItem(DEMO_KEY, "1");
  else localStorage.removeItem(DEMO_KEY);

  // Notify same-tab listeners (React SPA navigation won't remount components)
  window.dispatchEvent(new Event(DEMO_EVENT));
}

export function isDemoMode(): boolean {
  if (typeof window === "undefined") return false;
  return localStorage.getItem(DEMO_KEY) === "1";
}