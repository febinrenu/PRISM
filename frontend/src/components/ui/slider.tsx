"use client";

import * as React from "react";
import * as SliderPrimitive from "@radix-ui/react-slider";
import { cn } from "@/lib/utils";

const Slider = React.forwardRef<
  React.ElementRef<typeof SliderPrimitive.Root>,
  React.ComponentPropsWithoutRef<typeof SliderPrimitive.Root>
>(({ className, ...props }, ref) => (
  <SliderPrimitive.Root
    ref={ref}
    className={cn("relative flex w-full touch-none select-none items-center py-2", className)}
    {...props}
  >
    <SliderPrimitive.Track className="relative h-px w-full grow bg-border-light">
      <SliderPrimitive.Range className="absolute h-px bg-accent-primary" />
    </SliderPrimitive.Track>
    <SliderPrimitive.Thumb
      className="block h-3.5 w-3.5 rounded-full border border-accent-primary bg-bg-elevated transition-colors hover:bg-accent-primary/20 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-accent-primary disabled:pointer-events-none disabled:opacity-40"
      aria-label="Value"
    />
  </SliderPrimitive.Root>
));
Slider.displayName = SliderPrimitive.Root.displayName;

export { Slider };
