import * as React from "react";
import { cn } from "@/lib/utils";

export const BentoGrid = ({
  className,
  children,
}: {
  className?: string;
  children?: React.ReactNode;
}) => {
  return (
    <div
      className={cn(
        "grid grid-cols-1 md:grid-cols-6 gap-6 max-w-6xl mx-auto",
        className
      )}
    >
      {children}
    </div>
  );
};

export const BentoGridItem = ({
  className,
  title,
  description,
  header,
  icon,
  footer,
}: {
  className?: string;
  title?: string | React.ReactNode;
  description?: string | React.ReactNode;
  header?: React.ReactNode;
  icon?: React.ReactNode;
  footer?: React.ReactNode;
}) => {
  return (
    <div
      className={cn(
        "row-span-1 rounded-2xl group/bento hover:shadow-lg transition-all duration-300",
        "p-6 md:p-8 bg-[var(--card)] border border-[var(--line)]",
        "flex flex-col justify-between space-y-4",
        "hover:border-[var(--accent)]/40 relative overflow-hidden",
        className
      )}
    >
      {header && <div className="w-full">{header}</div>}
      <div className="group-hover/bento:translate-x-1 transition duration-200 space-y-2">
        {icon && <div className="mb-2">{icon}</div>}
        {title && (
          <div className="font-heading font-bold text-[var(--fg)] text-lg md:text-xl">
            {title}
          </div>
        )}
        {description && (
          <div className="text-sm text-[var(--muted)] leading-relaxed">
            {description}
          </div>
        )}
      </div>
      {footer && <div className="pt-2">{footer}</div>}
    </div>
  );
};
