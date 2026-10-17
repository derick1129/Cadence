import * as React from "react";
import { cn } from "@/lib/utils";

export interface BadgeProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: "default" | "secondary" | "outline" | "accent";
}

function Badge({ className, variant = "default", ...props }: BadgeProps) {
  const variantStyles = {
    default:
      "border-transparent bg-[#0A0A0A] text-white dark:bg-[#EDEDED] dark:text-[#0A0A0A]",
    secondary:
      "border-transparent bg-[var(--line)] text-[var(--fg)]",
    outline:
      "border-[var(--line)] text-[var(--fg)]",
    accent:
      "border-[var(--accent)]/30 bg-[var(--accent)]/10 text-[var(--accent)]",
  };

  return (
    <div
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-hidden",
        variantStyles[variant],
        className
      )}
      {...props}
    />
  );
}

export { Badge };
