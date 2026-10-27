"use client";

import * as React from "react";
import { User, Bot } from "lucide-react";

export interface Turn {
  id: string;
  seq: number;
  speaker: "caller" | "agent";
  text: string;
  started_at_ms: number;
}

export const TranscriptViewer: React.FC<{ turns: Turn[] }> = ({ turns }) => {
  return (
    <div className="space-y-4 max-w-3xl">
      {turns.map((turn) => {
        const isAgent = turn.speaker === "agent";
        return (
          <div
            key={turn.id}
            className={`flex items-start gap-3 ${isAgent ? "flex-row" : "flex-row-reverse"}`}
          >
            <div
              className={`w-7 h-7 rounded-full flex items-center justify-center shrink-0 text-xs font-semibold ${
                isAgent ? "bg-[var(--accent)] text-white" : "bg-[var(--line)] text-[var(--fg)]"
              }`}
            >
              {isAgent ? <Bot className="w-3.5 h-3.5" /> : <User className="w-3.5 h-3.5" />}
            </div>
            <div
              className={`p-3.5 rounded-xl max-w-lg text-sm border ${
                isAgent
                  ? "bg-[var(--card)] border-[var(--line)] text-[var(--fg)]"
                  : "bg-[var(--line)]/50 border-transparent text-[var(--fg)]"
              }`}
            >
              <div className="text-[10px] text-[var(--muted)] mb-1 uppercase font-mono">
                {isAgent ? "Agent" : "Caller"} • {`${(turn.started_at_ms / 1000).toFixed(1)}s`}
              </div>
              <p className="leading-relaxed">{turn.text}</p>
            </div>
          </div>
        );
      })}
    </div>
  );
};
