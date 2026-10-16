/** Data and wording shared by the semantic map's parts. */
import { ENTITY_COLORS } from "@/lib/colors";
import { tokens } from "@/lib/tokens";
import type { Clause } from "@/types";

export interface MapPoint {
  id: string;
  x: number;
  y: number;
  page: number;
  text: string;
  /** The clause's first tagged entity type, or NONE. */
  label: string;
}

export const ENTITY_MEANING: Record<string, string> = {
  OBLIGATION: "A legal duty: requires the subject to act or refrain",
  PENALTY: "A punishable consequence: fine, imprisonment or liability",
  RIGHT: "An entitlement or protection granted to a party",
  THRESHOLD: "A numeric limit, monetary value or qualifying condition",
  ACTOR: "An authority, office or responsible party",
  BENEFICIARY: "A party receiving an exemption, benefit or protection",
  NONE: "No tagged entity",
};

export const CONF_DOT: Record<string, { bg: string; label: string }> = {
  HIGH: { bg: tokens.status.success, label: "High confidence" },
  MEDIUM: { bg: tokens.status.warning, label: "Medium confidence" },
  LOW: { bg: tokens.text.muted, label: "Low confidence" },
};

export const RISK_COLOR: Record<string, string> = {
  CRITICAL: tokens.risk.CRITICAL.text,
  HIGH: tokens.risk.HIGH.text,
  MEDIUM: tokens.risk.MEDIUM.text,
  LOW: tokens.risk.LOW.text,
};

export const colorOf = (label: string, fallback: string = tokens.text.dim): string =>
  (ENTITY_COLORS as Record<string, { hex: string }>)[label]?.hex ?? fallback;

export function toPoints(clauses: Clause[]): MapPoint[] {
  return clauses
    .filter((c) => c.embedding_2d)
    .map((c) => ({
      id: c.clause_id,
      x: c.embedding_2d![0],
      y: c.embedding_2d![1],
      page: c.page,
      text: c.text,
      label: c.entities[0]?.label ?? "NONE",
    }));
}

/** The k nearest points in the projection (Euclidean, 2D). */
export function nearest(selected: MapPoint, all: MapPoint[], k = 5) {
  return all
    .filter((p) => p.id !== selected.id)
    .map((p) => ({ ...p, dist: Math.hypot(p.x - selected.x, p.y - selected.y) }))
    .sort((a, b) => a.dist - b.dist)
    .slice(0, k);
}

/** Ray-casting point-in-polygon test. */
export function pointInPolygon(x: number, y: number, poly: [number, number][]): boolean {
  let inside = false;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const [xi, yi] = poly[i];
    const [xj, yj] = poly[j];
    if (yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) inside = !inside;
  }
  return inside;
}
