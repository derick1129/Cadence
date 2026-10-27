import { describe, it, expect, vi } from "vitest";
import React from "react";
import { renderToString } from "react-dom/server";
import DashboardOverviewPage from "@/app/(app)/dashboard/page";

vi.mock("@/lib/hooks", () => ({
  useAgents: () => ({
    data: [{ id: "agt-1", name: "Inbound Support Agent", updated_at: "2026-10-24T10:00:00Z" }],
    isLoading: false,
  }),
  useSessions: () => ({
    data: [
      { id: "sess-1", channel: "web", status: "completed", duration_s: 45, created_at: "2026-10-24T11:00:00Z" },
      { id: "sess-2", channel: "phone", status: "active", duration_s: 12, created_at: "2026-10-24T11:05:00Z" },
    ],
    isLoading: false,
  }),
  useTools: () => ({
    data: [{ id: "tool-1", name: "check_order_status" }],
    isLoading: false,
  }),
}));

describe("DashboardOverviewPage", () => {
  it("renders live dynamic metrics and active agent list", () => {
    const html = renderToString(<DashboardOverviewPage />);

    expect(html).toContain("Dashboard Overview");
    expect(html).toContain("Inbound Support Agent");
    expect(html).toContain("check_order_status");
    expect(html).toContain("1 / 5"); // active concurrency
  });
});
