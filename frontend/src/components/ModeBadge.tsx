export default function ModeBadge() {
  const isMock = import.meta.env.VITE_USE_MOCK !== "0";
  return (
    <span
      title={isMock ? "Data fra mockSession" : "Data fra backend"}
      className="text-[11px] px-2 py-1 rounded-full border bg-white"
    >
      MODE: {isMock ? "MOCK" : "LIVE"}
    </span>
  );
}