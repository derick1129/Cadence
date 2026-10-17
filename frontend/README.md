# Cadence Frontend

Next.js App Router frontend for Cadence, the multi-tenant AI voice agent platform.

## Overview

The Cadence frontend is built with Next.js (App Router), React 19, Tailwind CSS, SWR, and Framer Motion. It hosts both the customer dashboard (`(app)`) and the public marketing site (`(marketing)`).

## Tech Stack

- **Framework**: Next.js 15+ (App Router)
- **UI Library**: React 19, Tailwind CSS
- **Data Fetching**: SWR for server state management
- **Component Primitives**: shadcn/ui patterns, Lucide React icons
- **Animations**: Framer Motion
- **Language**: TypeScript (strict mode, no `any`)
- **Testing**: Vitest

## Directory Structure

```
frontend/
├── src/
│   ├── app/
│   │   ├── (marketing)/    # Public static marketing landing page
│   │   ├── (app)/          # Authenticated app shell and dashboard routes
│   │   ├── globals.css     # Global styles and CSS variable definitions
│   │   └── layout.tsx      # Root layout
│   ├── features/           # Feature folders (agents, calls, numbers, tools, billing, settings)
│   ├── components/
│   │   ├── ui/             # Reusable shared UI primitives (shadcn/ui style)
│   │   └── marketing/      # Marketing page visual components
│   └── lib/
│       ├── tokens.ts       # Design system tokens (colors, fonts, spacing)
│       └── utils.ts        # Helper utilities (cn, formatting)
├── tests/                  # Frontend tests (Vitest)
├── next.config.ts          # Next.js configuration
├── tailwind.config.ts      # Tailwind configuration with brand tokens
├── postcss.config.js       # PostCSS plugins (Tailwind, Autoprefixer)
├── tsconfig.json           # TypeScript configuration
└── package.json            # Scripts and dependencies
```

## Available Scripts

Run from the `frontend/` directory (or use `pnpm --filter frontend <command>` from the root if workspaces are configured):

- `pnpm dev`: Start the development server at `http://localhost:3000`
- `pnpm build`: Build the application for production
- `pnpm start`: Start the production server
- `pnpm lint`: Run ESLint checks
- `pnpm typecheck`: Run TypeScript type checking (`tsc --noEmit`)
- `pnpm test`: Run unit tests with Vitest

## Design System & Tokens

Cadence adheres to strict brand styling guidelines:

- **Light Mode**: Pure white background (`#FFFFFF`), near-black text (`#0A0A0A`), light gray lines (`#EAEAEA`), mint green accent (`#0A7F5E`).
- **Dark Mode**: Neutral near-black (`#0A0A0A`), card surfaces (`#111111`), subtle borders (`#242424`), vibrant mint green accent (`#3DD9A8`).
- **Typography**:
  - Headings: Bricolage Grotesque (`--font-heading`, `font-heading`)
  - Body: Hanken Grotesk (`--font-body`, `font-body`)
- **Whitespace**: Generous section spacing (160px section gap, 40px card padding, 24px grid gap).

Tokens are defined in `src/lib/tokens.ts` and mapped to CSS variables in `src/app/globals.css`.

## Development Rules

- **Strict TypeScript**: Do not use `any` unless justified with a comment.
- **Architectural Isolation**: Features must be modular. Colocate components, hooks, and feature-specific utilities within their respective feature directory.
- **No Direct Vendor SDKs**: Browser test calls connect via WebRTC using LiveKit components, communicating with the backend API under `/api/v1`.
