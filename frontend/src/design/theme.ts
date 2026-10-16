"use client";

/**
 * Light or dark for the app (the landing story is always dark). The choice is
 * stored per browser and applied to <html data-theme> before first paint by
 * the inline script in the root layout, so there is no flash.
 */
import { useSyncExternalStore } from "react";
import { THEME_KEY as KEY } from "./themeScript";
import { themedTokens, type ThemeName } from "./tokens";

const listeners = new Set<() => void>();

function read(): ThemeName {
  if (typeof document === "undefined") return "dark";
  return document.documentElement.dataset.theme === "light" ? "light" : "dark";
}

export function setTheme(t: ThemeName) {
  document.documentElement.dataset.theme = t;
  document.documentElement.style.colorScheme = t;
  try {
    window.localStorage.setItem(KEY, t);
  } catch {
    /* storage blocked: the choice lasts for this page */
  }
  listeners.forEach((l) => l());
}

const subscribe = (l: () => void) => {
  listeners.add(l);
  return () => {
    listeners.delete(l);
  };
};

export function useTheme(): [ThemeName, (t: ThemeName) => void] {
  const theme = useSyncExternalStore(subscribe, read, () => "dark" as ThemeName);
  return [theme, setTheme];
}

/** Hex tokens for the current theme, for code that draws with colour values (SVG, canvas, charts). */
export function useTokens() {
  const [theme] = useTheme();
  return themedTokens(theme);
}
