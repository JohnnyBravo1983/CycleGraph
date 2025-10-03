// frontend/src/components/ErrorBanner.tsx
// Enkel, gjenbrukbar feilbanner med "Prøv igjen"-knapp.
// Ingen selvreferanse-import! Ingen eksterne libs, kun Tailwind-klasser.

type Props = {
  message: string;
  onRetry: () => void;
};

export default function ErrorBanner({ message, onRetry }: Props) {
  return (
    <div
      role="alert"
      aria-live="polite"
      className="flex items-start justify-between gap-4 rounded-xl border border-red-200 bg-red-50 p-4 text-red-800"
    >
      <div className="text-sm leading-5">
        <strong className="mb-0.5 block font-medium">Noe gikk galt</strong>
        <span className="break-words">{message}</span>
      </div>

      <button
        type="button"
        onClick={onRetry}
        className="shrink-0 inline-flex items-center gap-1 rounded-lg border border-red-300 bg-white px-3 py-1.5 text-sm font-medium text-red-700 hover:bg-red-100 focus:outline-none focus:ring-2 focus:ring-red-400"
      >
        Prøv igjen
      </button>
    </div>
  );
}
