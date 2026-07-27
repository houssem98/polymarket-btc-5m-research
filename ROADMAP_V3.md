# ROADMAP_V3 — Post-Deep-Research Gate Set

Supersedes [ROADMAP_V2.md](ROADMAP_V2.md). Written 2026-07-27 against
`compass_artifact_wf-5c2a6ce7-…md` (the Fable deep-research report produced from
[DEEP_RESEARCH_PROMPT.md](DEEP_RESEARCH_PROMPT.md)).

**State at handover:** `ladder.jsonl` 181 · `maker_probe.jsonl` 174 ·
`paper_trades.jsonl` 191. Three collectors running. Still no order-placement code
anywhere in the repo.

---

## 1. What the report changes

The report's verdict is **no viable strategy; do not trade**. That agrees with every
measurement this project has made, so agreement is not evidence — a report that
confirms the operator's own prior is exactly the one to check hardest. Two of its
claims are load-bearing and neither has been verified by this project:

| # | Claim | Why it is load-bearing | Status |
|---|---|---|---|
| A | Resolution is **Chainlink Data Streams** (sub-second, pull-based), not a heartbeat/deviation on-chain aggregator | Kills Q1 outright. If false, the stale-round edge is back on the table | **unverified here** |
| B | The BTC 5m **liquidity-reward pool is ~$0** (published program funds sports/esports only) | Sole input that could flip the maker branch positive | **unverified here** |

Claim A is a correction to the *prompt*, not to a measurement — DEEP_RESEARCH_PROMPT
asserted a heartbeat feed from memory, which was wrong. The report cites the market
rule text and Chainlink docs. Accept the correction in substance, verify the artifact.

Claim B is arithmetic this project never did. It closed the maker branch on adverse
selection alone with reward income implicitly zero. The report reaches the same sign
via a different route (published program excludes crypto). One live CLOB read settles it.

## 2. Adjudication of the report

| Report claim | Verdict | Basis |
|---|---|---|
| Market calibrated; nothing survives Šidák over 8 buckets (needs \|z\|>2.73) | ✅ **accept** | Matches our 700-window table, z ∈ [−1.14, +0.71]. The correction is the piece we had flagged but not applied |
| Fee 1.75× spread kills all spread-crossing | ✅ **accept** | Our own measurement |
| Maker branch negative | ✅ **accept, pending E1** | Our 85/85 loser-fill streak, p=3.8e-6, is the stronger evidence. Report adds only the reward-income term |
| Hedging a one-sided fill locks the loss (fill *is* the adverse move) | 🟡 **plausible, untested** | Mechanistically consistent with 85/85. E4 tests it directly. Do not accept on argument alone |
| Two-sided-fill predictive filter collapses fill volume | 🟡 **plausible, untested** | E5 |
| Oracle = Data Streams, no stale round | 🟡 **accept pending E0** | Citations are dated 2026 and were not fetched by this project |
| Settlement manipulation is the real surface (Stanford/SMU paper) | ⛔ **out of scope** | Requires capital to move BTC spot, is prohibited by Polymarket's rules, and is plausibly illegal manipulation. Not a candidate. Its only relevance is as a **risk to a resting maker** |
| $8.2M vs $1.28M profit figures unreconciled | ⚠️ **noted** | Report flags its own discrepancy. Irrelevant to any action we take |
| Reward pool $0 | 🟡 **accept pending E1** | E1 is a minutes-long read; do not carry this on a doc citation |

### 2.1 A gap the report did not catch

`ladder.py:80-86` derives `open_px` from a **Binance 1m kline**. The market opens and
resolves on **Chainlink**. Every `delta_pct` in 181 rows of `ladder.jsonl` is therefore
measured against the wrong reference. Under a ±2 bps basis this is small, but E3 buckets
by signal and any Binance-vs-Chainlink signal bucket built on this field is measuring the
basis error, not the signal. Fix before E3, or restrict E3 to price-band buckets that do
not use `delta_pct`.

## 3. The V2 gate set is retired

| V2 gate | Outcome | Disposition |
|---|---|---|
| G1 fill | **PASSED** at T-120 (90%, CI [85%,94%]); T-90 tested marginal and fell back | Closed. Fillability established; it was never edge |
| G2 calibration | never ran (needed 200 rows) | **Replaced by E3**, which adds the Šidák correction and real `/book` VWAP |
| G3 feed | blocked on G2 | Folded into E3 as a bucket |
| G4 maker | 174 rows, both offsets negative, 85/85 loser-fill | **Decided in substance.** Formal 200/offset is ceremony. Replaced by E1 |

