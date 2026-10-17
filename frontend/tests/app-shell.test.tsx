import { describe, it, expect } from "vitest";
import React from "react";
import { renderToString } from "react-dom/server";
import { Button } from "../src/components/ui/button";
import { Sidebar, navItems } from "../src/components/ui/sidebar";
import AppLayout from "../src/app/(app)/layout";
import DashboardOverviewPage from "../src/app/(app)/dashboard/page";

describe("Button component", () => {
  it("renders with default primary variant", () => {
    const html = renderToString(<Button>Click me</Button>);
    expect(html).toContain("Click me");
    expect(html).toContain("bg-[#0A0A0A]");
  });

  it("renders secondary variant", () => {
    const html = renderToString(<Button variant="secondary">Cancel</Button>);
    expect(html).toContain("Cancel");
    expect(html).toContain("border-[var(--line)]");
  });

  it("renders ghost variant", () => {
    const html = renderToString(<Button variant="ghost">Ghost</Button>);
    expect(html).toContain("Ghost");
    expect(html).toContain("hover:bg-[var(--line)]");
  });

  it("renders icon variant", () => {
    const html = renderToString(<Button variant="icon" aria-label="Icon button" />);
    expect(html).toContain("aria-label=\"Icon button\"");
  });
});

describe("Sidebar component", () => {
  it("renders Cadence brand logo and pulsing dot", () => {
    const html = renderToString(<Sidebar />);
    expect(html).toContain("Cadence");
    expect(html).toContain("animate-pulse");
    expect(html).toContain("bg-[var(--accent)]");
  });

  it("renders all 6 navigation links", () => {
    const html = renderToString(<Sidebar />);
    for (const item of navItems) {
      expect(html).toContain(item.label);
      expect(html).toContain(`href="${item.href}"`);
    }
  });

  it("renders plan usage widget with progress bar", () => {
    const html = renderToString(<Sidebar minutesUsed={0} minutesLimit={300} />);
    expect(html).toContain("Plan Usage");
    expect(html).toContain("0 / 300 minutes used");
    expect(html).toContain('role="progressbar"');
    expect(html).toContain('aria-valuenow="0"');
    expect(html).toContain('aria-valuemax="300"');
  });
});

describe("AppLayout component", () => {
  it("mounts sidebar and content", () => {
    const html = renderToString(
      <AppLayout>
        <div data-testid="main-content">Test Page Content</div>
      </AppLayout>
    );
    expect(html).toContain("Cadence");
    expect(html).toContain("Test Page Content");
    expect(html).toContain("System Operational");
  });
});

describe("DashboardOverviewPage component", () => {
  it("renders the 4 stat tiles", () => {
    const html = renderToString(<DashboardOverviewPage />);
    expect(html).toContain("Calls today");
    expect(html).toContain("Median response");
    expect(html).toContain("Tool calls");
    expect(html).toContain("Concurrency");
    expect(html).toContain("0 / 5");
  });
});
