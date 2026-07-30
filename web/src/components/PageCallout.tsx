import React from "react";

export default function PageCallout({ children }: { children: React.ReactNode }) {
  return (
    <div className="mb-4 rounded-lg border border-emerald-900/50 bg-emerald-950/30 px-4 py-3 text-sm text-emerald-100">
      {children}
    </div>
  );
}
