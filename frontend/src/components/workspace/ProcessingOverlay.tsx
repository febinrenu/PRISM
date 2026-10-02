"use client";
import { motion, AnimatePresence } from "framer-motion";
import { CheckCircle2, Loader2, AlertCircle, FileText, Brain, Zap, Cpu, GitBranch } from "lucide-react";
import { useDocumentStore } from "@/hooks/useDocumentStore";
import PrismMark from "@/components/brand/PrismMark";
import { tokens, alpha } from "@/lib/tokens";

const STAGES = [
  { key: "parsing",      icon: FileText,   label: "PDF Parsing",         desc: "Extracting text and bounding boxes" },
  { key: "segmentation", icon: Brain,      label: "Clause Segmentation", desc: "Detecting structural boundaries" },
  { key: "ner",          icon: Cpu,        label: "Legal NER",           desc: "Extracting entities & causal patterns" },
  { key: "embedding",    icon: Zap,        label: "Semantic Embeddings", desc: "MiniLM + UMAP projection" },
  { key: "graph",        icon: GitBranch,  label: "Provenance Graph",    desc: "Building knowledge structure" },
] as const;

const STAGE_ORDER = STAGES.map((s) => s.key);

function getStageStatus(stageKey: string, currentStage: string): "done" | "active" | "pending" {
  if (currentStage === "complete") return "done";
  const ci = STAGE_ORDER.indexOf(currentStage as (typeof STAGE_ORDER)[number]);
  const si = STAGE_ORDER.indexOf(stageKey   as (typeof STAGE_ORDER)[number]);
  if (ci < 0 || si < 0) return "pending";
  if (si < ci) return "done";
  if (si === ci) return "active";
  return "pending";
}

