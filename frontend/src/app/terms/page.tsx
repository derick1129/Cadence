import * as React from "react";
import Link from "next/link";

export default function TermsPage() {
  return (
    <div className="max-w-3xl mx-auto px-6 py-20 space-y-6">
      <Link href="/" className="text-xs text-[var(--muted)] hover:text-[var(--fg)]">
        ← Back to home
      </Link>
      <h1 className="text-3xl font-bold font-heading">Terms of Service</h1>
      <p className="text-sm text-[var(--muted)] leading-relaxed">
        By accessing Cadence, you agree to comply with telecommunication regulations,
        consent requirements, and our multi-tenant fair use guidelines.
      </p>
    </div>
  );
}
