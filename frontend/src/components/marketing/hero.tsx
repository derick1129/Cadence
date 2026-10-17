"use client";

import * as React from "react";
import Link from "next/link";
import { ArrowRight, Play, Wrench, CheckCircle2 } from "lucide-react";
import { BackgroundBeams } from "@/components/ui/background-beams";
import { TextGenerateEffect } from "@/components/ui/text-generate-effect";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

export function Hero() {
  return (
    <section className="relative overflow-hidden pt-20 pb-24 md:pt-28 md:pb-36 border-b border-[var(--line)]">
      {/* Aceternity Background Beams */}
      <BackgroundBeams />

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
              <Link href="/register">
                <Button size="lg" className="rounded-xl px-6 gap-2">
                  <span>Start free</span>
                  <ArrowRight className="w-4 h-4" />
                </Button>
              </Link>

              <Link href="#how">
                <Button variant="secondary" size="lg" className="rounded-xl px-5 gap-2">
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

              {/* Live Waveform Indicator */}
              <div
                className="h-12 flex items-center justify-center gap-1 px-4 bg-[var(--bg)] rounded-lg border border-[var(--line)] overflow-hidden"
                aria-hidden="true"
              >
                {[
                  8, 14, 22, 12, 28, 36, 18, 30, 42, 24, 16, 34, 40, 22, 14,
                  30, 38, 20, 16, 26, 32, 18, 10, 6,
                ].map((height, i) => (
                  <span
                    key={i}
                    className="w-1 rounded-full bg-[var(--fg)] opacity-80 motion-safe:animate-pulse"
                    style={{
                      height: `${height}px`,
                      animationDelay: `${(i % 5) * 0.15}s`,
                      animationDuration: "1.2s",
                    }}
                  />
                ))}
              </div>

              {/* Message Transcript Exchange */}
              <div
                className="space-y-2.5 text-xs font-sans min-h-[220px] flex flex-col justify-end"
                aria-live="polite"
              >
                {/* Caller Message */}
                <div className="max-w-[85%] self-start rounded-xl px-3.5 py-2.5 bg-[var(--line)]/50 border border-[var(--line)] text-[var(--fg)]">
                  <span className="block text-[10px] text-[var(--muted)] mb-0.5 font-medium">
                    Caller (Phone)
                  </span>
                  <span>Hi, I need to move my cleaning from Tuesday to Thursday.</span>
                </div>

                {/* Agent Message */}
                <div className="max-w-[85%] self-end rounded-xl px-3.5 py-2.5 bg-[#0A0A0A] text-white dark:bg-[#EDEDED] dark:text-[#0A0A0A]">
                  <span className="block text-[10px] opacity-75 mb-0.5 font-medium">
                    Cadence Agent
                  </span>
                  <span>Of course. Let me check Thursday for you.</span>
                </div>

                {/* Tool Call Badge */}
                <div className="self-center flex items-center gap-1.5 px-3 py-1 rounded-md border border-dashed border-[var(--accent)]/60 bg-[var(--accent)]/5 text-[var(--accent)] text-[11px] font-mono">
                  <Wrench className="w-3 h-3 shrink-0" />
                  <span>Tool: Check calendar</span>
                </div>

                {/* Agent Response */}
                <div className="max-w-[85%] self-end rounded-xl px-3.5 py-2.5 bg-[#0A0A0A] text-white dark:bg-[#EDEDED] dark:text-[#0A0A0A]">
                  <span className="block text-[10px] opacity-75 mb-0.5 font-medium">
                    Cadence Agent
                  </span>
                  <span>Thursday at 10:30 is open. Want me to move it there?</span>
                </div>
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
