import { cn } from "@/lib/utils";
import * as React from "react";

type Variant = "primary" | "secondary" | "ghost" | "danger" | "accent";
type Size = "sm" | "md" | "lg" | "icon";

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  /**
   * Quando `true`, NÃO renderiza um `<button>` — clona o único filho
   * mesclando as classes e props neste. Útil pra envolver `<Link>` do
   * Next sem reescrever as classes manualmente.
   *
   * Restrições: o filho deve ser um único React element que aceite
   * `className`. `type="button"` não é propagado em modo `asChild`
   * (não faz sentido em `<a>`).
   */
  asChild?: boolean;
}

const VARIANTS: Record<Variant, string> = {
  primary:
    "bg-brand text-primary-foreground shadow-sm hover:bg-brand-light hover:shadow-md focus-visible:ring-ring",
  secondary:
    "bg-surface-1 text-foreground border border-border-strong shadow-xs hover:bg-muted hover:border-foreground/30 focus-visible:ring-ring",
  ghost:
    "bg-transparent text-foreground hover:bg-muted focus-visible:ring-ring",
  danger:
    "bg-danger text-danger-foreground shadow-sm hover:bg-danger/90 hover:shadow-md focus-visible:ring-danger",
  accent:
    "bg-accent text-accent-foreground shadow-sm hover:bg-accent-light hover:shadow-accent focus-visible:ring-accent",
};

const SIZES: Record<Size, string> = {
  sm: "h-9 px-3 text-xs gap-1.5",
  md: "h-11 px-4 text-sm gap-2",
  lg: "h-12 px-6 text-base gap-2",
  icon: "h-11 w-11 p-0",
};

const BASE_CLASSES =
  "inline-flex items-center justify-center rounded-md font-medium whitespace-nowrap " +
  "transition-[background-color,box-shadow,transform,border-color] duration-fast ease-out " +
  "active:scale-[0.98] " +
  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-offset-background " +
  "disabled:pointer-events-none disabled:opacity-50";

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      className,
      variant = "primary",
      size = "md",
      type = "button",
      asChild = false,
      children,
      ...props
    },
    ref,
  ) => {
    const merged = cn(BASE_CLASSES, SIZES[size], VARIANTS[variant], className);

    if (asChild) {
      const child = React.Children.only(children) as React.ReactElement<{
        className?: string;
      }>;
      return React.cloneElement(child, {
        ...props,
        // Mescla classes preservando overrides do filho.
        className: cn(merged, child.props.className),
      });
    }

    return (
      <button ref={ref} type={type} className={merged} {...props}>
        {children}
      </button>
    );
  },
);
Button.displayName = "Button";
