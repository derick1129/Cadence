import * as React from "react";
import { Phone, Activity, Wrench, Radio, Plus, ArrowUpRight } from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/button";

interface StatTile {
  id: string;
  title: string;
  value: string;
  description: string;
  icon: React.ComponentType<{ className?: string }>;
}

const stats: StatTile[] = [
  {
    id: "calls-today",
    title: "Calls today",
    value: "0",
    description: "Total inbound & outbound calls today",
    icon: Phone,
  },
  {
    id: "median-response",
    title: "Median response",
    value: "-- ms",
    description: "Per-turn voice pipeline latency",
    icon: Activity,
  },
  {
    id: "tool-calls",
    title: "Tool calls",
    value: "0",
    description: "Executed webhooks & transfers",
    icon: Wrench,
  },
  {
    id: "concurrency",
    title: "Concurrency",
    value: "0 / 5",
    description: "Active simultaneous live calls",
    icon: Radio,
  },
];

export default function DashboardOverviewPage() {
  return (
    <div className="space-y-8 max-w-7xl mx-auto">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-[var(--fg)]">
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
        {stats.map((stat) => {
          const Icon = stat.icon;
          return (
            <div
              key={stat.id}
              className="p-6 rounded-xl border border-[var(--line)] bg-[var(--card)] shadow-sm space-y-2"
            >
              <div className="flex items-center justify-between text-[var(--muted)]">
                <span className="text-sm font-medium">{stat.title}</span>
                <Icon className="w-4 h-4 text-[var(--muted)]" />
              </div>
              <div className="text-3xl font-bold tracking-tight text-[var(--fg)] font-heading">
                {stat.value}
              </div>
              <p className="text-xs text-[var(--muted)]">{stat.description}</p>
            </div>
          );
        })}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="p-6 rounded-xl border border-[var(--line)] bg-[var(--card)] shadow-sm">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-[var(--fg)]">
              Voice Agents
            </h2>
            <Link
              href="/agents"
              className="text-xs text-[var(--accent)] hover:underline flex items-center gap-1"
            >
              <span>View all</span>
              <ArrowUpRight className="w-3.5 h-3.5" />
            </Link>
          </div>
          <p className="text-sm text-[var(--muted)] mb-4">
            No agents configured yet. Create your first voice agent to start handling live phone calls.
          </p>
          <Link href="/agents">
            <Button variant="secondary" size="sm">
              Configure New Agent
            </Button>
          </Link>
        </div>

        <div className="p-6 rounded-xl border border-[var(--line)] bg-[var(--card)] shadow-sm">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-[var(--fg)]">
              Recent Calls
            </h2>
            <Link
              href="/calls"
              className="text-xs text-[var(--accent)] hover:underline flex items-center gap-1"
            >
              <span>View call log</span>
              <ArrowUpRight className="w-3.5 h-3.5" />
            </Link>
          </div>
          <p className="text-sm text-[var(--muted)] mb-4">
            No call activity recorded. Inbound and outbound call logs will appear here in real-time.
          </p>
          <Link href="/calls">
            <Button variant="ghost" size="sm">
              Explore Call Records
            </Button>
          </Link>
        </div>
      </div>
    </div>
  );
}
