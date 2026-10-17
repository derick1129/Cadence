import * as React from "react";
import Link from "next/link";
import { Hero } from "@/components/marketing/hero";
import { ArrowRight, AudioWaveform, ShieldCheck, GitBranch, PhoneForwarded, Lock } from "lucide-react";

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

      {/* Features: Bento Grid */}
      <section id="features" className="max-w-6xl mx-auto px-6">
        <div className="max-w-2xl mb-14 md:mb-20 space-y-4">
          <h2 className="text-3xl md:text-5xl font-bold tracking-tight text-[var(--fg)] font-heading leading-tight">
            Built for real conversations, not phone menus.
          </h2>
          <p className="text-base md:text-lg text-[var(--muted)]">
            Everything an agent needs to handle a call, and everything you need
            to trust what it did.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-6 gap-6">
          {/* Card 1: Interrupt handling (Wide) */}
          <div className="md:col-span-4 rounded-2xl border border-[var(--line)] bg-[var(--card)] p-8 shadow-xs hover:border-[var(--muted)]/40 transition-colors space-y-4 flex flex-col justify-between">
            <div className="space-y-2">
              <div className="w-8 h-8 rounded-lg bg-[var(--bg)] border border-[var(--line)] flex items-center justify-center text-[var(--fg)] mb-4">
                <AudioWaveform className="w-4 h-4" />
              </div>
              <h3 className="text-xl font-bold font-heading text-[var(--fg)]">
                Interrupt it. It stops and listens.
              </h3>
              <p className="text-sm text-[var(--muted)] leading-relaxed max-w-lg">
                Callers talk over agents all the time. Cadence cancels the reply
                mid-sentence and answers what was just said without lag.
              </p>
            </div>
            <div className="pt-4 flex items-center gap-1.5 text-xs text-[var(--accent)] font-medium font-mono">
              <span className="w-1.5 h-1.5 rounded-full bg-[var(--accent)]" />
              <span>Instant speech cancellation & barge-in detection</span>
            </div>
          </div>

          {/* Card 2: Two doors */}
          <div className="md:col-span-2 rounded-2xl border border-[var(--line)] bg-[var(--card)] p-8 shadow-xs hover:border-[var(--muted)]/40 transition-colors space-y-4 flex flex-col justify-between">
            <div className="space-y-2">
              <div className="w-8 h-8 rounded-lg bg-[var(--bg)] border border-[var(--line)] flex items-center justify-center text-[var(--fg)] mb-4">
                <PhoneForwarded className="w-4 h-4" />
              </div>
              <h3 className="text-xl font-bold font-heading text-[var(--fg)]">
                One agent, two doors
              </h3>
              <p className="text-sm text-[var(--muted)] leading-relaxed">
                The same agent answers a phone number or a call button on your
                site with identical capabilities and voice identity.
              </p>
            </div>
            <div className="text-xs text-[var(--muted)]">WebRTC + SIP Trunking</div>
          </div>

          {/* Card 3: Mid-call actions */}
          <div className="md:col-span-3 rounded-2xl border border-[var(--line)] bg-[var(--card)] p-8 shadow-xs hover:border-[var(--muted)]/40 transition-colors space-y-4">
            <h3 className="text-xl font-bold font-heading text-[var(--fg)]">
              Does things mid-call
            </h3>
            <p className="text-sm text-[var(--muted)] leading-relaxed">
              Check a calendar, call your API, or hand the call to a person.
            </p>
            <div className="flex flex-wrap gap-2 pt-2">
              <span className="px-3 py-1 rounded-full border border-[var(--line)] bg-[var(--bg)] text-xs text-[var(--fg)]">
                Check calendar
              </span>
              <span className="px-3 py-1 rounded-full border border-[var(--line)] bg-[var(--bg)] text-xs text-[var(--fg)]">
                Book appointment
              </span>
              <span className="px-3 py-1 rounded-full border border-[var(--line)] bg-[var(--bg)] text-xs text-[var(--fg)]">
                Transfer
              </span>
            </div>
          </div>

          {/* Card 4: Full Audit Records (Wide) */}
          <div className="md:col-span-3 rounded-2xl border border-[var(--line)] bg-[var(--card)] p-8 shadow-xs hover:border-[var(--muted)]/40 transition-colors space-y-4">
            <h3 className="text-xl font-bold font-heading text-[var(--fg)]">
              Every call on record
            </h3>
            <p className="text-sm text-[var(--muted)] leading-relaxed">
              Listen back to the audio, read the transcript, and see how long
              each reply took. Tool calls are logged, so you can see what the
              agent did and when.
            </p>
          </div>

          {/* Card 5: Safe edits */}
          <div className="md:col-span-2 rounded-2xl border border-[var(--line)] bg-[var(--card)] p-8 shadow-xs hover:border-[var(--muted)]/40 transition-colors space-y-3">
            <div className="w-8 h-8 rounded-lg bg-[var(--bg)] border border-[var(--line)] flex items-center justify-center text-[var(--fg)] mb-2">
              <GitBranch className="w-4 h-4" />
            </div>
            <h3 className="text-lg font-bold font-heading text-[var(--fg)]">
              Safe edits
            </h3>
            <p className="text-xs text-[var(--muted)] leading-relaxed">
              Each save is a new version. A live call never changes halfway through.
            </p>
          </div>

          {/* Card 6: Knowledge Base */}
          <div className="md:col-span-2 rounded-2xl border border-[var(--line)] bg-[var(--card)] p-8 shadow-xs hover:border-[var(--muted)]/40 transition-colors space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs px-2 py-0.5 rounded-full border border-[var(--line)] bg-[var(--bg)] text-[var(--muted)] font-medium">
                Coming soon
              </span>
            </div>
            <h3 className="text-lg font-bold font-heading text-[var(--fg)]">
              Your company’s knowledge
            </h3>
            <p className="text-xs text-[var(--muted)] leading-relaxed">
              Upload documents so the agent answers from your own material.
            </p>
          </div>

          {/* Card 7: Outbound campaigns */}
          <div className="md:col-span-2 rounded-2xl border border-[var(--line)] bg-[var(--card)] p-8 shadow-xs hover:border-[var(--muted)]/40 transition-colors space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs px-2 py-0.5 rounded-full border border-[var(--line)] bg-[var(--bg)] text-[var(--muted)] font-medium">
                Coming soon
              </span>
            </div>
            <h3 className="text-lg font-bold font-heading text-[var(--fg)]">
              Outbound campaigns
            </h3>
            <p className="text-xs text-[var(--muted)] leading-relaxed">
              Call a contact list within the hours you set, with consent checks built in.
            </p>
          </div>

          {/* Card 8: Tenancy Isolation */}
          <div className="md:col-span-6 rounded-2xl border border-[var(--line)] bg-[var(--card)] p-6 shadow-xs flex items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-lg bg-[var(--bg)] border border-[var(--line)] flex items-center justify-center text-[var(--accent)] shrink-0">
                <Lock className="w-4 h-4" />
              </div>
              <div>
                <h3 className="text-base font-bold font-heading text-[var(--fg)]">
                  Separate by organization
                </h3>
                <p className="text-xs text-[var(--muted)]">
                  Each team’s agents, calls and recordings are strictly isolated with tenant-scoped encryption.
                </p>
              </div>
            </div>
            <ShieldCheck className="w-5 h-5 text-[var(--accent)] shrink-0 hidden sm:block" />
          </div>
        </div>
      </section>

      {/* How It Works: 3 Steps */}
      <section id="how" className="max-w-6xl mx-auto px-6">
        <div className="max-w-2xl mb-14 md:mb-20 space-y-4">
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
              Write what the agent should do, pick a voice, and attach the tools
              it can use.
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
              Start a test call, interrupt it, and adjust until it sounds right.
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
              Point a phone number at the agent and review every call afterward.
            </p>
          </div>
        </div>
      </section>

      {/* Final Call to Action */}
      <section id="start" className="max-w-6xl mx-auto px-6">
        <div className="rounded-3xl border border-[var(--line)] bg-[var(--card)] py-16 px-8 md:py-24 md:px-16 text-center shadow-lg relative overflow-hidden">
          <div className="max-w-xl mx-auto space-y-6 relative z-10">
            <h2 className="text-3xl md:text-5xl font-bold tracking-tight text-[var(--fg)] font-heading leading-tight">
              Hear your agent before you commit.
            </h2>
            <p className="text-base md:text-lg text-[var(--muted)] leading-relaxed">
              Create one in minutes and talk to it from your browser. No phone
              number needed to start.
            </p>
            <div className="pt-2">
              <Link
                href="/register"
                className="inline-flex items-center justify-center gap-2 h-12 px-8 rounded-xl bg-[#0A0A0A] text-white hover:bg-[#262626] dark:bg-[#EDEDED] dark:text-[#0A0A0A] dark:hover:bg-white text-base font-semibold transition-transform active:scale-98 shadow-md"
              >
                <span>Start free</span>
                <ArrowRight className="w-4 h-4" />
              </Link>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
