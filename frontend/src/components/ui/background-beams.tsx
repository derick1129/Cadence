"use client";

import * as React from "react";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";

export const BackgroundBeams = ({ className }: { className?: string }) => {
  return (
    <div
      className={cn(
        "absolute inset-0 overflow-hidden pointer-events-none [mask-image:radial-gradient(ellipse_at_center,transparent_20%,black)]",
        className
      )}
    >
      <svg
        className="absolute w-full h-full stroke-[var(--line)] [stroke-dasharray:6_6] opacity-35 dark:opacity-20"
        xmlns="http://www.w3.org/2000/svg"
      >
        <defs>
          <linearGradient id="beam-grad" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="var(--accent)" stopOpacity="0" />
            <stop offset="50%" stopColor="var(--accent)" stopOpacity="0.8" />
            <stop offset="100%" stopColor="var(--accent)" stopOpacity="0" />
          </linearGradient>
        </defs>
        <pattern
          id="grid-pattern"
          width="48"
          height="48"
          patternUnits="userSpaceOnUse"
        >
          <path d="M 48 0 L 0 0 0 48" fill="none" strokeWidth="1" />
        </pattern>
        <rect width="100%" height="100%" fill="url(#grid-pattern)" />
      </svg>

      {/* Animated glowing beam paths */}
      <motion.div
        initial={{ opacity: 0, x: -100, y: -50 }}
        animate={{
          opacity: [0.1, 0.35, 0.1],
          x: [-100, 100, -100],
          y: [-50, 50, -50],
        }}
        transition={{
          duration: 12,
          repeat: Infinity,
          ease: "easeInOut",
        }}
        className="absolute top-1/4 left-1/4 w-[500px] h-[500px] rounded-full bg-[var(--accent)]/10 blur-[120px]"
        aria-hidden="true"
      />
      <motion.div
        initial={{ opacity: 0, x: 100, y: 100 }}
        animate={{
          opacity: [0.08, 0.25, 0.08],
          x: [100, -100, 100],
          y: [100, -50, 100],
        }}
        transition={{
          duration: 16,
          repeat: Infinity,
          ease: "easeInOut",
        }}
        className="absolute bottom-1/3 right-1/4 w-[450px] h-[450px] rounded-full bg-[var(--accent)]/10 blur-[130px]"
        aria-hidden="true"
      />
    </div>
  );
};
