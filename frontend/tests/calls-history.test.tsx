import { describe, it, expect } from "vitest";
import React from "react";
import { renderToString } from "react-dom/server";
import { TranscriptViewer } from "@/components/calls/transcript-viewer";
import { AudioPlayer } from "@/components/calls/audio-player";

describe("Call History Components", () => {
  it("renders ordered transcript turns with caller and agent tags", () => {
    const turns = [
      { id: "1", seq: 1, speaker: "caller" as const, text: "I need an appointment", started_at_ms: 1200 },
      { id: "2", seq: 2, speaker: "agent" as const, text: "Sure, what day works best?", started_at_ms: 2400 },
    ];
    const html = renderToString(<TranscriptViewer turns={turns} />);

    expect(html).toContain("I need an appointment");
    expect(html).toContain("Sure, what day works best?");
    expect(html).toContain("Caller");
    expect(html).toContain("Agent");
    expect(html).toContain("1.2s");
    expect(html).toContain("2.4s");
  });

  it("renders audio player with presigned URL source", () => {
    const testUrl = "https://s3.example.com/recording.mp3?sig=xyz";
    const html = renderToString(<AudioPlayer audioUrl={testUrl} />);

    expect(html).toContain('role="region"');
    expect(html).toContain('aria-label="audio player"');
    expect(html).toContain(testUrl);
    expect(html).toContain("Call Audio Recording");
  });
});
