"use client";

import * as React from "react";
import { cn } from "@/lib/utils";

export interface CardSpotlightProps extends React.HTMLAttributes<HTMLDivElement> {
  radius?: number;
  color?: string;
}

export function CardSpotlight({
  children,
  radius = 350,
  color = "var(--accent)",
  className,
  ...props
}: CardSpotlightProps) {
  const [position, setPosition] = React.useState<{ x: number; y: number } | null>(null);
  const [opacity, setOpacity] = React.useState(0);
  const divRef = React.useRef<HTMLDivElement>(null);

  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!divRef.current) return;
    const rect = divRef.current.getBoundingClientRect();
    setPosition({ x: e.clientX - rect.left, y: e.clientY - rect.top });
  };

  const handleMouseEnter = () => {
    setOpacity(1);
  };

  const handleMouseLeave = () => {
    setOpacity(0);
  };

  return (
    <div
      ref={divRef}
      onMouseMove={handleMouseMove}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      className={cn(
        "relative rounded-2xl border border-[var(--line)] bg-[var(--card)] p-8 overflow-hidden",
        "transition-colors duration-300 hover:border-[var(--muted)]/50",
        className
      )}
      {...props}
    >
      <div
        className="pointer-events-none absolute -inset-px opacity-0 transition-opacity duration-300"
        style={{
          opacity,
          background: position
            ? `radial-gradient(${radius}px circle at ${position.x}px ${position.y}px, ${color}15, transparent 80%)`
            : undefined,
        }}
        aria-hidden="true"
      />
      <div className="relative z-10">{children}</div>
    </div>
  );
}
