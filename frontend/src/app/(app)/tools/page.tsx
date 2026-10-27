"use client";

import * as React from "react";
import { Plus, Wrench, Globe, PhoneForwarded, Trash2, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useTools } from "@/lib/hooks";
import { apiClient } from "@/lib/api";
import { ToolModal } from "@/components/tools/tool-modal";

export default function ToolsPage() {
  const { data: tools = [], isLoading, mutate } = useTools();
  const [isModalOpen, setIsModalOpen] = React.useState(false);
  const [deletingId, setDeletingId] = React.useState<string | null>(null);

  const handleCreateTool = async (payload: {
    name: string;
    type: "http" | "transfer";
    config: Record<string, unknown>;
    json_schema: Record<string, unknown>;
    outcome_label?: string;
  }) => {
    try {
      await apiClient("/v1/tools", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      await mutate();
    } catch (err) {
      console.error("Failed to create tool:", err);
    }
  };

  const handleDeleteTool = async (toolId: string) => {
    setDeletingId(toolId);
    try {
      await apiClient(`/v1/tools/${toolId}`, {
        method: "DELETE",
      });
      await mutate();
    } catch (err) {
      console.error("Failed to delete tool:", err);
    } finally {
      setDeletingId(null);
    }
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-[var(--fg)] font-heading">
            Tools & Webhooks
          </h1>
          <p className="text-sm text-[var(--muted)] mt-1">
            Configure external API webhooks and live SIP call transfer capabilities.
          </p>
        </div>
        <Button
          variant="primary"
          onClick={() => setIsModalOpen(true)}
          className="flex items-center gap-2"
        >
          <Plus className="w-4 h-4" />
          <span>New Tool</span>
        </Button>
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center p-12 text-[var(--muted)]">
          <Loader2 className="w-6 h-6 animate-spin mr-2" />
          <span>Loading tools...</span>
        </div>
      ) : tools.length === 0 ? (
        <div className="p-12 text-center border border-[var(--line)] rounded-xl bg-[var(--card)] space-y-3">
          <Wrench className="w-10 h-10 text-[var(--muted)] mx-auto opacity-50" />
          <h3 className="text-base font-semibold text-[var(--fg)]">No tools configured yet</h3>
          <p className="text-xs text-[var(--muted)] max-w-sm mx-auto">
            Create an HTTP webhook or SIP call transfer tool so your voice agents can execute real-time actions during conversations.
          </p>
          <Button
            variant="secondary"
            size="sm"
            onClick={() => setIsModalOpen(true)}
          >
            Create Your First Tool
          </Button>
        </div>
      ) : (
        <div className="border border-[var(--line)] rounded-xl overflow-hidden bg-[var(--card)]">
          <table className="w-full text-left text-sm">
            <thead className="bg-[var(--line)]/30 text-[11px] uppercase tracking-wider text-[var(--muted)] font-mono">
              <tr>
                <th className="px-6 py-3">Tool Name</th>
                <th className="px-6 py-3">Type</th>
                <th className="px-6 py-3">Target Endpoint / Number</th>
                <th className="px-6 py-3">Created</th>
                <th className="px-6 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--line)]">
              {tools.map((tool) => (
                <tr key={tool.id} className="hover:bg-[var(--line)]/10 transition-colors">
                  <td className="px-6 py-4 font-medium text-[var(--fg)] flex items-center gap-3">
                    <div className="w-8 h-8 rounded-lg bg-[var(--accent)]/10 text-[var(--accent)] flex items-center justify-center shrink-0">
                      {tool.type === "http" ? (
                        <Globe className="w-4 h-4" />
                      ) : (
                        <PhoneForwarded className="w-4 h-4" />
                      )}
                    </div>
                    <span className="font-mono text-xs">{tool.name}</span>
                  </td>
                  <td className="px-6 py-4">
                    <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border border-[var(--line)] bg-[var(--line)]/50 text-[var(--fg)] capitalize">
                      {tool.type === "http" ? "HTTP Webhook" : "SIP Transfer"}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-xs font-mono text-[var(--muted)] truncate max-w-xs">
                    {(tool.config?.url as string) || (tool.config?.phone_number as string) || "—"}
                  </td>
                  <td className="px-6 py-4 text-xs text-[var(--muted)]">
                    {new Date(tool.created_at).toLocaleDateString()}
                  </td>
                  <td className="px-6 py-4 text-right">
                    <button
                      onClick={() => handleDeleteTool(tool.id)}
                      disabled={deletingId === tool.id}
                      aria-label={`Delete tool ${tool.name}`}
                      className="p-1.5 text-[var(--muted)] hover:text-red-500 rounded-md transition-colors disabled:opacity-50"
                    >
                      {deletingId === tool.id ? (
                        <Loader2 className="w-4 h-4 animate-spin" />
                      ) : (
                        <Trash2 className="w-4 h-4" />
                      )}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <ToolModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onSubmit={handleCreateTool}
      />
    </div>
  );
}
