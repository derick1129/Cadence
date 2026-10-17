import * as React from "react";
import Link from "next/link";
import { ThemeToggle } from "@/components/marketing/theme-toggle";

export interface MarketingLayoutProps {
  children: React.ReactNode;
}

export default function MarketingLayout({ children }: MarketingLayoutProps) {
  return (
    <div className="min-h-screen flex flex-col bg-[var(--bg)] text-[var(--fg)]">
      {/* Public Header */}
      <header className="sticky top-0 z-50 w-full border-b border-[var(--line)] bg-[var(--bg)]/80 backdrop-blur-md">
        <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-8">
            <Link
              href="/"
              className="flex items-center gap-2.5 font-heading text-xl font-bold tracking-tight text-[var(--fg)] hover:opacity-90 transition-opacity"
            >
              <span
                className="w-2.5 h-2.5 rounded-full bg-[var(--accent)] motion-safe:animate-pulse"
                aria-hidden="true"
              />
              <span>Cadence</span>
            </Link>

            <nav
              className="hidden md:flex items-center gap-6 text-sm text-[var(--muted)]"
              aria-label="Public Navigation"
            >
              <Link
                href="#features"
                className="hover:text-[var(--fg)] transition-colors"
              >
                Features
              </Link>
              <Link
                href="#how"
                className="hover:text-[var(--fg)] transition-colors"
              >
                How it works
              </Link>
              <Link
                href="#start"
                className="hover:text-[var(--fg)] transition-colors"
              >
                Get started
              </Link>
            </nav>
          </div>

          <div className="flex items-center gap-3">
            <ThemeToggle />
            <Link
              href="/login"
              className="px-3.5 py-1.5 text-sm font-medium text-[var(--muted)] hover:text-[var(--fg)] transition-colors"
            >
              Login
            </Link>
            <Link
              href="/register"
              className="inline-flex items-center justify-center h-9 px-4 rounded-lg bg-[#0A0A0A] text-white hover:bg-[#262626] dark:bg-[#EDEDED] dark:text-[#0A0A0A] dark:hover:bg-white text-sm font-semibold transition-colors shadow-sm"
            >
              Start free
            </Link>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1">{children}</main>

      {/* Public Footer */}
      <footer className="border-t border-[var(--line)] py-12 bg-[var(--bg)] text-sm text-[var(--muted)]">
        <div className="max-w-6xl mx-auto px-6 flex flex-col md:flex-row items-center justify-between gap-6">
          <div className="flex items-center gap-2">
            <span className="font-semibold text-[var(--fg)]">© Cadence</span>
            <span>·</span>
            <span>Voice agents that answer your calls.</span>
          </div>

          <nav className="flex items-center gap-6 text-xs text-[var(--muted)]" aria-label="Footer Legal Links">
            <Link href="/privacy" className="hover:text-[var(--fg)] transition-colors">
              Privacy
            </Link>
            <Link href="/terms" className="hover:text-[var(--fg)] transition-colors">
              Terms
            </Link>
            <Link href="/docs" className="hover:text-[var(--fg)] transition-colors">
              Documentation
            </Link>
            <Link href="mailto:support@cadence.dev" className="hover:text-[var(--fg)] transition-colors">
              Contact
            </Link>
          </nav>
        </div>
      </footer>
    </div>
  );
}
