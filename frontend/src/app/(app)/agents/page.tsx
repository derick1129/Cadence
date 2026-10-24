"use client";

import * as React from "react";
import Link from "next/link";
import { Plus, Bot, ArrowRight, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useAgents } from "@/lib/hooks";
import { apiClient } from "@/lib/api";

export default function AgentsPage() {
  const { data: agents = [], isLoading, mutate } = useAgents();
  const [isCreating, setIsCreating] = React.useState(false);
  const [newAgentName, setNewAgentName] = React.useState("");
  const [isSubmitting, setIsSubmitting] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  const handleCreateAgent = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newAgentName.trim()) return;
    setIsSubmitting(true);
    setError(null);
    try {
      await apiClient("/v1/agents", {
        method: "POST",
        body: JSON.stringify({
          name: newAgentName.trim(),
          system_prompt: "You are a helpful customer support voice assistant.",
        }),
      });
      setNewAgentName("");
      setIsCreating(false);
      await mutate();
    } catch (err) {
      console.error("Failed to create agent:", err);
      setError(err instanceof Error ? err.message : "Failed to create agent");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-[var(--fg)] font-heading">
            Voice Agents
          </h1>
          <p className="text-sm text-[var(--muted)] mt-1">
            Build, configure, and version manage your AI voice assistants.
          </p>
        </div>
        <Button
          variant="primary"
          onClick={() => setIsCreating(true)}
          className="flex items-center gap-2"
        >
          <Plus className="w-4 h-4" />
          <span>Create Agent</span>
        </Button>
      </div>

      {isCreating && (
        <form
          onSubmit={handleCreateAgent}
          className="p-4 bg-[var(--card)] border border-[var(--line)] rounded-xl space-y-3"
        >
          <h3 className="text-sm font-semibold text-[var(--fg)]">New Agent Name</h3>
          {error && (
            <p className="text-xs text-red-500 font-medium" role="alert">
              {error}
            </p>
          )}
          <div className="flex gap-3">
            <input
              type="text"
              value={newAgentName}
              onChange={(e) => setNewAgentName(e.target.value)}
              placeholder="e.g. Inbound Support Assistant"
              required
              className="flex-1 px-3 py-2 text-sm bg-[var(--bg)] border border-[var(--line)] rounded-lg text-[var(--fg)] focus:outline-none focus:border-[var(--accent)]"
            />
            <Button type="submit" variant="primary" disabled={isSubmitting}>
              {isSubmitting ? <Loader2 className="w-4 h-4 animate-spin" /> : "Create"}
            </Button>
            <Button
              type="button"
              variant="secondary"
              onClick={() => {
                setIsCreating(false);
                setError(null);
              }}
            >
              Cancel
            </Button>
          </div>
        </form>
      )}

      {isLoading ? (
        <div className="flex items-center justify-center p-12 text-[var(--muted)]">
          <Loader2 className="w-6 h-6 animate-spin mr-2" />
          <span>Loading agents...</span>
        </div>
      ) : agents.length === 0 ? (
        <div className="p-12 text-center border border-[var(--line)] rounded-xl bg-[var(--card)] space-y-3">
          <Bot className="w-10 h-10 text-[var(--muted)] mx-auto opacity-50" />
          <h3 className="text-base font-semibold text-[var(--fg)]">No voice agents found</h3>
          <p className="text-xs text-[var(--muted)] max-w-sm mx-auto">
            Get started by creating your first voice agent. You can configure system prompts, LLM models, and voices.
          </p>
          <Button
            variant="secondary"
            size="sm"
            onClick={() => setIsCreating(true)}
          >
            Create Your First Agent
          </Button>
        </div>
      ) : (
        <div className="border border-[var(--line)] rounded-xl overflow-hidden bg-[var(--card)]">
          <table className="w-full text-left text-sm">
            <thead className="bg-[var(--line)]/30 text-[11px] uppercase tracking-wider text-[var(--muted)] font-mono">
              <tr>
                <th className="px-6 py-3">Agent Name</th>
                <th className="px-6 py-3">Current Version</th>
                <th className="px-6 py-3">Updated</th>
                <th className="px-6 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--line)]">
              {agents.map((agent) => (
                <tr key={agent.id} className="hover:bg-[var(--line)]/10 transition-colors">
                  <td className="px-6 py-4 font-medium text-[var(--fg)] flex items-center gap-3">
                    <div className="w-8 h-8 rounded-lg bg-[var(--accent)]/10 text-[var(--accent)] flex items-center justify-center shrink-0">
                      <Bot className="w-4 h-4" />
                    </div>
                    <span>{agent.name}</span>
                  </td>
                  <td className="px-6 py-4 text-xs font-mono text-[var(--muted)]">
                    {agent.current_version_id ? agent.current_version_id.slice(0, 8) : "None"}
                  </td>
                  <td className="px-6 py-4 text-xs text-[var(--muted)]">
                    {new Date(agent.updated_at).toLocaleDateString()}
                  </td>
                  <td className="px-6 py-4 text-right">
                    <Link href={`/agents/${agent.id}`}>
                      <Button variant="secondary" size="sm" className="inline-flex items-center gap-1.5 text-xs">
                        <span>Configure</span>
                        <ArrowRight className="w-3.5 h-3.5" />
                      </Button>
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
