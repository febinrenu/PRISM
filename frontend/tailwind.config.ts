import type { Config } from "tailwindcss";
import plugin from "tailwindcss/plugin";
import { cssVariables } from "./src/lib/tokens";

const config: Config = {
  darkMode: ["class"],
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans:    ["var(--font-manrope)", "sans-serif"],
        display: ["var(--font-playfair)", "serif"],
        mono:    ["var(--font-mono)", "monospace"],
      },
      colors: {
        // rgb(var(--x-rgb) / <alpha-value>) lets Tailwind opacity modifiers
        // (bg-accent-primary/20) work with token-driven colors.
        bg: {
          deep:     "rgb(var(--bg-deep-rgb) / <alpha-value>)",
          base:     "rgb(var(--bg-base-rgb) / <alpha-value>)",
          surface:  "rgb(var(--bg-surface-rgb) / <alpha-value>)",
          elevated: "rgb(var(--bg-elevated-rgb) / <alpha-value>)",
          overlay:  "rgb(var(--bg-overlay-rgb) / <alpha-value>)",
        },
        border: {
          DEFAULT: "var(--border)",
          light:   "var(--border-light)",
          glow:    "var(--border-glow)",
        },
        accent: {
          primary:   "rgb(var(--accent-primary-rgb) / <alpha-value>)",
          secondary: "rgb(var(--accent-secondary-rgb) / <alpha-value>)",
          bright:    "rgb(var(--accent-bright-rgb) / <alpha-value>)",
        },
        text: {
          primary:   "rgb(var(--text-primary-rgb) / <alpha-value>)",
          secondary: "rgb(var(--text-secondary-rgb) / <alpha-value>)",
          muted:     "rgb(var(--text-muted-rgb) / <alpha-value>)",
          dim:       "rgb(var(--text-dim-rgb) / <alpha-value>)",
          inverse:   "rgb(var(--text-inverse-rgb) / <alpha-value>)",
        },
        status: {
          success: "rgb(var(--status-success-rgb) / <alpha-value>)",
          error:   "rgb(var(--status-error-rgb) / <alpha-value>)",
          warning: "rgb(var(--status-warning-rgb) / <alpha-value>)",
          info:    "rgb(var(--status-info-rgb) / <alpha-value>)",
        },
        entity: {
          obligation:  "rgb(var(--entity-obligation-rgb) / <alpha-value>)",
          penalty:     "rgb(var(--entity-penalty-rgb) / <alpha-value>)",
          right:       "rgb(var(--entity-right-rgb) / <alpha-value>)",
          threshold:   "rgb(var(--entity-threshold-rgb) / <alpha-value>)",
          actor:       "rgb(var(--entity-actor-rgb) / <alpha-value>)",
          beneficiary: "rgb(var(--entity-beneficiary-rgb) / <alpha-value>)",
        },
      },
      backgroundImage: {
        "prism-gradient": "linear-gradient(135deg, var(--accent-secondary) 0%, var(--accent-primary) 55%, var(--accent-bright) 100%)",
      },
      boxShadow: {
        "glow-sm": "0 0 10px rgba(197,168,128,0.15)",
        "glow-md": "0 0 25px rgba(197,168,128,0.20)",
        "glow-lg": "0 0 50px rgba(197,168,128,0.25)",
        "card":    "0 10px 30px rgba(0,0,0,0.40)",
      },
      animation: {
        "grid-pulse": "gridPulse 6s ease-in-out infinite",
        "float":      "float 6s ease-in-out infinite",
        "shimmer":    "shimmer 1.8s ease-in-out infinite",
        "ticker":     "tickerScroll 30s linear infinite",
        "pulse-soft": "pulseSoft 2.4s ease-in-out infinite",
      },
      keyframes: {
        gridPulse:    { "0%,100%": { opacity: "0.5" }, "50%": { opacity: "1" } },
        float:        { "0%,100%": { transform: "translateY(0)" }, "50%": { transform: "translateY(-8px)" } },
        shimmer:      { "0%": { backgroundPosition: "-200% 0" }, "100%": { backgroundPosition: "200% 0" } },
        tickerScroll: { "0%": { transform: "translateX(0)" }, "100%": { transform: "translateX(-50%)" } },
        pulseSoft:    { "0%,100%": { opacity: "1" }, "50%": { opacity: "0.55" } },
      },
    },
  },
  plugins: [
    // Injects the canonical token values (src/lib/tokens.ts) as CSS custom
    // properties — the theme colors above all read from these vars.
    plugin(({ addBase }) => {
      addBase({ ":root": cssVariables });
    }),
  ],
};

export default config;
