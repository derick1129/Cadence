"use client";

import * as React from "react";
import { Phone, Activity, Wrench, Radio, Plus, ArrowUpRight } from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { useAgents, useSessions, useTools } from "@/lib/hooks";

export default function DashboardOverviewPage() {
  const { data: agents = [] } = useAgents();
  const { data: sessions = [] } = useSessions(10);
  const { data: tools = [] } = useTools();

  const callsToday = sessions.length;
  const activeConcurrency = sessions.filter((s) => s.status === "active").length;

  return (
    <div className="space-y-8 max-w-7xl mx-auto">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-[var(--fg)] font-heading">
            Dashboard Overview
          </h1>
          <p className="text-sm text-[var(--muted)] mt-1">
            Real-time voice agent metrics and system performance.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Link href="/agents">
            <Button variant="primary" className="flex items-center gap-2">
              <Plus className="w-4 h-4" />
              <span>Create Agent</span>
            </Button>
          </Link>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <div className="p-6 rounded-xl border border-[var(--line)] bg-[var(--card)] shadow-sm space-y-2">
          <div className="flex items-center justify-between text-[var(--muted)]">
            <span className="text-sm font-medium">Calls today</span>
            <Phone className="w-4 h-4 text-[var(--muted)]" />
          </div>
          <div className="text-3xl font-bold tracking-tight text-[var(--fg)] font-heading">
            {callsToday}
          </div>
          <p className="text-xs text-[var(--muted)]">Total inbound &amp; web calls recorded</p>
        </div>

        <div className="p-6 rounded-xl border border-[var(--line)] bg-[var(--card)] shadow-sm space-y-2">
          <div className="flex items-center justify-between text-[var(--muted)]">
            <span className="text-sm font-medium">Median response</span>
            <Activity className="w-4 h-4 text-[var(--muted)]" />
          </div>
          <div className="text-3xl font-bold tracking-tight text-[var(--fg)] font-heading">
            320 ms
          </div>
          <p className="text-xs text-[var(--muted)]">Average voice turn latency</p>
        </div>

        <div className="p-6 rounded-xl border border-[var(--line)] bg-[var(--card)] shadow-sm space-y-2">
          <div className="flex items-center justify-between text-[var(--muted)]">
            <span className="text-sm font-medium">Tool calls</span>
            <Wrench className="w-4 h-4 text-[var(--muted)]" />
          </div>
          <div className="text-3xl font-bold tracking-tight text-[var(--fg)] font-heading">
            {tools.length}
          </div>
          <p className="text-xs text-[var(--muted)] truncate">
            {tools.length > 0
              ? tools.map((t) => t.name).join(", ")
              : "Executed webhooks & transfers"}
          </p>
        </div>

        <div className="p-6 rounded-xl border border-[var(--line)] bg-[var(--card)] shadow-sm space-y-2">
          <div className="flex items-center justify-between text-[var(--muted)]">
            <span className="text-sm font-medium">Concurrency</span>
            <Radio className="w-4 h-4 text-[var(--accent)]" />
          </div>
          <div className="text-3xl font-bold tracking-tight text-[var(--fg)] font-heading">
            {`${activeConcurrency} / 5`}
          </div>
          <p className="text-xs text-[var(--muted)]">Active simultaneous live calls</p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="p-6 rounded-xl border border-[var(--line)] bg-[var(--card)] shadow-sm">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-[var(--fg)] font-heading">Voice Agents</h2>
            <Link href="/agents" className="text-xs text-[var(--accent)] hover:underline flex items-center gap-1">
              <span>View all</span>
              <ArrowUpRight className="w-3.5 h-3.5" />
            </Link>
          </div>
          <div className="space-y-3">
            {agents.map((agent) => (
              <div key={agent.id} className="flex items-center justify-between p-3 border border-[var(--line)] rounded-lg">
                <span className="font-medium text-sm text-[var(--fg)]">{agent.name}</span>
                <Link href={`/agents/${agent.id}`}>
                  <Button variant="secondary" size="sm" className="text-xs px-2 py-1">
                    Configure
                  </Button>
                </Link>
              </div>
            ))}
            {agents.length === 0 && <p className="text-xs text-[var(--muted)]">No agents configured yet.</p>}
          </div>
        </div>

        <div className="p-6 rounded-xl border border-[var(--line)] bg-[var(--card)] shadow-sm">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-[var(--fg)] font-heading">Recent Calls</h2>
            <Link href="/calls" className="text-xs text-[var(--accent)] hover:underline flex items-center gap-1">
              <span>View all</span>
              <ArrowUpRight className="w-3.5 h-3.5" />
            </Link>
          </div>
          <div className="space-y-3">
            {sessions.map((sess) => (
              <div key={sess.id} className="flex items-center justify-between p-3 border border-[var(--line)] rounded-lg text-xs">
                <div>
                  <span className="font-semibold text-[var(--fg)] capitalize">{`${sess.channel} Call`}</span>
                  <p className="text-[var(--muted)]">{`${sess.duration_s}s • ${sess.status}`}</p>
                </div>
                <Link href={`/calls/${sess.id}`} className="text-[var(--accent)] hover:underline">
                  View
                </Link>
              </div>
            ))}
            {sessions.length === 0 && <p className="text-xs text-[var(--muted)]">No calls recorded yet.</p>}
          </div>
        </div>
      </div>
    </div>
  );
}
