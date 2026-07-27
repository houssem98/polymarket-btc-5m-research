# Polymarket 5-Minute BTC Up/Down: Strategy Feasibility Assessment

## 1. VERDICT

No positive-expectancy, capital-efficient, automatable strategy exists on these markets at retail size ($500–$50,000). The correct action is **do not trade them directionally or as a naive maker**. Three facts settle it. First, the market is calibrated at mid prices — no band reaches z>2 across eight buckets, and after a multiple-comparison correction nothing survives. Second, the taker fee (shares × 0.07 × p × (1-p) = $0.0175/share at p=0.50) exceeds the entire $0.01 spread being competed for, so any spread-crossing strategy is dead on fee alone. Third, the one genuinely unexplored angle — the settlement oracle — resolves against **Chainlink Data Streams**, a sub-second pull-based feed, **not** a heartbeat aggregator. There is therefore no "stale oracle round" that fixes the winner while the book still prices uncertainty. The exploitable surface documented in the literature is *spot-price manipulation of Binance in the final ~50 seconds*, which requires large capital, is now academically flagged, is being designed out by Polymarket (a signalled move to time-weighted/longer settlement), and is plausibly illegal market manipulation. The maker branch also stays negative: platform liquidity-reward pools for these specific markets appear to be zero (the published program funds only sports/esports), so reward income does not offset the measured −$0.077 to −$0.097/share adverse-selection bleed. The single defensible course is to run the read-only falsification experiments in Section 8 and, when they fail, deploy nothing.

## 2. STRATEGY CANDIDATES (ranked by EV ÷ cost-to-falsify)

| Rank | Candidate | Mechanism (1 line) | Edge source | EV $/day @ $500 / $5k / $50k | Biggest risk | Cheapest kill-experiment | Windows for 80% power |
|---|---|---|---|---|---|---|---|
| 1 | **Do nothing** | Hold USDC, deploy no capital | None | $0 / $0 / $0 | None (opportunity cost only) | N/A | N/A |
| 2 | Reward-farming maker | Quote 50sh two-sided, harvest liquidity rewards | Reward pool > adverse-selection bleed | ≈$0 / ≈$0 / ≈$0 (pool appears unfunded) | Reward pool is $0 for BTC 5m; naked one-sided fills | Read reward config on live market object via CLOB API | ~1–2 epochs (days) to confirm payout |
| 3 | Hedged maker | Quote maker, hedge one-sided fills on perp | Spread capture net of hedge cost | negative / negative / negative | Fill = adverse move already happened; hedge locks the loss | Log fill-time vs perp mid move for 200 one-sided fills | ~200 fills (~3–5 days) |
| 4 | Predictive signal (funding/OBI/CVD) at T-120..T-60 | Enter favourite when signal beats fee | Miscalibration | negative unless z>2.73 found | Market calibrated; fee floor 1.75× spread | Re-run calibration with real /book VWAP fills, bucketed by signal | 350–3,000+ per bucket |
| 5 | Cross-venue arb vs Kalshi/other | Buy mispriced leg on both venues | Price/settlement gap | negative after settlement-mismatch risk | Different oracle/window/timestamp → both legs can lose | Compare strike/timestamp/oracle rules; paper-log spreads | ~1,000 aligned windows |
| 6 | Spot-manipulation (push Binance into strike) | Move spot in final 50s to drag oracle | Settlement manipulation | positive only at large capital, illegal | Market-manipulation liability; being designed out | N/A — excluded on legal grounds | N/A |

Every candidate scores at or below "do nothing." Candidate 1 wins.

## 3. THE ORACLE ANALYSIS (Q1)

**This is the section the brief expected to contain an unexploited edge. It does not, and the reason is specific and verifiable.**

