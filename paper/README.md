# Paper

`sn-article.tex` is the manuscript for *Artificial Intelligence and Law*
(Springer Nature template `sn-jnl.cls`, author–year references). Compile on
Overleaf from the "Springer Nature Article" template, or locally with the
class files from Springer.

## Every number comes from a table file

The results sections `\input` the files in `tables/`, which are generated,
never edited by hand:

```bash
cd backend
python -m cli reproduce            # all tables from frozen inputs and cached model outputs
python -m cli reproduce --sensitivity   # also re-run the Sobol analysis (slow)
```

`reproduce` runs with model calls disabled (`PRISM_OFFLINE=1`). If an output
is missing from the cache it fails instead of producing a different table.

| Table | Content | Source |
|---|---|---|
| `corpus` | statutes, structure counts, hashes | parsed ASTs |
| `eval_sets` | frozen evaluation sets | `data/eval/v2/manifest.json` |
| `backtest_*` | in-sample, forecast, reform cost | `cli backtest` |
| `sensitivity` | Sobol indices | `cli sensitivity` |
| `headline` | expert vs extracted, per reform and system | `cli experiment` |
| `attribution` | Shapley attribution to provisions | experiment runs |
| `robustness`, `mcnemar` | flips under population uncertainty; system tests | `cli experiment-stats` |
| `error_injection` | typed errors injected into the expert law | `cli error-injection` |
| `extraction` | extraction quality against adjudicated annotation | `cli eval-score` |
| `faithfulness` | ERASER comprehensiveness / sufficiency | `cli eval-faithfulness` |

Limitations and deviations from the pre-registered design are recorded in
[`../docs/threats_to_validity.md`](../docs/threats_to_validity.md).
