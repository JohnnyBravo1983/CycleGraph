import React, { createContext, useContext, useEffect, useMemo, useState } from "react";
import { cgApi } from "../lib/cgApi";

export type GateStatus = "checking" | "guest" | "authed";

export type AuthGateState = {
  status: GateStatus;
  isOnboarded: boolean;
  lastStatus?: number;
};

const AuthGateContext = createContext<AuthGateState | null>(null);

// PATCH 2A: hard timeout helper
function withTimeout<T>(p: Promise<T>, ms: number, label: string): Promise<T> {
  return new Promise((resolve, reject) => {
    const t = window.setTimeout(
      () => reject(new Error(`${label} timeout after ${ms}ms`)),
      ms
    );
    p.then((v) => {
      window.clearTimeout(t);
      resolve(v);
    }).catch((e) => {
      window.clearTimeout(t);
      reject(e);
    });
  });
}

export function AuthGateProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<AuthGateState>({
    status: "checking",
    isOnboarded: false,
  });

  useEffect(() => {
    let alive = true;

    async function run() {
      // 1) session check (SSOT)
      try {
        console.log("[AuthGate] authMe start");
        await withTimeout(cgApi.authMe(), 4000, "authMe");
        console.log("[AuthGate] authMe ok");
      } catch (err: any) {
        if (!alive) return;
        const st = typeof err?.status === "number" ? err.status : undefined;
        console.log("[AuthGate] authMe FAIL", st);
        setState({ status: "guest", isOnboarded: false, lastStatus: st });
        return;
      }

      // 2) onboarding check via profileGet
      try {
        console.log("[AuthGate] profileGet start");
        const resp = await withTimeout(cgApi.profileGet(), 4000, "profileGet").catch(
          () => null
        );

        const profile = (resp as any)?.profile;

        // 🔒 SSOT-regel:
        // Kun onboarded === true teller som ferdig onboardet
        const onboarded =
          !!profile &&
          typeof profile === "object" &&
          (profile as Record<string, unknown>).onboarded === true;

        console.log("[AuthGate] profileGet done onboarded=", onboarded);

        if (!alive) return;
        setState({
          status: "authed",
          isOnboarded: onboarded,
          lastStatus: 200,
        });
      } catch (err) {
        if (!alive) return;
        console.log("[AuthGate] profileGet FAIL", err);
        // Safe default: krev onboarding hvis noe er uklart
        setState({
          status: "authed",
          isOnboarded: false,
          lastStatus: 200,
        });
      }
    }

    run();
    return () => {
      alive = false;
    };
  }, []);

  const value = useMemo(() => state, [state]);
  return <AuthGateContext.Provider value={value}>{children}</AuthGateContext.Provider>;
}

export function useAuthGate(): AuthGateState {
  const ctx = useContext(AuthGateContext);
  if (!ctx) {
    // Hard fail-safe
    return { status: "checking", isOnboarded: false, lastStatus: 500 };
  }
  return ctx;
}
