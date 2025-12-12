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
        <div className="text-slate-600 mb-1">CdA</div>
        <input
          disabled={disabled}
          type="number"
          step="0.001"
          className="border rounded px-3 py-2 w-full"
          value={value.cda}
          onChange={(e) => onChange({ cda: Number(e.target.value) })}
        />
      </label>

      <label className="text-sm">
        <div className="text-slate-600 mb-1">Crr</div>
        <input
          disabled={disabled}
          type="number"
          step="0.0001"
          className="border rounded px-3 py-2 w-full"
          value={value.crr}
          onChange={(e) => onChange({ crr: Number(e.target.value) })}
        />
      </label>

      <label className="text-sm">
        <div className="text-slate-600 mb-1">Crank efficiency (0–1)</div>
        <input
          disabled={disabled}
          type="number"
          step="0.001"
          className="border rounded px-3 py-2 w-full"
          value={value.crank_efficiency}
          onChange={(e) => onChange({ crank_efficiency: Number(e.target.value) })}
        />
      </label>
    </div>
  );
}
