"use client";

import * as React from "react";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";

export const TextGenerateEffect = ({
  words,
  className,
  filter = true,
  duration = 0.5,
}: {
  words: string;
  className?: string;
  filter?: boolean;
  duration?: number;
}) => {
  const wordsArray = React.useMemo(() => words.split(" "), [words]);

  return (
    <span className={cn("inline-block", className)} aria-label={words}>
      {/* Screen-reader and search crawler accessible full text */}
      <span className="sr-only">{words}</span>
      {/* Staggered visual animation */}
      <span aria-hidden="true">
        {wordsArray.map((word, idx) => (
          <motion.span
            key={`${word}-${idx}`}
            initial={{
              opacity: 0,
              filter: filter ? "blur(8px)" : "none",
            }}
            animate={{
              opacity: 1,
              filter: filter ? "blur(0px)" : "none",
            }}
            transition={{
              duration: duration,
              delay: idx * 0.08,
              ease: "easeOut",
            }}
            className="inline-block mr-[0.28em] last:mr-0 text-[var(--fg)]"
          >
            {word}
          </motion.span>
        ))}
      </span>
    </span>
  );
};
