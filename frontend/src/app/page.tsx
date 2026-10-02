"use client";

import { motion } from "framer-motion";
import Link from "next/link";
import {
  Github,
  Brain,
  Network,
  Zap,
  GitBranch,
  Lock,
  ChevronRight,
  Sparkles,
  Cpu,
  ScanSearch,
  Users,
  GitCompare,
  MessageSquare,
  Layers,
} from "lucide-react";
import UploadZone from "@/components/landing/UploadZone";
import PipelineDiagram from "@/components/landing/PipelineDiagram";
import DocumentCorpus from "@/components/landing/DocumentCorpus";
import PrismMark from "@/components/brand/PrismMark";
import { tokens, alpha } from "@/lib/tokens";

const TICKER_ITEMS = [
  "LEGAL NAMED ENTITY RECOGNITION",
  "CAUSAL PATTERN DETECTION",
  "LLM CAUSAL EXTRACTION",
  "LIME + ATTENTION XAI",
  "SEMANTIC EMBEDDINGS",
  "UMAP CLUSTERING",
  "PROVENANCE GRAPH",
  "SOCIOECONOMIC SIMULATION",
  "POLICY DIFF ARENA",
  "REAL-TIME SSE STREAMING",
];

const STATS = [
  { value: "6", label: "Entity Types" },
  { value: "5", label: "Agent Strata" },
  { value: "16", label: "Policy Templates" },
  { value: "100%", label: "Local & Private" },
];

const FEATURES = [
  {
    icon: Brain,
    title: "Legal NER",
    desc: "Tags obligations, rights, penalties, thresholds, actors, and beneficiaries via spaCy and custom legal rules.",
    color: tokens.entity.OBLIGATION.base,
    bg: alpha(tokens.entity.OBLIGATION.base, 0.12),
    border: alpha(tokens.entity.OBLIGATION.base, 0.22),
  },
  {
    icon: Zap,
    title: "Causal Detection",
    desc: "Finds IF-THEN and condition-action structures that encode policy behavior and compliance triggers.",
    color: tokens.accent.primary,
    bg: alpha(tokens.accent.primary, 0.08),
    border: alpha(tokens.accent.primary, 0.24),
  },
  {
    icon: Network,
    title: "Semantic Clustering",
    desc: "Projects MiniLM embeddings to 2D UMAP space so similar legal clauses become immediately visible.",
    color: tokens.entity.RIGHT.base,
    bg: alpha(tokens.entity.RIGHT.base, 0.08),
    border: alpha(tokens.entity.RIGHT.base, 0.24),
  },
  {
    icon: GitBranch,
    title: "Provenance Graph",
    desc: "Builds a traceable graph from Document to Clause to Entity and Causal links for transparent auditability.",
    color: tokens.entity.ACTOR.base,
    bg: alpha(tokens.entity.ACTOR.base, 0.08),
    border: alpha(tokens.entity.ACTOR.base, 0.24),
  },
  {
    icon: Cpu,
    title: "LLM Causal Extraction",
    desc: "A local Phi-3.5-mini reads each clause and extracts structured causal rules (condition → action → consequence) as JSON, cross-checked against the rule-based pass.",
    color: tokens.entity.BENEFICIARY.base,
    bg: alpha(tokens.entity.BENEFICIARY.base, 0.1),
    border: alpha(tokens.entity.BENEFICIARY.base, 0.24),
  },
  {
    icon: ScanSearch,
    title: "Explainability Studio",
    desc: "Every extraction is explained token-by-token with LIME, a transformer-attention lens, and on-demand deep reasoning — no black boxes.",
    color: tokens.status.warning,
    bg: alpha(tokens.status.warning, 0.1),
    border: alpha(tokens.status.warning, 0.22),
  },
  {
    icon: Users,
    title: "Socioeconomic Simulation",
    desc: "A Mesa agent-based model of five income strata simulates a law's revenue, compliance, and who actually bears the burden — with an auditable assumptions panel.",
    color: tokens.entity.PENALTY.base,
    bg: alpha(tokens.entity.PENALTY.base, 0.1),
    border: alpha(tokens.entity.PENALTY.base, 0.24),
  },
  {
    icon: GitCompare,
    title: "Policy Diff Arena",
    desc: "Compare two statutes clause-by-clause via embedding matching, and simulate both to see how the socioeconomic impact shifts.",
    color: tokens.status.info,
    bg: alpha(tokens.status.info, 0.1),
    border: alpha(tokens.status.info, 0.22),
  },
  {
    icon: MessageSquare,
    title: "RAG Legal Assistant",
    desc: "Ask questions across the whole corpus and get grounded, source-cited answers from a ChromaDB retriever — every claim traces to a clause, nothing is invented.",
    color: tokens.entity.RIGHT.base,
    bg: alpha(tokens.entity.RIGHT.base, 0.1),
    border: alpha(tokens.entity.RIGHT.base, 0.24),
  },
  {
    icon: Layers,
    title: "Fine-Tuned Legal LLM",
    desc: "A QLoRA-specialised Phi-3.5 (PRISM-Legal) trained on the pipeline's own extractions, plus a deployable multi-user API with keys, auth, and a public /v1 surface.",
    color: tokens.accent.primary,
    bg: alpha(tokens.accent.primary, 0.1),
    border: alpha(tokens.accent.primary, 0.24),
  },
];

