"use client";

import * as React from "react";
import { X } from "lucide-react";
import { Button } from "@/components/ui/button";

export interface ToolModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (payload: {
    name: string;
    type: "http" | "transfer";
    config: Record<string, unknown>;
    json_schema: Record<string, unknown>;
    outcome_label?: string;
  }) => void;
}

export const ToolModal: React.FC<ToolModalProps> = ({ isOpen, onClose, onSubmit }) => {
  const [name, setName] = React.useState("");
  const [type, setType] = React.useState<"http" | "transfer">("http");
  const [url, setUrl] = React.useState("");
  const [transferNumber, setTransferNumber] = React.useState("");

  if (!isOpen) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSubmit({
      name,
      type,
      config: type === "http" ? { url, method: "POST" } : { phone_number: transferNumber },
      json_schema: { type: "object", properties: {}, required: [] },
    });
    setName("");
    setUrl("");
    setTransferNumber("");
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
      <div className="bg-[var(--card)] border border-[var(--line)] rounded-xl max-w-lg w-full p-6 shadow-2xl space-y-4">
        <div className="flex items-center justify-between pb-3 border-b border-[var(--line)]">
          <h2 className="text-lg font-bold text-[var(--fg)]">Configure New Tool</h2>
          <button
            onClick={onClose}
            className="text-[var(--muted)] hover:text-[var(--fg)]"
            aria-label="Close modal"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-[var(--muted)] mb-1 uppercase">Name</label>
            <input
              type="text"
              required
              placeholder="e.g. check_shipping"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full px-3 py-2 text-sm bg-[var(--bg)] border border-[var(--line)] rounded-lg text-[var(--fg)] focus:outline-none focus:border-[var(--accent)]"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-[var(--muted)] mb-1 uppercase">Type</label>
            <select
              value={type}
              onChange={(e) => setType(e.target.value as "http" | "transfer")}
              className="w-full px-3 py-2 text-sm bg-[var(--bg)] border border-[var(--line)] rounded-lg text-[var(--fg)]"
            >
              <option value="http">HTTP Webhook</option>
              <option value="transfer">SIP Transfer</option>
            </select>
          </div>

          {type === "http" ? (
            <div>
              <label className="block text-xs font-semibold text-[var(--muted)] mb-1 uppercase">Endpoint URL</label>
              <input
                type="url"
                required
                placeholder="https://api.example.com/webhook"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                className="w-full px-3 py-2 text-sm bg-[var(--bg)] border border-[var(--line)] rounded-lg text-[var(--fg)] focus:outline-none focus:border-[var(--accent)]"
              />
            </div>
          ) : (
            <div>
              <label className="block text-xs font-semibold text-[var(--muted)] mb-1 uppercase">Transfer E.164 Number</label>
              <input
                type="text"
                required
                placeholder="+15551234567"
                value={transferNumber}
                onChange={(e) => setTransferNumber(e.target.value)}
                className="w-full px-3 py-2 text-sm bg-[var(--bg)] border border-[var(--line)] rounded-lg text-[var(--fg)] focus:outline-none focus:border-[var(--accent)]"
              />
            </div>
          )}

          <div className="flex items-center justify-end gap-3 pt-3 border-t border-[var(--line)]">
            <Button type="button" variant="secondary" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" variant="primary">
              Create Tool
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
};
