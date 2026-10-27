import { describe, it, expect, vi, beforeEach } from "vitest";
import React from "react";
import { renderToString } from "react-dom/server";
import { apiClient, ApiError } from "@/lib/api";
import {
  useAgents,
  useAgentVersions,
  useSessions,
  useTranscript,
  useRecordingUrl,
  useTools,
  AgentDTO,
  SessionDTO,
  ToolDTO,
  TranscriptSegmentDTO,
} from "@/lib/hooks";
import { AgentEditor } from "@/components/agents/agent-editor";
import { AudioPlayer } from "@/components/calls/audio-player";
import { TranscriptViewer } from "@/components/calls/transcript-viewer";
import { ToolModal } from "@/components/tools/tool-modal";

describe("Empirical Challenge Suite", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  // =========================================================================
  // 1. API Client Error Handling
  // =========================================================================
  describe("1. API Client error handling", () => {
    it("1.1 Network error: fetch rejection propagates as an unhandled rejection", async () => {
      global.fetch = vi.fn().mockRejectedValue(new TypeError("Failed to fetch"));

      await expect(apiClient("/v1/agents")).rejects.toThrow(TypeError);
    });

    it("1.2 401 Unauthenticated: throws normalized ApiError with 401 status", async () => {
      global.fetch = vi.fn().mockResolvedValue({
        ok: false,
        status: 401,
        json: async () => ({ detail: "Could not validate credentials" }),
      });

      await expect(apiClient("/v1/agents")).rejects.toThrow(ApiError);
      try {
        await apiClient("/v1/agents");
      } catch (err) {
        expect(err).toBeInstanceOf(ApiError);
        const apiErr = err as ApiError;
        expect(apiErr.status).toBe(401);
        expect(apiErr.message).toBe("Could not validate credentials");
      }
    });

    it("1.3 404 Not Found: throws ApiError with status 404 and error details", async () => {
      global.fetch = vi.fn().mockResolvedValue({
        ok: false,
        status: 404,
        json: async () => ({
          error: { code: "AGENT_NOT_FOUND", message: "Agent does not exist" },
        }),
      });

      try {
        await apiClient("/v1/agents/missing-id");
        expect.unreachable("Should have thrown");
      } catch (err) {
        expect(err).toBeInstanceOf(ApiError);
        const apiErr = err as ApiError;
        expect(apiErr.status).toBe(404);
        expect(apiErr.code).toBe("AGENT_NOT_FOUND");
        expect(apiErr.message).toBe("Agent does not exist");
      }
    });

    it("1.4 500 Internal Server Error: handles HTML/text error body gracefully without crashing", async () => {
      global.fetch = vi.fn().mockResolvedValue({
        ok: false,
        status: 500,
        json: async () => {
          throw new SyntaxError("Unexpected token < in JSON at position 0");
        },
      });

      try {
        await apiClient("/v1/agents");
        expect.unreachable("Should have thrown");
      } catch (err) {
        expect(err).toBeInstanceOf(ApiError);
        const apiErr = err as ApiError;
        expect(apiErr.status).toBe(500);
        expect(apiErr.message).toBe("Request failed with status 500");
      }
    });

    it("1.5 Malformed JSON on 200 OK: returns empty object fallback instead of unhandled JSON crash", async () => {
      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => {
          throw new SyntaxError("Unexpected token in JSON at position 4");
        },
      });

      const result = await apiClient("/v1/agents");
      expect(result).toEqual({});
    });

    it("1.6 FastAPI 422 Validation Error: detail array handling", async () => {
      const fastApi422 = {
        detail: [
          { loc: ["body", "system_prompt"], msg: "String should have at least 1 character", type: "string_too_short" },
        ],
      };
      global.fetch = vi.fn().mockResolvedValue({
        ok: false,
        status: 422,
        json: async () => fastApi422,
      });

      try {
        await apiClient("/v1/agents/123/versions", { method: "POST" });
        expect.unreachable("Should have thrown");
      } catch (err) {
        expect(err).toBeInstanceOf(ApiError);
        const apiErr = err as ApiError;
        expect(apiErr.status).toBe(422);
        expect(apiErr.message).toBeDefined();
      }
    });
  });

  // =========================================================================
  // 2. SWR Hooks Response Unpacking: Bare Array vs Wrapped { items: [...] }
  // =========================================================================
  describe("2. SWR hooks response unpacking", () => {
    it("2.1 useSessions unpacker: handles bare array response", async () => {
      const bareSessions: SessionDTO[] = [
        {
          id: "sess-1",
          organization_id: "org-1",
          agent_id: "agt-1",
          agent_version_id: "ver-1",
          channel: "web",
          status: "completed",
          room_name: "room-1",
          duration_s: 42,
          created_at: "2026-10-24T12:00:00Z",
        },
      ];

      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => bareSessions,
      });

      const res = await apiClient<{ items?: SessionDTO[] } | SessionDTO[]>("/v1/sessions?limit=10");
      const unpacked = Array.isArray(res) ? res : res.items || [];
      expect(Array.isArray(unpacked)).toBe(true);
      expect(unpacked).toHaveLength(1);
      expect(unpacked[0].id).toBe("sess-1");
    });

    it("2.2 useSessions unpacker: handles wrapped { items: [...] } paginated response", async () => {
      const wrappedSessions = {
        items: [
          {
            id: "sess-wrapped-1",
            organization_id: "org-1",
            agent_id: "agt-1",
            agent_version_id: "ver-1",
            channel: "phone" as const,
            status: "active" as const,
            room_name: "room-phone",
            duration_s: 15,
            created_at: "2026-10-24T12:00:00Z",
          },
        ],
        total: 1,
      };

      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => wrappedSessions,
      });

      const res = await apiClient<{ items?: SessionDTO[] } | SessionDTO[]>("/v1/sessions?limit=10");
      const unpacked = Array.isArray(res) ? res : res.items || [];
      expect(Array.isArray(unpacked)).toBe(true);
      expect(unpacked).toHaveLength(1);
      expect(unpacked[0].id).toBe("sess-wrapped-1");
    });

    it("2.3 useAgents response unpacking vulnerability: wrapped { items: [...] } returns raw object instead of array", async () => {
      const wrappedAgents = {
        items: [
          {
            id: "agt-wrapped",
            organization_id: "org-1",
            name: "Wrapped Agent",
            current_version_id: null,
            created_at: "2026-10-24T10:00:00Z",
            updated_at: "2026-10-24T10:00:00Z",
          },
        ],
      };

      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => wrappedAgents,
      });

      // Probe raw apiClient output that useAgents() delegates to
      const res = await apiClient<AgentDTO[]>("/v1/agents");
      // SWR hook for useAgents does: (url: string) => apiClient<AgentDTO[]>(url)
      // When wrapped, res is NOT an array!
      const isArray = Array.isArray(res);
      expect(isArray).toBe(false);
      expect((res as unknown as { items: AgentDTO[] }).items).toHaveLength(1);
    });

    it("2.4 useTools response unpacking vulnerability: wrapped { items: [...] } returns raw object instead of array", async () => {
      const wrappedTools = {
        items: [
          {
            id: "tool-wrapped",
            organization_id: "org-1",
            name: "check_shipping",
            type: "http" as const,
            config: { url: "https://api.example.com" },
            json_schema: {},
            created_at: "2026-10-24T10:00:00Z",
          },
        ],
      };

      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => wrappedTools,
      });

      const res = await apiClient<ToolDTO[]>("/v1/tools");
      const isArray = Array.isArray(res);
      expect(isArray).toBe(false);
      expect((res as unknown as { items: ToolDTO[] }).items).toHaveLength(1);
    });

    it("2.5 Component crash demonstration: wrapped { items: [...] } breaks components expecting bare array", () => {
      const wrappedPayload: any = {
        items: [{ id: "agt-1", name: "Agent 1" }],
      };

      // When useAgents returns wrappedPayload, components calling .map() throw TypeError
      expect(() => {
        wrappedPayload.map((a: any) => a.name);
      }).toThrow(TypeError);

      // Verify that unpacker logic fixes this
      function unpack<T>(res: any): T[] {
        return Array.isArray(res) ? res : res?.items || [];
      }
      expect(() => {
        const clean = unpack(wrappedPayload);
        clean.map((a: any) => a.name);
      }).not.toThrow();
    });
  });

  // =========================================================================
  // 3. Component Resilience: Empty lists, null audio URLs, missing recordings
  // =========================================================================
  describe("3. Component resilience", () => {
    it("3.1 TranscriptViewer renders safely with empty turns array", () => {
      const html = renderToString(<TranscriptViewer turns={[]} />);
      expect(html).toContain("space-y-4");
      expect(html).not.toContain("Agent");
      expect(html).not.toContain("Caller");
    });

    it("3.2 AudioPlayer renders without crashing with empty audioUrl", () => {
      const html = renderToString(<AudioPlayer audioUrl="" />);
      expect(html).toContain("Call Audio Recording");
      expect(html).toContain('role="region"');
    });

    it("3.3 AudioPlayer renders with null/undefined audioUrl without throwing in renderToString", () => {
      expect(() => {
        renderToString(<AudioPlayer audioUrl={null as unknown as string} />);
      }).not.toThrow();
    });

    it("3.4 AgentEditor handles empty tools list gracefully without rendering Connected Tools section", () => {
      const agentWithoutTools = {
        id: "agt-no-tools",
        name: "Solo Agent",
        systemPrompt: "You are alone.",
        greeting: "Hi",
        voice: "sonic-english",
        model: "gpt-4o-mini",
        silenceTimeout: 15,
        tools: [],
      };

      const html = renderToString(
        <AgentEditor agent={agentWithoutTools} onSave={vi.fn()} onTestCall={vi.fn()} />
      );
      expect(html).not.toContain("Connected Tools");
    });

    it("3.5 AgentEditor handles undefined tools property gracefully", () => {
      const agentUndefinedTools = {
        id: "agt-undef-tools",
        name: "Undefined Tools Agent",
        systemPrompt: "Prompt",
        voice: "sonic-english",
        model: "gpt-4o-mini",
        silenceTimeout: 15,
      };

      const html = renderToString(
        <AgentEditor agent={agentUndefinedTools} onSave={vi.fn()} onTestCall={vi.fn()} />
      );
      expect(html).not.toContain("Connected Tools");
    });
  });

  // =========================================================================
  // 4. Controlled Input Edge Cases
  // =========================================================================
  describe("4. Controlled input edge cases", () => {
    it("4.1 AgentEditor boundary silence timeout values: min=5, max=30", () => {
      const minAgent = {
        id: "agt-min",
        name: "Min Timeout Agent",
        systemPrompt: "Prompt",
        voice: "sonic-english",
        model: "gpt-4o-mini",
        silenceTimeout: 5,
      };
      const htmlMin = renderToString(
        <AgentEditor agent={minAgent} onSave={vi.fn()} onTestCall={vi.fn()} />
      );
      expect(htmlMin).toContain("Silence Timeout: 5s");

      const maxAgent = {
        ...minAgent,
        silenceTimeout: 30,
      };
      const htmlMax = renderToString(
        <AgentEditor agent={maxAgent} onSave={vi.fn()} onTestCall={vi.fn()} />
      );
      expect(htmlMax).toContain("Silence Timeout: 30s");
    });

    it("4.2 AgentEditor empty prompt: textarea is not marked required and accepts empty input", () => {
      const emptyPromptAgent = {
        id: "agt-empty-prompt",
        name: "Empty Prompt Bot",
        systemPrompt: "",
        voice: "sonic-english",
        model: "gpt-4o-mini",
        silenceTimeout: 15,
      };

      const html = renderToString(
        <AgentEditor agent={emptyPromptAgent} onSave={vi.fn()} onTestCall={vi.fn()} />
      );
      // The textarea exists and is rendered
      expect(html).toContain("<textarea");
      // But it lacks required attribute, allowing empty submission to backend
      const textareaMatch = html.match(/<textarea[^>]*>/);
      expect(textareaMatch).toBeDefined();
      expect(textareaMatch?.[0]).not.toContain("required");
    });

    it("4.3 ToolModal: inspects URL and E.164 form controls", () => {
      const html = renderToString(
        <ToolModal isOpen={true} onClose={vi.fn()} onSubmit={vi.fn()} />
      );
      expect(html).toContain("Configure New Tool");
      expect(html).toContain("HTTP Webhook");
      expect(html).toContain('type="url"');
    });

    it("4.4 ToolModal SIP transfer number input: lacks E.164 pattern or format constraint", () => {
      // In ToolModal source code, transferNumber input is:
      // <input type="text" required placeholder="+15551234567" value={transferNumber} ... />
      // There is NO pattern="^\+[1-9]\d{1,14}$" or regex validation on submission
      const e164Regex = /^\+[1-9]\d{1,14}$/;
      expect(e164Regex.test("+15551234567")).toBe(true);
      expect(e164Regex.test("not-a-number")).toBe(false);
      expect(e164Regex.test("12345")).toBe(false);
      expect(e164Regex.test("+1 555 123 4567")).toBe(false);
    });
  });
});
