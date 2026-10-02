import * as React from "react";
import { cn } from "@/lib/utils";

type SectionHeadingProps = React.HTMLAttributes<HTMLDivElement> & {
  kicker: string;
  title: string;
  description?: string;
};

/** Editorial section heading: kicker rule + Playfair title + optional lede. */
export function SectionHeading({ kicker, title, description, className, ...props }: SectionHeadingProps) {
  return (
    <div className={cn("flex flex-col gap-3", className)} {...props}>
      <div className="flex items-center gap-3">
        <span className="h-px w-8 bg-accent-primary/60" aria-hidden />
        <span className="kicker">{kicker}</span>
      </div>
      <h2 className="font-display text-3xl md:text-4xl text-text-primary leading-tight">{title}</h2>
      {description ? (
        <p className="text-sm text-text-muted max-w-xl leading-relaxed">{description}</p>
      ) : null}
    </div>
  );
}