## 4. New gate set — E0 … E5

Ordered by (decisiveness ÷ cost). Stop at the first failure. E0 and E1 together are
under an hour and will most likely end the project.

| # | Experiment | Cost | Statistic | Kill threshold | n |
|---|---|---|---|---|---|
| **E0** | **Citation verification.** Fetch each URL the report cites: the market rule text, `docs.chain.link/data-streams`, the liquidity-rewards page, the arXiv paper, the Polymarket RTDS docs. Confirm each says what is quoted | minutes | claim-by-claim match | any load-bearing quote not found ⇒ treat A/B as UNKNOWN and re-open Q1 | ~8 URLs |
| **E1** | **Reward-pool read.** Pull every open BTC 5m market object from the CLOB API; read the rewards config (`rewards`, `rewardsMinSize`, `rewardsMaxSpread`, daily rate) | minutes | daily reward pool $ | pool = $0 or below §5 break-even ⇒ **maker branch dead, permanently** | all open BTC 5m markets |
| **E2** | **Open-price capture.** Subscribe to RTDS `crypto_prices_chainlink` (btc/usd); compare the first print at/after each window boundary to the market's published Price-to-Beat | hours | \|diff\| | any material diff ⇒ the +0ms open rule is wrong and **Q1 re-opens** | ~100 windows |
| **E3** | **Book-VWAP recalibration.** Re-run the 700-window band analysis using real `/book` VWAP at 5 and 50 shares as the fill, net of fee, bucketed by signal | days (data exists) | z per bucket, Šidák-corrected | no bucket \|z\| > 2.73 out of sample ⇒ **taker branch dead** | ≥350/bucket |
| **E4** | **One-sided-fill timing.** For 200 one-sided fills, log perp mid at fill-time vs +30s | 3–5 d | sign/size of move relative to fill | adverse move *precedes* the fill ⇒ **hedged-maker dead** | ~200 fills |
| **E5** | **Two-sided-fill predictability.** Two-sided rate and captured spread by depth-symmetry / spread / vol decile | 5–7 d | two-sided rate × volume × net spread, minus bleed | no decile net positive ⇒ **filtered-maker dead** | ≥500 windows |

E4 and E5 only run if E1 shows a funded pool. With a $0 pool the maker branch is dead on
arithmetic and neither experiment can rescue it — do not run them "for completeness".

## 5. The maker break-even, stated once

Per window, one 50-share two-sided quote:

| Term | $/share | Source |
|---|---|---|
| Spread capture, two-sided fill | **+0.015** | measured, n=90+ |
| Maker rebate (rate 0.2) | + small, on filled volume | `feeSchedule`, verified live |
| Liquidity reward income | **? — E1** | report says ~0; unverified |
| Adverse-selection bleed | **−0.077 … −0.097** | measured, both offsets |
| Hedge cost, if hedging | −0.045%…0.05% of notional + slippage | report, unverified |
| **Net** | **negative unless reward income > bleed** | |

Break-even needs the one-sided fill rate under ~8%. Observed **45–62%**. Reward income
is the only term that can close a gap that size, which is why E1 outranks everything.

## 6. Collectors — what to keep running

| Process | Rows | Feeds | Recommendation |
|---|---|---|---|
| `ladder.py` | 181 | E3 | **keep.** Only source of real book VWAP |
| `maker_probe.py` | 174 | E4, E5, the bleed denominator | **keep until E1 returns.** If E1 shows $0, stop it — the branch it measures is closed |
| `bot.py` | 191 | nothing | **retire.** Decides at T-10s where the book is 0% fillable, so it emits only skips. Operator's call, not the loop's |

## 7. Stopping

Call the project finished when **either**:

- **E1 returns a $0 pool and E3 finds no bucket at \|z\| > 2.73** — both branches closed
  on measurement. Write it up, push, stop. This is the expected outcome and it is a
  result, not a failure.
- **E0 finds a load-bearing citation does not check out** — in that case do not stop;
  re-open Q1 and re-run E2 first, because the oracle question would be live again.

Do not invent a sixth strategy to keep the project alive. The report's own top-ranked
candidate is "do nothing" at $0 EV and zero risk, and every measured alternative scores
below it.

See [LOOPS_V3.md](LOOPS_V3.md) for the execution graph and
[LOOP_PROMPT_V3.md](LOOP_PROMPT_V3.md) for the session driver.
