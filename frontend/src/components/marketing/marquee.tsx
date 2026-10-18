"use client";

import * as React from "react";

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

export function StackMarquee() {
  const duplicated = providers.concat(providers);

  return (
    <div className="mq">
      <p>Designed to work with the voice stack you choose (example names)</p>
      <div className="track" aria-hidden="true" id="track">
        {duplicated.map((n, i) => (
          <span key={`${n}-${i}`}>{n}</span>
        ))}
      </div>
    </div>
  );
}
