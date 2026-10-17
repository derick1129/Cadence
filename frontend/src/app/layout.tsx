import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Cadence - Voice Agent Platform",
  description: "Multi-tenant AI voice agent platform",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-[var(--bg)] text-[var(--fg)] antialiased">
        {children}
      </body>
    </html>
  );
}
