"use client";

import * as React from "react";
import { Mic, MicOff, PhoneOff, PhoneCall, Radio, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { LiveWaveform } from "@/components/voice/live-waveform";

export interface TestCallPanelProps {
  agentId: string;
  onStartCall: (agentId: string) => Promise<{ session_id: string; token: string; url: string }>;
  onClose: () => void;
  initialStatus?: "idle" | "connecting" | "connected" | "ended";
}

export const TestCallPanel: React.FC<TestCallPanelProps> = ({
  agentId,
  onStartCall,
  onClose,
  initialStatus = "idle",
}) => {
  const [status, setStatus] = React.useState(initialStatus);
  const [muted, setMuted] = React.useState(false);
  const [seconds, setSeconds] = React.useState(0);
  const [transcripts] = React.useState<{ speaker: string; text: string }[]>([
    { speaker: "agent", text: "Hello! How can I help you today?" },
  ]);

  React.useEffect(() => {
    let timer: NodeJS.Timeout;
    if (status === "connected") {
      timer = setInterval(() => setSeconds((s) => s + 1), 1000);
    }
    return () => clearInterval(timer);
  }, [status]);

  const handleStart = async () => {
    setStatus("connecting");
    try {
      await onStartCall(agentId);
      setStatus("connected");
    } catch {
      setStatus("idle");
    }
  };

  const handleEnd = () => {
    setStatus("ended");
  };

  const formatTime = (total: number) => {
    const mins = Math.floor(total / 60);
    const secs = total % 60;
    return `${mins}:${secs < 10 ? "0" : ""}${secs}`;
  };

  return (
    <div className="p-6 bg-[var(--card)] border border-[var(--line)] rounded-xl shadow-lg space-y-4 max-w-md w-full">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Radio
            className={`w-4 h-4 ${
              status === "connected" ? "text-[var(--accent)] animate-pulse" : "text-[var(--muted)]"
            }`}
          />
          <span className="text-sm font-semibold text-[var(--fg)] capitalize">{status}</span>
          {status === "connected" && (
            <span className="text-xs text-[var(--muted)] font-mono">({formatTime(seconds)})</span>
          )}
        </div>
        <button
          onClick={onClose}
          className="text-[var(--muted)] hover:text-[var(--fg)]"
          aria-label="Close panel"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      <LiveWaveform active={status === "connected"} />

      <div className="h-48 overflow-y-auto space-y-2 p-3 bg-[var(--bg)] border border-[var(--line)] rounded-lg text-xs">
        {transcripts.map((t, idx) => (
          <div
            key={idx}
            className={t.speaker === "agent" ? "text-left text-[var(--fg)]" : "text-right text-[var(--muted)]"}
          >
            <span className="font-semibold uppercase tracking-wider text-[10px] block opacity-75">
              {t.speaker}
            </span>
            <span>{t.text}</span>
          </div>
        ))}
      </div>

      <div className="flex items-center justify-between pt-2">
        {status === "idle" ? (
          <Button
            onClick={handleStart}
            variant="primary"
            className="w-full flex items-center justify-center gap-2"
          >
            <PhoneCall className="w-4 h-4" />
            <span>Start Test Call</span>
          </Button>
        ) : (
          <>
            <Button
              type="button"
              variant="secondary"
              onClick={() => setMuted(!muted)}
              className="flex items-center gap-2"
            >
              {muted ? <MicOff className="w-4 h-4 text-red-500" /> : <Mic className="w-4 h-4" />}
              <span>{muted ? "Unmute" : "Mute"}</span>
            </Button>
            <Button
              type="button"
              variant="primary"
              onClick={handleEnd}
              className="bg-red-600 hover:bg-red-700 text-white flex items-center gap-2"
            >
              <PhoneOff className="w-4 h-4" />
              <span>End Call</span>
            </Button>
          </>
        )}
      </div>
    </div>
  );
};
