import type { LucideIcon } from "lucide-react";
import * as React from "react";

import { cn } from "@/lib/utils";

type Intent = "neutral" | "success" | "danger" | "warning" | "info" | "brand";

const INTENTS: Record<Intent, string> = {
  neutral: "bg-muted text-muted-foreground",
  success: "bg-success-soft text-success-soft-foreground",
  danger: "bg-danger-soft text-danger-soft-foreground",
  warning: "bg-warning-soft text-warning-soft-foreground",
  info: "bg-info-soft text-info-soft-foreground",
  brand: "bg-primary/10 text-primary",
};

interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  intent?: Intent;
  icon?: LucideIcon;
}

export function Badge({
  intent = "neutral",
  icon: Icon,
  className,
  children,
  ...props
}: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-semibold",
        INTENTS[intent],
        className,
      )}
      {...props}
    >
      {Icon && <Icon className="h-3 w-3" aria-hidden="true" />}
      {children}
    </span>
  );
}
