import type { UserProfileDraft } from "../types/profile";

type Props = {
  value: UserProfileDraft;
  onChange: (patch: Partial<UserProfileDraft>) => void;
  disabled?: boolean;
};

export default function ProfileForm({ value, onChange, disabled }: Props) {
  return (
    <div className="grid gap-3 max-w-md">
      <label className="text-sm">
        <div className="text-slate-600 mb-1">Weight (kg)</div>
        <input
          disabled={disabled}
          type="number"
          step="0.1"
          className="border rounded px-3 py-2 w-full"
          value={value.weight_kg}
          onChange={(e) => onChange({ weight_kg: Number(e.target.value) })}
        />
      </label>

      <label className="text-sm">
        <div className="text-slate-600 mb-1">CdA (locked in MVP)</div>
        <input
          disabled
          type="number"
          step="0.001"
          className="border rounded px-3 py-2 w-full bg-slate-100 cursor-not-allowed"
          value={value.cda}
          readOnly
        />
      </label>

      <label className="text-sm">
        <div className="text-slate-600 mb-1">Crr (locked in MVP)</div>
        <input
          disabled
          type="number"
          step="0.0001"
          className="border rounded px-3 py-2 w-full bg-slate-100 cursor-not-allowed"
          value={value.crr}
          readOnly
        />
      </label>

      <label className="text-sm">
        <div className="text-slate-600 mb-1">Crank efficiency (locked in MVP)</div>
        <input
          disabled
          type="number"
          step="0.001"
          className="border rounded px-3 py-2 w-full bg-slate-100 cursor-not-allowed"
          value={value.crank_efficiency}
          readOnly
        />
      </label>

      <p className="text-xs text-slate-500 mt-1">
        CdA, Crr og krank-effektivitet er låst i MVP for å gi stabile og
        forståelige analyser. Avansert kalibrering kommer senere.
      </p>
    </div>
  );
}
