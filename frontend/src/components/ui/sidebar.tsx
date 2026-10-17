"use client";

import * as React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Bot,
  PhoneCall,
  Hash,
  Wrench,
  CreditCard,
  Settings,
  type LucideIcon,
} from "lucide-react";
import { cn } from "@/lib/utils";

export interface NavItem {
  label: string;
  href: string;
  icon: LucideIcon;
}

export const navItems: NavItem[] = [
  { label: "Agents", href: "/agents", icon: Bot },
  { label: "Calls", href: "/calls", icon: PhoneCall },
  { label: "Numbers", href: "/numbers", icon: Hash },
  { label: "Tools", href: "/tools", icon: Wrench },
  { label: "Billing", href: "/billing", icon: CreditCard },
  { label: "Settings", href: "/settings", icon: Settings },
];

export interface SidebarProps {
  className?: string;
  minutesUsed?: number;
  minutesLimit?: number;
}

export const Sidebar: React.FC<SidebarProps> = ({
  className,
  minutesUsed = 0,
  minutesLimit = 300,
}) => {
  const pathname = usePathname();
  const usagePercentage = Math.min(
    100,
    Math.round((minutesUsed / Math.max(1, minutesLimit)) * 100)
  );

  return (
    <aside
      className={cn(
        "w-64 border-r border-[var(--line)] bg-[var(--card)] flex flex-col h-screen p-4 select-none shrink-0",
        className
      )}
    >
      <div className="font-bold text-xl mb-8 flex items-center gap-2 px-2 text-[var(--fg)]">
        <span
          className="w-2.5 h-2.5 rounded-full bg-[var(--accent)] animate-pulse"
          aria-hidden="true"
        />
        <span>Cadence</span>
      </div>

      <nav className="flex-1 space-y-1">
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive =
            pathname === item.href ||
            Boolean(pathname && pathname.startsWith(`${item.href}/`));
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors",
                isActive
                  ? "bg-[var(--line)] text-[var(--fg)] font-semibold"
                  : "text-[var(--muted)] hover:bg-[var(--line)] hover:text-[var(--fg)]"
              )}
            >
              <Icon className="w-4 h-4 shrink-0" />
              <span>{item.label}</span>
            </Link>
          );
        })}
      </nav>

      <div className="p-3 border border-[var(--line)] rounded-lg text-xs bg-[var(--bg)]/50">
        <div className="flex items-center justify-between mb-1.5">
          <span className="font-semibold text-[var(--fg)]">Plan Usage</span>
          <span className="text-[11px] text-[var(--muted)]">
            {`${usagePercentage}%`}
          </span>
        </div>
        <div className="text-[var(--muted)] mb-2">
          {`${minutesUsed} / ${minutesLimit} minutes used`}
        </div>
        <div
          className="w-full bg-[var(--line)] h-1.5 rounded-full overflow-hidden"
          role="progressbar"
          aria-valuenow={minutesUsed}
          aria-valuemin={0}
          aria-valuemax={minutesLimit}
        >
          <div
            className="bg-[var(--accent)] h-full transition-all duration-300 rounded-full"
            style={{ width: `${usagePercentage}%` }}
          />
        </div>
      </div>
    </aside>
  );
};
