# Polymarket BTC 5-Minute Markets — Measurement, Not Trading

Research into whether Polymarket's 5-minute BTC up/down markets are tradeable.

**Nothing here places an order.** No `ClobClient`, no private key, no `post_order` in any
module that runs. That is deliberate: the point is to find out whether a profitable strategy
exists *before* writing anything that can spend money. Every conclusion below is measured
against live APIs, not assumed.

## The market

Every 5 minutes, Polymarket opens a binary market: will BTC be up or down when the window
closes? Shares of the winning side settle at $1, the losing side at $0. The price is the
market's implied probability. Taker fee is `shares × 0.07 × p × (1−p)`; makers pay zero and
earn a 20% rebate (verified live from `market.feeSchedule`).

## Findings

### 1. The order book is empty exactly when everyone trades

Every bot in the reference comparison decides at T-10s. We sampled both books at
T-120/90/60/45/30/20/10s across 128 resolved windows:

| offset | favourite fillable at 5 shares under $0.99 |
|---|---|
| T-120 | **119/127 = 94%** (95% CI [88%, 97%]) |
| T-90 | **101/128 = 79%** (CI [71%, 85%]) |
| T-60 | 83/128 = 65% |
| T-45 | 72/128 = 56% |
| T-30 | 50/128 = 39% |
| T-20 | 1/128 = 1% |
| **T-10** | **0/128 = 0%** |

The book is liquid for most of the window and vacates in the final ~20 seconds. The
"no liquidity" conclusion in earlier work was an artifact of only ever sampling T-10s.

### 2. Two-sided market making loses to adverse selection

Makers pay no fee and earn a rebate, so quoting both sides looks structurally favourable.
Because the tick is $0.01, the two best bids sum to ~$0.99 — fill both and you have bought
the entire outcome space for 99¢ against a $1 payout. **A two-sided fill is a locked +1.5¢
regardless of who wins.**

It fails anyway. Roughly half of windows fill on one side only, leaving a naked position:

| quote offset | n | one-sided | mean PnL/share |
|---|---|---|---|
| T-120 | 68 | 47% | **−0.0872** |
| T-60 | 53 | 62% | **−0.0965** |

> **In 65 of 65 one-sided fills, the side that filled was the side that lost.**

That is a statement about mechanism, not luck: a resting bid is hit *because* the market is
leaving that token. Break-even requires the one-sided rate below ~8%; it runs 47–62%. The
result is offset-independent, so no choice of quote time fixes it.

Checked against the obvious objection — that consecutive 5-minute windows are correlated and
a trending hour could fake the streak. Runs test on the winner sequence gave z = +0.61
(slightly *more* alternation than chance), and the fills split evenly across both directions.
The streak is not a trend artifact.

### 3. Fees exceed the spread

At p = 0.50 the taker fee is $0.0175/share against a $0.01 spread — **1.75× the entire
margin being traded for.** None of the five reference bots model it.

### 4. The price is not beatable — and this closes the project

Being able to buy is not an edge. The only test that matters is whether the favourite wins
*more often than its price implies*. Over 189 tradeable windows at T-120s, using real ask
VWAPs:

| band | n | hit | implied | edge | z | PnL/share | ROI |
|---|---|---|---|---|---|---|---|
| ≤0.88 | 108 | 67.59% | 71.14% | −3.55% | −0.81 | −0.0489 | −6.87% |
| 0.88–0.94 | 22 | 100.00% | 91.34% | +8.66% | +1.44 | +0.0811 | +8.87% |
| 0.94–0.99 | 59 | 100.00% | 97.40% | +2.60% | +1.25 | +0.0242 | +2.49% |

**Aggregate: the favourite won 81.48% against 81.69% implied — z = −0.07.** Calibrated to
within a fifth of a percentage point. Trading every window returns −$0.055/window, which is
almost exactly the fee. The band holding most of the volume is outright negative.

