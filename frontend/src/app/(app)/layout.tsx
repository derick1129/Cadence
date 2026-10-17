import * as React from "react";
import { Sidebar } from "@/components/ui/sidebar";

export interface AppLayoutProps {
  children: React.ReactNode;
}

export default function AppLayout({ children }: AppLayoutProps) {
  return (
    <div className="flex h-screen w-full overflow-hidden bg-[var(--bg)] text-[var(--fg)]">
      <Sidebar />
      <div className="flex flex-1 flex-col min-w-0 overflow-hidden">
        <header className="h-14 border-b border-[var(--line)] bg-[var(--card)] px-6 flex items-center justify-between shrink-0">
          <div className="flex items-center gap-3">
            <span className="text-sm font-semibold text-[var(--fg)]">
              Workspace
            </span>
            <span className="text-xs text-[var(--muted)]">/</span>
            <span className="text-xs text-[var(--muted)] font-mono">
              Production
            </span>
          </div>
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2 text-xs text-[var(--muted)]">
              <span className="w-2 h-2 rounded-full bg-[var(--accent)]" />
              <span>System Operational</span>
            </div>
          </div>
        </header>
        <main className="flex-1 overflow-y-auto p-8 bg-[var(--bg)]">
          {children}
        </main>
      </div>
    </div>
  );
}
