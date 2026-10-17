"use client";

import * as React from "react";
import { Sun, Moon } from "lucide-react";

export function ThemeToggle() {
  const [theme, setTheme] = React.useState<"light" | "dark">("light");

  React.useEffect(() => {
    // Check initial theme from html attribute or prefers-color-scheme
    const currentTheme = document.documentElement.getAttribute("data-theme");
    if (currentTheme === "dark" || currentTheme === "light") {
      setTheme(currentTheme);
    } else if (window.matchMedia("(prefers-color-scheme: dark)").matches) {
      setTheme("dark");
    }
  }, []);

  const toggleTheme = () => {
    const nextTheme = theme === "dark" ? "light" : "dark";
    setTheme(nextTheme);
    document.documentElement.setAttribute("data-theme", nextTheme);
  };

  return (
    <button
      type="button"
      onClick={toggleTheme}
      aria-label="Toggle light and dark theme"
      className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-[var(--line)] bg-[var(--card)] text-[var(--fg)] hover:bg-[var(--line)] transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)]"
    >
      {theme === "dark" ? (
        <Sun className="h-4 w-4 text-[var(--fg)] transition-transform motion-reduce:transition-none" />
      ) : (
        <Moon className="h-4 w-4 text-[var(--fg)] transition-transform motion-reduce:transition-none" />
      )}
    </button>
  );
}
