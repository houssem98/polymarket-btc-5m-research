# LOOP_PROMPT.md — Measurement-Loop Driver

The polymarket gates are closed (see [FINDINGS.md](FINDINGS.md)). What survives is the
loop design, corrected. This is the reusable driver.

**What changed and why.** The original ran 36 iterations, 11 of them consecutive
no-change ticks, with no budget, no stall rule, no escalation trigger, and a 30-minute
foreground cadence over a 17-hour data collection. Four parts were missing. They are
added below, marked **[+]**. The two things the original did better than most —
pre-registration and multiple-comparison correction — are kept and made explicit.

---

## The nine parts

Adapted from the loop anatomy in *Product Faculty, "How I Build Loops"*. Six were already
here; four were not.

| # | Part | Status |
|---|---|---|
| 1 | **Goal** — a finish line you can measure | had it (gate criteria) |
| 2 | **Context** — what the loop knows going in | had it (ROADMAP, FINDINGS) |
| 3 | **Actions** — the moves it may make each round | had it |
| 4 | **Tools** — what it may touch | had it |
| 5 | **Evals** — what judges each round | had it, plus pre-registration |
| 6 | **Memory** — what carries between rounds | had it (FINDINGS.md, append-only) |
| 7 | **Guardrails** — lines it cannot cross | had it, with a grep-verified check |
| 8 | **Escalation** — when to stop and ask a human | **[+] missing** |
| 9 | **Stop** — target, budget, stall | had target only; **[+] budget, stall** |

---

## The prompt

```
Working dir: <project root>

You are advancing <project>. Read <roadmap> and <findings> for state. Do ONE iteration.

STEP 1 — HEALTH
  Verify each long-running collector is running exactly once. Restart what is missing
  with the explicit interpreter path. Kill duplicates — two writers corrupt one file.

STEP 2 — DATA
  Count rows in each output. Report counts and growth since the previous iteration.
  Investigate any unresolved row older than the known settlement time.

STEP 3 — GATES
  Run a gate ONLY when its sample threshold is met. Otherwise say how many more
  samples are needed and stop. Do not preview a gate's verdict from partial data;
  reporting the trend is fine, calling it is not.

STEP 4 — REPORT
  Append a dated entry to <findings>: row counts, any gate run and its verdict, and
  what the next iteration should do. A short table plus three lines. If the entry is
  longer than that, the iteration probably had no content — say "no change" instead.

STOP CONDITIONS — all three are checked every iteration
  TARGET   the gate threshold is met and the gate has been run, or
  BUDGET   <N> iterations OR <$X> spend, whichever comes first, or
  STALL    3 consecutive iterations with no change in any gate's verdict AND no new
           failure mode found. On stall: do not simply continue. Either widen the
           cadence to the data's actual rate, or stop and schedule a single run at
           the projected threshold time.

ESCALATE — halt and ask, do not decide alone
  - any irreversible or outward-facing action (publish, push, post, send, deploy)
  - any file entering the repo that this loop did not write and has not read
  - any spend above <$X>
  - any result that would justify committing capital
  - anything the loop cannot verify this iteration
  Escalation is the loop working, not the loop failing.

CADENCE
  Match the tick to the rate the data actually changes, not to how often you want to
  look. If a threshold is H hours away, a 30-minute tick buys nothing and costs 2H
  analysis passes. Collectors run unattended; the loop wakes to decide, not to watch.

RULES
  - <hard guardrail, e.g. never place an order>. Verify by grepping for call-syntax
    before reporting any file as safe — a prohibition with no check is a wish.
  - Verify claims against live sources before writing them down. If something cannot
    be verified this iteration, say so.
  - Report a failed gate as a real result. A closed path is a valid output.
  - If every gate has failed, say the project is finished and recommend stopping. Do
    not invent a new hypothesis to keep it alive.
```

---

## Inference discipline

The parts most loop guidance omits. Both earned their place in the polymarket run.

**Pre-register the gate before the data exists.** Write the analysis — thresholds,
buckets, exclusions, pass criteria — while the sample is still short of the threshold,
and run it unmodified. `gate_g2.py` was written at 194/200 rows for exactly this reason.
A holdout split protects against overfitting the model; pre-registration protects against
tuning the *analysis*, which is the easier and more common failure.

**Correct for every bucket you looked at.** Report the number tested alongside the
result. Four buckets at α=0.05 needs |z| > 2.50, not 2.00. A bucket found by merging
others after seeing the data is a *new* test, so the correction gets harsher, not
gentler — the polymarket 81/81 band hit z=+1.89 post-hoc and was rejected on this rule.

**Check your own streaks for artifacts.** A 93-of-93 result across consecutive time
windows may be one correlated event, not 93 draws. Run the cheap check — a runs test
took two minutes and returned z=+0.61, which is what let the streak stand.

**Watch for promotion on noise.** Compute the standard error of your acceptance metric
before setting the bar. Repeated "promote if better" against a small fixed holdout will
promote noise: 15 cases on a 0–5 rubric has SE ≈ 0.27, so a 0.2 improvement is half a
standard error, and twelve rounds of it will find something every time.

---

## What the missing parts cost

Concrete, from the run that closed on 2026-07-27:

| Missing part | What happened |
|---|---|
| Stall rule | 11 consecutive no-change iterations; noticed at iteration 13, no mechanism to act |
| Budget cap | 36 iterations over 17 h, spend never measured |
| Cadence | 30-min foreground tick against a 17-h collection — "your time plus the machine's" |
| Escalation | `git add -A` published five unread files to a public repo |
