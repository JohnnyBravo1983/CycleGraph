// frontend/src/lib/axiosDevRewrite.ts

// Minimal axios-typer så vi slipper å importere axios
type AxiosRequestConfigLike = {
  url?: string;
  // resten av feltene er ikke relevante for oss
};

type AxiosLike = {
  interceptors: {
    request: {
      use: (onFulfilled: (cfg: AxiosRequestConfigLike) => AxiosRequestConfigLike) => void;
    };
  };
};

export function installAxiosDevRewrite(): void {
  if (!import.meta.env.DEV) return;

  // Finn evt. axios på globalThis (no-op hvis den ikke finnes)
  const axiosObj = (globalThis as unknown as { axios?: AxiosLike }).axios;
  if (!axiosObj || !axiosObj.interceptors?.request?.use) return;

  const base =
    (import.meta as unknown as { env: Record<string, string | undefined> }).env
      .VITE_BACKEND_URL || "";

  axiosObj.interceptors.request.use((cfg: AxiosRequestConfigLike) => {
    if (!cfg || typeof cfg !== "object" || !cfg.url) return cfg;

    let u = cfg.url;

    // Normaliser same-origin absolute URLer til path + query
    try {
      const asURL = new URL(u, window.location.origin);
      if (asURL.origin === window.location.origin) {
        u = asURL.pathname + asURL.search;
      }
    } catch {
      // ignorér parsing-feil; behold u som den er
    }

    // Omskriv trender-endepunkt til /api/… (så Vite-proxy fanger det)
    if (u.startsWith("/trends")) {
      u = "/api" + u;
    }
    // Legg til flere ved behov:
    // if (u.startsWith("/session")) u = "/api" + u;
    // if (u.startsWith("/stats"))   u = "/api" + u;

    // Prefiks med backend-base hvis satt (for dev med separat host/port)
    if (base && u.startsWith("/api/")) {
      u = base.replace(/\/+$/, "") + u;
    }

    return { ...cfg, url: u };
  });
}