### 3.1 What resolves these markets
- **Resolution source = Chainlink Data Streams BTC/USD**, not the on-chain Polygon push aggregator. Verbatim market rule: *"This market will resolve to 'Up' if the Bitcoin price at the end of the time range specified in the title is greater than or equal to the price at the beginning of that range. Otherwise, it will resolve to 'Down'. The resolution source for this market is information from Chainlink, specifically the BTC/USD data stream available at https://data.chain.link/streams/btc-usd. Please note that this market is about the price according to Chainlink data stream BTC/USD, not according to other sources or spot markets."* [VERIFIED: https://polymarket.com/event/btc-updown-5m-1772837700]
- Data Streams is **pull-based and sub-second** — a continuous low-latency signed-report feed, categorically different from a heartbeat/deviation on-chain feed. Chainlink docs, verbatim: *"Chainlink Data Streams supports sub-second data resolution for latency-sensitive use cases by retrieving data only when needed."* [VERIFIED: https://docs.chain.link/data-streams]
- The arXiv paper confirms Polymarket reads Data Streams "so the settlement value can be sampled at the exact close." [VERIFIED: https://arxiv.org/html/2606.31675]
- On-chain posting combines **Chainlink Data Streams + Chainlink Automation**. Press release, verbatim: the integration *"combines Chainlink Data Streams, which provide low-latency, timestamped, and verifiable oracle reports, with Chainlink Automation, enabling timely, automated onchain settlement of markets."* The 5-minute BTC markets launched Feb 12–13, 2026. [VERIFIED: https://www.prnewswire.com/news-releases/polymarket-partners-with-chainlink-to-enhance-accuracy-of-prediction-market-resolutions-302555123.html]

### 3.2 The settlement rule
- Open ("Price to Beat") = oracle price at window open; close = oracle price at window close; **Up wins iff close ≥ open (ties → Up).** [VERIFIED: arXiv 2606.31675; polymarket.com rules]
- Windows are Unix timestamps divisible by 300; the open is the first stream print at/after the boundary, matching Price-to-Beat at +0ms. [INFERRED from developer gist https://gist.github.com/Archetapp/7680adabc48f812a561ca79d73cbac69 — falsified if a resolved market's Price-to-Beat diverges from the +0ms stream print, which is Experiment 2 below]

### 3.3 The consequence — the exploit that isn't
Because the feed is continuous/sub-second and publicly streamed (Polymarket's own `crypto_prices_chainlink` RTDS topic carries millisecond timestamps [VERIFIED: https://docs.polymarket.com/developers/RTDS/RTDS-crypto-prices]), **there is no stale oracle round.** The settlement price is not "determined but not yet public" in the final 10–20 seconds — it tracks spot in real time. The Q1 premise (a discrete heartbeat feed that fixes the winner while the market still prices uncertainty) is **false for this feed**. This contradicts the ground-truth characterisation of the oracle as "a DISCRETE feed … heartbeat and/or deviation threshold." The primary Chainlink documentation and the market rule text both specify Data Streams, which is a continuous pull feed, not the heartbeat on-chain aggregator. I believe the ground-truth "heartbeat/deviation" description conflates Chainlink's standard Data **Feeds** with the Data **Streams** product actually used, and is therefore the wrong measurement. The correct implication is the opposite of an edge: there is no oracle-latency gap to trade.

### 3.4 The real surface, and why it is not for a retail bot
The documented vulnerability is **settlement manipulation**: pushing Binance spot across the strike in the final seconds, because the oracle tracks spot ~1:1 (Binance mid sits ~2.5 bps from the oracle and moves one-for-one within each window). The Stanford/SMU working paper — Dai, Jia & Yu, *"Settlement Manipulation in Prediction Markets"* (arXiv 2606.31675, dated June 30 / July 1, 2026) — examined ~16,000 five-minute BTC contracts from the Feb 12, 2026 launch through April and found near-settlement order-flow spikes followed by post-settlement reversals, concentrated in near-the-money cycles and largely absent at the 15-minute horizon. **Profit-estimate conflict, flagged:** press coverage of the same paper reports two figures — roughly **$8.2 million captured by ~821 flagged wallets** (higher-end framing) and roughly **$1.28 million transferred from ordinary traders to manipulators** (narrower framing); the discrepancy is real across coverage and I have not reconciled it to the paper's precise definition. [VERIFIED (existence and range): arXiv 2606.31675; https://finance.yahoo.com/markets/crypto/articles/stanford-study-finds-signs-bitcoin-134715897.html; https://moneycheck.com/stanford-study-exposes-manipulation-in-polymarkets-bitcoin-prediction-markets/] Either way, this strategy requires enough capital to move BTC spot, is circumstantially illegal manipulation (and now explicitly prohibited by Polymarket's March 2026 market-integrity rules), and Polymarket has signalled a move to average-price/longer settlement that would remove it. **Excluded on legal and capital grounds.**

For a maker, the **killer interaction is confirmed**: the book is 0–1% fillable at T-20s/T-10s (per the ground-truth liquidity curve) precisely when late information exists, so there is no fillable liquidity to lift the deterministic side, and a resting maker order at that moment is exactly what a settlement manipulator runs over. There is no maker price at which the "determined" side can be lifted, because the maker is the one being lifted.

## 4. THE MAKER ARITHMETIC (Q2 + Q3)

The liquidity-reward formula is a per-minute quadratic order-scoring function S(v,s) = ((v−s)/v)²·b, combined into a two-sided minimum score Q_min = max(min(Q_one, Q_two), max(Q_one/c, Q_two/c)) with scaling factor c = 3.0, summed over 10,080 one-minute samples/epoch, normalised across all makers, then multiplied by the market's daily pool. In the price bands these markets occupy near the extremes — midpoint in [0, 0.10) or (0.90, 1.0] — **single-sided liquidity scores nothing; you must quote both sides to earn at all.** [VERIFIED: https://docs.polymarket.com/market-makers/liquidity-rewards]

The decisive input is the **daily reward pool for BTC 5m markets**, which the project assumed to be zero and never priced. The evidence supports that assumption: Polymarket's published April 2026 incentive program (>$5M) enumerates pools **only for sports and esports** — e.g. English Premier League at $10,000/game ($2,800 pre-game + $7,200 live) and Champions League quarterfinals at $24,000/game — with **no crypto/BTC line item anywhere in the schedule.** [VERIFIED: https://docs.polymarket.com/market-makers/liquidity-rewards] Platform-funded reward income for these markets therefore appears to be ~$0. Any rewards would have to be user-sponsored via the Rewards contract (a third party depositing USDC, e.g. $500 over 10 days = $50/day), which no rational actor does for a 5-minute market that resolves before it matters. [VERIFIED: https://help.polymarket.com/en/articles/13755867-sponsor-market-rewards]

All terms in $/share, for one 50-share two-sided quote, per window:

| Term | $/share | Notes |
|---|---|---|
| Spread capture (two-sided fill) | +0.015 | Two best bids sum ~$0.99; locked regardless of winner |
| Maker rebate (rate 0.2) | + small | Rebate on filled maker volume only; makers pay zero taker fee |
| Liquidity reward income | ≈0.000 | BTC 5m pool appears unfunded [UNKNOWN: exact reward config on live market object — must read CLOB market API] |
| Adverse-selection bleed | −0.077 to −0.097 | One-sided fills 45–62% of windows; 100% of one-sided fills (85 of 85 measured) on the losing side |
| Hedge cost (if hedging) | −(see §4.1) | Perp fee + spread + slippage on delta-notional |
| **Net** | **negative** | Sign is negative; reward income would need to exceed the bleed to flip it |

**Break-even reward rate:** rewards must cover the expected bleed ≈ (one-sided-fill rate) × (loss per filled share). At ~50% one-sided and ~$0.09 loss on the filled 50-share side, expected loss is on the order of $2–$3 per adverse window; across 288 windows/day this compounds far beyond any plausible unsponsored reward share (which is ~$0). The break-even daily reward pool the maker would need to capture is many multiples of anything the platform allocates to these markets. **Unless a live BTC 5m market object shows a funded reward rate large enough that a 50-share two-sided quote earns more than the bleed, the maker branch is negative.** This is the arithmetic the project never completed, and completing it **confirms** the project's conclusion rather than overturning it.

### 4.1 Hedging the one-sided fill (Q3)
A one-sided fill is a directional BTC position, but with two fatal properties: (1) near-the-money 5-minute binaries carry very high delta/gamma, so the perp notional needed to neutralise even a small share position is large relative to the share price; and (2) **the fill and the adverse move are the same event** — a resting bid is hit precisely because the token is leaving that side. The paper's own "the timing of the spot flow is wrong for a hedge" analysis confirms the informed flow precedes the fill. Hedging then locks in the loss rather than preventing it. Perp taker costs are 0.045% of notional on Hyperliquid (base Tier-0) and 0.05% on Binance USDⓈ-M standard tier [VERIFIED: https://eco.com/support/en/articles/15039715; binance.com futures fee schedule], plus spread and slippage on a thin near-close book. At 5 / 50 / 500 shares the hedge notional to delta-neutralise scales up while the loss being avoided is already realised, so hedge cost ≥ loss avoided in exactly the near-money cycles that flip. [INFERRED — falsified by Experiment 4: logging perp mid at fill-time vs +30s for 200 one-sided fills and finding the adverse move has *not* yet happened.]

### 4.2 Cancel/requote and pre-condition filters
- **Aggressive cancel:** would require cancel latency below the adverse-move-to-fill interval, but those are the same event, so no achievable cancel latency helps. (Cancel rate limit is 3,000/10s burst, ample; latency is the binding constraint, not throughput.) [VERIFIED: rate-limit docs]
- **Quote only when a two-sided fill is likely:** the observable pre-conditions that raise two-sided probability — symmetric depth, tight spread, low realised vol, longer time-to-close — are exactly the conditions in which *no one crosses you*. The filter that raises two-sided-fill probability simultaneously collapses fill volume toward zero, so the surviving fraction of windows carries near-zero captured spread. [INFERRED — falsified by Experiment 5: measuring two-sided fill rate and fill volume conditional on depth-symmetry deciles over 500 windows.]

## 5. SIGNAL SURVEY (Q4)

Required edge to beat the fee as a taker = fee/share ÷ probability-cents captured. Fee = 0.07·p·(1−p). At **p=0.50** fee = $0.0175 → need >1.75 probability-cents of true edge over mid; at **p=0.75** fee = $0.01313 → need >1.31c; at **p=0.94** fee = $0.00395 → need >0.40c. Makers pay zero fee but inherit the adverse-selection bleed instead, so the maker "required edge" is the ~$0.08/share bleed, which is worse.

| Signal | Required effect @ p=.50 / .75 / .94 | Measured / literature effect | Verdict |
|---|---|---|---|
| Perp funding rate | >1.75c / 1.31c / 0.40c | Funding accrues over 1h–8h; drift over 5 min ≪ 1c | KILL |
| Open-interest change | same | No published 5-min OI→direction edge at cent scale | KILL |
| CEX order-book imbalance | same | Predictive only at ms–s horizon; decays before T-60s where the book is fillable | KILL at usable offsets |
| Aggressive trade flow (CVD) | same | Same decay; the only place it bites (final seconds) is the 0–1% fillable dead zone | KILL |
| Realised-vol regime | same | Changes variance, not direction; no sign edge | KILL |
| Time-of-day / session | same | Manipulation concentrates overnight/weekends on thin books — a *risk to a maker*, not a retail edge | KILL |
| Chainlink−Binance basis | same | 5.3% of windows disagree, all <2 bps; ~2.5 bps mean gap moves ~1:1 → no persistent exploitable basis | KILL |
| Cross-venue (Kalshi etc.) | same | Different oracle, window boundary and settlement timestamp; settlement mismatch can lose *both* legs | KILL on mismatch risk |

No candidate clears the fee at an offset where the book is fillable. The calibration table already shows every band inside z ∈ [−1.14, +0.71] across eight buckets. Applying a Šidák correction over 8 buckets at α=0.05 (per-bucket α ≈ 0.0064, requiring |z| > 2.73), **nothing survives** — and a lone |z|>2 out of eight independent buckets would occur by chance roughly one time in three, i.e. it is noise, not signal.

## 6. IMPLEMENTATION SPEC

No candidate other than "do nothing" survives Sections 3–5, so **there is nothing to implement for live capital.** The only build authorised is the **read-only measurement harness** for Section 8:
- CLOB REST base `https://clob.polymarket.com`; market WebSocket `wss://ws-subscriptions-clob.polymarket.com/ws/market`.
- Gamma API for discovery; query with `closed=true` to see settled markets (Gamma hides settled markets otherwise). Discover BTC 5m markets deterministically via `window_ts = now − (now % 300)`, slug `btc-updown-5m-{window_ts}`.
- Use `/book` only for fill proxies (Gamma bestBid/bestAsk are non-tradeable; prices-history "p" is the midpoint). Compute real book VWAP at the intended clip size; never use mid or mid+half-spread as a fill.
- RTDS `crypto_prices_chainlink` (btc/usd filter) for the oracle print.
- **No orders. No signing keys on the box.** Authentication for reads is unnecessary (public read endpoints require none); order placement would require EIP-712 L1 signing plus L2 API-key headers, which this harness deliberately does not implement.

Order-type reference (for completeness, not for use here): GTC (resting limit, maker), GTD (expiry), FOK/FAK (marketable, taker), plus post-only to reject any order that would cross. [VERIFIED: https://docs.polymarket.com/trading/orders/create]

## 7. RISK CONTROLS

Because the recommendation is not to trade, the controls are gating conditions on ever going live:
- **Hard gate 1 (rewards):** Do not deploy capital unless a live BTC 5m market object returns a funded reward rate large enough that the §4 break-even flips positive, verified over ≥2 epochs.
- **Hard gate 2 (no fake backtests):** Do not deploy any strategy whose backtest used mid or mid+half-spread as a fill price, or that omits the fee term. Require real `/book` VWAP at clip size.
- **Kill-switch conditions (if ever live):** API 429/503/425 storm; WebSocket staleness > 2s; any single-window loss > 2× expected spread capture; cumulative daily loss > a pre-set hard cap; observed one-sided-fill streak beyond the historical 85/85 baseline.
- **API outage mid-window:** a resting maker order left in the book at window close is a naked directional bet on the losing side (the ground-truth mechanism). The only safe posture is post-and-cancel with a hard cancel by ~T-90s, and any uncancelled order must be treated as a realised loss, not a hopeful hold. RPC is not in the trade path, so multi-RPC routing does nothing for this.
- **Permanent shut-off signal:** if the measured one-sided-fill rate stays above ~8% **and** reward income is zero, the maker branch can never be positive — stop permanently. Likewise, if Polymarket migrates these contracts to time-weighted/longer settlement, re-run the whole analysis from scratch before touching it.

## 8. FALSIFICATION PLAN (cheapest, most decisive first)

Run in order; stop at the first failure. Experiments 1–2 alone will almost certainly end the project at near-zero cost.

1. **Reward-pool read** (minutes, free). Pull every currently-open BTC 5m market object from the CLOB API; read the reward-rate / rewards config. *Statistic:* daily reward pool ($). *Threshold:* if $0 (or below the §4 break-even), the maker branch is dead. *n =* all open BTC 5m markets.
2. **Open-price capture check** (hours, free). Subscribe to `crypto_prices_chainlink` btc/usd; compare the first print at/after each window boundary to the market's published Price-to-Beat. *Statistic:* |diff|. *Threshold:* any material |diff| > 0 falsifies the +0ms open-capture assumption and re-opens (not closes) the oracle question. *n ≈* 100 windows.
3. **Book-VWAP recalibration** (days, free). Re-run the 700-window calibration using real `/book` VWAP at 5 and 50 shares as the fill, bucketed by each candidate signal. *Statistic:* z per bucket with Šidák correction. *Threshold:* deploy nothing unless a bucket shows |z| > 2.73 out of sample. *n ≥* 350/bucket.
4. **One-sided-fill timing** (3–5 days, free). For 200 simulated one-sided fills, log perp mid at fill vs +30s. *Statistic:* sign and size of the move relative to fill time. *Threshold:* if the adverse move precedes the fill, hedging cannot help — kill the hedged-maker branch. *n ≈* 200 fills.
5. **Two-sided-fill predictability** (5–7 days, free). Measure two-sided fill rate and captured spread conditional on depth-symmetry / spread / vol deciles. *Statistic:* two-sided rate × fill volume × net spread per decile. *Threshold:* no decile yields net positive after the bleed. *n ≥* 500 windows.

## 9. WHAT I COULD NOT VERIFY

- **Exact reward rate / pool on live BTC 5m market objects.** The published program excludes crypto, but a per-market or user-sponsored pool cannot be ruled out without a live CLOB market read (Experiment 1). This is the single highest-value unknown, because it is the only input that could in principle flip the maker sign.
- **The ~4.6-minute close-to-settlement delay** is the project's internal measurement; public sources say only "seconds to minutes"/"near-instantaneous." Not externally corroborated.
- **The exact numeric report interval of the Chainlink BTC/USD Data Stream.** Chainlink docs state only "sub-second"/"on-demand"; no fixed millisecond figure is published.
- **The precise close-price sampling algorithm** (whether it is symmetric with the +0ms open-capture rule) is inferred from a developer gist, not an official Polymarket spec.
- **The specific Polygon resolver/adapter contract address** for these fast markets (the UMA CTF Adapter addresses are documented, but the Chainlink-Automation resolver path for the 5-min markets was not pinned to an address).
- **Measured order-placement round-trip latency from a commodity VPS** to the London (AWS eu-west-2) CLOB. Documented limits are known (3,500 orders/10s burst, 36,000/10min sustained; 3,000 cancels/10s), but real RTT was not measured here.
- **Current status of Polymarket's announced migration** to time-weighted / longer settlement for these contracts.
- **The $8.2M vs $1.28M profit-estimate discrepancy** in coverage of the Stanford/SMU paper (Section 3.4) is unreconciled; both figures are attributed to the same working paper by different outlets.
- **Legality of a given operator's access.** Polymarket's ToS prohibit US persons and geo-restricted jurisdictions (Ontario, Italy, Germany and others), and VPN circumvention violates the ToS and has led to enforcement. Programmatic trading via the CLOB API is permitted in principle, but is subject to those jurisdictional bans and to the March 2026 rules prohibiting manipulation, spoofing, wash trading and self-dealing. This is a factual account, not legal advice; obtain counsel before operating.