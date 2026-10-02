"use client";
import { useState } from "react";
import { Loader2, Play } from "lucide-react";
import { Slider } from "@/components/ui/slider";
import { alpha, tokens, type AgentType } from "@/lib/tokens";
import type { AgentTypeKey, CalibrationMode, SimulationRuleInfo } from "@/types";

const AGENT_SLIDERS: Array<{ key: AgentTypeKey; label: string; max: number; default: number }> = [
  { key: "low_income", label: "Low income households", max: 1000, default: 500 },
  { key: "middle_income", label: "Middle income households", max: 1000, default: 300 },
  { key: "high_income", label: "High income households", max: 500, default: 150 },
  { key: "small_business", label: "Small businesses", max: 300, default: 100 },
  { key: "large_corporate", label: "Large corporates", max: 100, default: 20 },
];

export interface ControlValues {
  agentConfig: Record<AgentTypeKey, number>;
  nSteps: number;
  ruleClauseIds: string[] | null;
  adaptive: boolean;
  calibrationMode: CalibrationMode;
}

const CALIBRATION_OPTIONS: Array<{ value: CalibrationMode; label: string; hint: string }> = [
  { value: "nsso", label: "Calibrated (NSSO/PLFS)", hint: "Income & consumption distributions from national survey data" },
  { value: "legacy", label: "Illustrative ranges", hint: "Hand-set demo ranges — faster to reason about, not survey-grounded" },
];

interface Props {
  running: boolean;
  availableRules: SimulationRuleInfo[] | null;
  prefilterClauseId?: string | null;
  onRun: (values: ControlValues) => void;
}

