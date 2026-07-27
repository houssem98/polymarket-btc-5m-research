# DEEP_RESEARCH_PROMPT.md

Paste the block below into **Fable 5 deep research**. It is grounded in the measured
results in [FINDINGS.md](FINDINGS.md), [README.md](README.md) and [ROADMAP_V2.md](ROADMAP_V2.md)
so the research spends its budget on open questions instead of re-deriving closed ones.

---

```
# ROLE

You are a quantitative researcher specialising in short-horizon prediction-market
microstructure. Your output will be used to decide whether to build and fund a live
trading bot on Polymarket's 5-minute BTC up/down markets, and if so, which strategy.
Money will be risked on your conclusions. A correct "no edge exists, stop" is a
successful outcome and is worth more than an optimistic strategy that loses.

# MISSION

Determine whether a positive-expectancy, capital-efficient, automatable strategy exists
on Polymarket's 5-minute BTC up/down binary markets, net of all real costs, and specify
it precisely enough to implement. Rank every candidate strategy by expected value per
day at $500, $5,000 and $50,000 of deployed capital, with the sample size needed to
distinguish it from zero.

# GROUND TRUTH — ALREADY MEASURED, DO NOT RE-DERIVE

The following were measured live against Polymarket's APIs across 700 historical windows
and 170+ freshly-sampled resolved windows. Treat them as given. You may contradict any
of them ONLY by citing a primary source (official docs, on-chain data, or the API itself)
and saying explicitly which measurement you believe is wrong and why.

Market mechanics (verified live from the market object):
- Binary up/down on BTC, new window every 5 minutes, 288 windows/day.
- Winning side settles $1, losing side $0. Price = implied probability.
- Taker fee = shares x 0.07 x p x (1-p). takerOnly = true. Makers pay ZERO.
- Maker rebateRate = 0.2. Tick size = 0.01. orderMinSize = 5 shares.
- Liquidity rewards: rewardsMinSize = 50 shares, maxSpread = 4.5 (cents).
- Resolution source is CHAINLINK, not Binance. Measured Binance/Chainlink
  disagreement: 5.3% of windows, all under 2 bps.
- Settlement takes ~4.6 minutes after window close, NOT T+30s.
- Orders are EIP-712 signed off-chain and POSTed to Polymarket's REST CLOB.
  Polygon RPC is NOT in the trade path — only approvals and redemption.
- Gamma's bestBid/bestAsk are NOT tradeable (observed 0.47/0.48 vs a live /book of
  0.40/0.41). Use /book only. prices-history "p" is the MIDPOINT, not a fill price.
- Gamma hides settled markets unless closed=true.

Cost dominance:
- At p=0.50 the taker fee is $0.0175/share against a $0.01 spread. The fee is 1.75x
  the entire margin being traded for. Any strategy that crosses the spread at mid
  prices is dead on arrival on fee alone.

Liquidity vs time (n=170 resolved windows, favourite fillable at 5 shares under $0.99):
  T-120s: 90%  [85%, 94%]
  T-90s:  76%  [69%, 82%]
  T-60s:  61%
  T-45s:  52%
  T-30s:  36%
  T-20s:   1%
  T-10s:   0%
The book is liquid for most of the window and vacates in the final ~20 seconds.
Every public reference bot decides at T-50s..T-10s, i.e. inside the dead zone.

Calibration (700 windows, mid+half-spread as the fill proxy):
  all underdogs      n=700 hit=15.57% implied=17.20% z=-1.14  ROI=-14.30%
  band <=0.88        n=350 hit=71.71% implied=70.86% z=+0.35  ROI= -0.70%
  band 0.88-0.94     n= 81 hit=93.83% implied=91.64% z=+0.71  ROI= +1.80%
  band 0.94-0.99     n=214 hit=97.66% implied=97.47% z=+0.18  ROI= +0.02%
  band >0.99         n= 55 hit=100.0% implied=99.90% z=+0.23  ROI= +0.09%
No band reaches z > 2. The market looks calibrated. The tail is priced almost exactly
fair (dog mid 0.00-0.02: hit 1.55% vs implied 1.58%, z=-0.03), so "micro-hedge with
cheap tails" is a fee-paying lottery ticket, not a hedge.

Naive two-sided market making (read-only simulation, 90+ resolved windows, quoting
alternately at T-120s and T-60s):
- Because tick = $0.01, the two best bids sum to ~$0.99. A TWO-SIDED fill is a locked
  ~+1.5c/share regardless of who wins. Adverse selection cannot touch it.
- But 45-62% of windows fill on ONE side only, leaving a naked position.
- In 85 of 85 one-sided fills, the side that filled was the side that LOST
  (p = 3.8e-6 and falling). This is mechanism, not luck: a resting bid is hit
  precisely because the market is leaving that token.
- Mean PnL: T-120s = -0.077/share, T-60s = -0.097/share. Break-even needs the
  one-sided rate under ~8%. The result is offset-independent, so no choice of quote
  time fixes it.
- Checked against the "correlated windows / trending hour" objection: runs test on
  the winner sequence gave z=+0.61 (slightly MORE alternation than chance), and the
  one-sided fills split evenly across both directions. The streak is not an artifact.

# DEAD ENDS — DO NOT PROPOSE THESE

Do not spend research budget on, or recommend, any of the following. Each was tested
and rejected on evidence:
1. Buying cheap underdog tails as a hedge against whipsaw. Priced fair; fee is 6.8%
   of notional on a 2.6c bet. Every bucket negative.
2. Deciding at T-10s or T-20s. The book is empty there (0% and 1% fillable).
3. Capping entry at p<=0.88. That selects the worst-performing band (-0.70% ROI).
4. Naive symmetric two-sided quoting with no hedge and no cancel logic. See above.
5. Multi-RPC routing "to prevent execution drops". RPC is not in the trade path.
6. Signalling on Binance while the market resolves on Chainlink, without modelling
   the basis.
7. Any strategy justified by a backtest that uses mid or midpoint prices as fill
   prices, or that omits the fee term.

# THE OPEN QUESTIONS — RANKED, ANSWER IN THIS ORDER

## Q1. Is the settlement oracle exploitable? (highest value, least explored)
These markets resolve on Chainlink, which is a DISCRETE feed: it updates on a
heartbeat and/or a deviation threshold, not continuously. Establish, from primary
sources and on-chain data:
- Exactly which feed/aggregator resolves these markets (address, network, decimals).
- Its heartbeat and deviation threshold, and its actual observed update interval
  distribution over a recent week.
- The precise resolution rule: which round/answer/timestamp is compared to which,
  and how ties and stale rounds are handled. Quote the UMA/Polymarket resolution
  text verbatim.
- The consequence: if the resolving price is a stale oracle round rather than the
  spot price at T=0, then in the final seconds the outcome may be DETERMINED while
  the market is still pricing it as uncertain. Quantify how often, and by how much,
  the last pre-close oracle round already fixes the winner.
- Then confront the killer interaction: the book is 0-1% fillable at T-20s/T-10s,
  which is exactly when that information exists. Does any fillable liquidity exist
  for a MAKER (resting order placed earlier, still live) at that moment? Is there a
  price at which the deterministic side can be lifted?

## Q2. Do liquidity rewards change the sign of market making?
The maker rebate (0.2) was modelled, but the liquidity REWARDS program was not.
rewardsMinSize = 50 shares at maxSpread = 4.5c. Establish:
- The exact current reward formula, epoch length, scoring (one-sided vs two-sided,
  time-weighted), and the daily reward pool allocated to these specific markets.
- Empirically or from published data, the realistic $/day a maker quoting 50 shares
  within 4.5c earns.
- Compare directly against the measured -0.077 to -0.097/share adverse-selection
  bleed at that size. State the break-even reward rate. This is a straight
  arithmetic comparison and it decides the entire maker branch.

## Q3. Can the one-sided fill be hedged instead of avoided?
The maker loss is entirely in one-sided fills, which are 100% on the losing side.
A one-sided fill is a directional BTC position with known delta. Assess:
- Hedging the naked side on a liquid CEX perp (Binance/Bybit/OKX) or a DEX perp
  (Hyperliquid) within seconds of the fill: cost per hedge (taker fee + spread +
  slippage at the relevant notional), latency feasibility, and residual basis risk
  from the Chainlink-vs-perp difference.
- Whether the hedge cost is smaller than the measured loss. Give the arithmetic at
  5, 50 and 500 shares.
- Alternative: aggressive cancel/requote — cancel the resting quote the instant the
  other side's book moves away. Quantify the cancel latency required, given that
  the adverse move and the fill are the same event.
- Alternative: quote only when a two-sided fill is likely. Identify observable
  pre-conditions (spread, depth symmetry, realised vol, time-to-close) that predict
  two-sided fills, and state what fraction of windows survive that filter.

## Q4. Is there any genuine predictive signal at T-120s to T-60s?
The market is calibrated at mid prices. Establish whether any of the following
produce a calibrated-probability improvement large enough to clear the fee at the
offsets where the book is actually fillable:
- Perp funding rate, open interest change, CEX order-book imbalance, aggressive
  trade flow (CVD), realised vol regime, time-of-day / session effects.
- The Chainlink-vs-Binance basis itself as a signal (measured 5.3% disagreement,
  all under 2 bps).
- Cross-venue: does the same or similar short-horizon BTC binary trade anywhere
  else (Kalshi, other prediction venues, exotic options desks)? Is there a
  price-disagreement arbitrage, and what is the settlement-rule mismatch risk?
For each candidate signal, state the required effect size to beat the fee at
p=0.50, p=0.75 and p=0.94, and the number of windows needed to detect it at 80%
power.

## Q5. Execution and operational reality
- CLOB REST/WebSocket endpoints, authentication model, rate limits, and measured
  order-placement round-trip latency from a commodity VPS.
- Whether market/marketable orders, post-only, GTD/FOK/FAK and mass-cancel are
  supported, and their exact semantics.
- Capital efficiency: USDC per window, collateral lockup, how many concurrent
  windows can be worked, and the redemption path
  (redeemPositions, gas cost, batching across windows).
- Failure modes: partial fills, rejected orders near close, order-book outages,
  what happens to a resting order at window close.
- Jurisdiction and Terms of Service: is programmatic trading permitted, is the
  operator's access lawful, and what are the account-level risks. Be factual, not
  reassuring.

# STANDARD OF EVIDENCE

Every factual claim must be tagged:
  [VERIFIED: <url or contract address or API endpoint>]
  [INFERRED: <the reasoning and what would falsify it>]
  [UNKNOWN: <what measurement would settle it>]
An untagged claim will be treated as fabricated.

Rules:
- Prefer primary sources: official Polymarket/CLOB docs, on-chain contract reads,
  the live API. Blog posts, YouTube, and GitHub READMEs are hearsay unless the
  underlying claim is independently verifiable.
- Any GitHub bot you cite: state its star count, last-push date, and whether it
  models the fee. Most public bots do not, which makes their logic evidence of
  what people believe, not of what works.
- Every quantitative claim gets a sample size and a confidence interval. A point
  estimate with no n is not a result.
- Report multiple-hypothesis testing honestly. State how many buckets/variants were
  examined and apply the correction. A z>2 out of eight buckets is noise.
- Never use midpoint or mid+half-spread as a fill price. Use real book VWAP at the
  intended clip size, or say the number is a floor.
- Every PnL figure must be net of: taker fee (if crossing), spread, gas, hedge cost
  (if hedging), and adverse selection. State each term.
- Where you cannot verify something, say so and specify the exact measurement that
  would resolve it. Do not fill gaps with plausible-sounding numbers.

# DELIVERABLE

Produce a single research report with these sections:

1. VERDICT (<=200 words). Does a viable strategy exist? If yes, name it in one
   sentence. If no, say so plainly and stop recommending. Lead with the answer.

2. STRATEGY CANDIDATES — a ranked table. For each:
   name | mechanism in one line | edge source | expected $/day at $500 / $5k / $50k |
   biggest risk | the single cheapest experiment that would kill it | windows needed
   for 80% power.
   Order by (expected value) / (cost to falsify). Include "do nothing" as a row with
   its honest EV of $0 and zero risk, so every candidate is scored against it.

3. THE ORACLE ANALYSIS (Q1) in full. This is the section most likely to contain
   something nobody has exploited. Include the exact resolution rule, verbatim.

4. THE MAKER ARITHMETIC (Q2 + Q3). One table that puts rewards income, rebate,
   spread capture, adverse-selection bleed and hedge cost in the same units
   ($/share and $/day) and sums them. State the sign.

5. SIGNAL SURVEY (Q4). Every candidate signal with required effect size vs
   measured or literature-reported effect size. Kill the ones that cannot clear
   the fee, explicitly.

6. IMPLEMENTATION SPEC — only for candidates that survive. Endpoints, order types,
   the exact decision rule with all thresholds as named constants, the timing
   schedule relative to window close, position sizing (Kelly fraction and the cap),
   and a claim/redemption loop timed for ~4.6 min settlement.

7. RISK CONTROLS — hard position limits, daily loss limit, kill-switch conditions,
   what happens on API outage mid-window, and the specific observation that should
   make the operator shut the bot off permanently.

8. FALSIFICATION PLAN — the ordered list of cheap read-only experiments that would
   confirm or kill the top candidate, each with the data to collect, the statistic,
   the threshold, and the sample size. Cheapest and most decisive first.

9. WHAT I COULD NOT VERIFY — an explicit list. Do not omit this section.

# TONE

Write like a desk quant reporting to a risk committee. No marketing language, no
"world-class", no hype, no motivational framing. Short declarative sentences.
Tables over prose where a table is clearer. If the honest answer is "this market is
efficient at retail size and the correct action is not to trade it", say exactly
that in section 1 and support it. Do not invent a strategy to avoid a negative
conclusion.
```

---

## Notes on using this

- The ground-truth block is what makes it worth running. Without it a deep-research
  pass burns most of its budget rediscovering that fees exceed the spread.
- **Q1 (oracle) and Q2 (liquidity rewards) are the two genuinely unexplored angles.**
  Q2 in particular is pure arithmetic that this project never did: the maker branch was
  closed on adverse selection alone, with reward income assumed to be zero.
- If the report comes back with a candidate, do not implement it. Run its section-8
  falsification experiment first, read-only, at the stated sample size.
