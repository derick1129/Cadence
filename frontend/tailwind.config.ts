import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: ["class", '[data-theme="dark"]'],
  content: [
    "./src/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          light: {
            bg: "#FFFFFF",
            fg: "#0A0A0A",
            muted: "#5E5E5E",
            card: "#FFFFFF",
            line: "#EAEAEA",
            accent: "#0A7F5E",
          },
          dark: {
            bg: "#0A0A0A",
            fg: "#EDEDED",
            muted: "#A1A1A1",
            card: "#111111",
            line: "#242424",
            accent: "#3DD9A8",
          },
        },
        bg: "var(--bg)",
        fg: "var(--fg)",
        muted: "var(--muted)",
        card: "var(--card)",
        line: "var(--line)",
        accent: "var(--accent)",
      },
      fontFamily: {
        heading: ["var(--font-heading)", "sans-serif"],
        body: ["var(--font-body)", "sans-serif"],
      },
    },
  },
  plugins: [],
};

export default config;
