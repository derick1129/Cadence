"use client";

import * as React from "react";
import Link from "next/link";
import { ArrowLeft, Loader2, CheckCircle2 } from "lucide-react";
import { useAgent, useAgentVersions } from "@/lib/hooks";
import { apiClient } from "@/lib/api";
import { AgentEditor } from "@/components/agents/agent-editor";
import { TestCallPanel } from "@/components/voice/test-call-panel";

interface PageProps {
  params: Promise<{ id: string }>;
}

export default function AgentDetailPage({ params }: PageProps) {
  const { id } = React.use(params);
  const { data: agent, isLoading: agentLoading, mutate: mutateAgent } = useAgent(id);
  const { data: versions = [], mutate: mutateVersions } = useAgentVersions(id);

  const [saveSuccess, setSaveSuccess] = React.useState(false);
  const [showTestCall, setShowTestCall] = React.useState(false);

  const currentVersion = versions.length > 0 ? versions[versions.length - 1] : null;

  const handleSave = async (payload: {
    system_prompt: string;
    greeting: string;
    voice: string;
    model: string;
    silence_timeout_s: number;
  }) => {
    try {
      await apiClient(`/v1/agents/${id}/versions`, {
        method: "POST",
        body: JSON.stringify({
          system_prompt: payload.system_prompt,
          greeting: payload.greeting,
          llm_config: { provider: "openai", model: payload.model },
          tts_config: {
            provider: payload.voice.includes("eleven") ? "elevenlabs" : "cartesia",
            voice: payload.voice,
          },
          stt_config: { provider: "deepgram", model: "nova-2" },
          silence_timeout_s: payload.silence_timeout_s,
          max_duration_s: 1800,
        }),
      });
      await Promise.all([mutateAgent(), mutateVersions()]);
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 3000);
    } catch (err) {
      console.error("Failed to save agent version:", err);
    }
  };

  const handleStartCall = async (agentId: string) => {
    const res = await apiClient<{
      session_id: string;
      livekit_token: string;
      livekit_url: string;
      room_name: string;
    }>("/v1/sessions/web", {
      method: "POST",
      body: JSON.stringify({ agent_id: agentId }),
    });
    return {
      session_id: res.session_id,
      token: res.livekit_token,
      url: res.livekit_url,
    };
  };

  if (agentLoading) {
    return (
      <div className="flex items-center justify-center p-12 text-[var(--muted)]">
        <Loader2 className="w-6 h-6 animate-spin mr-2" />
        <span>Loading agent configuration...</span>
      </div>
    );
  }

  if (!agent) {
    return (
      <div className="p-8 text-center space-y-4">
        <p className="text-sm text-[var(--muted)]">Agent not found.</p>
        <Link href="/agents" className="text-xs text-[var(--accent)] hover:underline">
          Return to Agents list
        </Link>
      </div>
    );
  }

  const editorAgent = {
    id: agent.id,
    name: agent.name,
    systemPrompt:
      currentVersion?.system_prompt ||
      "You are a helpful and polite customer support voice assistant.",
    greeting: currentVersion?.greeting || "Hello! How can I help you today?",
    voice: (currentVersion?.tts_config?.voice as string) || "sonic-english",
    model: (currentVersion?.llm_config?.model as string) || "gpt-4o-mini",
    silenceTimeout: currentVersion?.silence_timeout_s || 15,
    tools: [],
  };

  return (
    <div className="space-y-6 max-w-4xl mx-auto pb-12">
      <div className="flex items-center justify-between">
        <Link
          href="/agents"
          className="inline-flex items-center gap-1.5 text-xs text-[var(--muted)] hover:text-[var(--fg)]"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          <span>Back to Agents</span>
        </Link>
        {saveSuccess && (
          <div className="flex items-center gap-1.5 text-xs text-[var(--accent)] font-medium">
            <CheckCircle2 className="w-4 h-4" />
            <span>New version saved successfully</span>
          </div>
        )}
      </div>

      <AgentEditor
        agent={editorAgent}
        onSave={handleSave}
        onTestCall={() => setShowTestCall(true)}
      />

      {showTestCall && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
          <TestCallPanel
            agentId={agent.id}
            onStartCall={handleStartCall}
            onClose={() => setShowTestCall(false)}
          />
        </div>
      )}
    </div>
  );
}
