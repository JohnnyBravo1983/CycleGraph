// frontend/src/routes/ProfilePage.tsx
import { useEffect } from "react";
import { useProfileStore } from "../state/profileStore";
import ProfileForm from "../components/ProfileForm";

export default function ProfilePage() {
  const { draft, loading, error, init, setDraft, commit } = useProfileStore();

  useEffect(() => {
    init();
  }, [init]);

  const handleSave = async () => {
    await commit();
  };

  if (loading) {
    return <div className="max-w-xl mx-auto p-4">Loading profile...</div>;
  }

  if (error) {
    return <div className="max-w-xl mx-auto p-4 text-red-600">{error}</div>;
  }

  return (
    <div className="max-w-xl mx-auto flex flex-col gap-4 p-4">
      <h1 className="text-2xl font-semibold">Profile Settings</h1>
      
      <ProfileForm value={draft} onChange={setDraft} disabled={loading} />

      <button
        onClick={handleSave}
        disabled={loading}
        className="px-4 py-2 rounded bg-slate-900 text-white hover:bg-slate-800 disabled:bg-slate-400"
      >
        Save Profile
      </button>
    </div>
  );
}