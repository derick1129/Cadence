"use client";

import * as React from "react";
import Link from "next/link";
import { ArrowRight, Play, Wrench, CheckCircle2 } from "lucide-react";
import { TextGenerateEffect } from "@/components/ui/text-generate-effect";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

// 26 waveform bars matching reference demo Math.sin formula
const WAVEFORM_BARS = Array.from({ length: 26 }, (_, i) => ({
  height: 10 + Math.round(Math.abs(Math.sin(i * 1.7)) * 56),
  delay: (i * 0.07).toFixed(2),
}));

interface MessageItem {
  kind: "c" | "a" | "t";
  text: string;
}

const CONVERSATION_SCRIPT: MessageItem[] = [
  { kind: "c", text: "Hi, I need to move my cleaning from Tuesday to Thursday." },
  { kind: "a", text: "Of course. Let me check Thursday for you." },
  { kind: "t", text: "Tool: Check calendar" },
  { kind: "a", text: "Thursday at 10:30 is open. Want me to move it there?" },
  { kind: "c", text: "Yes, please." },
  { kind: "t", text: "Tool: Reschedule appointment" },
  { kind: "a", text: "Done. You’re booked for Thursday at 10:30." },
];

export function Hero() {
  const heroRef = React.useRef<HTMLElement>(null);
  const [messages, setMessages] = React.useState<MessageItem[]>(() =>
    CONVERSATION_SCRIPT.slice(0, 4)
  );

  const handlePointerMove = (e: React.PointerEvent<HTMLElement>) => {
    if (!heroRef.current) return;
    const r = heroRef.current.getBoundingClientRect();
    heroRef.current.style.setProperty("--mx", `${e.clientX - r.left}px`);
    heroRef.current.style.setProperty("--my", `${e.clientY - r.top}px`);
  };

  React.useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      setMessages(CONVERSATION_SCRIPT);
      return;
    }

    let currentIndex = 4;
    let timer: NodeJS.Timeout;

    const step = () => {
      if (currentIndex >= CONVERSATION_SCRIPT.length) {
        timer = setTimeout(() => {
          setMessages([]);
          currentIndex = 0;
          step();
        }, 3200);
        return;
      }

      const nextMessage = CONVERSATION_SCRIPT[currentIndex];
      currentIndex++;

      setMessages((prev) => {
        const updated = [...prev, nextMessage];
        return updated.length > 5 ? updated.slice(updated.length - 5) : updated;
      });

      const delay = nextMessage.kind === "t" ? 900 : 1700;
      timer = setTimeout(step, delay);
    };

    timer = setTimeout(step, 1800);
    return () => clearTimeout(timer);
  }, []);

  return (
    <section
      ref={heroRef}
      onPointerMove={handlePointerMove}
      className="hero relative overflow-hidden pt-20 pb-24 md:pt-28 md:pb-36 border-b border-[var(--line)]"
      id="hero"
    >
      {/* Background Grid Layer (44px) & Pointer-following Spotlight */}
      <div className="hero-grid-bg" data-testid="hero-grid" aria-hidden="true" />
      <div className="hero-spotlight" data-testid="hero-spotlight" aria-hidden="true" />

      <div className="max-w-6xl mx-auto px-6 relative z-10">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-12 lg:gap-16 items-center">
          {/* Left Column: Headline and Call-to-actions */}
          <div className="lg:col-span-7 space-y-6">
            <Badge variant="outline" className="gap-2 py-1.5 px-3 bg-[var(--card)]/80 backdrop-blur-xs">
              <span
                className="w-2 h-2 rounded-full bg-[var(--accent)] motion-safe:animate-pulse"
                aria-hidden="true"
              />
              <span className="text-[var(--muted)] font-medium">Phone and browser voice agents</span>
            </Badge>

            <h1 className="text-4xl sm:text-5xl lg:text-6xl font-bold tracking-tight text-[var(--fg)] font-heading leading-[1.08]">
              <TextGenerateEffect words="Voice agents that answer your calls" />
            </h1>

            <p className="text-base sm:text-lg text-[var(--muted)] max-w-xl leading-relaxed">
              Cadence builds voice agents that listen, reply in real time and take
              action during the call. Afterward you get the recording,
              transcript and timing for every conversation.
            </p>

            <div className="flex flex-wrap items-center gap-4 pt-2">
              <span className="moving-border-btn">
                <Link href="/register" className="moving-border-btn-inner">
                  <span>Start free</span>
                  <ArrowRight className="w-4 h-4 ml-2" />
                </Link>
              </span>

              <Link href="#how">
                <Button variant="secondary" size="lg" className="rounded-xl px-5 h-12 gap-2">
                  <Play className="w-3.5 h-3.5 fill-current" />
                  <span>See how it works</span>
                </Button>
              </Link>
            </div>

            <div className="pt-4 flex flex-wrap items-center gap-6 text-xs text-[var(--muted)]">
              <div className="flex items-center gap-1.5">
                <CheckCircle2 className="w-4 h-4 text-[var(--accent)]" />
                <span>&lt; 500ms voice response</span>
              </div>
              <div className="flex items-center gap-1.5">
                <CheckCircle2 className="w-4 h-4 text-[var(--accent)]" />
                <span>Browser & SIP phone</span>
              </div>
              <div className="flex items-center gap-1.5">
                <CheckCircle2 className="w-4 h-4 text-[var(--accent)]" />
                <span>Zero vendor lock-in</span>
              </div>
            </div>
          </div>

          {/* Right Column: Live Call Preview Card Illustration */}
          <div className="lg:col-span-5">
            <div
              className="rounded-2xl border border-[var(--line)] bg-[var(--card)] p-6 shadow-2xl space-y-4 relative backdrop-blur-xs"
              aria-label="Example live call illustration"
            >
              {/* Card Header */}
              <div className="flex items-center justify-between pb-3 border-b border-[var(--line)] text-xs">
                <div className="flex items-center gap-2">
                  <span className="font-semibold text-[var(--fg)]">
                    Front desk assistant
                  </span>
                  <span className="text-[var(--muted)]">· Inbound</span>
                </div>
                <Badge variant="accent" className="gap-1.5 font-semibold">
                  <span
                    className="w-1.5 h-1.5 rounded-full bg-[var(--accent)] motion-safe:animate-pulse"
                    aria-hidden="true"
                  />
                  <span>Live call</span>
                </Badge>
              </div>

              {/* Live Waveform Indicator (26 bars) */}
              <div
                className="h-16 flex items-center justify-center gap-1 px-4 my-2 overflow-hidden"
                data-testid="waveform-bars"
                aria-hidden="true"
              >
                {WAVEFORM_BARS.map((bar, i) => (
                  <span
                    key={i}
                    className="waveform-bar"
                    style={
                      {
                        "--h": `${bar.height}px`,
                        animationDelay: `${bar.delay}s`,
                      } as React.CSSProperties
                    }
                  />
                ))}
              </div>

              {/* Message Transcript Exchange (Animated Simulation) */}
              <div
                className="space-y-2.5 text-xs font-sans min-h-[200px] flex flex-col justify-end"
                aria-live="polite"
              >
                {messages.map((msg, idx) => {
                  if (msg.kind === "t") {
                    return (
                      <div
                        key={`${idx}-${msg.text}`}
                        className="self-center flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-dashed border-[var(--mint)]/60 bg-[var(--mint)]/5 text-[var(--mint)] text-[11px] font-mono animate-[msg-in_0.35s_ease-out]"
                      >
                        <Wrench className="w-3 h-3 shrink-0" />
                        <span>{msg.text}</span>
                      </div>
                    );
                  }
                  const isAgent = msg.kind === "a";
                  return (
                    <div
                      key={`${idx}-${msg.text}`}
                      className={cn(
                        "max-w-[88%] rounded-2xl px-3.5 py-2.5 text-[13px] animate-[msg-in_0.35s_ease-out]",
                        isAgent
                          ? "self-end bg-[var(--acc)] text-[var(--on-acc)]"
                          : "self-start bg-[var(--fg)]/6 border border-[var(--line)] text-[var(--fg)]"
                      )}
                    >
                      <span
                        className={cn(
                          "block text-[10px] mb-0.5 font-medium",
                          isAgent ? "opacity-75" : "text-[var(--muted)]"
                        )}
                      >
                        {isAgent ? "Cadence Agent" : "Caller"}
                      </span>
                      <span>{msg.text}</span>
                    </div>
                  );
                })}
              </div>

              {/* Card Footer Stat Tile */}
              <div className="pt-2 border-t border-[var(--line)] flex items-center justify-between text-[11px] text-[var(--muted)]">
                <span>Latency: 280ms</span>
                <span>Isolated tenant</span>
                <span className="text-[var(--accent)] font-medium">Audio recorded</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
