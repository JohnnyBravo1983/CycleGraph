import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useProfileStore } from "../state/profileStore";
import ProfileForm from "../components/ProfileForm";

export default function OnboardingPage() {
  const navigate = useNavigate();
  const { draft, loading, error, init, setDraft, applyDefaults, commit, profile } =
    useProfileStore();

  useEffect(() => {
    init();
  }, [init]);

  // Hvis profil allerede finnes → hopp rett til app
  useEffect(() => {
    if (profile) navigate("/rides");
  }, [profile, navigate]);

  const onFinish = async () => {
    const ok = await commit();
    if (ok) navigate("/rides");
  };

  return (
    <div className="max-w-xl mx-auto flex flex-col gap-4">
      <h1 className="text-2xl font-semibold tracking-tight">
        Velkommen til CycleGraph
      </h1>

      <p className="text-slate-600">
        Før vi starter trenger vi et grovt utgangspunkt for profilen din.
        Dette kan justeres senere.
      </p>

      {error ? <div className="text-red-600 text-sm">{error}</div> : null}

      <ProfileForm value={draft} onChange={setDraft} disabled={loading} />

      <div className="flex gap-3 pt-2">
        <button
          onClick={applyDefaults}
          disabled={loading}
          className="px-4 py-2 rounded border"
        >
          Bruk standardverdier
        </button>

        <button
          onClick={onFinish}
          disabled={loading}
          className="px-4 py-2 rounded bg-slate-900 text-white hover:bg-slate-800 disabled:bg-slate-400"
        >
          Fullfør og gå videre
        </button>
      </div>
    </div>
  );
}
