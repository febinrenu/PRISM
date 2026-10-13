/**
 * Motion vocabulary shared by framer-motion (app) and GSAP (story).
 * Durations in seconds. Curves are cubic-bezier control points.
 */
export const ease = {
  /** Default for entrances: fast start, long settle. */
  out: [0.16, 1, 0.3, 1] as const,
  outQuart: [0.25, 1, 0.5, 1] as const,
  inOut: [0.83, 0, 0.17, 1] as const,
  /** GSAP string equivalents. */
  gsapOut: "expo.out",
  gsapInOut: "power4.inOut",
};

export const duration = {
  instant: 0.12,
  quick: 0.2,
  base: 0.32,
  slow: 0.6,
  scene: 1.1,
};

export const stagger = {
  tight: 0.035,
  base: 0.06,
  loose: 0.12,
};

/** framer-motion presets. */
export const fadeUp = {
  initial: { opacity: 0, y: 14 },
  animate: { opacity: 1, y: 0 },
  transition: { duration: duration.slow, ease: ease.out },
};

export const spring = { type: "spring", stiffness: 420, damping: 34, mass: 0.7 } as const;
