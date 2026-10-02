"""
Generate/collect all figures the paper references into paper/figures/.

- Copies the eval-harness charts (causal_f1.png, sim_validity.png) from
  backend/eval/results/ if present.
- Draws a clean architecture diagram (matplotlib) so the paper builds without a
  hand-made asset.

    python paper/make_figures.py
"""
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIG = HERE / "figures"
RESULTS = HERE.parent / "backend" / "eval" / "results"


def collect_eval_charts() -> list[str]:
    FIG.mkdir(parents=True, exist_ok=True)
    copied = []
    for name in ("causal_f1.png", "sim_validity.png"):
        src = RESULTS / name
        if src.exists():
            shutil.copy(src, FIG / name)
            copied.append(name)
    return copied


def draw_architecture() -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

    fig, ax = plt.subplots(figsize=(7.2, 3.6))
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 6)
    ax.axis("off")

    modules = [
        (0.5, "A\nLegal NLP", "#345C4B"),
        (2.8, "B\nLLM + XAI", "#B07D4C"),
        (5.1, "C\nSimulation", "#8B444A"),
        (7.4, "D\nRAG", "#597387"),
        (9.7, "E\nQLoRA", "#62506B"),
    ]
    for x, label, color in modules:
        box = FancyBboxPatch((x, 3.4), 2.0, 1.4, boxstyle="round,pad=0.08",
                             linewidth=1.2, edgecolor=color, facecolor=color + "33")
        ax.add_patch(box)
        ax.text(x + 1.0, 4.1, label, ha="center", va="center", fontsize=9, color="#222")
    for i in range(len(modules) - 1):
        x0 = modules[i][0] + 2.0
        x1 = modules[i + 1][0]
        ax.add_patch(FancyArrowPatch((x0, 4.1), (x1, 4.1), arrowstyle="-|>",
                                     mutation_scale=12, color="#666"))

    # Provenance band under all modules.
    ax.add_patch(FancyBboxPatch((0.5, 1.2), 11.2, 1.1, boxstyle="round,pad=0.08",
                                linewidth=1.0, edgecolor="#C5A880", facecolor="#C5A88022"))
    ax.text(6.1, 1.75, "Provenance: outcome → rule → clause (page/bbox) → LIME tokens",
            ha="center", va="center", fontsize=8.5, color="#8a6d3b")
    for x, _, _ in modules:
        ax.add_patch(FancyArrowPatch((x + 1.0, 3.4), (x + 1.0, 2.3), arrowstyle="-",
                                     linewidth=0.8, color="#C5A880", linestyle=":"))

    ax.text(6.1, 5.5, "PRISM — statute PDF → structured, explainable, simulatable intelligence",
            ha="center", va="center", fontsize=10, weight="bold", color="#333")
    fig.tight_layout()
    fig.savefig(FIG / "architecture.png", dpi=160, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    copied = collect_eval_charts()
    draw_architecture()
    print(f"[ok] figures -> {FIG}")
    print(f"     collected from eval: {copied or 'none (run eval.run_benchmark first)'}")
    print("     drew: architecture.png")


if __name__ == "__main__":
    main()