export default function SimulationControls({ running, availableRules, prefilterClauseId, onRun }: Props) {
  const [agents, setAgents] = useState<Record<AgentTypeKey, number>>(
    Object.fromEntries(AGENT_SLIDERS.map((s) => [s.key, s.default])) as Record<AgentTypeKey, number>
  );
  const [nSteps, setNSteps] = useState(50);
  const [adaptive, setAdaptive] = useState(true);
  const [calibrationMode, setCalibrationMode] = useState<CalibrationMode>("nsso");
  const [selectedRules, setSelectedRules] = useState<Set<string> | null>(
    prefilterClauseId ? new Set([prefilterClauseId]) : null
  );

  const totalAgents = Object.values(agents).reduce((a, b) => a + b, 0);

  const toggleRule = (clauseId: string) => {
    setSelectedRules((prev) => {
      const next = new Set(prev ?? []);
      if (next.has(clauseId)) next.delete(clauseId);
      else next.add(clauseId);
      return next.size === 0 ? null : next;
    });
  };

  return (
    <div className="glass-card p-6 space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-x-8 gap-y-5">
        {AGENT_SLIDERS.map((slider) => (
          <div key={slider.key}>
            <div className="flex items-center justify-between mb-1">
              <label className="text-[11px] font-mono text-text-secondary flex items-center gap-2">
                <span
                  className="inline-block w-2 h-2 rounded-full"
                  style={{ background: tokens.agent[slider.key as AgentType] }}
                />
                {slider.label}
              </label>
              <span className="text-xs font-display text-text-primary">{agents[slider.key]}</span>
            </div>
            <Slider
              min={0}
              max={slider.max}
              step={10}
              value={[agents[slider.key]]}
              onValueChange={([v]) => setAgents((a) => ({ ...a, [slider.key]: v }))}
              disabled={running}
            />
          </div>
        ))}

        <div>
          <div className="flex items-center justify-between mb-1">
            <label className="text-[11px] font-mono text-text-secondary">Simulation steps (months)</label>
            <span className="text-xs font-display text-text-primary">{nSteps}</span>
          </div>
          <Slider
            min={10}
            max={100}
            step={5}
            value={[nSteps]}
            onValueChange={([v]) => setNSteps(v)}
            disabled={running}
          />
        </div>
      </div>

      {/* Calibration mode */}
      <div className="rounded-lg border border-border px-4 py-3">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <div className="min-w-0">
            <p className="text-[11px] font-mono text-text-secondary">Agent calibration</p>
            <p className="text-[10px] font-mono text-text-dim mt-0.5">
              {CALIBRATION_OPTIONS.find((o) => o.value === calibrationMode)?.hint}
            </p>
          </div>
          <div className="flex rounded-lg border border-border overflow-hidden flex-shrink-0">
            {CALIBRATION_OPTIONS.map((opt) => {
              const active = calibrationMode === opt.value;
              return (
                <button
                  key={opt.value}
                  type="button"
                  onClick={() => setCalibrationMode(opt.value)}
                  disabled={running}
                  className="px-3 py-1.5 text-[10px] font-mono uppercase tracking-wider transition-colors disabled:opacity-50"
                  style={{
                    background: active ? alpha(tokens.accent.primary, 0.15) : "transparent",
                    color: active ? tokens.accent.primary : tokens.text.dim,
                  }}
                >
                  {opt.label}
                </button>
              );
            })}
          </div>
        </div>
      </div>

      {/* Adaptive agents toggle */}
      <div className="flex items-center justify-between rounded-lg border border-border px-4 py-3">
        <div>
          <p className="text-[11px] font-mono text-text-secondary">Adaptive agents (Q-learning)</p>
          <p className="text-[10px] font-mono text-text-dim mt-0.5">
            Agents learn a comply/defect policy over the run instead of a fixed tendency —
            watch behavior converge as enforcement bites.
          </p>
        </div>
        <button
          type="button"
          role="switch"
          aria-checked={adaptive}
          onClick={() => setAdaptive((v) => !v)}
          disabled={running}
          className="relative w-11 h-6 rounded-full transition-colors flex-shrink-0 disabled:opacity-50"
          style={{ background: adaptive ? tokens.status.success : tokens.bg.elevated }}
        >
          <span
            className="absolute top-0.5 left-0.5 w-5 h-5 rounded-full bg-text-primary transition-transform"
            style={{ transform: adaptive ? "translateX(20px)" : "none" }}
          />
        </button>
      </div>

      {/* Rule filter */}
      {availableRules && availableRules.length > 0 && (
        <div>
          <p className="kicker !text-[9px] mb-2">
            Active policy rules{" "}
            <span className="text-text-dim normal-case tracking-normal">
              — {selectedRules ? `${selectedRules.size} selected` : "all"}
            </span>
          </p>
          <div className="flex flex-wrap gap-1.5 max-h-28 overflow-y-auto pr-1">
            {availableRules.map((rule) => {
              const active = selectedRules === null || selectedRules.has(rule.clause_id);
              return (
                <button
                  key={rule.clause_id}
                  onClick={() => toggleRule(rule.clause_id)}
                  disabled={running}
                  className={`entity-pill border transition-colors max-w-[260px] ${
                    active
                      ? "border-accent-primary/50 bg-accent-primary/10 text-accent-primary"
                      : "border-border text-text-dim hover:text-text-muted"
                  }`}
                  title={rule.description}
                >
                  <span className="truncate">
                    {rule.rate_percent != null ? `${rule.rate_percent}% · ` : ""}
                    {rule.description.slice(0, 42)}
                  </span>
                </button>
              );
            })}
          </div>
        </div>
      )}

      <div className="flex items-center gap-4 pt-1">
        <button
          onClick={() =>
            onRun({
              agentConfig: agents,
              nSteps,
              ruleClauseIds: selectedRules ? Array.from(selectedRules) : null,
              adaptive,
              calibrationMode,
            })
          }
          disabled={running || totalAgents === 0}
          className={`flex items-center gap-2 px-6 py-3 rounded-lg text-xs font-mono font-bold uppercase tracking-[0.15em] transition-all disabled:opacity-60 ${
            running
              ? "bg-status-success/10 border border-status-success/40 text-status-success animate-pulse-soft"
              : "bg-accent-primary text-text-inverse hover:bg-accent-bright"
          }`}
        >
          {running ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" /> Simulating…
            </>
          ) : (
            <>
              <Play className="w-4 h-4" /> Run simulation
            </>
          )}
        </button>
        <p className="text-[10px] font-mono text-text-dim">
          {totalAgents.toLocaleString()} agents · {nSteps} steps · Mesa ABM · seeded
        </p>
      </div>
    </div>
  );
}
