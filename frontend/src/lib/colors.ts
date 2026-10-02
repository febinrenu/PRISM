/**
 * Thin re-export layer over src/lib/tokens.ts (the single source of truth),
 * preserving the shapes existing components import.
 */
import type { EntityLabel } from "@/types";
import { alpha, tokens } from "@/lib/tokens";

function entityEntry(label: keyof typeof tokens.entity) {
  const { base, text } = tokens.entity[label];
  return {
    bg: alpha(base, label === "THRESHOLD" ? 0.15 : 0.2),
    text,
    border: alpha(base, label === "THRESHOLD" ? 0.35 : 0.4),
    hex: base,
    tailwind: label.toLowerCase(),
  };
}

export const ENTITY_COLORS: Record<
  EntityLabel,
  { bg: string; text: string; border: string; hex: string; tailwind: string }
> = {
  OBLIGATION: entityEntry("OBLIGATION"),
  PENALTY: entityEntry("PENALTY"),
  RIGHT: entityEntry("RIGHT"),
  THRESHOLD: entityEntry("THRESHOLD"),
  ACTOR: entityEntry("ACTOR"),
  BENEFICIARY: entityEntry("BENEFICIARY"),
};

export const NODE_TYPE_COLORS: Record<string, string> = { ...tokens.node };

export const PATTERN_COLORS: Record<string, string> = {
  IF_THEN: tokens.accent.primary,
  CONDITION_ACTION: tokens.accent.secondary,
  PENALTY_TRIGGER: tokens.entity.PENALTY.base,
};
