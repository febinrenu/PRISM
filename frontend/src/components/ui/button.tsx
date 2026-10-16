import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex select-none items-center justify-center gap-2 whitespace-nowrap rounded-[4px] font-medium transition-[background-color,border-color,color,transform] duration-200 ease-out-expo active:translate-y-px disabled:pointer-events-none disabled:opacity-40",
  {
    variants: {
      variant: {
        /** Ink text on vermilion: the one primary action on a view. */
        primary: "bg-signal text-ink hover:bg-signal-soft border border-transparent",
        /** Paper fill: strong but not the signal. */
        secondary: "bg-contrast text-on-contrast hover:bg-contrast/85 border border-transparent",
        outline: "border border-light text-text-primary hover:border-glow hover:bg-bg-elevated",
        ghost: "text-text-secondary hover:text-text-primary hover:bg-bg-elevated border border-transparent",
        quiet: "text-text-muted hover:text-text-primary border border-transparent",
        link: "text-text-primary underline decoration-border-light underline-offset-4 hover:decoration-signal px-0 h-auto",
        danger: "border border-status-critical/45 text-status-error hover:bg-status-critical/10",
      },
      size: {
        sm: "h-8 px-3 text-[13px]",
        md: "h-10 px-4 text-sm",
        lg: "h-12 px-6 text-[15px]",
        icon: "h-9 w-9 p-0",
      },
    },
    defaultVariants: { variant: "primary", size: "md" },
  }
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, type = "button", ...props }, ref) => (
    <button ref={ref} type={type} className={cn(buttonVariants({ variant, size }), className)} {...props} />
  )
);
Button.displayName = "Button";

export { Button, buttonVariants };
