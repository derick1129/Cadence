"use client";

import * as React from "react";

export const LiveWaveform: React.FC<{ active?: boolean }> = ({ active = false }) => {
  return (
    <div className="flex items-center justify-center gap-1.5 h-12 px-4 py-2 bg-[var(--card)] border border-[var(--line)] rounded-lg">
      {[40, 75, 30, 90, 60, 20, 85, 45].map((height, i) => (
        <span
          key={i}
          style={{ height: active ? `${height}%` : "15%" }}
          className="w-1 bg-[var(--accent)] rounded-full transition-all duration-150"
        />
      ))}
    </div>
  );
};
