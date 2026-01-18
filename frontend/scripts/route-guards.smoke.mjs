import { chromium } from "playwright";

const FRONTEND = process.env.CG_FRONTEND || "http://localhost:5173";
const BACKEND  = process.env.CG_BACKEND  || "http://127.0.0.1:5175";

function mustCookie(setCookieHeader, name) {
  const re = new RegExp(`${name}=([^;]+)`);
  const m = String(setCookieHeader || "").match(re);
  if (!m) throw new Error(`Missing cookie ${name} in Set-Cookie`);
  return m[1];
}

async function signupViaFetch() {
  const email = `guard_${new Date().toISOString().replace(/[-:.TZ]/g,"").slice(0,14)}@cg.local`;

  const res = await fetch(`${BACKEND}/api/auth/signup`, {
    method: "POST",
    headers: { "content-type": "application/json", "accept": "application/json" },
    body: JSON.stringify({ email, password: "password123" })
  });

  const txt = await res.text().catch(() => "");
  if (!res.ok) throw new Error(`signup failed ${res.status}: ${txt.slice(0,200)}`);

  const setCookie = res.headers.get("set-cookie") || "";
  const cg_auth = mustCookie(setCookie, "cg_auth");
  const cg_uid  = mustCookie(setCookie, "cg_uid");

  return { cg_auth, cg_uid };
}

async function profileSaveViaFetch(cookies) {
  const cookieHeader = `cg_auth=${cookies.cg_auth}; cg_uid=${cookies.cg_uid}`;

  const res = await fetch(`${BACKEND}/api/profile/save`, {
    method: "PUT",
    headers: {
      "content-type": "application/json",
      "accept": "application/json",
      "cookie": cookieHeader
    },
    body: JSON.stringify({ profile: { rider_weight_kg: 95 } })
  });

  const txt = await res.text().catch(() => "");
  if (!res.ok) throw new Error(`profile/save failed ${res.status}: ${txt.slice(0,200)}`);
}

async function injectCookiesForFrontend(ctx, cookies) {
  const u = new URL(FRONTEND);
  const domain = u.hostname;

  await ctx.addCookies([
    { name: "cg_auth", value: cookies.cg_auth, domain, path: "/" },
    { name: "cg_uid",  value: cookies.cg_uid,  domain, path: "/" },
  ]);
}

async function run() {
  const browser = await chromium.launch();

  // T1: guest /dashboard -> /login
  {
    const ctx = await browser.newContext();
    await ctx.addInitScript(() => {
      try { localStorage.removeItem("cg_demo"); } catch {}
    });

    const page = await ctx.newPage();
    await page.goto(`${FRONTEND}/dashboard`, { waitUntil: "domcontentloaded" });

    await page.waitForURL(/\/login(\?|$)/, { timeout: 8000 }).catch(() => {});
    const url = page.url();
    console.log("[T1] guest /dashboard ->", url);
    if (!url.includes("/login")) throw new Error("T1 FAIL");
    await ctx.close();
  }

  const cookies = await signupViaFetch();

  // T2: new user (authed but NOT onboarded) /rides -> /onboarding
  {
    const ctx = await browser.newContext();
    await injectCookiesForFrontend(ctx, cookies);
    const page = await ctx.newPage();

    await page.goto(`${FRONTEND}/rides`, { waitUntil: "domcontentloaded" });
    await page.waitForURL(/\/onboarding(\?|$)/, { timeout: 8000 }).catch(() => {});

    const url = page.url();
    console.log("[T2] new user /rides ->", url);
    if (!url.includes("/onboarding")) throw new Error("T2 FAIL: expected /onboarding");
    await ctx.close();
  }

  // T3: refresh onboarding stays onboarding
  {
    const ctx = await browser.newContext();
    await injectCookiesForFrontend(ctx, cookies);
    const page = await ctx.newPage();

    await page.goto(`${FRONTEND}/onboarding`, { waitUntil: "domcontentloaded" });
    await page.reload({ waitUntil: "domcontentloaded" });

    const url = page.url();
    console.log("[T3] refresh /onboarding ->", url);
    if (!url.includes("/onboarding")) throw new Error("T3 FAIL: expected stay on /onboarding");
    await ctx.close();
  }

  // Complete onboarding via backend
  await profileSaveViaFetch(cookies);

  // T4: onboarded -> /dashboard stays /dashboard
  {
    const ctx = await browser.newContext();
    await injectCookiesForFrontend(ctx, cookies);
    const page = await ctx.newPage();

    await page.goto(`${FRONTEND}/dashboard`, { waitUntil: "domcontentloaded" });
    await page.waitForURL(/\/dashboard(\?|$)/, { timeout: 8000 }).catch(() => {});

    const url = page.url();
    console.log("[T4] onboarded /dashboard ->", url);
    if (!url.includes("/dashboard")) throw new Error("T4 FAIL: expected /dashboard");
    await ctx.close();
  }

  console.log("✅ Route guards smoke OK");
  await browser.close();
}

run().catch((e) => {
  console.error("❌ Route guards smoke FAIL:", e?.message || e);
  process.exit(1);
});
