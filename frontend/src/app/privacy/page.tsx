import * as React from "react";
import Link from "next/link";

export default function PrivacyPage() {
  return (
    <div className="max-w-3xl mx-auto px-6 py-20 space-y-6">
      <Link href="/" className="text-xs text-[var(--muted)] hover:text-[var(--fg)]">
        ← Back to home
      </Link>
      <h1 className="text-3xl font-bold font-heading">Privacy Policy</h1>
      <p className="text-sm text-[var(--muted)] leading-relaxed">
        Cadence takes privacy seriously. Call audio recordings, transcripts, and telemetry
        are strictly isolated by organization ID and never shared across tenants.
      </p>
    </div>
  );
}
