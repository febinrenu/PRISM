import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap font-mono uppercase tracking-[0.14em] transition-colors duration-200 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-accent-primary focus-visible:ring-offset-1 focus-visible:ring-offset-bg-base disabled:pointer-events-none disabled:opacity-40",
  {
    variants: {
      variant: {
        primary:
          "bg-accent-primary text-text-inverse hover:bg-accent-bright border border-transparent",
        outline:
          "border border-light text-accent-primary hover:border-glow hover:bg-bg-elevated",
        ghost:
          "text-text-secondary hover:text-text-primary hover:bg-bg-elevated border border-transparent",
        danger:
          "border border-status-error/40 text-status-error hover:bg-status-error/10",
      },
      size: {
        sm: "h-8 px-3 text-[10px]",
        md: "h-10 px-5 text-[11px]",
        lg: "h-12 px-7 text-xs",
      },
    },
    defaultVariants: { variant: "primary", size: "md" },
  }
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, ...props }, ref) => (
    <button ref={ref} className={cn(buttonVariants({ variant, size }), className)} {...props} />
  )
);
Button.displayName = "Button";

export { Button, buttonVariants };
