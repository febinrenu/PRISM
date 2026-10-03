/**
 * Client for the human-annotation API (/api/annotate). Spans are character
 * offsets into the item's frozen text.
 */
import { tokenStore } from "@/lib/api";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export type Modality = "obligation" | "prohibition" | "permission" | "power" | "deeming" | "definition";
export const MODALITIES: Modality[] = ["obligation", "prohibition", "permission", "power", "deeming", "definition"];
export const AGENT_CLASSES = [
  "individual", "company", "firm", "huf", "any_person", "employer", "registered_person",
  "data_fiduciary", "authority", "other",
];

export interface AnnSpan { start: number; end: number }
export interface AnnCondition extends AnnSpan { negated: boolean }
export interface AnnEffect { kind: string; fields: Record<string, string | number | boolean | null>; source: AnnSpan | null }
export interface AnnRule {
  modality: Modality;
  agent_class: string | null;
  subject: AnnSpan | null;
  conditions: AnnCondition[];
  action: AnnSpan | null;
  consequence: AnnSpan | null;
  exceptions: AnnSpan[];
  cross_refs: AnnSpan[];
  effects: AnnEffect[];
  executable: boolean;
  note: string;
}
export interface Annotation {
  item_id?: string;
  status: "draft" | "done";
  no_rule: boolean;
  rules: AnnRule[];
  seconds: number;
  note: string;
  annotator_name?: string;
  updated_at?: string;
}
export interface SetSummary { set: string; items: number; done: number; draft: number }
export interface SetItem { item_id: string; statute: string; path: string; kind: string; chars: number; status: "todo" | "draft" | "done" }
export interface ItemView {
  item: { item_id: string; statute: string; path: string; kind: string; chars: number };
  text: string;
  context: string;
  heading: string;
  section: string;
  annotation: Annotation | null;
  effect_fields: Record<string, string[]>;
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const token = tokenStore.get();
  const res = await fetch(`${API}${path}`, {
    ...init,
    headers: {
      ...(init?.body ? { "Content-Type": "application/json" } : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(init?.headers || {}),
    },
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(typeof err.detail === "string" ? err.detail : JSON.stringify(err.detail));
  }
  return res.json();
}

export const annotateApi = {
  sets: () => call<{ sets: SetSummary[]; guideline_version: number }>("/api/annotate/sets"),
  items: (set: string) => call<{ set: string; items: SetItem[] }>(`/api/annotate/sets/${set}`),
  item: (id: string) => call<ItemView>(`/api/annotate/items/${id}`),
  save: (id: string, ann: Annotation) =>
    call<{ saved: boolean; status: string; warnings: string[] }>(`/api/annotate/items/${id}`, {
      method: "PUT",
      body: JSON.stringify(ann),
    }),
};

export function emptyRule(): AnnRule {
  return {
    modality: "obligation", agent_class: null, subject: null, conditions: [], action: null,
    consequence: null, exceptions: [], cross_refs: [], effects: [], executable: true, note: "",
  };
}
