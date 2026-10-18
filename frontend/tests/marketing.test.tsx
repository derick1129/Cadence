import { describe, it, expect } from "vitest";
import React from "react";
import { renderToString } from "react-dom/server";
import MarketingLayout from "../src/app/(marketing)/layout";
import MarketingPage from "../src/app/(marketing)/page";
import { Hero } from "../src/components/marketing/hero";

describe("MarketingLayout component", () => {
  it("renders the public header with Cadence logo, links, theme toggle, and auth buttons", () => {
    const html = renderToString(
      <MarketingLayout>
        <div data-testid="page-content">Marketing Content</div>
      </MarketingLayout>
    );

    // Public Header Logo
    expect(html).toContain("Cadence");
    // Navigation links
    expect(html).toContain("Features");
    expect(html).toContain("How it works");
    // Theme toggle
    expect(html).toContain('aria-label="Toggle light and dark theme"');
    // Auth and CTA buttons
    expect(html).toContain("Login");
    expect(html).toContain("Start free");
    // Content insertion
    expect(html).toContain("Marketing Content");
    // Public Footer
    expect(html).toContain("© Cadence");
    expect(html).toContain("Privacy");
    expect(html).toContain("Terms");
  });
});

describe("Hero component", () => {
  it("renders headline, background grid, cursor spotlight, waveform, and live call card", () => {
    const html = renderToString(<Hero />);

    // Headline from reference demo
    expect(html).toContain("Answer every call, and sound like your best person.");
    // Subtext
    expect(html).toContain("Cadence builds voice agents that listen");
    // Background grid & cursor spotlight elements
    expect(html).toContain('id="hero"');
    // Call-to-action buttons
    expect(html).toContain("Start free");
    expect(html).toContain("See how it works");
    // Preview card illustration
    expect(html).toContain("Live call");
    expect(html).toContain("Front desk assistant");
    expect(html).toContain('id="bars"');
    expect(html).toContain("Tool: Check calendar");
  });
});

describe("MarketingPage component", () => {
  it("renders the hero, stack marquee, bento value propositions, steps, and final CTA", () => {
    const html = renderToString(<MarketingPage />);

    // Hero headline
    expect(html).toContain("Answer every call, and sound like your best person.");
    // Stack marquee strip with continuous loop
    expect(html).toContain(
      "Designed to work with the voice stack you choose (example names)"
    );
    expect(html).toContain('id="track"');
    // Marquee should duplicate providers for infinite slide
    const livekitMatches = html.match(/LiveKit/g);
    expect(livekitMatches && livekitMatches.length).toBeGreaterThanOrEqual(2);

    // Value proposition bento section
    expect(html).toContain("Built for real conversations, not phone menus.");
    expect(html).toContain("Interrupt it. It stops and listens.");
    expect(html).toContain("One agent, two doors");
    expect(html).toContain("Does things mid-call");
    expect(html).toContain("Every call on record");
    expect(html).toContain("Safe edits");
    expect(html).toContain("Your company’s knowledge");
    expect(html).toContain("Outbound campaigns");
    expect(html).toContain("Separate by organization");
    // Coming soon items
    expect(html).toContain("Coming soon");
    // How it works steps
    expect(html).toContain("From idea to a ringing phone in an afternoon.");
    expect(html).toContain("Describe the job");
    expect(html).toContain("Talk to it in your browser");
    expect(html).toContain("Connect a number");
    // Final CTA
    expect(html).toContain("Hear your agent before you commit.");
    expect(html).toContain("Create your first agent");
  });
});
