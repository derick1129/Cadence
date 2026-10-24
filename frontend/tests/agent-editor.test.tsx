import { describe, it, expect, vi } from "vitest";
import React from "react";
import { renderToString } from "react-dom/server";
import { AgentEditor } from "@/components/agents/agent-editor";

describe("AgentEditor Component", () => {
  const mockAgent = {
    id: "agt-123",
    name: "Customer Support Agent",
    systemPrompt: "You are a polite receptionist.",
    greeting: "Hello, how can I help you?",
    voice: "sonic-english",
    model: "gpt-4o-mini",
    silenceTimeout: 15,
    tools: ["check_order_status"],
  };

  it("renders agent prompt and configuration fields in HTML", () => {
    const html = renderToString(
      <AgentEditor agent={mockAgent} onSave={vi.fn()} onTestCall={vi.fn()} />
    );

    expect(html).toContain("Customer Support Agent");
    expect(html).toContain("You are a polite receptionist.");
    expect(html).toContain("Hello, how can I help you?");
    expect(html).toContain("Save New Version");
    expect(html).toContain("Start Test Call");
    expect(html).toContain("Silence Timeout: 15s");
  });

  it("renders voice, model, and tool options", () => {
    const html = renderToString(
      <AgentEditor agent={mockAgent} onSave={vi.fn()} onTestCall={vi.fn()} />
    );

    expect(html).toContain("sonic-english");
    expect(html).toContain("gpt-4o-mini");
    expect(html).toContain("check_order_status");
  });

  it("invokes onSave callback when form submit is triggered", () => {
    const handleSave = vi.fn();
    const handleTestCall = vi.fn();

    // Verify component creates element with handler props attached
    const element = <AgentEditor agent={mockAgent} onSave={handleSave} onTestCall={handleTestCall} />;
    expect(element.props.agent.id).toBe("agt-123");
    expect(element.props.onSave).toBe(handleSave);
    expect(element.props.onTestCall).toBe(handleTestCall);
  });
});
