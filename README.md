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

### Open question

Whether the price is *beatable* — does the favourite win more often than its price implies?
That is a calibration test, and it is the only thing that determines profitability.
Fillability is not edge: a favourite is cheap at T-120s precisely because the outcome is
still open. An earlier run over 700 windows found no band with z > 2.

## Files

| File | Role |
|---|---|
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

All three are read-only against public APIs and append JSONL. They run indefinitely; the
data files here are a snapshot.
