"use client";
import { useState } from "react";
import Link from "next/link";
import { BarChart3, Network, Zap, ScatterChart, Search, Download, FlaskConical, Bot } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { useDocumentStore } from "@/hooks/useDocumentStore";
import { api } from "@/lib/api";
import OverviewTab from "./OverviewTab";
import EntityNetworkTab from "./EntityNetworkTab";
import CausalTab from "./CausalTab";
import EmbeddingTab from "./EmbeddingTab";
import SearchTab from "./SearchTab";
import LLMCompareTab from "./LLMCompareTab";
import { tokens } from "@/lib/tokens";

const TABS = [
  { key: "overview",  label: "Overview",  Icon: BarChart3    },
  { key: "causal",    label: "Causal",    Icon: Zap          },
  { key: "llm",       label: "LLM",       Icon: Bot          },
  { key: "search",    label: "Search",    Icon: Search       },
  { key: "network",   label: "Entities",  Icon: Network      },
  { key: "embedding", label: "UMAP",      Icon: ScatterChart },
] as const;

type TabKey = (typeof TABS)[number]["key"];

export default function AnalyticsTabs() {
  const [activeTab, setActiveTab] = useState<TabKey>("overview");
  const [exporting, setExporting] = useState(false);
  const { docId, stage } = useDocumentStore();

  const handleExport = () => {
    if (!docId || exporting) return;
    setExporting(true);
    api.downloadReport(docId);
    setTimeout(() => setExporting(false), 1500);
  };

  return (
    <div className="flex flex-col h-full min-h-0">
      {/* Tab bar */}
      <div className="flex-shrink-0 flex items-center gap-0 px-2 pt-2 pb-0 border-b border-border">
        {TABS.map((tab) => {
          const active = activeTab === tab.key;
          const Icon = tab.Icon;
          return (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`relative flex items-center gap-1.5 px-4 py-2.5 text-xs font-semibold transition-all duration-150 rounded-t ${
                active ? "text-text-primary bg-accent-primary/5" : "text-text-muted bg-transparent"
              }`}
            >
              <Icon style={{ width: 12, height: 12 }} />
              {tab.label}
              {active && (
                <motion.div
                  layoutId="tab-underline"
                  className="absolute bottom-0 left-0 right-0 h-[2px] rounded-t-full"
                  style={{ background: `linear-gradient(90deg, ${tokens.accent.primary}, ${tokens.accent.bright})` }}
                />
              )}
            </button>
          );
        })}

        {/* Actions — only shown after analysis is complete */}
        {stage === "complete" && docId && (
          <div className="ml-auto mr-2 flex items-center gap-2">
            <Link
              href={`/simulate/${docId}`}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[10px] font-mono font-semibold transition-all bg-status-success/10 border border-status-success/30 text-status-success hover:bg-status-success/20"
              title="Open the Simulation Theater"
            >
              <FlaskConical style={{ width: 11, height: 11 }} />
              Simulate
            </Link>
            <button
              onClick={handleExport}
              disabled={exporting}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[10px] font-mono font-semibold transition-all disabled:opacity-50 bg-accent-primary/10 border border-accent-primary/30 text-accent-primary hover:bg-accent-primary/20"
              title="Download HTML analysis report"
            >
              <Download style={{ width: 11, height: 11 }} />
              {exporting ? "Opening…" : "Export Report"}
            </button>
          </div>
        )}
      </div>

      {/* Tab content */}
      <div className="flex-1 overflow-hidden min-h-0">
        <AnimatePresence mode="wait">
          <motion.div
            key={activeTab}
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            transition={{ duration: 0.15 }}
            className="h-full"
          >
            {activeTab === "overview"  && <div className="h-full overflow-y-auto"><OverviewTab /></div>}
            {activeTab === "causal"    && <div className="h-full overflow-y-auto"><CausalTab /></div>}
            {activeTab === "llm"       && <div className="h-full overflow-y-auto"><LLMCompareTab /></div>}
            {activeTab === "search"    && <div className="h-full overflow-y-auto"><SearchTab /></div>}
            {activeTab === "network"   && <div className="h-full overflow-y-auto"><EntityNetworkTab /></div>}
            {activeTab === "embedding" && <div className="h-full overflow-y-auto"><EmbeddingTab /></div>}
          </motion.div>
        </AnimatePresence>
      </div>
    </div>
  );
}