export default function LandingPage() {
  return (
    <main className="relative min-h-screen overflow-x-hidden app-shell bg-bg-base text-text-primary">
      <div className="animated-grid" />
      <div className="noise-overlay" />

      <div className="content-layer">
        <nav className="relative z-20 px-6 md:px-10 pt-6 max-w-7xl mx-auto">
          <div
            className="rounded-md px-4 sm:px-5 py-3 flex items-center justify-between glass-card backdrop-blur-md"
          >
            <div className="flex items-center gap-3">
              <PrismMark size={40} />
              <div>
                <span className="font-display font-bold tracking-tight text-lg text-text-primary">
                  PRISM
                </span>
                <span className="ml-2 text-[10px] font-mono px-1.5 py-0.5 rounded-sm uppercase tracking-widest text-accent-primary border border-accent-primary/35 bg-accent-primary/10">
                  Experience v2
                </span>
              </div>
            </div>
            <div className="flex items-center gap-6 text-xs uppercase tracking-widest font-mono text-text-secondary">
              <Link href="/chat" className="hidden md:block transition-colors hover:text-text-primary">
                Chat
              </Link>
              <Link href="/corpus" className="hidden md:block transition-colors hover:text-text-primary">
                Corpus
              </Link>
              <Link href="/dashboard" className="hidden md:block transition-colors hover:text-text-primary">
                Dashboard
              </Link>
              <a href="#features" className="hidden lg:block transition-colors hover:text-text-primary">
                Features
              </a>
              <a
                href="https://github.com"
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-2 px-3 py-1.5 transition-all text-xs border border-light hover:border-glow bg-bg-deep"
              >
                <Github className="w-3.5 h-3.5" />
                <span className="hidden sm:block">GitHub</span>
              </a>
            </div>
          </div>
        </nav>

        <div className="relative z-10 overflow-hidden mt-7 py-2.5 border-y border-accent-primary/20 bg-bg-deep">
          <div className="ticker-track">
            {[...TICKER_ITEMS, ...TICKER_ITEMS].map((item, i) => (
              <span
                key={i}
                className="inline-flex items-center gap-4 px-6 font-mono text-[11px] font-medium tracking-[0.1em] uppercase text-text-muted"
              >
                {item}
                <span className="text-accent-primary/50">/ / /</span>
              </span>
            ))}
          </div>
        </div>

        <section className="relative z-10 pt-16 pb-12 px-6 max-w-7xl mx-auto">
          <div className="max-w-5xl">
            <motion.div
              initial={{ opacity: 0, y: -8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5 }}
              className="inline-flex items-center gap-2.5 mb-8 px-3 py-1.5 rounded-sm font-mono text-[10px] uppercase tracking-widest border-l-[3px] border-accent-primary bg-bg-surface text-text-secondary"
            >
              <Sparkles className="w-3.5 h-3.5 text-accent-primary" />
              Legal Cognition Engine // Phase 3 // Extraction · Explainability · Simulation
            </motion.div>

            <h1 className="font-display font-medium leading-[0.92] tracking-tight uppercase">
              {[
                { word: "STATUTE", cls: "font-normal text-text-primary" },
                { word: "INTELLIGENCE", cls: "hero-gradient font-semibold" },
                { word: "ENGINE", cls: "font-normal text-text-muted" },
              ].map((line, i) => (
                <motion.span
                  key={line.word}
                  initial={{ opacity: 0, y: 34 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.65, delay: 0.12 + i * 0.14, ease: [0.22, 1, 0.36, 1] }}
                  className={`block text-[clamp(52px,9vw,114px)] ${line.cls}`}
                >
                  {line.word}
                </motion.span>
              ))}
            </h1>

            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.4 }}
              className="mt-8 flex flex-col md:flex-row md:items-end gap-8"
            >
              <p className="max-w-lg text-[15px] leading-relaxed text-text-secondary">
                A local-first system that reads dense legal texts, extracts causal
                rules with a local LLM, explains every extraction token by token,
                and simulates the law’s socioeconomic impact on a synthetic society.
              </p>

              <div className="flex flex-wrap gap-4">
                <a
                  href="#demo"
                  className="flex items-center gap-2 px-8 py-3.5 font-mono text-xs uppercase tracking-widest transition-all glass-card glass-card-hover font-semibold text-text-inverse bg-accent-primary border-accent-primary"
                >
                  <Lock className="w-4 h-4" />
                  Local Analysis
                </a>
                <a
                  href="#pipeline"
                  className="group flex items-center gap-2 px-8 py-3.5 font-mono text-xs uppercase tracking-widest transition-all glass-card glass-card-hover text-text-primary"
                >
                  View Pipeline
                  <ChevronRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
                </a>
              </div>
            </motion.div>
          </div>
        </section>

        <section id="demo" className="relative z-10 py-16 px-6 max-w-7xl mx-auto">
          <div className="grid lg:grid-cols-3 gap-8">
            <div className="lg:col-span-2">
              <div className="glass-card p-1 md:p-3">
                <UploadZone />
              </div>
            </div>
            <div className="flex flex-col gap-6">
              <div className="glass-card p-6 flex flex-col justify-center flex-1" style={{ minHeight: "220px" }}>
                <div className="flex items-center gap-3 mb-4">
                  <Lock className="w-5 h-5 text-accent-primary" />
                  <h3 className="font-display text-xl uppercase tracking-wider text-text-primary">Privacy-First</h3>
                </div>
                <p className="text-sm leading-relaxed text-text-secondary">
                  All parsing, embeddings, and entity recognition happen entirely
                  within the local environment. Zero external API calls ensures absolute client confidentiality.
                </p>
              </div>

              <div className="grid grid-cols-2 gap-4 flex-1">
                {STATS.map((stat, i) => (
                  <div key={i} className="glass-card p-5 flex flex-col justify-center">
                    <div className="font-display text-3xl mb-1 text-accent-primary">
                      {stat.value}
                    </div>
                    <div className="font-mono text-[9px] uppercase tracking-widest text-text-muted">
                      {stat.label}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </section>

        <section id="corpus" className="relative z-10 py-16 px-6 max-w-7xl mx-auto">
          <DocumentCorpus />
        </section>

        <div id="features" className="relative z-10 py-24 border-t border-border bg-bg-deep">
          <div className="max-w-7xl mx-auto px-6">
            <div className="flex items-center gap-4 mb-16">
              <div className="h-px flex-1 bg-border" />
              <h2 className="font-display text-2xl uppercase tracking-widest text-text-primary">Capabilities</h2>
              <div className="h-px flex-1 bg-border" />
            </div>

            <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-6">
              {FEATURES.map((feature, i) => {
                const Icon = feature.icon;
                return (
                  <div key={i} className="glass-card p-6 md:p-8 group glass-card-hover">
                    <div
                      className="w-12 h-12 rounded-sm flex items-center justify-center mb-6 transition-transform group-hover:scale-110"
                      style={{ border: "1px solid " + feature.border, background: feature.bg }}
                    >
                      <Icon className="w-5 h-5" style={{ color: feature.color }} />
                    </div>
                    <h3 className="font-display text-lg uppercase tracking-wider mb-3 text-text-primary">
                      {feature.title}
                    </h3>
                    <p className="text-[13px] leading-relaxed text-text-secondary">
                      {feature.desc}
                    </p>
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        <section id="pipeline" className="relative z-10 py-24 px-6 max-w-7xl mx-auto">
          <div className="glass-card p-1 md:p-8">
            <PipelineDiagram />
          </div>
        </section>

        <footer className="relative z-10 py-12 border-t border-border">
          <div className="max-w-7xl mx-auto px-6 flex flex-col sm:flex-row items-center justify-between gap-4">
            <div className="flex items-center gap-3 grayscale opacity-60">
              <PrismMark size={24} />
              <span className="font-display font-medium tracking-widest uppercase text-sm text-text-primary">
                PRISM
              </span>
            </div>
            <p className="font-mono text-[10px] uppercase tracking-widest text-text-muted">
              © 2026 PRISM // LEGAL COGNITION ENGINE
            </p>
          </div>
        </footer>
      </div>
    </main>
  );
}
