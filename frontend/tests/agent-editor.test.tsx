import { describe, it, expect, vi } from "vitest";
import React from "react";
import { renderToString } from "react-dom/server";
import { AgentEditor } from "@/components/agents/agent-editor";

interface FormProps {
  onSubmit: (e: React.FormEvent) => void;
  [key: string]: unknown;
}

function withComponentHooks<T>(fn: () => T) {
  const states: unknown[] = [];
  let idx = 0;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const internals = (React as any).__CLIENT_INTERNALS_DO_NOT_USE_OR_WARN_USERS_THEY_CANNOT_UPGRADE;
  const prevH = internals.H;
  internals.H = {
    useState: (init: unknown) => {
      const cur = idx++;
      if (states.length <= cur) {
        states.push(typeof init === "function" ? (init as () => unknown)() : init);
      }
      return [
        states[cur],
        (val: unknown) => {
          states[cur] = typeof val === "function" ? (val as (p: unknown) => unknown)(states[cur]) : val;
        },
      ];
    },
  };

  try {
    const result = fn();
    return { result, states };
  } finally {
    internals.H = prevH;
  }
}

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

  it("invokes onSave callback with validated payload when form submit is triggered", () => {
    const handleSave = vi.fn();
    const handleTestCall = vi.fn();

    const { result } = withComponentHooks(() =>
      AgentEditor({
        agent: mockAgent,
        onSave: handleSave,
        onTestCall: handleTestCall,
      })
    );

    const formElement = result as React.ReactElement<FormProps>;
    expect(formElement).toBeDefined();
    expect(formElement.type).toBe("form");

    const preventDefault = vi.fn();
    formElement.props.onSubmit({ preventDefault } as unknown as React.FormEvent);

    expect(preventDefault).toHaveBeenCalled();
    expect(handleSave).toHaveBeenCalledTimes(1);
    expect(handleSave).toHaveBeenCalledWith({
      system_prompt: "You are a polite receptionist.",
      greeting: "Hello, how can I help you?",
      voice: "sonic-english",
      model: "gpt-4o-mini",
      silence_timeout_s: 15,
    });
  });

  it("trims system_prompt before invoking onSave", () => {
    const handleSave = vi.fn();
    const untrimmedAgent = {
      ...mockAgent,
      systemPrompt: "   Prompt with whitespace padding   \n",
    };

    const { result } = withComponentHooks(() =>
      AgentEditor({
        agent: untrimmedAgent,
        onSave: handleSave,
        onTestCall: vi.fn(),
      })
    );

    const formElement = result as React.ReactElement<FormProps>;
    const preventDefault = vi.fn();
    formElement.props.onSubmit({ preventDefault } as unknown as React.FormEvent);

    expect(handleSave).toHaveBeenCalledWith(
      expect.objectContaining({
        system_prompt: "Prompt with whitespace padding",
      })
    );
  });

  it("does not invoke onSave and sets validation error when system_prompt is empty or whitespace-only", () => {
    const handleSave = vi.fn();
    const emptyAgent = {
      ...mockAgent,
      systemPrompt: "   ",
    };

    const { result, states } = withComponentHooks(() =>
      AgentEditor({
        agent: emptyAgent,
        onSave: handleSave,
        onTestCall: vi.fn(),
      })
    );

    const formElement = result as React.ReactElement<FormProps>;
    const preventDefault = vi.fn();
    formElement.props.onSubmit({ preventDefault } as unknown as React.FormEvent);

    expect(handleSave).not.toHaveBeenCalled();
    // Index 6 corresponds to error state in AgentEditor
    expect(states[6]).toBe("System prompt is required and cannot be empty.");
  });
});
