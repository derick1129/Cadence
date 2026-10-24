import { describe, it, expect, vi } from "vitest";
import React from "react";
import { renderToString } from "react-dom/server";
import { ToolModal } from "@/components/tools/tool-modal";

interface FormElementProps {
  children?: React.ReactNode;
  onSubmit?: (e: React.FormEvent) => void;
  [key: string]: unknown;
}

function withComponentHooks<T>(fn: () => T, initialOverrides: Record<number, unknown> = {}) {
  const states: unknown[] = [];
  let idx = 0;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const internals = (React as any).__CLIENT_INTERNALS_DO_NOT_USE_OR_WARN_USERS_THEY_CANNOT_UPGRADE;
  const prevH = internals.H;
  internals.H = {
    useState: (init: unknown) => {
      const cur = idx++;
      if (states.length <= cur) {
        if (cur in initialOverrides) {
          states.push(initialOverrides[cur]);
        } else {
          states.push(typeof init === "function" ? (init as () => unknown)() : init);
        }
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

// Helper to find the form element inside ToolModal tree
function findFormElement(node: React.ReactNode): React.ReactElement<FormElementProps> | null {
  if (!React.isValidElement(node)) return null;
  const element = node as React.ReactElement<FormElementProps>;
  if (element.type === "form") return element;
  if (element.props && element.props.children) {
    const children = Array.isArray(element.props.children)
      ? element.props.children
      : [element.props.children];
    for (const child of children) {
      const found = findFormElement(child);
      if (found) return found;
    }
  }
  return null;
}

describe("ToolModal Component", () => {
  it("renders configuration form with fields and buttons when isOpen is true", () => {
    const onSubmitMock = vi.fn();
    const onCloseMock = vi.fn();

    const element = (
      <ToolModal isOpen={true} onClose={onCloseMock} onSubmit={onSubmitMock} />
    );

    expect(element.props.isOpen).toBe(true);
    expect(element.props.onSubmit).toBe(onSubmitMock);
    expect(element.props.onClose).toBe(onCloseMock);

    const html = renderToString(element);
    expect(html).toContain("Configure New Tool");
    expect(html).toContain("Name");
    expect(html).toContain("Type");
    expect(html).toContain("HTTP Webhook");
    expect(html).toContain("SIP Transfer");
    expect(html).toContain("Create Tool");
    expect(html).toContain("Cancel");
  });

  it("renders nothing when isOpen is false", () => {
    const html = renderToString(
      <ToolModal isOpen={false} onClose={vi.fn()} onSubmit={vi.fn()} />
    );
    expect(html).toBe("");
  });

  it("submits HTTP webhook tool with valid payload and calls onClose", () => {
    const onSubmit = vi.fn();
    const onClose = vi.fn();

    // Overrides: 0: name, 1: type, 2: url, 3: transferNumber, 4: error
    const { result } = withComponentHooks(
      () => ToolModal({ isOpen: true, onClose, onSubmit }),
      {
        0: "lookup_customer",
        1: "http",
        2: "https://api.example.com/lookup",
      }
    );

    const form = findFormElement(result as React.ReactNode);
    expect(form).not.toBeNull();

    const preventDefault = vi.fn();
    form?.props.onSubmit?.({ preventDefault } as unknown as React.FormEvent);

    expect(preventDefault).toHaveBeenCalled();
    expect(onSubmit).toHaveBeenCalledTimes(1);
    expect(onSubmit).toHaveBeenCalledWith({
      name: "lookup_customer",
      type: "http",
      config: { url: "https://api.example.com/lookup", method: "POST" },
      json_schema: { type: "object", properties: {}, required: [] },
    });
    expect(onClose).toHaveBeenCalled();
  });

  it("submits SIP transfer tool with valid E.164 phone number", () => {
    const onSubmit = vi.fn();
    const onClose = vi.fn();

    // Overrides: 0: name, 1: type, 2: url, 3: transferNumber, 4: error
    const { result } = withComponentHooks(
      () => ToolModal({ isOpen: true, onClose, onSubmit }),
      {
        0: "transfer_support",
        1: "transfer",
        3: "+15551234567",
      }
    );

    const form = findFormElement(result as React.ReactNode);
    expect(form).not.toBeNull();

    const preventDefault = vi.fn();
    form?.props.onSubmit?.({ preventDefault } as unknown as React.FormEvent);

    expect(preventDefault).toHaveBeenCalled();
    expect(onSubmit).toHaveBeenCalledTimes(1);
    expect(onSubmit).toHaveBeenCalledWith({
      name: "transfer_support",
      type: "transfer",
      config: { phone_number: "+15551234567" },
      json_schema: { type: "object", properties: {}, required: [] },
    });
    expect(onClose).toHaveBeenCalled();
  });

  it("rejects invalid transfer phone number and displays error message", () => {
    const onSubmit = vi.fn();
    const onClose = vi.fn();

    // Invalid number: "12345" (not E.164)
    const { result, states } = withComponentHooks(
      () => ToolModal({ isOpen: true, onClose, onSubmit }),
      {
        0: "transfer_support",
        1: "transfer",
        3: "12345",
      }
    );

    const form = findFormElement(result as React.ReactNode);
    expect(form).not.toBeNull();

    const preventDefault = vi.fn();
    form?.props.onSubmit?.({ preventDefault } as unknown as React.FormEvent);

    expect(preventDefault).toHaveBeenCalled();
    expect(onSubmit).not.toHaveBeenCalled();
    expect(onClose).not.toHaveBeenCalled();
    // Index 4 corresponds to error state in ToolModal
    expect(states[4]).toBe("Invalid phone number. Must be in E.164 format (e.g. +15551234567).");
  });
});
