// frontend/src/lib/format.ts

export function formatLocalDateTime(input?: string | null): string {
  if (!input) return "—";

  // "YYYY-MM-DD" blir tolket som UTC av Date() -> kan gi off-by-one.
  // Vi behandler ren dato som lokal dato for stabil visning.
  const isDateOnly = /^\d{4}-\d{2}-\d{2}$/.test(input);

  let d: Date;
  if (isDateOnly) {
    const [y, m, day] = input.split("-").map((x) => Number(x));
    d = new Date(y, (m ?? 1) - 1, day ?? 1, 12, 0, 0); // lokal midt på dagen
  } else {
    d = new Date(input);
  }

  if (Number.isNaN(d.getTime())) return "—";

  return new Intl.DateTimeFormat(undefined, {
    year: "numeric",
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(d);
}
