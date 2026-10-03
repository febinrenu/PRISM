# Annotation guidelines (v1)

These guidelines are for the two annotators who label the PRISM evaluation
sets. Read them once in full before the pilot, and keep them open while you
work.

## 1. How the work is organised

- **Work alone.** Both annotators label every item independently. Don't
  discuss items or look at each other's work until a set is finished. The
  tool never shows you a model's output or the other annotator's labels.
- **Pilot first.** Start with the 30 *pilot* items. Then meet and compare
  every disagreement. Where the guidelines were unclear, write a rule into
  §10 together. Start the *test* set only after that.
- **Settle differences together after each set.** For every item where you
  disagree, decide which reading the statute supports. Record the decision;
  don't average.
- **Time:** about 4–8 minutes per item. Take a break every hour. Tired
  annotation is noisy annotation.

Open the tool at **/annotate** (log in first). Each item is one *provision*:
a section, sub-section, clause, proviso, schedule paragraph or rate-table
row. Annotate only the provision text. The grey context box shows the
enclosing section's opening words; use it to understand the provision, but
never take spans from it.

## 2. What counts as a rule

A rule is **one deontic statement**. In order of precedence:

| Modality | Signal | Example |
|---|---|---|
| prohibition | "shall not", "no person shall", "shall not be allowed" | "No person shall furnish a false return." |
| deeming | "shall be deemed", "is deemed to" | "…shall be deemed to accrue or arise in India." |
| definition | "means", "includes", a clause of a definitions section | "“accountant” means a chartered accountant…" |
| power | "may", where the subject is an authority (Board, Officer, Government, Tribunal) | "The Board may, by notification, specify…" |
| permission | "may" for a private person; "entitled to"; "shall be allowed" a deduction | "An assessee may claim a deduction…" |
| obligation | "shall", "must", "is required to", "liable to" | "Every person … shall furnish a return…" |

Decision steps:

1. Does the provision state anything that binds, permits, defines or deems?
   If not (a heading, "This Act may be called…", a bare list item with no
   verb), tick **This provision states no rule** and finish.
2. Count the rules. Each separate modal verb with its own subject or action
   is a separate rule. "X shall file a return **and** shall pay the tax" is
   **two** rules. A proviso that changes the rule is **not** a new rule: it
   goes in that rule's *exceptions* (see §5).
3. For each rule, choose its modality from the table, taking the **first**
   row that applies.

"may extend to" in a penalty ("imprisonment which may extend to two years")
is not a permission. It sets the penalty's maximum, which belongs to the
penalty rule.

## 3. Spans

Select the words in the provision, then press the key (or click the button):

| Key | Field | What to select |
|---|---|---|
| S | Subject | Who the rule binds: "Every person whose total income exceeds…", "Any registered person", "The Board". |
| A | Action | What must / may / must not be done, **including the modal**: "shall furnish a return of income on or before the due date". |
| Q | Consequence | What follows: a penalty, liability or legal effect: "shall pay a penalty of Rs. 5,000". |
| C | Condition | Each separate trigger: "Where any person fails to furnish the return under sub-section (1)". Tick *negated* for "unless …" / "where … not". |
| E | Exception | Each proviso or carve-out that qualifies the rule: "Provided that no return is required where …". |
| R | Cross-reference | Each reference to another provision: "sub-section (1) of section 139", "Schedule VII". |

Boundary rules:

- **Minimal but complete.** Include every word needed for the meaning and
  nothing more. Leave out the label ("(2)"), leading connectors ("and",
  "or") and trailing punctuation.
- **Keep the modal in the action** ("shall furnish …", not "furnish …").
- **One condition per trigger.** "Where A, and B, …" gives two conditions if A
  and B are independent triggers, and one if they read as a single
  description.
- A field the provision doesn't state stays empty. Don't fill it from the
  context box.

## 4. Who the rule binds

Choose the closest class: individual, company, firm, huf (Hindu undivided
family), any_person, employer, registered_person (GST), data_fiduciary,
authority (Board, officer, Government), other.

## 5. Provisos, explanations and exceptions

- A **proviso** ("Provided that …") or an **unless / except** clause that
  changes when or how the rule applies: select it as an **Exception** of
  the rule it qualifies.
- A proviso that states a separate rule of its own (its own modal verb
  and its own subject): annotate it as its own rule **as well**.
