import React from "react";
import { Link } from "react-router-dom";
import { getProfile, saveProfileFromUi } from "../../api/profile";

type ProfileData = {
  // core fields (today scope)
  name?: string | null;
  rider_weight_kg?: number | null;
  bike_weight_kg?: number | null;
  bike_type?: string | null;
  ftp_watts?: number | null;

  // existing extra fields (read-only / keep)
  cda?: number | null;
  crr?: number | null;
  crank_efficiency?: number | null; // 0-1 eller 0-100
  tire_width_mm?: number | null;
  tire_quality?: string | null;
  profile_version?: number | null;
};

function fmtNumber(v: any, suffix = ""): string {
  if (v === null || v === undefined || v === "") return "—";
  const n = Number(v);
  if (!Number.isFinite(n)) return String(v);
  return `${n}${suffix}`;
}
function fmtPercent(v: any): string {
  if (v === null || v === undefined || v === "") return "—";
  const n = Number(v);
  if (!Number.isFinite(n)) return String(v);
  const pct = n <= 1 ? n * 100 : n;
  return `${pct.toFixed(0)}%`;
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-6 border-b border-slate-100 py-2.5 last:border-b-0">
      <div className="text-sm text-slate-600">{label}</div>
      <div className="text-sm font-semibold text-slate-900 text-right">{value}</div>
    </div>
  );
}

function toNumOrNull(s: string): number | null {
  const t = s.trim();
  if (t === "") return null;
  const n = Number(t);
  if (!Number.isFinite(n)) return null;
  return n;
}

