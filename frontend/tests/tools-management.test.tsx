import { describe, it, expect, vi } from "vitest";
import React from "react";
import { renderToString } from "react-dom/server";
import { ToolModal } from "@/components/tools/tool-modal";

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
});
