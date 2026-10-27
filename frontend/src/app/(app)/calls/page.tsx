"use client";

import * as React from "react";
import Link from "next/link";
import { PhoneCall, Globe, ArrowRight, Loader2, Phone } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useSessions } from "@/lib/hooks";

export default function CallsPage() {
  const { data: sessions = [], isLoading } = useSessions(50);

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "active":
        return "bg-emerald-500/10 text-emerald-500 border-emerald-500/20";
      case "completed":
        return "bg-[var(--accent)]/10 text-[var(--accent)] border-[var(--accent)]/20";
      case "failed":
        return "bg-red-500/10 text-red-500 border-red-500/20";
      default:
        return "bg-[var(--line)] text-[var(--muted)] border-transparent";
    }
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-[var(--fg)] font-heading">
            Call History
          </h1>
          <p className="text-sm text-[var(--muted)] mt-1">
            Review past agent conversations, inspect turn-by-turn transcripts, and playback audio.
          </p>
        </div>
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center p-12 text-[var(--muted)]">
          <Loader2 className="w-6 h-6 animate-spin mr-2" />
          <span>Loading calls...</span>
        </div>
      ) : sessions.length === 0 ? (
        <div className="p-12 text-center border border-[var(--line)] rounded-xl bg-[var(--card)] space-y-3">
          <Phone className="w-10 h-10 text-[var(--muted)] mx-auto opacity-50" />
          <h3 className="text-base font-semibold text-[var(--fg)]">No calls recorded yet</h3>
          <p className="text-xs text-[var(--muted)] max-w-sm mx-auto">
            Once agents receive inbound telephone calls or web browser test sessions, they will be listed here.
          </p>
        </div>
      ) : (
        <div className="border border-[var(--line)] rounded-xl overflow-hidden bg-[var(--card)]">
          <table className="w-full text-left text-sm">
            <thead className="bg-[var(--line)]/30 text-[11px] uppercase tracking-wider text-[var(--muted)] font-mono">
              <tr>
                <th className="px-6 py-3">Channel</th>
                <th className="px-6 py-3">Session ID</th>
                <th className="px-6 py-3">Status</th>
                <th className="px-6 py-3">Duration</th>
                <th className="px-6 py-3">Created</th>
                <th className="px-6 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--line)]">
              {sessions.map((session) => (
                <tr key={session.id} className="hover:bg-[var(--line)]/10 transition-colors">
                  <td className="px-6 py-4 font-medium text-[var(--fg)] flex items-center gap-2">
                    {session.channel === "phone" ? (
                      <PhoneCall className="w-4 h-4 text-[var(--accent)]" />
                    ) : (
                      <Globe className="w-4 h-4 text-[var(--muted)]" />
                    )}
                    <span className="capitalize">{session.channel}</span>
                  </td>
                  <td className="px-6 py-4 text-xs font-mono text-[var(--muted)]">
                    {session.id.slice(0, 12)}...
                  </td>
                  <td className="px-6 py-4">
                    <span
                      className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border capitalize ${getStatusBadge(
                        session.status
                      )}`}
                    >
                      {session.status}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-xs font-mono text-[var(--muted)]">
                    {session.duration_s}s
                  </td>
                  <td className="px-6 py-4 text-xs text-[var(--muted)]">
                    {new Date(session.created_at).toLocaleString()}
                  </td>
                  <td className="px-6 py-4 text-right">
                    <Link href={`/calls/${session.id}`}>
                      <Button variant="secondary" size="sm" className="inline-flex items-center gap-1.5 text-xs">
                        <span>Inspect</span>
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
