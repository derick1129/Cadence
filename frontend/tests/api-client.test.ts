import { describe, it, expect, vi, beforeEach } from "vitest";
import { apiClient, ApiError } from "@/lib/api";

describe("apiClient", () => {
  let store: Record<string, string> = {};

  beforeEach(() => {
    vi.restoreAllMocks();
    store = {};
    const mockStorage = {
      getItem: vi.fn((key: string) => store[key] ?? null),
      setItem: vi.fn((key: string, value: string) => {
        store[key] = String(value);
      }),
      removeItem: vi.fn((key: string) => {
        delete store[key];
      }),
      clear: vi.fn(() => {
        store = {};
      }),
      length: 0,
      key: vi.fn((_index: number) => null),
    };
    Object.defineProperty(global, "localStorage", {
      value: mockStorage,
      writable: true,
      configurable: true,
    });
    if (typeof window !== "undefined") {
      Object.defineProperty(window, "localStorage", {
        value: mockStorage,
        writable: true,
        configurable: true,
      });
    }
  });

  it("injects Authorization header when token exists in storage", async () => {
    global.localStorage.setItem("cadence_token", "test-token-123");

    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ id: "agent-1", name: "Support Bot" }),
    });
    global.fetch = fetchMock;

    const result = await apiClient<{ id: string; name: string }>("/v1/agents/agent-1");
    expect(result.name).toBe("Support Bot");
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/v1/agents/agent-1"),
      expect.objectContaining({
        headers: expect.any(Headers),
      })
    );
    const headers = fetchMock.mock.calls[0][1]?.headers as Headers;
    expect(headers.get("Authorization")).toBe("Bearer test-token-123");
  });

  it("throws normalized ApiError on 4xx/5xx responses", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 404,
      json: async () => ({
        error: { code: "AGENT_NOT_FOUND", message: "Agent does not exist" },
      }),
    });

    await expect(apiClient("/v1/agents/missing")).rejects.toThrow(ApiError);
  });

  it("handles 204 No Content response gracefully", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 204,
    });

    const result = await apiClient("/v1/agents/agent-1", { method: "DELETE" });
    expect(result).toEqual({});
  });
});