export default function ProcessingOverlay() {
  const { stage, stageMessage, totalClauses, processedCount, filename } = useDocumentStore();
  const visible = stage !== "idle" && stage !== "complete";

  return (
    <AnimatePresence>
      {visible && (
        <motion.div
          key="overlay"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0, transition: { duration: 0.6, delay: 0.2 } }}
          className="fixed inset-0 z-50 flex items-center justify-center bg-bg-deep/95"
        >
          {/* Ambient glow */}
          <div className="absolute inset-0 overflow-hidden pointer-events-none">
            <motion.div
              className="absolute rounded-full"
              style={{
                width: 600, height: 600,
                background: `radial-gradient(circle, ${alpha(tokens.accent.primary, 0.07)} 0%, transparent 70%)`,
                top: "50%", left: "50%", transform: "translate(-50%,-50%)",
              }}
              animate={{ scale: [1, 1.4, 1] }}
              transition={{ duration: 6, repeat: Infinity, ease: "easeInOut" }}
            />
          </div>

          <div className="relative z-10 w-full max-w-xl mx-auto px-6">
            {/* Header */}
            <motion.div initial={{ opacity: 0, y: -20 }} animate={{ opacity: 1, y: 0 }} className="text-center mb-10">
              <div className="relative w-16 h-16 mx-auto mb-6">
                <motion.div
                  className="absolute inset-0 rounded-2xl"
                  style={{ background: `linear-gradient(135deg, ${tokens.accent.primary}, ${tokens.accent.bright}, ${tokens.accent.secondary}, ${tokens.accent.primary})` }}
                  animate={{ rotate: 360 }}
                  transition={{ duration: 6, repeat: Infinity, ease: "linear" }}
                />
                <div className="absolute inset-[2px] rounded-[10px] flex items-center justify-center bg-bg-base">
                  <PrismMark size={30} />
                </div>
              </div>
              <h2 className="font-display font-bold text-2xl mb-1 text-text-primary">
                {stage === "error" ? "Analysis Failed" : "Running Pipeline…"}
              </h2>
              <p className="text-sm font-mono truncate max-w-xs mx-auto text-text-secondary">
                {filename || "document.pdf"}
              </p>
            </motion.div>

            {/* Stages */}
            {stage !== "error" ? (
              <div className="space-y-2.5">
                {STAGES.map((s, i) => {
                  const status = getStageStatus(s.key, stage);
                  const Icon = s.icon;
                  const isNer = s.key === "ner";
                  const nerPct = isNer && totalClauses > 0 ? (processedCount / totalClauses) * 100 : 0;

                  return (
                    <motion.div
                      key={s.key}
                      initial={{ opacity: 0, x: -16 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: i * 0.07 }}
                      className="rounded-xl p-4"
                      style={{
                        background: status === "active"
                          ? alpha(tokens.accent.primary, 0.07)
                          : status === "done"
                          ? alpha(tokens.status.success, 0.04)
                          : alpha(tokens.bg.surface, 0.5),
                        border: status === "active"
                          ? `1px solid ${alpha(tokens.accent.primary, 0.28)}`
                          : status === "done"
                          ? `1px solid ${alpha(tokens.status.success, 0.18)}`
                          : `1px solid ${tokens.border.DEFAULT}`,
                      }}
                    >
                      <div className="flex items-center gap-3.5">
                        <div className="w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0"
                          style={{
                            background: status === "active"
                              ? alpha(tokens.accent.primary, 0.15)
                              : status === "done"
                              ? alpha(tokens.status.success, 0.12)
                              : alpha(tokens.bg.elevated, 0.6),
                          }}>
                          {status === "done" ? (
                            <CheckCircle2 className="text-status-success" style={{ width: 18, height: 18 }} />
                          ) : status === "active" ? (
                            <motion.div animate={{ rotate: 360 }} transition={{ duration: 1.4, repeat: Infinity, ease: "linear" }}>
                              <Loader2 className="text-accent-primary" style={{ width: 16, height: 16 }} />
                            </motion.div>
                          ) : (
                            <Icon className="text-text-muted" style={{ width: 16, height: 16 }} />
                          )}
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center justify-between mb-0.5">
                            <span className={`font-semibold text-sm ${status === "pending" ? "text-text-muted" : "text-text-primary"}`}>
                              {s.label}
                            </span>
                            {status === "active" && isNer && totalClauses > 0 && (
                              <span className="text-xs font-mono text-accent-primary">
                                {processedCount}/{totalClauses}
                              </span>
                            )}
                            {status === "done" && (
                              <span className="text-[10px] font-mono uppercase tracking-wider text-status-success">Done</span>
                            )}
                          </div>
                          <p className="text-xs text-text-muted">
                            {status === "active" && stageMessage ? stageMessage : s.desc}
                          </p>
                          {status === "active" && (
                            <div className="mt-2 h-[3px] rounded-full overflow-hidden bg-border">
                              {isNer && totalClauses > 0 ? (
                                <motion.div
                                  className="h-full rounded-full"
                                  style={{ background: `linear-gradient(90deg, ${tokens.accent.primary}, ${tokens.accent.bright})` }}
                                  animate={{ width: `${nerPct}%` }}
                                  transition={{ duration: 0.25 }}
                                />
                              ) : (
                                <motion.div
                                  className="h-full rounded-full w-1/3"
                                  style={{ background: `linear-gradient(90deg, ${tokens.accent.primary}, ${tokens.accent.bright})` }}
                                  animate={{ x: ["-200%", "500%"] }}
                                  transition={{ duration: 2, repeat: Infinity, ease: "easeInOut" }}
                                />
                              )}
                            </div>
                          )}
                        </div>
                      </div>
                    </motion.div>
                  );
                })}
              </div>
            ) : (
              <motion.div
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                className="rounded-2xl p-8 text-center bg-status-error/10 border border-status-error/20"
              >
                <AlertCircle className="w-12 h-12 mx-auto mb-4 text-status-error" />
                <p className="font-semibold text-lg mb-2 text-status-error">Analysis Failed</p>
                <p className="text-sm leading-relaxed text-text-secondary">
                  {stageMessage || "An unexpected error occurred. Check that the backend is running."}
                </p>
              </motion.div>
            )}

            {stage !== "error" && (
              <motion.p
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 1 }}
                className="text-center text-[11px] mt-6 font-mono text-text-dim"
              >
                First run downloads sentence-transformer model (~80MB)
              </motion.p>
            )}
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