export default function ProfilePeekCard() {
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [profile, setProfile] = React.useState<ProfileData | null>(null);

  const [open, setOpen] = React.useState(false);
  const wrapRef = React.useRef<HTMLDivElement | null>(null);

  // edit state
  const [isEditing, setIsEditing] = React.useState(false);
  const [saving, setSaving] = React.useState(false);
  const [successMsg, setSuccessMsg] = React.useState<string | null>(null);
  const [form, setForm] = React.useState<{
    name: string;
    rider_weight_kg: string;
    ftp_watts: string;
    bike_type: string;
    bike_weight_kg: string;
  } | null>(null);

  React.useEffect(() => {
    let alive = true;
    (async () => {
      try {
        setLoading(true);
        setError(null);
        const data = await getProfile();
        if (!alive) return;
        setProfile((data as any) ?? null);
      } catch (e: any) {
        if (!alive) return;
        setError(e?.message || "Kunne ikke hente profilen.");
      } finally {
        if (alive) setLoading(false);
      }
    })();
    return () => {
      alive = false;
    };
  }, []);

  // keep form in sync when profile changes
  React.useEffect(() => {
    if (!profile) {
      setForm(null);
      return;
    }
    setForm({
      name: (profile.name ?? "").toString(),
      rider_weight_kg:
        profile.rider_weight_kg === null || profile.rider_weight_kg === undefined
          ? ""
          : String(profile.rider_weight_kg),
      ftp_watts:
        profile.ftp_watts === null || profile.ftp_watts === undefined ? "" : String(profile.ftp_watts),
      bike_type: (profile.bike_type ?? "").toString(),
      bike_weight_kg:
        profile.bike_weight_kg === null || profile.bike_weight_kg === undefined
          ? ""
          : String(profile.bike_weight_kg),
    });
  }, [profile]);

  function resetEditState() {
    setIsEditing(false);
    setSaving(false);
    setSuccessMsg(null);
    if (profile) {
      setForm({
        name: (profile.name ?? "").toString(),
        rider_weight_kg:
          profile.rider_weight_kg === null || profile.rider_weight_kg === undefined
            ? ""
            : String(profile.rider_weight_kg),
        ftp_watts:
          profile.ftp_watts === null || profile.ftp_watts === undefined
            ? ""
            : String(profile.ftp_watts),
        bike_type: (profile.bike_type ?? "").toString(),
        bike_weight_kg:
          profile.bike_weight_kg === null || profile.bike_weight_kg === undefined
            ? ""
            : String(profile.bike_weight_kg),
      });
    } else {
      setForm(null);
    }
  }

  function validateForm(): string | null {
    if (!form) return "Mangler profil-data.";
    const name = form.name.trim();
    const w = toNumOrNull(form.rider_weight_kg);
    const ftp = toNumOrNull(form.ftp_watts);
    const bikeType = form.bike_type.trim();
    const bw = toNumOrNull(form.bike_weight_kg);

    if (!name) return "Name er påkrevd.";
    if (w === null || w <= 0) return "Weight må være > 0.";
    if (ftp !== null && ftp < 0) return "FTP kan ikke være negativ.";
    if (!bikeType) return "Bike type er påkrevd.";
    if (bw === null || bw <= 0) return "Bike weight må være > 0.";

    return null;
  }

  async function onSave() {
    const v = validateForm();
    if (v) {
      setError(v);
      return;
    }
    if (!form) return;

    setSaving(true);
    setError(null);

    const payload = {
      name: form.name.trim(),
      rider_weight_kg: toNumOrNull(form.rider_weight_kg),
      ftp_watts: toNumOrNull(form.ftp_watts),
      bike_type: form.bike_type.trim(),
      bike_weight_kg: toNumOrNull(form.bike_weight_kg),
    };

    try {
    const resp = await saveProfileFromUi(payload as any); 

      // backend might return updated profile, else we re-fetch
      if (resp && typeof resp === "object") {
        const maybeProfile =
          (resp.profile as any) ||
          (resp.data as any) ||
          (resp.updated_profile as any) ||
          null;

        if (maybeProfile) {
          setProfile(maybeProfile);
        } else {
          const fresh = await getProfile();
          setProfile((fresh as any) ?? null);
        }
      } else {
        const fresh = await getProfile();
        setProfile((fresh as any) ?? null);
      }

      setSuccessMsg("Profile updated.");
      setIsEditing(false);

      window.setTimeout(() => setSuccessMsg(null), 3000);
    } catch (e: any) {
      setError(e?.message || "Kunne ikke lagre profilen.");
    } finally {
      setSaving(false);
    }
  }

  // Close popover on outside click / escape
  React.useEffect(() => {
    function onDocDown(ev: MouseEvent | TouchEvent) {
      const el = wrapRef.current;
      if (!el) return;
      if (!el.contains(ev.target as Node)) {
        // outside: close & cancel edit without saving
        setOpen(false);
        if (isEditing) resetEditState();
      }
    }
    function onKey(ev: KeyboardEvent) {
      if (ev.key === "Escape") {
        setOpen(false);
        if (isEditing) resetEditState();
      }
    }
    document.addEventListener("mousedown", onDocDown);
    document.addEventListener("touchstart", onDocDown, { passive: true });
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDocDown);
      document.removeEventListener("touchstart", onDocDown);
      document.removeEventListener("keydown", onKey);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isEditing, profile, form]);

  const subtitle = isEditing ? "Rytter- og sykkeldata (edit mode)" : "Rytter- og sykkeldata (kun visning)";

  return (
    <div ref={wrapRef} className="relative">
      {/* Compact card */}
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        onMouseEnter={!isEditing ? () => setOpen(true) : undefined}
        onMouseLeave={!isEditing ? () => setOpen(false) : undefined}
        className="w-full text-left rounded-2xl bg-white/98 backdrop-blur-xl p-5 shadow-[0_20px_60px_rgba(0,0,0,0.25)] border border-white/40 hover:shadow-[0_24px_70px_rgba(0,0,0,0.28)] transition"
        aria-haspopup="dialog"
        aria-expanded={open}
      >
        <div className="flex items-start justify-between gap-6">
          <div>
            <div className="text-lg font-bold text-slate-900">Profile</div>
            <div className="text-sm text-slate-600">{subtitle}</div>
            <div className="mt-2 text-xs text-slate-500">
              {loading
                ? "Laster …"
                : error
                ? "Kunne ikke hente profil"
                : profile
                ? "Hover / klikk for detaljer"
                : "Ingen profil ennå"}
            </div>
          </div>

          <div className="flex items-center gap-2">
            {!loading && !error && profile && (
              <div className="text-xs font-semibold text-slate-700 bg-slate-100 px-3 py-1.5 rounded-full">
                v{profile.profile_version ?? "—"}
              </div>
            )}
            <div className="text-slate-400 text-sm">▾</div>
          </div>
        </div>
      </button>

      {/* Popover */}
      {open && (
        <div
          className="absolute z-20 mt-3 w-full rounded-2xl border border-slate-200 bg-white shadow-[0_20px_60px_rgba(0,0,0,0.20)] p-4"
          role="dialog"
          aria-label="Profil-detaljer"
        >
          {loading && <div className="text-sm text-slate-600">Laster profil …</div>}

          {!loading && error && (
            <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">
              {error}
            </div>
          )}

          {!loading && successMsg && (
            <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-800">
              {successMsg}
            </div>
          )}

          {!loading && !error && !profile && (
            <div className="rounded-xl border border-slate-200 bg-slate-50 p-5">
              <div className="text-sm font-semibold text-slate-900">Ingen profil ennå</div>
              <div className="mt-1 text-sm text-slate-600">
                Fullfør onboarding for å sette opp profilen din.
              </div>
              <div className="mt-4">
                <Link
                  to="/onboarding"
                  className="inline-flex items-center justify-center rounded-xl bg-slate-900 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-800 transition"
                >
                  Gå til onboarding
                </Link>
              </div>
            </div>
          )}

          {!loading && !error && profile && (
            <div className="rounded-xl border border-slate-200 bg-white p-4">
              {/* Header actions */}
              <div className="mb-3 flex items-center justify-between gap-3">
                <div className="text-sm font-semibold text-slate-900">Profil</div>

                {!isEditing ? (
                  <button
                    type="button"
                    onClick={() => {
                      setIsEditing(true);
                      setError(null);
                      setSuccessMsg(null);
                      setOpen(true);
                    }}
                    className="inline-flex items-center justify-center rounded-xl bg-slate-900 px-3 py-2 text-xs font-semibold text-white hover:bg-slate-800 transition"
                  >
                    Edit Profile
                  </button>
                ) : (
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={() => {
                        resetEditState();
                        setError(null);
                      }}
                      disabled={saving}
                      className="inline-flex items-center justify-center rounded-xl bg-white px-3 py-2 text-xs font-semibold text-slate-900 border border-slate-200 hover:bg-slate-50 transition disabled:opacity-60"
                    >
                      Cancel
                    </button>
                    <button
                      type="button"
                      onClick={onSave}
                      disabled={saving}
                      className="inline-flex items-center justify-center rounded-xl bg-emerald-600 px-3 py-2 text-xs font-semibold text-white hover:bg-emerald-500 transition disabled:opacity-60"
                    >
                      {saving ? "Saving…" : "Save"}
                    </button>
                  </div>
                )}
              </div>

              {/* Edit mode */}
              {isEditing ? (
                <div className="space-y-3">
                  <div>
                    <label className="block text-xs font-semibold text-slate-600 mb-1">Name</label>
                    <input
                      value={form?.name ?? ""}
                      onChange={(e) =>
                        setForm((prev) =>
                          prev ? { ...prev, name: e.target.value } : prev
                        )
                      }
                      className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 outline-none focus:ring-2 focus:ring-slate-200"
                      placeholder="Name"
                    />
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="block text-xs font-semibold text-slate-600 mb-1">
                        Rider weight (kg)
                      </label>
                      <input
                        inputMode="decimal"
                        value={form?.rider_weight_kg ?? ""}
                        onChange={(e) =>
                          setForm((prev) =>
                            prev ? { ...prev, rider_weight_kg: e.target.value } : prev
                          )
                        }
                        className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 outline-none focus:ring-2 focus:ring-slate-200"
                        placeholder="e.g. 80"
                      />
                    </div>

                    <div>
                      <label className="block text-xs font-semibold text-slate-600 mb-1">
                        FTP (W)
                      </label>
                      <input
                        inputMode="numeric"
                        value={form?.ftp_watts ?? ""}
                        onChange={(e) =>
                          setForm((prev) =>
                            prev ? { ...prev, ftp_watts: e.target.value } : prev
                          )
                        }
                        className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 outline-none focus:ring-2 focus:ring-slate-200"
                        placeholder="optional"
                      />
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="block text-xs font-semibold text-slate-600 mb-1">
                        Bike type
                      </label>
                      <input
                        value={form?.bike_type ?? ""}
                        onChange={(e) =>
                          setForm((prev) =>
                            prev ? { ...prev, bike_type: e.target.value } : prev
                          )
                        }
                        className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 outline-none focus:ring-2 focus:ring-slate-200"
                        placeholder="e.g. road"
                      />
                    </div>

                    <div>
                      <label className="block text-xs font-semibold text-slate-600 mb-1">
                        Bike weight (kg)
                      </label>
                      <input
                        inputMode="decimal"
                        value={form?.bike_weight_kg ?? ""}
                        onChange={(e) =>
                          setForm((prev) =>
                            prev ? { ...prev, bike_weight_kg: e.target.value } : prev
                          )
                        }
                        className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 outline-none focus:ring-2 focus:ring-slate-200"
                        placeholder="e.g. 8.2"
                      />
                    </div>
                  </div>
                </div>
              ) : (
                // Read-only mode (existing rows)
                <div>
                  <Row label="Name" value={(profile.name && profile.name.trim()) || "—"} />
                  <Row label="Rider weight" value={fmtNumber(profile.rider_weight_kg, " kg")} />
                  <Row label="Bike weight" value={fmtNumber(profile.bike_weight_kg, " kg")} />
                  <Row label="CdA" value={fmtNumber(profile.cda)} />
                  <Row label="Crr" value={fmtNumber(profile.crr)} />
                  <Row label="Crank efficiency" value={fmtPercent(profile.crank_efficiency)} />
                  <Row label="Bike type" value={profile.bike_type || "—"} />
                  <Row label="Tire width" value={fmtNumber(profile.tire_width_mm, " mm")} />
                  <Row label="Tire quality" value={profile.tire_quality || "—"} />
                  <Row
                    label="FTP"
                    value={
                      profile.ftp_watts === null || profile.ftp_watts === undefined
                        ? "Not set"
                        : `${profile.ftp_watts} W`
                    }
                  />
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
