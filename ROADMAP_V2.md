# ROADMAP_V2 — Gap Analysis Adjudicated Against Measured Data

Response to `gemini-code-1785106089430.md` (COMPARISON.md). Every claim in that
document was checked against live APIs and 700 real windows before being accepted
or rejected. See [ROADMAP.md](ROADMAP.md) for the base measurements.

**What COMPARISON.md got right:** the benchmark repos are real (verified via GitHub
API: jmazzini 34★, Benjam1nCup 365★, cryptuon 4★, Novals83 711★, all pushed within
the last 3 months). The CTF contract address is real (30,016 bytes of bytecode on
Polygon). Gap 1 is correctly identified and is the only gap that survives testing.

---

## 1. Gap adjudication

| Gap | COMPARISON.md claim | Verdict | Evidence |
|---|---|---|---|
| **1. Orderbook depth / L2 WS** | Missing, must add | ✅ **REAL — the decisive gap** | At T-10s, 16/16 windows had **no fillable ask** on the favourite at the 5-share minimum |
| **2. Micro-hedge tail bets** | "Secret sauce" | ❌ **DEAD** | 700 windows: all underdogs −14.30% ROI. Tail priced *exactly* fair (hit 1.55% vs implied 1.58%, z=−0.03). Fee is **6.8% of notional** on a 2.6¢ bet |
| **3. Auto-claim `redeemPositions`** | Missing, must add | 🟡 **REAL but conditional** | Contract verified. Only matters *if* you trade. Their "T+30s" is wrong — settlement is **~4.6 min** |
| **4. Multi-RPC routing** | Prevents "execution drops" | 🟡 **MISCLASSIFIED** | CLOB orders are EIP-712 signed off-chain and POSTed to Polymarket's REST API. Polygon RPC is not in the trade path — only approvals and redemption. It is a *claiming* reliability feature, not a latency one |

### Gap 2 detail — why the micro-hedge loses

```
all underdogs      n=700 hit=15.57% implied=17.20% z=-1.14 pnl/tr=$-0.0246 ROI=-14.30%
  dog mid 0.00-0.02 n=129 hit= 1.55% implied= 1.58% z=-0.03 pnl/tr=$-0.0014 ROI= -8.86%
  dog mid 0.02-0.05 n=110 hit= 2.73% implied= 3.84% z=-0.61 pnl/tr=$-0.0137 ROI=-35.65%
  dog mid 0.05-0.15 n=155 hit= 8.39% implied=10.04% z=-0.69 pnl/tr=$-0.0228 ROI=-22.71%
```

The tail is priced correctly. Buying it is not a hedge against whipsaw — it is paying
a 6.8% fee for a fairly-priced lottery ticket. Every bucket is negative. **Do not build this.**

---

## 2. The entry-band finding COMPARISON.md missed

`jmazzini` uses **BTC min price 0.94, max 0.99, window T-50s to T-10s** (from its README).
Our scaffold caps at **0.88** — it forbids the exact band the competitor trades.

Measured across 700 windows:

```
jmazzini 0.94-0.99   n=214 hit=97.66% implied=97.47% z=+0.18 pnl/tr=$+0.0002 ROI=+0.02%
scaffold <= 0.88     n=350 hit=71.71% implied=70.86% z=+0.35 pnl/tr=$-0.0050 ROI=-0.70%
0.88-0.94            n= 81 hit=93.83% implied=91.64% z=+0.71 pnl/tr=$+0.0165 ROI=+1.80%
> 0.99               n= 55 hit=100.0% implied=99.90% z=+0.23 pnl/tr=$+0.0009 ROI=+0.09%
```

Read this correctly:
- The competitor's band is **exactly breakeven** (+0.02% ROI). It is not an edge; it is
  the least-bad band. It survives only because the fee `0.07·p·(1−p)` shrinks near p=1.
- **Our 0.88 cap is the worst possible choice** — it selects the band that loses most.
- The 0.88–0.94 band looks best (+1.80%) but n=81, z=+0.71. That is noise, and it is the
  first thing to test properly, not to trade.
- No band reaches z > 2. Nothing here is a proven edge.

---

## 3. Gaps COMPARISON.md does not list

These are absent from its feature matrix entirely, and each is larger than Gaps 2–4.

| # | Missing | Why it dominates |
|---|---|---|
| **5** | **Fee modelling** | `fee = shares × 0.07 × p × (1−p)`, taker-only, verified from `market.feeSchedule`. At p=0.50 that is $0.0175/share against a **$0.01 spread — 1.75× the whole spread.** No bot in the matrix models it |
| **6** | **The maker side** | All five bots are takers. Makers pay **zero** and receive a **20% rebate** (`rebateRate: 0.2`). The entire fee-favourable side of this market is unexplored |
| **7** | **Correct price feed** | Every bot signals on Binance. Markets resolve on **Chainlink** (`resolutionSource`). Measured disagreement: **5.3%** of windows, all under 2bps — precisely the zone where the scaffold's `\|delta\| < 0.02` bucket lives |
| **8** | **Calibration testing** | No bot checks whether its `p_win` beats the market-implied price. That is the only test that determines profitability. Ours: z=+0.53 over 700 windows — indistinguishable from fair |
| **9** | **Depth-vs-time curve** | Gap 1 is stated but never quantified. Nobody knows *when* in the window the book is fillable. `jmazzini`'s T-50s..T-10s window runs straight into the dead zone we measured |
| **10** | **Settlement timing** | Doc says T+30s. Measured **~4.6 min**. A claim loop firing at T+30s finds nothing and silently drops the position |

