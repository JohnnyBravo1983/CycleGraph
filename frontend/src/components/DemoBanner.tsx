import { useEffect, useState } from "react";
import { isDemoMode, setDemoMode, DEMO_EVENT } from "../demo/demoMode";
import { useNavigate } from "react-router-dom";

export default function DemoBanner() {
  const [mounted, setMounted] = useState(false);
  const [demo, setDemo] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    setMounted(true);

    const sync = () => setDemo(isDemoMode());
    sync();

    // Same-tab updates (our custom event)
    window.addEventListener(DEMO_EVENT, sync);

    // Cross-tab updates (native storage event)
    window.addEventListener("storage", sync);

    return () => {
      window.removeEventListener(DEMO_EVENT, sync);
      window.removeEventListener("storage", sync);
    };
  }, []);

  if (!mounted || !demo) return null;

  return (
    <div className="bg-amber-100 border-b border-amber-200 text-amber-900">
      <div className="max-w-5xl mx-auto px-6 py-2 flex items-center justify-between text-sm">
        <div>
          🎬 <strong>Demo Mode</strong> – Viewing <strong>Johnny</strong>’s training data
        </div>

        <button
          className="text-xs underline hover:text-amber-700"
          onClick={() => {
            setDemoMode(false);
            navigate("/");
          }}
        >
          Exit demo
        </button>
      </div>
    </div>
  );
}