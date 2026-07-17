import { cn } from "@/lib/utils";
import * as React from "react";

export const Textarea = React.forwardRef<
  HTMLTextAreaElement,
  React.TextareaHTMLAttributes<HTMLTextAreaElement>
>(({ className, ...props }, ref) => (
  <textarea
    ref={ref}
    className={cn(
      "flex w-full rounded-input border border-input bg-card px-3 py-2 transition-colors duration-fast",
      "text-base text-foreground shadow-input placeholder:text-muted-foreground",
      "hover:border-border-strong",
      "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background focus-visible:border-ring",
      "disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:border-input",
      className,
    )}
    {...props}
  />
));
Textarea.displayName = "Textarea";
