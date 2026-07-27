# LOOP_PROMPT_V3 — Session Driver

Supersedes [LOOP_PROMPT.md](LOOP_PROMPT.md). V2's loop was a 30-minute surveillance
tick over three collectors; it produced eleven consecutive "no change" iterations
because it was waiting on row counts. V3 is **not a surveillance loop** — the data
already exists. It is a short serial chain of kill-experiments that a new session runs
to completion.

**Run it once, not on a timer.** Only re-enter the loop for E2/E4/E5, which need
elapsed wall-clock.

```
/loop Execute LOOP_PROMPT_V3.md in the polymarket project.
```

---

## The prompt

Copy the block below into a new session.

```
Working dir: c:\Users\unicentrale\Downloads\trading polymarket and equitie , crypto

You are running the post-deep-research experiment chain on the Polymarket BTC 5m
research project. Read ROADMAP_V3.md and LOOPS_V3.md for state. Everything here is
read-only. No iteration may place an order.

CONTEXT YOU DO NOT NEED TO RE-DERIVE
  Taker fee = shares x 0.07 x p x (1-p), takerOnly. Makers pay zero, rebateRate 0.2.
  Tick 0.01, orderMinSize 5, rewardsMinSize 50 @ maxSpread 4.5.
  Favourite fillable at 5 shares under 0.99: 90% at T-120s, 1% at T-20s, 0% at T-10s.
  700-window calibration: every band z in [-1.14, +0.71]. No band clears z>2.
  Maker probe: 45-62% of windows fill one side only; 85 of 85 one-sided fills were on
  the LOSING side (p=3.8e-6). Mean -0.077/share at T-120, -0.097/share at T-60.
  Settlement ~4.6 min after close. Gamma hides settled markets unless closed=true.
  Gamma bestBid/bestAsk are NOT tradeable — use /book. prices-history "p" is the MIDPOINT.

RUN THE CHAIN IN ORDER. STOP AT THE FIRST KILL.

E0 — CITATION VERIFICATION  (minutes, do this first, always)
  The deep-research report (compass_artifact_wf-5c2a6ce7-*.md) rests on two claims this
  project has never verified. Fetch and check each cited source:
    - the market rule text on a live BTC 5m event page (resolution source wording)
    - docs.chain.link/data-streams (is it sub-second pull-based, or heartbeat?)
    - docs.polymarket.com/market-makers/liquidity-rewards (which markets are funded?)
    - docs.polymarket.com/developers/RTDS/RTDS-crypto-prices
    - the arXiv settlement-manipulation paper, if it resolves
  Report claim-by-claim: quote found / quote not found / URL dead.
  If a load-bearing quote is not found, mark the claim UNKNOWN, say so plainly, and
  go to E2 — the oracle question is live again. Do not paper over a dead link.

E1 — REWARD-POOL READ  (minutes; this single read decides the maker branch)
  GET the CLOB market object for every currently-open BTC 5m market. Print the full
  rewards config: rewards rate/pool, rewardsMinSize, rewardsMaxSpread, epoch.
  Compute the daily $ a 50-share two-sided quote could plausibly earn.
  Compare against the measured bleed: ~50% one-sided x ~0.09/share on 50 shares.
  PASS if reward income exceeds the bleed.
  FAIL => the maker branch is dead permanently. Write it to ROADMAP_V3.md, recommend
          stopping maker_probe.py, and skip E4 and E5 entirely. Do not run them for
          completeness — they cannot rescue a branch that is dead on arithmetic.

E2 — OPEN-PRICE CAPTURE  (hours; only if E0 failed, or run in background alongside E3)
  Subscribe to RTDS crypto_prices_chainlink (btc/usd). For each window boundary,
  compare the first print at/after the boundary to the market's published Price-to-Beat.
  Statistic: |diff|, n >= 100 windows.
  If materially different, the +0ms open-capture rule is wrong, the settlement rule
  must be re-derived from scratch, and Q1 (oracle exploitability) re-opens. That would
  be the single most valuable finding available — treat it seriously, do not explain
  it away.

E3 — BOOK-VWAP RECALIBRATION  (the taker branch; data already exists)
  Re-run the band analysis on ladder.jsonl using REAL /book ask VWAP at 5 and 50 shares
  as the fill price. Never mid, never mid+half-spread.
  Bands: <=0.88, 0.88-0.94, 0.94-0.99, >0.99, at T-120s (the only offset that cleared
  the fill gate; T-90 was tested and fell back below it).
  Subtract fee = 0.07*p*(1-p) per share.
  Report n, hit, implied, edge, z, ROI per band.
  Apply the SIDAK correction over every bucket examined: at 8 buckets, alpha=0.05
  requires |z| > 2.73. State how many buckets you tried, including ones you looked at
  and discarded.
  PASS only if a bucket clears |z| > 2.73 AND positive ROI net of fee AND survives
  out-of-sample on held-back windows.
  FAIL => the market is calibrated. Say so plainly.

  BEFORE E3, fix or route around this: ladder.py:80-86 derives open_px from a BINANCE
  1m kline, but the market opens and resolves on CHAINLINK. Every delta_pct in
  ladder.jsonl is measured against the wrong reference. Either recompute open_px from
  the Chainlink stream, or restrict E3 to buckets that do not use delta_pct, and say
  which you did.

E4 — ONE-SIDED-FILL TIMING  (only if E1 passed)
  For 200 one-sided fills in maker_probe.jsonl, log perp mid (Binance/Bybit/Hyperliquid)
  at fill time vs +30s.
  If the adverse move PRECEDES the fill, hedging locks in a loss that has already
  happened and the hedged-maker branch is dead. If it FOLLOWS, hedging is live and worth
  costing out at 5 / 50 / 500 shares against real perp taker fees and slippage.

E5 — TWO-SIDED-FILL PREDICTABILITY  (only if E1 passed)
  Two-sided fill rate, fill volume and captured spread by decile of depth symmetry,
  spread and realised vol, n >= 500 windows.
  The hypothesis to beat: the conditions that raise two-sided-fill probability are the
  same conditions in which nobody crosses you, so the filter collapses volume toward
  zero. PASS only if some decile is net positive after the bleed, with enough volume
  to matter.

REPORT
  Append a dated entry to FINDINGS.md: which experiments ran, the statistic, the
  verdict, and what the next session should do. Short table plus 3 lines.
  Update the node table in LOOPS_V3.md and section 3 of ROADMAP_V3.md if a branch closed.
  Re-push the repo if a gate produced a real result.

RULES
  - Never place an order. Never add ClobClient, a private key, or post_order to any
    file. Grep for call-syntax before reporting any file as safe.
  - Verify against live APIs before writing anything down. Do not assert from memory,
    and do not assert from the deep-research report either — it is a secondary source
    and E0 exists precisely because of that.
  - Every quantitative claim gets an n and a confidence interval.
  - Report multiple-bucket testing honestly, including buckets you tried and dropped.
  - A closed path is the most valuable output this project can produce. Report a
    failed gate as a result, not a setback.
  - Settlement manipulation (pushing spot across the strike near close) is OUT OF
    SCOPE at any size: it is prohibited by Polymarket's rules and is plausibly illegal
    market manipulation. Do not model it, size it, or recommend it. It is relevant only
    as a risk to a resting maker order.
  - If E1 returns a $0 pool and E3 finds no bucket over |z|>2.73, both branches are
    closed. Say the project is finished and recommend stopping. Do not invent a sixth
    strategy to keep it alive.

COLLECTORS
  ladder.py    keep running — feeds E3
  maker_probe.py  keep until E1 returns; stop it if the pool is $0
  bot.py       recommend retiring — it decides at T-10s where the book is 0% fillable,
               so all 191 rows are skips. Operator's call, not yours.
```

---

## Thresholds

| Gate | Needs | Have | Blocking on |
|---|---|---|---|
| E0 | web access | — | nothing — run now |
| E1 | one CLOB read | — | nothing — run now |
| E2 | ~100 windows of RTDS | 0 | ~8 h of streaming |
| E3 | ladder.jsonl ≥350/bucket | 181 rows × 7 offsets | usable now at reduced buckets |
| E4 | 200 one-sided fills | ~80 | E1 passing first |
| E5 | 500 windows | 174 | E1 passing first |

## Stopping

- **E1 = $0 pool AND E3 finds nothing over \|z\| > 2.73** → both branches closed.
  Write up, push, stop. Expected outcome.
- **E0 finds a broken citation** → do not stop. Re-open Q1, run E2 first.

End with `ScheduleWakeup(stop: true)` or by saying "stop the loop".
