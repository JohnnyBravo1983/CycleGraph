// frontend/src/devFetchShim.ts
// Intercept dev/mock-requests og tving same-origin (/api/...) i stedet for absolutte :8000-URLer.

type ViteEnv = Record<string, string | undefined>;

function readViteEnv(): ViteEnv {
  return (
    (typeof import.meta !== "undefined"
      ? (import.meta as unknown as { env?: ViteEnv }).env
      : undefined) ?? {}
  );
}

const viteEnv = readViteEnv();
const mode = (viteEnv.MODE ?? "development").toLowerCase();
const useMock = (viteEnv.VITE_USE_MOCK ?? "").toLowerCase() === "true";

// Bare i dev/test eller mock
if (typeof window !== "undefined" && (useMock || mode !== "production")) {
  const origFetch = window.fetch.bind(window);

  function toUrlString(input: string | Request | URL): string {
    if (typeof input === "string") return input;
    if (input instanceof Request) return input.url;
    // URL -> string for å matche fetch-signaturen i eldre TS/lib.dom
    return input.toString();
  }

  window.fetch = (...args: Parameters<typeof fetch>): ReturnType<typeof fetch> => {
    const [input, init] = args;

    const urlStr = toUrlString(input as string | Request | URL);

    try {
      const url = new URL(urlStr, window.location.href);
      // Treffer absolutte :8000-kall mot /api → skriv om til relative /api
      if (url.host === "localhost:8000" && url.pathname.startsWith("/api")) {
        const rewritten = `${url.pathname}${url.search}${url.hash}`;
        return origFetch(rewritten, init);
      }
    } catch {
      // Ikke en absolutt URL, la den gå
    }

    // Pass alltid string/Request videre (ikke URL-objekt)
    if (typeof input === "string" || input instanceof Request) {
      return origFetch(input, init);
    }
    // input kan ha vært URL – send som string
    return origFetch(urlStr, init);
  };
}
