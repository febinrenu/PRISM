"use client";
import { useState } from "react";
import { BarChart3, Network, Zap, ScatterChart, Search, Bot, Table2 } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import OverviewTab from "./OverviewTab";
import EntityNetworkTab from "./EntityNetworkTab";
import CausalTab from "./CausalTab";
import EmbeddingTab from "./EmbeddingTab";
import SearchTab from "./SearchTab";
import LLMCompareTab from "./LLMCompareTab";
import RatesTab from "./RatesTab";
import { tokens } from "@/lib/tokens";

const TABS = [
  { key: "overview",  label: "Overview",  Icon: BarChart3    },
  { key: "causal",    label: "Causal",    Icon: Zap          },
  { key: "llm",       label: "LLM",       Icon: Bot          },
  { key: "rates",     label: "Rates",     Icon: Table2       },
  { key: "search",    label: "Search",    Icon: Search       },
  { key: "network",   label: "Entities",  Icon: Network      },
  { key: "embedding", label: "UMAP",      Icon: ScatterChart },
] as const;

type TabKey = (typeof TABS)[number]["key"];

export default function AnalyticsTabs() {
  const [activeTab, setActiveTab] = useState<TabKey>("overview");


  return (
    <div className="flex flex-col h-full min-h-0">
      {/* Tab bar: scrolls sideways when the panel is narrow. The sandbox and the
          report are tabs of the document bar above, so they are not repeated here. */}
      <div
        role="tablist"
        aria-label="Analysis views"
        className="scroll-thin flex flex-shrink-0 items-center gap-0 overflow-x-auto overflow-y-hidden whitespace-nowrap border-b border-border px-2 pt-2"
      >
        {TABS.map((tab) => {
          const active = activeTab === tab.key;
          const Icon = tab.Icon;
          return (
            <button
              key={tab.key}
              type="button"
              role="tab"
              aria-selected={active}
              onClick={() => setActiveTab(tab.key)}
              className={`relative flex shrink-0 items-center gap-1.5 rounded-t px-3.5 py-2.5 text-xs font-semibold transition-colors duration-150 ${
                active ? "bg-accent-primary/5 text-text-primary" : "bg-transparent text-text-muted hover:text-text-secondary"
              }`}
            >
              <Icon style={{ width: 12, height: 12 }} aria-hidden />
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
            {activeTab === "rates"     && <div className="h-full overflow-y-auto"><RatesTab /></div>}
            {activeTab === "search"    && <div className="h-full overflow-y-auto"><SearchTab /></div>}
            {activeTab === "network"   && <div className="h-full overflow-y-auto"><EntityNetworkTab /></div>}
            {activeTab === "embedding" && <div className="h-full overflow-y-auto"><EmbeddingTab /></div>}
          </motion.div>
        </AnimatePresence>
      </div>
    </div>
  );
}
