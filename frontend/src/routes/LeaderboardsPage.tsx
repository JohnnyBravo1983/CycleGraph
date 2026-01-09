import React, { useState } from "react";
import { Link } from "react-router-dom";
import { leaderboardMockData } from "../demo/leaderboardMockData";
import { isDemoMode } from "../demo/demoMode";

export const LeaderboardsPage: React.FC = () => {
  const [tab, setTab] = useState<"ftp" | "wkg">("ftp");

  const sorted = [...leaderboardMockData].sort((a, b) =>
    tab === "ftp" ? b.ftp - a.ftp : b.wkg - a.wkg
  );

  return (
    <div className="max-w-4xl mx-auto px-4 py-10">
      <Link to="/dashboard" className="text-sm text-slate-500 hover:text-slate-700">
        ← Back to Dashboard
      </Link>

      <h1 className="text-3xl font-bold text-slate-800 mt-4 mb-6">🏆 Leaderboards</h1>

      {/* Tabs */}
      <div className="flex gap-6 border-b border-slate-200 mb-6">
        {(["ftp", "wkg"] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={[
              "pb-3 text-base font-medium",
              tab === t
                ? "text-emerald-600 border-b-2 border-emerald-600"
                : "text-slate-500 hover:text-slate-800",
            ].join(" ")}
          >
            {t === "ftp" ? "FTP" : "W/kg"}
          </button>
        ))}
      </div>

      {/* Table */}
      <div className="rounded-xl border border-slate-200 bg-white overflow-hidden">
        <div className="grid grid-cols-[60px_1fr_140px_140px] bg-slate-50 px-5 py-3 text-xs font-semibold text-slate-500 uppercase">
          <div>#</div>
          <div>Name</div>
          <div>{tab === "ftp" ? "FTP" : "W/kg"}</div>
          <div>Last updated</div>
        </div>

        {sorted.map((u, i) => (
          <div
            key={u.name}
            className={[
              "grid grid-cols-[60px_1fr_140px_140px] px-5 py-4 border-t border-slate-100",
              "hover:bg-slate-50",
              u.isCurrentUser
                ? "bg-emerald-50 border-y-2 border-emerald-500"
                : "",
            ].join(" ")}
          >
            <div className="font-bold text-slate-800">{i + 1}</div>
            <div className="text-slate-800 font-medium">{u.name}</div>
            <div className="font-semibold text-emerald-600">
              {tab === "ftp" ? `${u.ftp} W` : `${u.wkg.toFixed(2)} W/kg`}
              {u.isCurrentUser ? " ⚡" : ""}
            </div>
            <div className="text-slate-500 text-sm">{u.lastUpdated ?? "—"}</div>
          </div>
        ))}
      </div>

      {isDemoMode() && (
        <div className="mt-6 rounded-xl border border-dashed border-slate-300 bg-slate-50 p-4 text-sm text-slate-600">
          💡 Demo note: Leaderboards are populated with demo data. In production,
          you’ll compete with real users globally.
        </div>
      )}
    </div>
  );
};