The two upper bands both hit 100%, and merging them gives 81/81 wins at +4.14% ROI — but
z = +1.89, under the pre-registered threshold of 2.00 and well under the Bonferroni
threshold of 2.50 for four buckets. That merge is also post-hoc. The reason it looks good is
mechanical: the fee `0.07·p·(1−p)` collapses as p → 1, so the band nearest certainty is
necessarily the least-bad one. Paying less to be right about something obvious is not an
edge.

The gate criteria were **pre-registered in `gate_g2.py` at 194/200 rows**, before the
qualifying data existed, so no parameter could be tuned to the outcome.

## Verdict

| gate | verdict | evidence |
|---|---|---|
| **G1** — can you buy? | **PASS** | 90% of windows at T-120s, CI [84%, 93%] |
| **G2** — is the price beatable? | **FAIL** | aggregate z = −0.07; no band z > 2 |
| **G3** — does the edge survive the right feed? | never run | cannot create an edge that does not exist |
| **G4** — does market making work? | **FAIL** | 93/94 one-sided fills on the losing side |

**There is no tradeable strategy in these markets.** The market is efficient at the only
moment you can trade it, the fee exceeds the spread, and the one structurally favourable
side is destroyed by adverse selection.

A fourth result arrived unplanned: `bot.py`, the paper taker, eventually did trade — 3
times, losing all 3 and 28.8% of its bankroll, before its circuit breaker halted it. It
bought at $0.01 a side the market priced as ~99% certain to lose, because its EV filter
computed `0.78 − 0.01 − 0.0007 = +0.769` from a model that disagreed with a correct market.
The filter did not fail to catch bad trades; it manufactured them.

This cost 17 hours of measurement and zero capital.

## Files

| File | Role |
|---|---|
| `gate_g2.py` | The calibration gate, pre-registered at 194/200 rows |
| `ladder.py` | Samples both books at 7 offsets per window → `ladder.jsonl` |
| `maker_probe.py` | Read-only maker simulation, alternating T-120/T-60 → `maker_probe.jsonl` |
| `bot.py` | Paper taker bot, momentum + Kelly + EV filter → `paper_trades.jsonl` |
| `backtest.py` | Calibration and z-scores over 700 historical windows |
| `gaps.py` | Entry-band and micro-hedge adjudication |
| `basis.py` | Binance vs Chainlink feed agreement |
| `scaffold_sim.py` | Reference scaffold's own logic replayed on real windows |
| `ROADMAP_V2.md` | Gap analysis, each claim checked against live data |
| `LOOPS.md` | Execution graph and gate definitions |
| `FINDINGS.md` | Dated journal, one entry per research iteration |

`gemini-code-*.py` is a third-party scaffold **generator** kept for reference. Running it
writes a project containing live order-placement code and a private-key prompt. It is not
imported or executed by anything here.

## Method notes

Things that were wrong on the first attempt and had to be fixed — recorded because they are
the difference between a result and an artifact:

- **Fill detection took three revisions.** `ask <= quote` ignores queue position and logged
  fills with 1,199 shares resting ahead. Size leaving a level is cancellation as often as
  consumption. The working rule requires both: the ask came down to our price *and* the queue
  ahead of us was consumed.
- **Gamma's `bestBid`/`bestAsk` are not tradeable.** They disagreed with the live CLOB book
  (0.47/0.48 vs 0.40/0.41). Use `/book`.
- **`prices-history` `"p"` is the midpoint**, not a price you can transact at.
- **Settlement takes ~4.6 minutes**, not the T+30s assumed in the reference docs.
- **Gamma hides settled markets** unless `closed=true`.

## Running

```bash
python ladder.py       # depth-vs-time sampler
python maker_probe.py  # maker-side probe
python bot.py          # paper trader
```

All three are read-only against public APIs and append JSONL.

```bash
python gate_g2.py      # the calibration gate, run against ladder.jsonl
```

The collectors were stopped on 2026-07-27 at 203 / 196 / 213 rows once every gate had
resolved. The data here is the complete record, not a snapshot.
