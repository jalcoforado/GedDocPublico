import { cn } from "@/lib/utils";
import * as React from "react";

export const Checkbox = React.forwardRef<
  HTMLInputElement,
  Omit<React.InputHTMLAttributes<HTMLInputElement>, "type">
>(({ className, ...props }, ref) => (
  <input
    ref={ref}
    type="checkbox"
    className={cn(
      "h-5 w-5 cursor-pointer rounded border-input text-primary",
      "focus:ring-2 focus:ring-ring focus:ring-offset-1",
      className,
    )}
    {...props}
  />
));
Checkbox.displayName = "Checkbox";
