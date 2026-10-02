import * as React from "react";
import { cn } from "@/lib/utils";
import { alpha, entityStyle, riskStyle } from "@/lib/tokens";

type BadgeProps = React.HTMLAttributes<HTMLSpanElement> & {
  /** ENTITY label, RISK tier, or undefined for neutral */
  entity?: string;
  risk?: string;
};

/**
 * Pill badge. With `entity` or `risk` set, colors come from tokens (inline,
 * because the palette is data-driven); otherwise a neutral outline pill.
 */
const Badge = React.forwardRef<HTMLSpanElement, BadgeProps>(
  ({ className, entity, risk, style, ...props }, ref) => {
    let inline: React.CSSProperties | undefined = style;
    if (entity) {
      const c = entityStyle(entity);
      inline = { background: alpha(c.base, 0.18), color: c.text, borderColor: alpha(c.base, 0.4), ...style };
    } else if (risk) {
      const c = riskStyle(risk);
      inline = { background: alpha(c.base, 0.15), color: c.text, borderColor: alpha(c.base, 0.4), ...style };
    }
    return (
      <span
        ref={ref}
        className={cn(
          "entity-pill border",
          !entity && !risk && "border-light text-text-secondary bg-bg-elevated",
          className
        )}
        style={inline}
        {...props}
      />
    );
  }
);
Badge.displayName = "Badge";

export { Badge };
