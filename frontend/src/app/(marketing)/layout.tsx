"use client";

import * as React from "react";
import Link from "next/link";
import { ThemeToggle } from "@/components/marketing/theme-toggle";

export interface MarketingLayoutProps {
  children: React.ReactNode;
}

export default function MarketingLayout({ children }: MarketingLayoutProps) {
  const handleAnchorClick = (id: string) => (e: React.MouseEvent) => {
    const el = document.getElementById(id);
    if (el) {
      e.preventDefault();
      el.scrollIntoView({ behavior: "smooth" });
      if (typeof window !== "undefined") {
        window.history.pushState(null, "", `#${id}`);
      }
    }
  };

  return (
    <>
      {/* Header matching reference_for_landing_page.html */}
      <header className="nav">
        <div className="wrap">
          <Link
            className="logo"
            href="#top"
            onClick={handleAnchorClick("top")}
          >
            <i />
            Cadence
          </Link>
          <nav className="links" aria-label="Primary">
            <a href="#features" onClick={handleAnchorClick("features")}>
              Features
            </a>
            <a href="#how" onClick={handleAnchorClick("how")}>
              How it works
            </a>
            <a href="#start" onClick={handleAnchorClick("start")}>
              Get started
            </a>
          </nav>
          <div className="sp" />
          <ThemeToggle />
          <Link className="btn ghost hidden sm:inline-flex" href="/login">
            Login
          </Link>
          <Link className="btn pri" href="/register">
            Start free
          </Link>
        </div>
      </header>

      {/* Main Content */}
      <main id="top">{children}</main>

      {/* Footer matching reference_for_landing_page.html */}
      <footer>
        <div className="wrap">
          <span>© Cadence. Demo page.</span>
          <span>
            <Link href="/privacy">Privacy</Link> ·{" "}
            <Link href="/terms">Terms</Link> ·{" "}
            <Link href="mailto:support@cadence.dev">Contact</Link>
          </span>
        </div>
      </footer>
    </>
  );
}
