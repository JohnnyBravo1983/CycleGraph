import { useEffect } from "react";
import { useProfileStore } from "../state/profileStore";
import ProfileForm from "../components/ProfileForm";

export default function ProfilePage() {
  const { draft, loading, error, init, setDraft, commit } = useProfileStore();

  useEffect(() => {
    init();
  }, [init]);

  return (
    <div className="flex flex-col gap-4 max-w-xl">
      <h1 className="text-2xl font-semibold tracking-tight">Profil</h1>

      <p className="text-slate-600">
        Profilen brukes i analysene for å beregne Precision Watt, luftmotstand
        og andre fysiske parametere. Du kan endre disse når som helst.
      </p>

      {error ? <div className="text-red-600 text-sm">{error}</div> : null}

      <ProfileForm value={draft} onChange={setDraft} disabled={loading} />

      <div className="flex gap-3 pt-2">
        <button
          onClick={commit}
          disabled={loading}
          className="px-4 py-2 rounded bg-slate-900 text-white hover:bg-slate-800 disabled:bg-slate-400"
        >
          Lagre profil
        </button>
      </div>
    </div>
  );
}
