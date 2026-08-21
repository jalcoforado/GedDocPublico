import { cn } from "@/lib/utils";
import * as React from "react";

export const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(
  ({ className, type, ...props }, ref) => (
    <input
      ref={ref}
      type={type}
      className={cn(
        "flex h-11 w-full rounded-input border border-input bg-card px-3 py-2 transition-colors duration-fast",
        "text-base text-foreground shadow-input placeholder:text-muted-foreground",
        "hover:border-border-strong",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background focus-visible:border-ring",
        "aria-[invalid=true]:border-danger aria-[invalid=true]:focus-visible:ring-danger",
        "disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:border-input",
        className,
      )}
      {...props}
    />
  ),
);
Input.displayName = "Input";
