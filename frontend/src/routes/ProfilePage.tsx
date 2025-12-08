// frontend/src/routes/ProfilePage.tsx

export default function ProfilePage() {
  return (
    <div className="flex flex-col gap-4 max-w-xl">
      <h1 className="text-2xl font-semibold tracking-tight">Profile / Profil</h1>
      <p className="text-slate-600">
        Her vil du etter hvert kunne se og oppdatere profildataene dine:
        kroppsvekt, sykkelvalg, CdA, Crr, FTP og andre parametere som påvirker
        kalibrering og nøyaktighet i analysene.
      </p>

      <div className="border border-dashed border-slate-300 rounded-lg px-4 py-8 text-slate-500 text-sm">
        TODO: Implementer profilskjema og kobling til kalibrering og analyser.
      </div>
    </div>
  );
}
