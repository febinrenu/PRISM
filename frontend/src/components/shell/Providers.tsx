"use client";

import { MotionConfig } from "framer-motion";
import { Toaster } from "sonner";
import { AuthProvider } from "@/lib/auth";
import { TooltipProvider } from "@/components/ui/tooltip";
import { CommandPaletteProvider } from "./CommandPalette";
import DemoNotice from "./DemoNotice";

/** App-wide client providers. Motion honours the OS reduced-motion setting. */
export default function Providers({ children }: { children: React.ReactNode }) {
  return (
    <MotionConfig reducedMotion="user">
      <AuthProvider>
        <TooltipProvider delayDuration={250}>
          <CommandPaletteProvider>{children}</CommandPaletteProvider>
          <DemoNotice />
        </TooltipProvider>
      </AuthProvider>
      <Toaster
        theme="dark"
        position="bottom-right"
        toastOptions={{
          classNames: {
            toast: "!bg-bg-elevated !border !border-border-light !text-text-primary !rounded-md !font-sans",
            description: "!text-text-muted",
          },
        }}
      />
    </MotionConfig>
  );
}
