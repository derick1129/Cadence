import useSWR from "swr";
import { apiClient } from "@/lib/api";

export interface AgentDTO {
  id: string;
  organization_id: string;
  name: string;
  current_version_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface AgentVersionDTO {
  id: string;
  agent_id: string;
  version_no: number;
  system_prompt: string;
  greeting?: string | null;
  stt_config: Record<string, unknown>;
  llm_config: Record<string, unknown>;
  tts_config: Record<string, unknown>;
  silence_timeout_s: number;
  max_duration_s: number;
  created_at: string;
}

export interface SessionDTO {
  id: string;
  organization_id: string;
  agent_id: string;
  agent_version_id: string;
  channel: "web" | "phone";
  status: "initiated" | "active" | "completed" | "failed";
  outcome?: "completed" | "transferred" | "failed" | "abandoned" | null;
  outcome_label?: string | null;
  room_name: string;
  duration_s: number;
  recording_key?: string | null;
  created_at: string;
}

export interface TranscriptSegmentDTO {
  id: string;
  session_id: string;
  seq: number;
  speaker: "caller" | "agent";
  text: string;
  started_at_ms: number;
  created_at: string;
}

export interface ToolDTO {
  id: string;
  organization_id: string;
  name: string;
  type: "http" | "transfer";
  config: Record<string, unknown>;
  json_schema: Record<string, unknown>;
  outcome_label?: string | null;
  created_at: string;
}

export function useAgents() {
  return useSWR<AgentDTO[]>("/v1/agents", (url: string) =>
    apiClient<{ items?: AgentDTO[] } | AgentDTO[]>(url).then((res) =>
      Array.isArray(res) ? res : res?.items || []
    )
  );
}

export function useAgent(id?: string) {
  return useSWR<AgentDTO>(id ? `/v1/agents/${id}` : null, (url: string) => apiClient<AgentDTO>(url));
}

export function useAgentVersions(agentId?: string) {
  return useSWR<AgentVersionDTO[]>(
    agentId ? `/v1/agents/${agentId}/versions` : null,
    (url: string) => apiClient<AgentVersionDTO[]>(url)
  );
}

export function useSessions(limit: number = 50) {
  return useSWR<SessionDTO[]>(`/v1/sessions?limit=${limit}`, async (url: string) => {
    const res = await apiClient<{ items?: SessionDTO[] } | SessionDTO[]>(url);
    if (Array.isArray(res)) {
      return res;
    }
    return res.items || [];
  });
}

export function useSession(id?: string) {
  return useSWR<SessionDTO>(id ? `/v1/sessions/${id}` : null, (url: string) => apiClient<SessionDTO>(url));
}

export function useTranscript(sessionId?: string) {
  return useSWR<TranscriptSegmentDTO[]>(
    sessionId ? `/v1/sessions/${sessionId}/transcript` : null,
    (url: string) => apiClient<TranscriptSegmentDTO[]>(url)
  );
}

export function useRecordingUrl(sessionId?: string) {
  return useSWR<{ recording_url: string; expires_in_seconds: number }>(
    sessionId ? `/v1/sessions/${sessionId}/recording-url` : null,
    (url: string) => apiClient<{ recording_url: string; expires_in_seconds: number }>(url)
  );
}

export function useTools() {
  return useSWR<ToolDTO[]>("/v1/tools", (url: string) =>
    apiClient<{ items?: ToolDTO[] } | ToolDTO[]>(url).then((res) =>
      Array.isArray(res) ? res : res?.items || []
    )
  );
}
