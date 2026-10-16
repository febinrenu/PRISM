import type { Config } from "tailwindcss";
import plugin from "tailwindcss/plugin";
import { cssVariables, lightCssVariables } from "./src/design/tokens";

const rgb = (name: string) => `rgb(var(--${name}-rgb) / <alpha-value>)`;

const config: Config = {
  darkMode: ["class"],
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/story/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ["var(--font-geist-sans)", "ui-sans-serif", "system-ui", "sans-serif"],
        display: ["var(--font-serif)", "ui-serif", "Georgia", "serif"],
        serif: ["var(--font-serif)", "ui-serif", "Georgia", "serif"],
        mono: ["var(--font-geist-mono)", "ui-monospace", "monospace"],
      },
      fontSize: {
        // 12px is the floor for any text in the product.
        micro: ["0.75rem", { lineHeight: "1rem", letterSpacing: "0.02em" }],
        small: ["0.8125rem", { lineHeight: "1.25rem" }],
        body: ["0.9375rem", { lineHeight: "1.6rem" }],
        lead: ["1.125rem", { lineHeight: "1.75rem" }],
        title: ["1.5rem", { lineHeight: "1.2", letterSpacing: "-0.01em" }],
        headline: ["clamp(2rem, 4.5vw, 3.25rem)", { lineHeight: "1.02", letterSpacing: "-0.02em" }],
        display: ["clamp(3.25rem, 10vw, 9.5rem)", { lineHeight: "0.9", letterSpacing: "-0.035em" }],
      },
      colors: {
        bg: {
          deep: rgb("bg-deep"),
          base: rgb("bg-base"),
          surface: rgb("bg-surface"),
          elevated: rgb("bg-elevated"),
          overlay: rgb("bg-overlay"),
        },
        border: {
          DEFAULT: "var(--border)",
          light: "var(--border-light)",
          glow: "var(--border-glow)",
        },
        accent: {
          primary: rgb("accent-primary"),
          secondary: rgb("accent-secondary"),
          bright: rgb("accent-bright"),
        },
        text: {
          primary: rgb("text-primary"),
          secondary: rgb("text-secondary"),
          muted: rgb("text-muted"),
          dim: rgb("text-dim"),
          inverse: rgb("text-inverse"),
        },
        status: {
          success: rgb("status-success"),
          error: rgb("status-error"),
          warning: rgb("status-warning"),
          info: rgb("status-info"),
          critical: rgb("status-critical"),
        },
        entity: {
          obligation: rgb("entity-obligation"),
          penalty: rgb("entity-penalty"),
          right: rgb("entity-right"),
          threshold: rgb("entity-threshold"),
          actor: rgb("entity-actor"),
          beneficiary: rgb("entity-beneficiary"),
        },
        signal: {
          DEFAULT: rgb("signal"),
          soft: rgb("signal-soft"),
          deep: rgb("signal-deep"),
          ink: rgb("signal-ink"),
        },
        paper: {
          DEFAULT: rgb("paper"),
          50: rgb("paper-50"),
          200: rgb("paper-200"),
          300: rgb("paper-300"),
          400: rgb("paper-400"),
        },
        ink: {
          DEFAULT: rgb("ink"),
          950: rgb("ink-950"),
          800: rgb("ink-800"),
          700: rgb("ink-700"),
          600: rgb("ink-600"),
          500: rgb("ink-500"),
        },
      },
      // `border-light` / `hover:border-glow` are used across the app as
      // border colours; register them so they resolve.
      borderColor: {
        light: "var(--border-light)",
        glow: "var(--border-glow)",
      },
      zIndex: {
        raised: "10",
        sticky: "30",
        nav: "40",
        overlay: "60",
        modal: "70",
        toast: "80",
        curtain: "90",
      },
      transitionTimingFunction: {
        "out-expo": "cubic-bezier(0.16, 1, 0.3, 1)",
        "out-quart": "cubic-bezier(0.25, 1, 0.5, 1)",
        "in-out-quint": "cubic-bezier(0.83, 0, 0.17, 1)",
      },
      boxShadow: {
        "glow-sm": "0 0 0 1px rgba(255,79,31,0.25), 0 0 18px rgba(255,79,31,0.12)",
        "glow-md": "0 0 0 1px rgba(255,79,31,0.30), 0 0 32px rgba(255,79,31,0.16)",
        "glow-lg": "0 0 0 1px rgba(255,79,31,0.35), 0 0 60px rgba(255,79,31,0.20)",
        card: "0 1px 0 rgba(241,237,228,0.04) inset, 0 18px 40px -18px rgba(0,0,0,0.65)",
        lift: "0 1px 0 rgba(241,237,228,0.06) inset, 0 24px 60px -24px rgba(0,0,0,0.8)",
      },
      animation: {
        "grid-pulse": "gridPulse 6s ease-in-out infinite",
        float: "float 6s ease-in-out infinite",
        shimmer: "shimmer 1.8s ease-in-out infinite",
        ticker: "tickerScroll 40s linear infinite",
        "pulse-soft": "pulseSoft 2.4s ease-in-out infinite",
        "fade-up": "fadeUp 0.6s cubic-bezier(0.16,1,0.3,1) both",
      },
      keyframes: {
        gridPulse: { "0%,100%": { opacity: "0.5" }, "50%": { opacity: "1" } },
        float: { "0%,100%": { transform: "translateY(0)" }, "50%": { transform: "translateY(-8px)" } },
        shimmer: { "0%": { backgroundPosition: "-200% 0" }, "100%": { backgroundPosition: "200% 0" } },
        tickerScroll: { "0%": { transform: "translateX(0)" }, "100%": { transform: "translateX(-50%)" } },
        pulseSoft: { "0%,100%": { opacity: "1" }, "50%": { opacity: "0.55" } },
        fadeUp: { "0%": { opacity: "0", transform: "translateY(12px)" }, "100%": { opacity: "1", transform: "none" } },
      },
    },
  },
  plugins: [
    // Canonical token values (src/design/tokens.ts) as CSS custom properties.
    plugin(({ addBase }) => {
      addBase({ ":root": cssVariables });
      // The app can be light; the landing story is always ink.
      addBase({ 'html[data-theme="light"] body': lightCssVariables });
      addBase({ 'html[data-theme="light"] .story-root': cssVariables });
    }),
  ],
};

export default config;
