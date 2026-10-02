"use client";
import { motion } from "framer-motion";
import { Brain, Cpu, GitBranch, Microscope, Lock, ArrowRight, CheckCircle2 } from "lucide-react";
import { tokens, alpha } from "@/lib/tokens";

const MODULES = [
  {
    id: "A",
    phase: "Phase 1 — This Project",
    title: "Legal Cognition Engine",
    subtitle: "Module A",
    active: true,
    icon: Brain,
    color: tokens.accent.primary,
    glow: alpha(tokens.accent.primary, 0.26),
    border: alpha(tokens.accent.primary, 0.42),
    bg: `linear-gradient(160deg, ${alpha(tokens.accent.primary, 0.14)}, ${alpha(tokens.bg.surface, 0.92)})`,
    steps: [
      "PDF Parsing",
      "Clause Segmentation",
      "Legal NER (6 types)",
      "Causal Detection",
      "MiniLM Embeddings",
      "UMAP Clustering",
      "Provenance Graph",
    ],
  },
  {
    id: "B",
    phase: "Phase 3 — Active",
    title: "LLM Causal Extraction",
    subtitle: "Module B",
    active: true,
    icon: Cpu,
    color: tokens.entity.ACTOR.text,
    glow: alpha(tokens.entity.ACTOR.text, 0.18),
    border: alpha(tokens.entity.ACTOR.text, 0.3),
    bg: `linear-gradient(160deg, ${alpha(tokens.entity.ACTOR.text, 0.08)}, ${alpha(tokens.bg.surface, 0.9)})`,
    steps: [
      "Phi-3.5-mini via Ollama",
      "Structured JSON Rules",
      "LIME Explainability",
    ],
  },
  {
    id: "C",
    phase: "Phase 3 — Active",
    title: "Societal Simulation",
    subtitle: "Module C",
    active: true,
    icon: Microscope,
    color: tokens.entity.RIGHT.text,
    glow: alpha(tokens.entity.RIGHT.text, 0.18),
    border: alpha(tokens.entity.RIGHT.text, 0.3),
    bg: `linear-gradient(160deg, ${alpha(tokens.entity.RIGHT.text, 0.08)}, ${alpha(tokens.bg.surface, 0.9)})`,
    steps: [
      "Mesa Agent Framework",
      "5 Socioeconomic Strata",
      "Gini & Compliance Metrics",
    ],
  },
  {
    id: "D",
    phase: "Phase 3 — Active",
    title: "Policy Diff Arena",
    subtitle: "Module D",
    active: true,
    icon: GitBranch,
    color: tokens.entity.BENEFICIARY.text,
    glow: alpha(tokens.entity.BENEFICIARY.text, 0.18),
    border: alpha(tokens.entity.BENEFICIARY.text, 0.3),
    bg: `linear-gradient(160deg, ${alpha(tokens.entity.BENEFICIARY.text, 0.08)}, ${alpha(tokens.bg.surface, 0.9)})`,
    steps: [
      "Clause-level Diff",
      "Embedding Matching",
      "Comparative Simulation",
    ],
  },
];

export default function PipelineDiagram() {
  return (
    <div className="relative">
      <div className="hidden lg:block absolute top-[60px] left-[12.5%] right-[12.5%] h-px"
        style={{ background: `linear-gradient(90deg, ${alpha(tokens.accent.primary, 0.45)}, ${alpha(tokens.entity.ACTOR.text, 0.28)})` }} />
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {MODULES.map((mod, i) => {
          const Icon = mod.icon;
          return (
            <motion.div
              key={mod.id}
              initial={{ opacity: 0, y: 24 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.5, delay: i * 0.12 }}
              className="relative rounded-2xl p-5 flex flex-col gap-4"
              style={{
                border: `1px solid ${mod.border}`,
                background: mod.bg,
                boxShadow: mod.active ? `0 24px 42px ${mod.glow}` : "0 14px 24px rgba(0,0,0,0.2)",
              }}
            >
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-mono uppercase tracking-widest"
                  style={{ color: mod.active ? mod.color : tokens.text.muted }}>
                  {mod.phase}
                </span>
                {!mod.active ? (
                  <div className="flex items-center gap-1 px-2 py-0.5 rounded-full bg-bg-elevated/40 border border-border">
                    <Lock className="w-2.5 h-2.5 text-text-muted" />
                    <span className="text-[9px] font-mono uppercase tracking-wider text-text-muted">Soon</span>
                  </div>
                ) : (
                  <div className="flex items-center gap-1 px-2 py-0.5 rounded-full bg-status-success/10 border border-status-success/30">
                    <div className="w-1.5 h-1.5 rounded-full bg-status-success animate-pulse" />
                    <span className="text-[9px] font-mono text-status-success uppercase tracking-wider">Live</span>
                  </div>
                )}
              </div>

              <div className="w-12 h-12 rounded-xl flex items-center justify-center"
                style={{ background: alpha(mod.color, 0.09), border: `1px solid ${mod.border}` }}>
                <Icon className="w-6 h-6" style={{ color: mod.color }} />
              </div>

              <div>
                <p className="font-mono text-[11px] mb-0.5" style={{ color: mod.color }}>{mod.subtitle}</p>
                <h3 className="font-display font-bold text-base leading-tight text-text-primary">{mod.title}</h3>
              </div>

              <div className="space-y-1.5 flex-1">
                {mod.steps.map((step) => (
                  <div key={step} className="flex items-center gap-2">
                    {mod.active ? (
                      <CheckCircle2 className="w-3.5 h-3.5 flex-shrink-0" style={{ color: mod.color }} />
                    ) : (
                      <div className="w-3.5 h-3.5 flex-shrink-0 rounded-full border border-border" />
                    )}
                    <span className={`text-xs ${mod.active ? "text-text-secondary" : "text-text-muted"}`}>
                      {step}
                    </span>
                  </div>
                ))}
              </div>

              {i < MODULES.length - 1 && (
                <div className="lg:hidden flex justify-center mt-2">
                  <ArrowRight className="w-4 h-4 text-text-muted" />
                </div>
              )}
            </motion.div>
          );
        })}
      </div>
    </div>
  );
}