- An **Explanation** that defines a term for the provision: a rule with
  modality *definition*.

## 6. Amendments (Finance Acts)

Finance Acts mostly amend other Acts ("In section 87A, for the words
'seven hundred thousand rupees', the words 'twelve hundred thousand rupees'
shall be substituted"). Annotate the rule **as the amended provision reads
after the amendment**:

- The modality and spans describe the amended rule. Select the words in
  this provision that state it: the substituted words and the inserted
  text.
- Record the resulting numbers in **effects** (§7), with the source span
  on the substituted words.
- "shall be substituted / inserted / omitted" on its own is not the rule.
  Don't annotate the amending verb as an obligation.

## 7. Effects: the numbers a rule sets

Add an effect whenever the rule states or changes one of the following.
Write amounts in **rupees** (700000) and rates as **fractions** (0.05). Use
*Source ← selection* to mark the exact words the numbers come from.

| Kind | Fields | Notes |
|---|---|---|
| slab_row | lower, upper, rate, regime, age_band, applies_to_ay | One per row of a rate table. "From Rs. 4,00,001 to Rs. 8,00,000 \| 5 per cent." → lower 400000, upper 800000, rate 0.05. Leave the top row's upper empty. |
| rebate | max_income, max_rebate, marginal_relief, regime, applies_to_ay | s.87A / s.156. Tick marginal_relief when tax is capped at "the amount by which the total income exceeds" the limit. |
| standard_deduction | amount, regime | Fixed deduction from salary (s.16(ia)). |
| surcharge_band | threshold, rate, regime | One per band: "exceeding fifty lakh rupees … ten per cent." → threshold 5000000, rate 0.10. |
| surcharge_cap | max_rate, regime | "the rate of surcharge shall not exceed twenty-five per cent." |
| cess | rate | Health and Education Cess (0.04). |
| penalty / fee / interest | amount, per_day, rate, rate_per_month, max_amount, trigger | "one hundred rupees for every day … maximum of five thousand rupees" → per_day 100, max_amount 5000. |
| tds / advance_tax / due_date | rate, days, description | Rules about *when* tax is paid. |

- **regime:** *new* for the s.115BAC(1A) / s.202 regime, *old* for the
  normal schedule, *both* when the text doesn't say.
- **applies_to_ay:** fill it only when the provision names the year
  ("assessment year beginning on or after the 1st April, 2026" →
  2026-27).
- **executable:** untick when a condition depends on something no fact could
  answer: "in the opinion of the Assessing Officer", "reasonable cause",
  "as may be prescribed".

## 8. Worked examples

**Rate table (FA 2025 s.25):** "(iii) for any previous year relevant to the
assessment year beginning on or after the 1st April, 2026, shall be
computed at the rate of tax given in the following Table … 1. Upto Rs.
4,00,000 | Nil …"

- One rule: *obligation*; action "shall be computed at the rate of tax
  given in the following Table".
- Seven slab_row effects, each with regime *new* and applies_to_ay
  2026-27, and each with its own row as the source.

**Rebate amendment (FA 2025 s.20):** substitutes the limit and the amount in
the s.87A proviso.

- One rule: *permission* (the assessee is entitled to a deduction).
- One rebate effect: max_income 1200000, max_rebate 60000, marginal_relief
  ticked (the existing clause (b) keeps the cap), regime *new*,
  applies_to_ay 2026-27.
- Source: the substituted words.

**Late fee (CGST s.47(1)):**

- One rule: *obligation*; subject "Any registered person"; condition "who
  fails to furnish the details …"; consequence "shall pay a late fee of one
  hundred rupees for every day during which such failure continues subject
  to a maximum amount of five thousand rupees".
- One fee effect: per_day 100, max_amount 5000.

**Definition (DPDP s.2):** "“Data Fiduciary” means any person who alone or
in conjunction with other persons determines the purpose and means of
processing of personal data".

- One rule: *definition*.
- Subject: the defined term. Action: "means any person who … personal data".

**No rule:** "This Act may be called the Code on Wages, 2019." → tick *no
rule*.

## 9. When unsure

Choose your best reading and write a note on the rule explaining the doubt.
Never leave an item half-done; save a draft and come back. Mark an item
**Done** only when every rule in it is complete.

## 10. Decisions from the pilot

*(To be filled in after the pilot: each rule you agree on goes here with an
example, and the guideline version moves to v2.)*