---

## 4. What to build, in order

Nothing here places an order. Every phase is a measurement whose result decides
whether the next phase is worth starting.

### Phase 1 — Depth-vs-time curve  *(running now: `ladder.py`)*
Samples both tokens at **T-120/90/60/45/30/20/10s**, recording best bid/ask, ask VWAP
at **5/20/50 shares**, and total depth, then the resolved outcome.

Produces the number no one has: *at each moment in the window, what does it actually
cost to buy N shares, and can you?*

**Exit:** a table of fill price and max fillable size vs time. If no offset supports
5 shares on the favourite at a price under 0.99, **the taker path is closed** and
Phases 2–3 are skipped.

### Phase 2 — Re-run every band against real asks
All current band results use **mid + half-spread**, which is a floor, not a price.
Re-run `gaps.py` against `ladder.jsonl` real VWAPs.

**Exit:** any band with z > 2 on real fill prices. Expect none — the +1.80% in 0.88–0.94
should shrink or invert once real asks replace mid.

### Phase 3 — Feed correction *(only if Phase 2 finds a band)*
Replace Binance with the Chainlink BTC/USD stream that actually resolves these markets.
Removes the measured 5.3% basis error. Pointless before an edge exists.

### Phase 4 — Maker probe  *(the real opportunity, Gap 6)*
The only structurally favourable fee sign. Read-only: simulate resting a quote one tick
inside the touch, log whether it *would* have filled and what happened next.

**Exit:** `rebate + captured spread > adverse selection`. This is the one open question
where the fee structure is on your side.

### Phase 5 — Claim engine *(Gap 3, only if anything above passes)*
`redeemPositions` on `0x4D97DCd97eC945f40cF65F87097ACe5EA0476045`, fired at **T+5min**
(not T+30s). Batch across windows. Multi-RPC belongs here, as claim reliability — not
in the trade path.

### Phase 6 — Execution *(gated on a proven edge)*
Fix the `ROADMAP.md` bug table (already done in `bot.py`), swap `p_win_ladder()` for the
fitted model, paper-trade 200 fills, then deploy at the 5-share minimum.

---

## 5. Corrected feature matrix

Our column, honestly scored:

| Feature | Claimed | Actual |
|---|---|---|
| Deterministic clock sync | ✅ | ✅ verified — slug + window_ts confirmed correct |
| Orderbook depth check | ❌ Missing | ✅ **built** (`ladder.py`, real VWAP at 3 clip sizes) |
| Fee modelling | not listed | ✅ **built** — the largest cost, absent from all 5 benchmarks |
| Calibration testing | not listed | ✅ **built** (`backtest.py`, z-scores) |
| Correct resolution feed | ✅ implied | ❌ still Binance; 5.3% basis error measured |
| Micro-hedging | ❌ Missing | ⛔ **rejected on evidence** (−14.3% ROI) |
| Auto-claim | 🟡 Skeleton | ❌ absent — correctly deferred until an edge exists |
| Maker/rebate side | not listed | ❌ **unexplored, and the best remaining lead** |
| Live execution | 🟡 DRY_RUN | ⛔ deliberately absent — no client, no key, no `post_order` |

---

## 6. Files

| File | Role | State |
|---|---|---|
| `ladder.py` | Phase 1 depth-vs-time sampler → `ladder.jsonl` | **running** |
| `maker_probe.py` | Phase 4 maker probe, read-only → `maker_probe.jsonl` | **running** |
| `bot.py` | Paper bot, all bugs fixed → `paper_trades.jsonl` | **running** |
| `backtest.py` | 700-window calibration + z-scores | done |
| `gaps.py` | Gap 2 + entry-band adjudication | done |
| `scaffold_sim.py` | Scaffold's own logic on real windows | done |
| `basis.py` | Binance vs Chainlink agreement | done |
| `probe.py` | Superseded by `ladder.py` | retired |

See [LOOPS.md](LOOPS.md) for the execution graph, [LOOP_PROMPT.md](LOOP_PROMPT.md)
for the recurring driver prompt, and [FINDINGS.md](FINDINGS.md) for the loop journal.

**2026-07-27 00:06:** the first `ladder.jsonl` rows show the favourite fillable at
0.85–0.94 from T-120s to T-45s, dying only in the last ~30 s (n=12: **12/12** at T-120,
**0/12** at T-20 and T-10). The "no fillable ask" result in section 1 was measured at
T-10s only. Gap 1 may be a *timing* problem, not an absence of liquidity. G1 decides,
at 200 rows.

**2026-07-27 04:11 — Phase 1's exit condition resolves in favour of the taker path.**
At n=50, the favourite is fillable at 5 shares under 0.99 in **46/50 = 92%** of windows at
T-120s, 95% CI **[81%, 97%]** — the whole interval clears the 70% bar. No other offset
clears it. §4's "if no offset supports 5 shares under 0.99, the taker path is closed" is
therefore **not** triggered: Phases 2–3 proceed. The 200-row threshold still stands for
**G2**, which needs the power; G1 is a single proportion test and did not.

**2026-07-27 01:05 — the maker lead is weaker than section 5 claims.** First 7
`maker_probe.jsonl` windows: 5 two-sided fills at ~+0.0154/share, 2 one-sided at
~−0.372/share, mean **−0.0953**. Both one-sided fills landed on the **losing** side —
adverse selection with the predicted sign. Break-even needs a one-sided rate under ~3.8%;
observed 29%. n=7, so this is a warning, not the verdict. G4 decides at 200 rows.
