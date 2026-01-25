// devFetchShim.ts
// SSOT safety net: ensure all fetch calls include credentials (cookies)
// This prevents random 401s / "logged out" behavior across reloads.

const origFetch = window.fetch.bind(window);

window.fetch = async (
  input: RequestInfo | URL,
  init?: RequestInit
) => {
  const nextInit: RequestInit = { ...(init || {}) };

  // CRITICAL: always include cookies (Vercel -> Fly cross-site auth)
  if (!nextInit.credentials) {
    nextInit.credentials = "include";
  }

  nextInit.headers = {
    ...(nextInit.headers || {}),
  };

  return origFetch(input, nextInit);
};

export {};
