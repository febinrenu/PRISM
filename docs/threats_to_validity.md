# Threats to validity and known limitations

A running record of everything that limits what the results can claim. It
feeds the paper's threats-to-validity section, and every item says what was
done about it.

## Construct validity

- **Expert coding.** The income-tax parameters were coded by one person, with
  a citation for every value, and the slab tables were checked row by row
  against the parsed statutes. The second coding is a *blind automated
  coding* (a language model reading statute excerpts, `cli gold-blind`), not
  an independent human coder. The paper reports it as such. A practitioner
  spot-check is planned and optional.
- **Pre-registered conclusions.** The conclusion list (`experiment/conclusions.py`)
  was fixed before any language-model run was scored. Some conclusions are
  correlated: the ten decile directions usually move together. So the flip
  rate is reported alongside the individual flips, not as an independent
  count.
- **Deviation from pre-registration (2026-10-03).** The direction
  conclusions were first read with near-exact sign tests: ₹1 lakh of
  revenue, an effective-rate change of 1e-7, and a Kakwani change of 1e-6.
  The controlled error-injection study, which uses no system output, showed
  that a one-rupee shift of a band boundary then flips "revenue direction"
  and "top gaining decile" on reforms whose true change is zero. Directions
  are now read with materiality thresholds:
  - ₹500 crore of revenue;
  - 0.01 percentage points of decile effective rate;
  - 0.001 of Kakwani.

  The top gaining decile is reported only when some decile gains
  materially. Both versions are computed for every run (`flip_rate` and
  `flip_rate_original`) and both are reported.
- **Earliest coded year.** AY 2020-21 has no earlier coded year. Its
  conclusions are taken against a revenue-equivalent proportional tax.
- **Scope of the calculator.** It covers resident individuals with income
  at normal rates. It leaves out special-rate income (capital gains,
  lotteries), the surcharge treatment of dividend and capital-gains income,
  and the alternative minimum tax. These are stated in `PITParams.scope`.

## Internal validity

- **One assembler.** Every system's rules go through the same deterministic
  assembler, so divergences come from extraction. The assembler's own
  choices still matter:
  - year-scoped slab rows win over unscoped ones;
  - effects must be stated for the target's regime;
  - for a scalar parameter (rebate, standard deduction, cess), an effect
    stated for the target's regime wins over one stated for both, and
    candidates that still disagree make the target ambiguous: a review item,
    never a silent choice. Earlier versions took the first effect; the
    change followed GPT-OSS-120B's reading of s.156 of the Income-tax Act
    2025, where both rebates were extracted correctly but marked as applying
    to both regimes.

  Each choice is documented and tested, and the expert parameters round-trip
  through the assembler unchanged.
- **Failed model calls.** A call that fails on a quota or network error is
  not scored as a system failure; it is retried. Invalid JSON returned by a
  model *is* the model's answer and is scored as a parse error.
- **Incomplete assembly.** A target the system could not fill holds the
  expert value internally. Its regime is therefore reported as "no result"
  and every conclusion counts as flipped, so the system is never credited
  with the expert's answer.
- **Self-consistency.** k = 4 samples at temperature 0.7. The confidence is
  a vote share, not a calibrated probability, until calibration is measured
  against human gold.

## External validity

- **Population.** No microdata was available (MoSPI unit-level data could not
  be obtained). The taxpayer population is reconstructed from published
  Income Tax Return Statistics, so it reproduces the published returns by
  income range exactly. Within-band distributions, the top tail, deductions
  and age are modelled. The Sobol analysis shows which assumptions move
  which outcomes, and `cli experiment-stats` checks that conclusion flips
  persist across the whole assumption space.
- **Back-test results are mixed, and reported as such:**
  - in-sample revenue is 4–8% above reported tax payable;
  - the one-year forecast loses to the naive baseline;
  - the three-year forecast beats it;
  - simulated reform costs are 2–2.6 times the Budget-speech figures. The main
    reason is that the default-regime change moves taxpayers who do not
    optimise into the new regime.
- **Salaried taxpayers and the standard deduction.** The salaried share of
  each income range comes from the salary table (2.2), matched to the GTI
  table (2.1) by range. That matching assumes salary and GTI rank taxpayers
  alike, which overstates the salaried share where non-salary income
  dominates. Reported GTI is treated as net of the data year's standard
  deduction (₹50,000), although new-regime returns before AY 2024-25 had
  none.
- **Age.** The published statistics have no age breakdown. The calibrated
  population treats everyone as under 60, so errors in the senior slab
  tables do not show at the calibrated setting. The robustness draws vary
  the senior share from 0 to 20%. The taxpayer-level comparison (exact tax
  on a fixed grid for every age band) covers the senior tables directly.
- **Behaviour.** The simulation is static: it models no labour-supply or
  compliance response. Revenue changes are first-round effects.
- **Statutes.** The headline experiment covers personal income tax in five
  Finance Acts and the Income-tax Act 2025. The extraction evaluation also
  covers the CGST Act, the Code on Wages and the DPDP Act. GST incidence is
  out of scope because there is no item × fractile consumption data (see
  DATA.md).

## Reliability and measurement

- **Parser.** Known limitations:
  - The salary-deductions table in s.19 of the Income-tax Act 2025 wraps
    cells across lines, and the parser splits it into fragments. The
    new-Act provision set therefore excludes the standard deduction.
  - Inline sub-section labels ("156. (1) …") are recorded as zero-length
    markers, and their text stays in the section paragraph.
  - The user-supplied Income-tax Act 1961 PDF has a broken font encoding and
    is not parsed.
- **Language-model versions.** Hosted models change without notice. Every
  output is cached with the provider's reported model version or
  fingerprint, and `cli reproduce` regenerates every table from that cache
  with model calls disabled.
- **Annotation.** The two annotators are not lawyers. The guidelines, the
  pilot round (revised until agreement reaches the target), adjudication
  and the agreement statistics are all reported.

## Leakage

- **Fine-tuning data** excludes:
  - every evaluation provision;
  - any provision sharing more than 20% of its word 8-grams with one;
  - every provision the headline experiment extracts;
  - the whole DPDP Act.
- **Teacher overlap.** The teachers include GPT-OSS-120B, which is also an
  evaluated system. The fine-tuned model is therefore compared mainly with
  its base model.
