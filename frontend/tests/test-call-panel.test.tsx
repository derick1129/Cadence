import { describe, it, expect, vi } from "vitest";
import React from "react";
import { renderToString } from "react-dom/server";
import { LiveWaveform } from "@/components/voice/live-waveform";
import { TestCallPanel } from "@/components/voice/test-call-panel";

describe("LiveWaveform Component", () => {
  it("renders 8 waveform bars with styling", () => {
    const htmlInactive = renderToString(<LiveWaveform active={false} />);
    expect(htmlInactive).toContain("w-1 bg-[var(--accent)]");
    expect(htmlInactive).toContain("height:15%");

    const htmlActive = renderToString(<LiveWaveform active={true} />);
    expect(htmlActive).toContain("height:90%");
  });
});

describe("TestCallPanel Component", () => {
  it("renders in idle state with start call button and props", () => {
    const onStartMock = vi.fn().mockResolvedValue({
      session_id: "sess-web-1",
      token: "mock-lk-token",
      url: "wss://livekit.example.com",
    });
    const onCloseMock = vi.fn();

    const element = (
      <TestCallPanel
        agentId="agt-123"
        onStartCall={onStartMock}
        onClose={onCloseMock}
        initialStatus="idle"
      />
    );

    expect(element.props.agentId).toBe("agt-123");
    expect(element.props.onStartCall).toBe(onStartMock);
    expect(element.props.onClose).toBe(onCloseMock);

    const html = renderToString(element);
    expect(html).toContain("Start Test Call");
    expect(html).toContain("idle");
  });

  it("renders connected state with mute, end call, and waveform", () => {
    const html = renderToString(
      <TestCallPanel
        agentId="agt-123"
        onStartCall={vi.fn()}
        onClose={vi.fn()}
        initialStatus="connected"
      />
    );

    expect(html).toContain("connected");
    expect(html).toContain("End Call");
    expect(html).toContain("Mute");
    expect(html).toContain("height:90%");
    expect(html).toContain("Hello! How can I help you today?");
  });
});
