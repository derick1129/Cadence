"use client";

import * as React from "react";

export const defaultProviders = [
  "LiveKit",
  "Twilio",
  "Telnyx",
  "Deepgram",
  "Cartesia",
  "ElevenLabs",
  "OpenAI",
  "Stripe",
];

export function StackMarquee({
  providers = defaultProviders,
}: {
  providers?: string[];
}) {
  const duplicated = [...providers, ...providers];

  return (
    <section
      className="marquee-container bg-[var(--card)]/40"
      aria-label="Supported voice stack"
    >
      <p className="text-center text-sm text-[var(--muted)] mb-3.5">
        Designed to work with the voice stack you choose (example names)
      </p>
      <div
        className="marquee-track"
        data-testid="marquee-track"
        aria-hidden="true"
      >
        {duplicated.map((provider, i) => (
          <span
            key={`${provider}-${i}`}
            className="hover:text-[var(--fg)] transition-colors select-none"
          >
            {provider}
          </span>
        ))}
      </div>
    </section>
  );
}
