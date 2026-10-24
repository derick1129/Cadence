"use client";

import * as React from "react";
import { Play, Pause, Volume2 } from "lucide-react";

export const AudioPlayer: React.FC<{ audioUrl: string }> = ({ audioUrl }) => {
  const [playing, setPlaying] = React.useState(false);
  const audioRef = React.useRef<HTMLAudioElement | null>(null);

  const togglePlay = () => {
    if (!audioRef.current) return;
    if (playing) {
      audioRef.current.pause();
      setPlaying(false);
    } else {
      audioRef.current.play().catch(() => setPlaying(false));
      setPlaying(true);
    }
  };

  return (
    <div
      role="region"
      aria-label="audio player"
      className="flex items-center gap-4 p-4 bg-[var(--card)] border border-[var(--line)] rounded-xl max-w-xl"
    >
      <audio
        ref={audioRef}
        src={audioUrl}
        onEnded={() => setPlaying(false)}
        className="hidden"
      />
      <button
        type="button"
        onClick={togglePlay}
        aria-label={playing ? "Pause" : "Play"}
        className="w-10 h-10 rounded-full bg-[var(--fg)] text-[var(--bg)] flex items-center justify-center shrink-0 hover:opacity-90"
      >
        {playing ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4 ml-0.5" />}
      </button>
      <div className="flex-1 space-y-1">
        <div className="flex items-center justify-between text-xs text-[var(--muted)]">
          <span>Call Audio Recording</span>
          <Volume2 className="w-3.5 h-3.5" />
        </div>
        <div className="w-full bg-[var(--line)] h-1.5 rounded-full overflow-hidden">
          <div className="bg-[var(--accent)] h-full w-1/3" />
        </div>
      </div>
    </div>
  );
};
