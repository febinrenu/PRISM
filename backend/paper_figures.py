"""
Figures for the paper, generated from the same results as the tables
(called by reproduce.py; written to paper/figures/ as PDF and PNG).

    fig_assembly   systems × reforms: assembled law (conclusions compared) or
                   no conclusion, with the failure kind written in the cell
    fig_injection  injected error × reform: share of conclusions flipped
                   (single-hue sequential ramp; values shown where non-zero)
"""
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402

FIGURES = Path(__file__).resolve().parent.parent / "paper" / "figures"

# Reference palette (dataviz skill): surface, ink, sequential blue ramp.
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
GRID = "#e4e3df"
BLUE = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
ASSEMBLED = "#2a78d6"
NO_RESULT = "#e4e3df"

SET_LABELS = {
    "FA2020_new_regime": "FA 2020\nnew regime",
    "FA2020_old_schedule": "FA 2020\nold rates",
    "FA2023_new_default": "FA 2023\nnew default",
    "FA2023_old_schedule": "FA 2023\nold rates",
    "FA2024N2_budget": "FA 2024 (2)\nbudget",
    "FA2024N2_old_schedule": "FA 2024 (2)\nold rates",
    "FA2025_rebate_12L": "FA 2025\nRs 12 lakh",
    "FA2025_old_schedule": "FA 2025\nold rates",
    "FA2026_old_schedule_ITA2025": "FA 2026\nold rates",
    "ITA2025_new_act": "ITA 2025\nre-enacted",
}
SET_ORDER = list(SET_LABELS)
SYSTEM_ORDER = ["qwen3.8-27b", "gpt-oss-120b", "gpt-oss-20b", "rules", "phi3.5", "gemma2-2b"]
SYSTEM_LABELS = {"qwen3.8-27b": "Qwen3.8-27B", "gpt-oss-120b": "GPT-OSS-120B", "gpt-oss-20b": "GPT-OSS-20B",
                 "rules": "Rule baseline", "phi3.5": "Phi-3.5-mini", "gemma2-2b": "Gemma-2-2B"}

_REASON = [("conflicting", "regime\nscope"), ("open top band", "top\nband"), ("gap or overlap", "overlap"),
           ("no slab rows", "no\nrows"), ("no rebate", "no\nrebate"), ("no standard deduction", "no std.\ndeduction")]


def _short(reason: str) -> str:
    for key, label in _REASON:
        if key in reason:
            return label
    return "failed"


def _style(ax):
    ax.set_facecolor(SURFACE)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.tick_params(length=0, colors=INK_2, labelsize=7)


def fig_assembly(runs: list[dict]) -> Path:
    by = {(r["system"], r["set"]): r for r in runs}
    systems = [s for s in SYSTEM_ORDER if any(k[0] == s for k in by)]
    sets = [s for s in SET_ORDER if any(k[1] == s for k in by)]
    fig, ax = plt.subplots(figsize=(7.2, 0.42 * len(systems) + 1.1), facecolor=SURFACE)
    _style(ax)
    for i, system in enumerate(systems):
        for j, set_name in enumerate(sets):
            r = by.get((system, set_name))
            if r is None:
                continue
            if r["complete"]:
                flips = round(r["population"]["flip_rate"] * len(r["population"]["conclusions_expert"]))
                face, text, ink = ASSEMBLED, ("same" if flips == 0 else f"{flips} flipped"), "#ffffff"
            else:
                reasons = [x["reason"] for x in r.get("review", [])]
                face, text, ink = NO_RESULT, _short(reasons[0]) if reasons else "failed", INK_2
            ax.add_patch(plt.Rectangle((j + 0.04, i + 0.06), 0.92, 0.88, facecolor=face, edgecolor=SURFACE,
                                       linewidth=2, joinstyle="round"))
            ax.text(j + 0.5, i + 0.5, text, ha="center", va="center", fontsize=6, color=ink, linespacing=0.95)
    ax.set_xlim(0, len(sets))
    ax.set_ylim(len(systems), 0)
    ax.set_xticks([j + 0.5 for j in range(len(sets))], [SET_LABELS[s] for s in sets], fontsize=6.5)
    ax.xaxis.tick_top()
    ax.set_yticks([i + 0.5 for i in range(len(systems))], [SYSTEM_LABELS.get(s, s) for s in systems])
    handles = [plt.Rectangle((0, 0), 1, 1, color=ASSEMBLED), plt.Rectangle((0, 0), 1, 1, color=NO_RESULT)]
    ax.legend(handles, ["Assembled: conclusions compared with the expert's",
                        "No conclusion: assembly failed (cause in cell)"],
              loc="upper center", bbox_to_anchor=(0.5, -0.02), ncol=2, frameon=False, fontsize=7,
              labelcolor=INK_2, handlelength=1.2)
    return _save(fig, "assembly")


def fig_injection(rows: list[dict]) -> Path:
    sets = [s for s in SET_ORDER if any(r["set"] == s for r in rows)]
    errors = sorted({r["error"] for r in rows},
                    key=lambda e: -max(r["flip_rate"] for r in rows if r["error"] == e))
    grid = {}
    for r in rows:                      # worst target of the reform for that error
        k = (r["error"], r["set"])
        grid[k] = max(grid.get(k, 0.0), r["flip_rate"])
    cmap = LinearSegmentedColormap.from_list("seq", BLUE)
    vmax = max(grid.values(), default=1.0) or 1.0
    fig, ax = plt.subplots(figsize=(7.6, 0.3 * len(errors) + 1.2), facecolor=SURFACE)
    _style(ax)
    for i, e in enumerate(errors):
        for j, s in enumerate(sets):
            if (e, s) not in grid:
                continue                # error not applicable to this reform
            v = grid[(e, s)]
            face = SURFACE if v == 0 else cmap(v / vmax)
            ax.add_patch(plt.Rectangle((j + 0.04, i + 0.06), 0.92, 0.88, facecolor=face,
                                       edgecolor=GRID if v == 0 else SURFACE, linewidth=0.8 if v == 0 else 2))
            if v > 0:
                ax.text(j + 0.5, i + 0.5, f"{100 * v:.0f}", ha="center", va="center", fontsize=6,
                        color="#ffffff" if v / vmax > 0.5 else INK)
    ax.set_xlim(0, len(sets))
    ax.set_ylim(len(errors), 0)
    ax.set_xticks([j + 0.5 for j in range(len(sets))], [SET_LABELS[s] for s in sets], fontsize=5.8)
    ax.xaxis.tick_top()
    ax.set_yticks([i + 0.5 for i in range(len(errors))], [e.replace("_", " ") for e in errors])
    ax.text(0, len(errors) + 0.55, "Cell: % of the reform's conclusions flipped (outlined blank: none; "
            "empty: error not applicable)", fontsize=6.5, color=INK_2, va="top")
    return _save(fig, "error_injection")


def _save(fig, name: str) -> Path:
    FIGURES.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    for ext in ("pdf", "png"):
        fig.savefig(FIGURES / f"{name}.{ext}", dpi=200, facecolor=SURFACE, bbox_inches="tight")
    plt.close(fig)
    return FIGURES / f"{name}.pdf"


def all_figures(res_dir: Path, runs: list[dict]) -> list[Path]:
    out = [fig_assembly(runs)]
    inj = res_dir / "error_injection.json"
    if inj.exists():
        out.append(fig_injection(json.loads(inj.read_text(encoding="utf-8"))))
    return out
