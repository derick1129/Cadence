import * as React from "react";
import Link from "next/link";
import { Hero } from "@/components/marketing/hero";
import { BentoGrid, BentoGridItem } from "@/components/ui/bento-grid";
import { CardSpotlight } from "@/components/ui/card-spotlight";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  ArrowRight,
  AudioWaveform,
  ShieldCheck,
  GitBranch,
  PhoneForwarded,
  Lock,
  Layers,
  Wrench,
  Radio,
} from "lucide-react";

const providers = [
  "LiveKit",
  "Twilio",
  "Telnyx",
  "Deepgram",
  "Cartesia",
  "ElevenLabs",
  "OpenAI",
  "Stripe",
];

export default function MarketingPage() {
  return (
    <div className="space-y-24 md:space-y-36 pb-24">
      {/* Hero Section */}
      <Hero />

      {/* Provider Stack Marquee Strip */}
      <section className="border-y border-[var(--line)] py-10 overflow-hidden bg-[var(--card)]/40">
        <div className="max-w-6xl mx-auto px-6 text-center space-y-4">
          <p className="text-xs uppercase tracking-wider text-[var(--muted)] font-medium">
            Designed to work with the voice stack you choose
          </p>
          <div className="flex flex-wrap items-center justify-center gap-8 md:gap-14 text-sm md:text-base font-heading font-semibold text-[var(--muted)]">
            {providers.map((provider) => (
              <span
                key={provider}
                className="hover:text-[var(--fg)] transition-colors select-none"
              >
                {provider}
              </span>
            ))}
          </div>
        </div>
      </section>

      {/* Features: Aceternity Bento Grid */}
      <section id="features" className="max-w-6xl mx-auto px-6">
        <div className="max-w-2xl mb-14 md:mb-20 space-y-4">
          <Badge variant="outline" className="mb-2">Platform Capabilities</Badge>
          <h2 className="text-3xl md:text-5xl font-bold tracking-tight text-[var(--fg)] font-heading leading-tight">
            Built for real conversations, not phone menus.
          </h2>
          <p className="text-base md:text-lg text-[var(--muted)]">
            Everything an agent needs to handle a call, and everything you need
            to trust what it did.
          </p>
        </div>

        <BentoGrid>
          {/* Card 1: Interrupt handling (Wide with Spotlight) */}
          <CardSpotlight className="md:col-span-4 flex flex-col justify-between space-y-4">
            <div className="space-y-3">
              <div className="w-10 h-10 rounded-xl bg-[var(--bg)] border border-[var(--line)] flex items-center justify-center text-[var(--fg)] mb-2 shadow-2xs">
                <AudioWaveform className="w-5 h-5 text-[var(--accent)]" />
              </div>
              <h3 className="text-xl md:text-2xl font-bold font-heading text-[var(--fg)]">
                Interrupt it. It stops and listens.
              </h3>
              <p className="text-sm text-[var(--muted)] leading-relaxed max-w-lg">
                Callers talk over agents all the time. Cadence cancels the speech reply
                mid-sentence and answers what was just said without perceived lag.
              </p>
            </div>
            <div className="pt-4 flex items-center gap-2 text-xs text-[var(--accent)] font-medium font-mono">
              <span className="w-2 h-2 rounded-full bg-[var(--accent)] animate-pulse" />
              <span>Instant speech cancellation & barge-in detection (&lt; 200ms)</span>
            </div>
          </CardSpotlight>

          {/* Card 2: Two doors */}
          <BentoGridItem
            className="md:col-span-2"
            icon={
              <div className="w-10 h-10 rounded-xl bg-[var(--bg)] border border-[var(--line)] flex items-center justify-center text-[var(--fg)] shadow-2xs">
                <PhoneForwarded className="w-5 h-5" />
              </div>
            }
            title="One agent, two doors"
            description="The same agent answers a phone number via SIP trunking or an in-browser WebRTC call button with identical voice identity."
            footer={
              <Badge variant="outline" className="text-xs">
                WebRTC + SIP
              </Badge>
            }
          />

          {/* Card 3: Mid-call actions */}
          <BentoGridItem
            className="md:col-span-3"
            icon={
              <div className="w-10 h-10 rounded-xl bg-[var(--bg)] border border-[var(--line)] flex items-center justify-center text-[var(--fg)] shadow-2xs">
                <Wrench className="w-5 h-5" />
              </div>
            }
            title="Does things mid-call"
            description="Check live calendar availability, invoke your backend API, or gracefully hand off the caller to a team member."
            footer={
              <div className="flex flex-wrap gap-1.5 pt-1">
                <Badge variant="secondary">Check calendar</Badge>
                <Badge variant="secondary">Book slot</Badge>
                <Badge variant="secondary">Transfer call</Badge>
              </div>
            }
          />

          {/* Card 4: Full Audit Records */}
          <BentoGridItem
            className="md:col-span-3"
            icon={
              <div className="w-10 h-10 rounded-xl bg-[var(--bg)] border border-[var(--line)] flex items-center justify-center text-[var(--fg)] shadow-2xs">
                <Radio className="w-5 h-5 text-[var(--accent)]" />
              </div>
            }
            title="Every call on record"
            description="Listen to raw audio recordings, inspect timestamped transcripts, and audit tool invocations with millisecond latency metrics."
            footer={
              <Badge variant="accent" className="text-xs">
                Full session audit trail
              </Badge>
            }
          />

          {/* Card 5: Safe edits */}
          <BentoGridItem
            className="md:col-span-2"
            icon={
              <div className="w-8 h-8 rounded-lg bg-[var(--bg)] border border-[var(--line)] flex items-center justify-center text-[var(--fg)]">
                <GitBranch className="w-4 h-4" />
              </div>
            }
            title="Safe edits"
            description="Each prompt or configuration change generates an immutable version. Active calls are pinned to their starting version."
          />

          {/* Card 6: Knowledge Base */}
          <BentoGridItem
            className="md:col-span-2"
            icon={
              <div className="w-8 h-8 rounded-lg bg-[var(--bg)] border border-[var(--line)] flex items-center justify-center text-[var(--fg)]">
                <Layers className="w-4 h-4" />
              </div>
            }
            title="Company knowledge"
            description="Upload PDFs, guidelines, and manuals so agents answer with high precision from your proprietary docs."
            footer={<Badge variant="outline">Coming soon</Badge>}
          />

          {/* Card 7: Outbound campaigns */}
          <BentoGridItem
            className="md:col-span-2"
            icon={
              <div className="w-8 h-8 rounded-lg bg-[var(--bg)] border border-[var(--line)] flex items-center justify-center text-[var(--fg)]">
                <PhoneForwarded className="w-4 h-4" />
              </div>
            }
            title="Outbound campaigns"
            description="Schedule automated outreach with built-in consent enforcement, time-window controls, and retry rules."
            footer={<Badge variant="outline">Coming soon</Badge>}
          />

          {/* Card 8: Tenancy Isolation */}
          <CardSpotlight className="md:col-span-6 p-6 flex items-center justify-between gap-4">
            <div className="flex items-center gap-4">
              <div className="w-10 h-10 rounded-xl bg-[var(--bg)] border border-[var(--line)] flex items-center justify-center text-[var(--accent)] shrink-0 shadow-2xs">
                <Lock className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-base font-bold font-heading text-[var(--fg)]">
                  Strict multi-tenant isolation
                </h3>
                <p className="text-xs text-[var(--muted)]">
                  Every agent, telephony number, recording, and transcript is scoped by organization ID with zero cross-tenant access.
                </p>
              </div>
            </div>
            <ShieldCheck className="w-6 h-6 text-[var(--accent)] shrink-0 hidden sm:block" />
          </CardSpotlight>
        </BentoGrid>
      </section>

      {/* How It Works: 3 Steps */}
      <section id="how" className="max-w-6xl mx-auto px-6">
        <div className="max-w-2xl mb-14 md:mb-20 space-y-4">
          <Badge variant="outline" className="mb-2">Setup Flow</Badge>
          <h2 className="text-3xl md:text-5xl font-bold tracking-tight text-[var(--fg)] font-heading leading-tight">
            From idea to a ringing phone in an afternoon.
          </h2>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-8 md:gap-12">
          {/* Step 1 */}
          <div className="border-t border-[var(--line)] pt-6 space-y-3">
            <div className="w-8 h-8 rounded-full bg-[#0A0A0A] text-white dark:bg-[#EDEDED] dark:text-[#0A0A0A] text-sm font-bold flex items-center justify-center font-heading">
              1
            </div>
            <h3 className="text-xl font-bold font-heading text-[var(--fg)]">
              Describe the job
            </h3>
            <p className="text-sm text-[var(--muted)] leading-relaxed">
              Write what the agent should do, select models and voice providers, and attach the tools it can invoke.
            </p>
          </div>

          {/* Step 2 */}
          <div className="border-t border-[var(--line)] pt-6 space-y-3">
            <div className="w-8 h-8 rounded-full bg-[#0A0A0A] text-white dark:bg-[#EDEDED] dark:text-[#0A0A0A] text-sm font-bold flex items-center justify-center font-heading">
              2
            </div>
            <h3 className="text-xl font-bold font-heading text-[var(--fg)]">
              Talk to it in your browser
            </h3>
            <p className="text-sm text-[var(--muted)] leading-relaxed">
              Start an instant WebRTC test call, interrupt mid-speech, and adjust prompting until it sounds completely natural.
            </p>
          </div>

          {/* Step 3 */}
          <div className="border-t border-[var(--line)] pt-6 space-y-3">
            <div className="w-8 h-8 rounded-full bg-[#0A0A0A] text-white dark:bg-[#EDEDED] dark:text-[#0A0A0A] text-sm font-bold flex items-center justify-center font-heading">
              3
            </div>
            <h3 className="text-xl font-bold font-heading text-[var(--fg)]">
              Connect a number
            </h3>
            <p className="text-sm text-[var(--muted)] leading-relaxed">
              Assign an inbound phone number or trigger outbound dispatch, and monitor every live call with detailed recording metrics.
            </p>
          </div>
        </div>
      </section>

      {/* Final Call to Action */}
      <section id="start" className="max-w-6xl mx-auto px-6">
        <CardSpotlight className="rounded-3xl border border-[var(--line)] bg-[var(--card)] py-16 px-8 md:py-24 md:px-16 text-center shadow-lg relative overflow-hidden">
          <div className="max-w-xl mx-auto space-y-6 relative z-10">
            <h2 className="text-3xl md:text-5xl font-bold tracking-tight text-[var(--fg)] font-heading leading-tight">
              Hear your agent before you commit.
            </h2>
            <p className="text-base md:text-lg text-[var(--muted)] leading-relaxed">
              Create an agent in minutes and talk to it from your browser. No phone
              number or credit card needed to test.
            </p>
            <div className="pt-2">
              <Link href="/register">
                <Button size="lg" className="rounded-xl px-8 h-12 text-base gap-2">
                  <span>Start free</span>
                  <ArrowRight className="w-4 h-4" />
                </Button>
              </Link>
            </div>
          </div>
        </CardSpotlight>
      </section>
    </div>
  );
}
