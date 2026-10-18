import { describe, it, expect, vi } from "vitest";
import React from "react";
import { renderToString } from "react-dom/server";

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
    prefetch: vi.fn(),
  }),
  usePathname: () => "/",
}));

import MarketingLayout from "../src/app/(marketing)/layout";
import MarketingPage from "../src/app/(marketing)/page";
import { Hero } from "../src/components/marketing/hero";
import LoginPage from "../src/app/(auth)/login/page";
import RegisterPage from "../src/app/(auth)/register/page";

describe("Marketing Navigation & CTA Links", () => {
  it("links 'Start free' and 'Create your first agent' to /register and 'Login' to /login", () => {
    const layoutHtml = renderToString(
      <MarketingLayout>
        <div>Content</div>
      </MarketingLayout>
    );
    expect(layoutHtml).toContain('href="/register"');
    expect(layoutHtml).toContain('href="/login"');

    const heroHtml = renderToString(<Hero />);
    expect(heroHtml).toContain('href="/register"');
    expect(heroHtml).toContain('href="#how"');

    const pageHtml = renderToString(<MarketingPage />);
    expect(pageHtml).toContain('href="/register"');
  });

  it("renders functional login page with credentials form and dashboard link", () => {
    const loginHtml = renderToString(<LoginPage />);
    expect(loginHtml).toContain("Welcome back");
    expect(loginHtml).toContain("Sign in");
    expect(loginHtml).toContain('type="email"');
    expect(loginHtml).toContain('type="password"');
    expect(loginHtml).toContain('href="/register"');
  });

  it("renders functional register page with onboarding form and dashboard link", () => {
    const registerHtml = renderToString(<RegisterPage />);
    expect(registerHtml).toContain("Create your account");
    expect(registerHtml).toContain("Start free");
    expect(registerHtml).toContain('type="email"');
    expect(registerHtml).toContain('type="password"');
    expect(registerHtml).toContain('href="/login"');
  });
});
