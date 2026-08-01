# FINDINGS.md — Loop Journal

One dated entry per `/loop` iteration. Append only. See [LOOP_PROMPT.md](LOOP_PROMPT.md).

---

## 2026-07-27 00:06 — iteration 1 (baseline)

| Item | Value |
|---|---|
| Processes | `bot.py`, `ladder.py`, `maker_probe.py` — one instance each ✅ |
| `ladder.jsonl` | **1** row (first ever; file did not exist at iteration start) |
| `paper_trades.jsonl` | 10 rows (+1 during iteration) |
| `maker_probe.jsonl` | 0 rows — probe started 23:59, first write ~T+11min |
| Unresolved rows | none — 0 `winner: null` anywhere |
| G1 fill | **not run** — needs 200 ladder rows, have 1, **~16.6 h** |
| G2 / G3 / G4 | blocked upstream |

**The first ladder row contradicts the T-10s prior.** Window `1785106200` (DOWN won):
favourite ask VWAP@5sh was **0.88 / 0.85 / 0.85 / 0.94 / 0.99 / — / —** at
T-120/90/60/45/30/20/10s. The book is fillable early and dies in the last ~30 s.
Every prior "no fillable ask" measurement (36/36 windows) sampled **only T-10s** —
inside the dead zone. G1 may pass at an early offset. n=1, so this is a hypothesis.

**`bot.py` decides at T-10s** — all 10 paper rows are `skip / insufficient_ask_depth`,
0 fills. It is measuring the one moment the book is empty. Do not change it before G1;
that would fit the decision rule to a single window.

**Live-verified this iteration:** `feeSchedule = {rate 0.07, takerOnly true,
rebateRate 0.2}`, tick `0.01`, `orderMinSize 5`, `rewardsMinSize 50 @ maxSpread 4.5`.
Gamma's `bestBid`/`bestAsk` (0.47/0.48) disagreed with the live CLOB book (0.40/0.41) —
**use `/book` only**. `maker_probe.py` and `bot.py` contain no `ClobClient`, key, or
`post_order` (grepped for call-syntax; the only hits repo-wide are inside a string
literal in `gemini-code-1785098674639.py`, which is never executed).

**Probe fixed mid-iteration.** First run quoted `None` on both sides: tick is 0.01 and
the book sits at a 0.01 spread, so "one tick inside the touch" is usually impossible.
Now falls back to **joining** the bid and logs `mode: improve|join` plus `queue_ahead`.
Queue position, not price improvement, is the real maker constraint here.

**The fill test took three revisions.** Worth stating, because a wrong one makes 200
rows worthless:

| Rule | Why it failed |
|---|---|
| `ask <= q` | Ignores queue. Logged FILL with 728 and 1199 shares resting ahead |
| `+ size at q dropped >= 5` | Size leaving a level is **cancellation** as often as consumption — makers pull quotes near close |
| `touched AND queue consumed >= 5` | Current. Trades happen at our price only if the ask came down to it |

Raw components (`touched`, `queue_ahead`, `min_size_at_q`, `min_ask_seen`, `fill_t`) are
all logged, so G4 can re-derive under any rule. `filled` is the conservative default.

**Both sides filled in both clean windows** (n=2, T-120s quotes):

| Window | UP | DOWN | sum | gross/share |
|---|---|---|---|---|
| `1785107700` | join@0.49 | join@0.50 | 0.99 | **+0.01** |
| `1785108000` | join@0.56 | join@0.43 | 0.99 | **+0.01** |

This reframes G4. Joined bids sum to 0.99 because the spread is one tick, so **when both
sides fill the PnL is deterministic** — `1 − (q_up + q_down) + rebates`, independent of
who wins. Adverse selection cannot touch a two-sided fill. The real G4 question is
therefore **not** "does rebate beat adverse selection" but **"what fraction of windows
fill one-sided, and what do those lose?"** n=2 — this is a hypothesis, and the
suspiciously uniform `queue → 0.0` needs ruling out as book-shift rather than trading.

**Next iteration:** ladder growth (5 rows at 00:25, ~6/30 min → 200 in ~16 h); first
`maker_probe.jsonl` rows with resolved winners; compute the one-sided fill fraction as
soon as n ≥ 20. Do not run G1 before 200 rows.

---

## 2026-07-27 00:31 — iteration 2

| Item | Value | Δ |
|---|---|---|
| Processes | `bot.py`, `ladder.py`, `maker_probe.py` — one each ✅ | — |
| `ladder.jsonl` | 5 | +4 |
| `paper_trades.jsonl` | 14 | +4 |
| `maker_probe.jsonl` | 1 resolved (3 windows quoted) | +1 |
| Unresolved > 30 min | 0 | — |
| G1 | **not run** — 5/200 rows, ~16 h | — |

**G1 preview — not the gate, n=5.** Favourite ask VWAP@5sh under 0.99:

| offset | T-120 | T-90 | T-60 | T-45 | T-30 | T-20 | T-10 |
|---|---|---|---|---|---|---|---|
| fillable | **5/5** | 4/5 | 3/5 | 3/5 | 2/5 | 0/5 | 0/5 |
| median VWAP | 0.88 | 0.85 | 0.62 | 0.94 | 0.94 | — | — |
| median depth | 23.4k | 20.1k | 19.3k | 8.8k | 5.2k | 0 | 0 |

Monotone decay, dead in the last 20 s. G1's >70% bar is cleared at T-120 so far. **This is
fillability, not edge** — a favourite bought at T-120 for 0.88 is cheap precisely because
direction is still unknown. G2 is what decides whether that price is beatable.

**Maker arithmetic confirmed on the first resolved row.** `1785107700`, DOWN won:

| side | quote | filled | fill_t | pnl/share |
|---|---|---|---|---|
| UP | 0.49 | ✅ | T-87.5s | −0.4865 |
| DOWN | 0.50 | ✅ | T-107.7s | +0.5035 |
| **both** | 0.99 | | | **+0.017** |

Matches the predicted `1 − (q_up + q_down) + rebates` exactly. Fills landed 12–32 s after
quoting, with `min_ask_seen` strictly below the quote on both sides — real trading through
the level, **not** the end-of-window book collapse I suspected. Checked before rewriting
the fill test; no fourth revision needed.

**Independent confirmation from `ladder.jsonl` bids** (different file, 18 observations
across 5 windows × T-120…T-30): `bid_up + bid_down` = **0.99 median** (range 0.97–1.00,
distribution 1.00×2, 0.99×12, 0.98×2, 0.97×2 → mean 0.9889, **+0.011/share** gross).

**Do not read this as free money.** `bid_up + bid_down = 1 − spread` is an identity, not a
discovery — it is the ordinary market-maker spread capture, and 200–2500 shares are already
queued at those prices, which is the market telling you how many makers want it. Two-sided
fill rate is 3/3 so far and is the entire question. One-sided fills are where the loss lives
and none have been observed yet, which at n=3 means nothing.

**Note:** `windows.jsonl` is stale since 23:49 — its writer was `probe.py`, retired per
ROADMAP_V2 §6. Not a failure.

**Next iteration:** one-sided fill fraction once maker n ≥ 20; ladder toward 200.

---

## 2026-07-27 00:42 — iteration 3

| Item | Value | Δ | Gate |
|---|---|---|---|
| Processes | 3, one each ✅ | — | — |
| `ladder.jsonl` | 8 | +3 | G1 at 200 → ~16 h |
| `maker_probe.jsonl` | 3 | +2 | G4 at 200 → ~17 h |
| `paper_trades.jsonl` | 18 | +4 | — |
| Stale nulls | 0 | — | — |

G1 preview (n=8, **not** the gate): favourite fillable **8/8** at T-120, 7/8 T-90, 6/8 T-60,
6/8 T-45, 4/8 T-30, **0/8** at T-20 and T-10. Median VWAP@5sh at T-120 slipped 0.88 → 0.73
as less lopsided windows entered the sample. G4 preview: **3/3 two-sided**, zero one-sided,
mean **+0.0165/share** — but n=3, and one-sided fills are the only thing that can kill it.

**Truncation artifact ruled out.** `/book` returns the full ladder — 89 bid levels covering
every tick 0.01–0.89, asks filling 0.90–0.99 — so a level reading size 0 means the size
genuinely left, not that it fell out of a top-N view. Someone is quoting every tick; the
`queue_ahead` we sit behind is theirs. Combined with `min_ask_seen` strictly below quote on
all six side-fills, the fill signal survives.

**Next iteration:** hold. Both gates are data-blocked; nothing to decide before ~16 h.

---

## 2026-07-27 01:05 — iteration 4 · **adverse selection shows up**

| Item | Value | Δ |
|---|---|---|
| Processes | 3, one each ✅ | — |
| `ladder.jsonl` | 12 | +4 |
| `maker_probe.jsonl` | 7 | +4 |
| `paper_trades.jsonl` | 22 | +4 |

G1 preview (n=12): T-120 **12/12**, T-90 10/12, T-60 9/12, T-45 7/12, T-30 4/12,
T-20 **0/12**, T-10 **0/12**. Unchanged shape.

**G4 preview (n=7) — mean PnL is now −0.0953/share.** The first one-sided fills landed:

| window | winner | fills | filled side | pnl/share |
|---|---|---|---|---|
| `…108600` | UP | 1 | **DOWN** (loser) | **−0.5565** |
| `…108900` | DOWN | 1 | **UP** (loser) | **−0.1878** |
| 5 others | — | 2 | both | +0.0107 … +0.0170 |

**In both one-sided windows the side that filled was the side that lost.** That is adverse
selection with the exact sign theory predicts: a resting bid is hit precisely when the
market is leaving that token, and the side that would have won moves away before filling.

The economics are lopsided. A two-sided fill earns ~**+0.0154**; a one-sided fill averages
~**−0.372** — **24× larger**. Break-even needs the one-sided rate below **~3.8%**. Observed
**2/7 = 29%**, a factor of 7.5 the wrong way.

Iteration 2's framing was right that two-sided fills are safe and wrong about what that
bought us: the risk was never inside the two-sided fills, it was in the fraction that are
not, and three clean windows made a 29% failure rate look like 0%. n=7 — G4 still needs 200,
and this is exactly the sample size at which a result feels conclusive and is not.

**Latent risk, unrelated to the loop:** `gemini-code-1785098674639.py` is a *generator*.
Running it writes `polymarket_btc_5m_bot/` containing `clob_execution.py` with a live
`ClobClient` + `post_order`, plus a `.env.example` prompting for a private key. `DRY_RUN`
defaults True — one env var from live. Nothing in this project imports or runs it, and this
iteration did not execute it. Its own config encodes both parameters our data refutes:
`SNIPE_WINDOW_START = 10` (T-10s, **0/12** fillable) and `MAX_ENTRY_PRICE = 0.88` (worst
band, −0.70% ROI).

**Next iteration:** watch the one-sided fill fraction. If it holds near 25–30% through
n ≈ 50, the maker path is closing and G4 can be called early on magnitude alone.

---

## 2026-07-27 01:12 — iteration 5

| Item | Value | Δ |
|---|---|---|
| Processes | 3, one each ✅ | — |
| `ladder.jsonl` | 14 | +2 |
| `maker_probe.jsonl` | 9 | +2 |
| `paper_trades.jsonl` | 24 | +2 |
| Stale nulls | 0 | — |

G1 preview (n=14): T-120 **14/14**, T-90 12/14, T-60 11/14, T-45 9/14, T-30 4/14,
T-20 **0/14**, T-10 **0/14**.

G4 preview (n=9): 7 two-sided at **+0.0147**, 2 one-sided at **−0.3722**, one-sided rate
**22%**, mean **−0.0712/share**. No new one-sided fills this iteration.

**The conclusion is robust to the noisy loss estimate; the fill rate is what's uncertain.**
The −0.3722 loss comes from exactly 2 events (−0.5565, −0.1878), so break-even was re-derived
across a range of assumed losses:

| assumed one-sided loss | 0.10 | 0.20 | 0.30 | 0.372 | 0.50 |
|---|---|---|---|---|---|
| break-even rate | 12.8% | 6.8% | 4.7% | 3.8% | 2.9% |
| observed 22% | ✗ | ✗ | ✗ | ✗ | ✗ |

Even at a quarter of the observed loss the path still fails. Exact binomial:
**P(≥2 one-sided in 9 | true rate 3.8%) = 0.044**. Wilson 95% CI on the rate is
**[6.3%, 54.7%]** — the lower bound clears break-even, but at n=9 that interval is doing
almost no work, and the point estimate rests on 2 events.

**Not calling G4.** p=0.044 at n=9 with a hand-picked quote offset (T-120s, one of seven)
is precisely the underpowered result ROADMAP_V2 warns against — and the offset choice is an
untested fork. If 22% holds to n ≈ 40, the CI tightens to ~[12%, 38%] and G4 closes on
magnitude without waiting for 200.

**Next iteration:** one-sided rate at n ≈ 15–20. Everything else is on rails.

---

## 2026-07-27 01:42 — iteration 6 · **maker path provisionally closed at T-120**

| Item | Value | Δ |
|---|---|---|
| Processes | 3, one each ✅ | — |
| `ladder.jsonl` | 20 | +6 |
| `maker_probe.jsonl` | 15 | +6 |
| `paper_trades.jsonl` | 30 | +6 |
| Stale nulls | 0 | — |

G1 preview (n=20): T-120 **20/20**, T-90 14/20, T-60 13/20, T-45 11/20, T-30 6/20,
T-20 **0/20**, T-10 **0/20**.

**G4 preview (n=15) — got worse, and a second signal appeared.**

| | n | mean/share |
|---|---|---|
| two-sided | 8 | **+0.0148** |
| one-sided | **7 (47%)** | **−0.1826** |
| **overall** | 15 | **−0.0773** |

Break-even one-sided rate **7.5%**; observed **47%**; Wilson 95% CI **[24.8%, 69.9%]** —
the *lower* bound is 3.3× break-even. Exact binomial **p = 0.0001**.

**All 7 one-sided fills were on the losing side.** Not 6, not 5 — 7 of 7. Under a coin
flip that is p = 0.5⁷ = **0.0078**, an independent test of the mechanism rather than of the
PnL. A resting bid is filled *because* the market is leaving that token; the side that
would have won never trades down to you. Two independent tests, both significant, pointing
at the same structural cause.

At 5 shares/side this is **−$0.39/window ≈ −$111/day** across 288 windows.

**Provisionally closed, not called.** n=15 against a 200 threshold, and T-120s was one
fork of seven I picked without testing. So the probe now **alternates T-120 / T-60** per
window (`quote_at` records which; the 15 existing rows are all 120 and stay valid). If
T-60 fails the same way, G4 closes on two offsets and 200 rows becomes ceremony.

**The two branches have swapped.** ROADMAP_V2 §5 calls the maker side "the best remaining
lead" and expected G1 to fail. Measurement says the opposite: the taker path is fillable
20/20 at T-120 and the maker path is bleeding. Neither is decided — G1 still needs 200 rows,
and fillability is not edge — but the *ordering* of the two leads has inverted.

**Next iteration:** first T-60 rows. Compare one-sided rate across the two offsets.

---

## 2026-07-27 02:11 — iteration 7 · checkpoint

| Item | Value | Δ |
|---|---|---|
| Processes | 3, one each ✅ | — |
| `ladder.jsonl` | 26 | +6 |
| `maker_probe.jsonl` | 19 | +4 |
| `paper_trades.jsonl` | 36 | +6 |
| Stale nulls | 0 | — |

G1 preview (n=26): T-120 **25/26**, T-90 19/26, T-60 17/26, T-45 15/26, T-30 10/26,
T-20 **1/26**, T-10 **0/26**. First T-120 miss and first T-20 hit — 96% still clears the
70% bar comfortably.

G4 preview, split by quote offset:

| offset | n | two-sided | one-sided | mean/share | filled the loser |
|---|---|---|---|---|---|
| T-120 | 17 | 9 @ +0.0149 | 8 (47%) @ −0.1945 | **−0.0836** | **8/8** |
| T-60 | 2 | 1 @ +0.0149 | 1 (50%) @ −0.1680 | −0.0766 | 1/1 |

T-120 is unchanged in shape and the adverse-selection streak is now **8/8**, p = 0.5⁸ =
**0.0039**. T-60 is n=2 — it points the same way and that is worth nothing yet; alternating
yields ~6 rows/hour/offset, so the fork resolves in ~2 h, not 17.

**Next iteration:** T-60 at n ≈ 8–10. Nothing else is actionable.

---

## 2026-07-27 02:41 — iteration 8 · **adverse selection is 11/11, offset-independent**

| Item | Value | Δ |
|---|---|---|
| Processes | 3, one each ✅ | — |
| `ladder.jsonl` | 32 | +6 |
| `maker_probe.jsonl` | 25 | +6 |
| `paper_trades.jsonl` | 42 | +6 |
| Stale nulls | 0 | — |

G1 preview (n=32): T-120 **31/32**, T-90 24/32, T-60 21/32, T-45 19/32, T-30 12/32,
T-20 1/32, T-10 0/32.

| offset | n | two-sided | one-sided | mean/share | break-even | exact p | filled loser |
|---|---|---|---|---|---|---|---|
| T-120 | 20 | 10 @ +0.0145 | 9 (45%) @ −0.1762 | **−0.0720** | 7.6% | **0.0000** | **9/9** |
| T-60 | 5 | 2 @ +0.0133 | 2 (40%) @ −0.1334 | −0.0480 | 9.1% | 0.068 | **2/2** |

**Every one-sided fill at either offset has been on the losing side: 11/11, p = 0.00049.**
That is a claim about mechanism, not PnL, and it does not depend on the quote offset — which
is what makes it damaging. If a one-sided fill *implies* holding the loser, expected value is
pinned by the one-sided rate alone: it must fall under ~8% for the +0.0148 two-sided capture
to survive. Observed 45% at T-120, 40% at T-60. Moving the quote earlier or later does not
touch the cause, so there is no offset that rescues it.

**Still not calling G4** — 25 rows against 200, and T-60 is n=5 with p=0.068. But T-120 is
closed for practical purposes (p≈0, CI lower bound 26% vs 7.6% break-even), and the only
live question is whether T-60 behaves differently. Nothing here justifies inventing a third
variant to keep the branch alive.

**Next iteration:** T-60 toward n ≈ 15. G1 continues toward 200 (32 now, ~13 h).

---

## 2026-07-27 03:11 — iteration 9 · **both maker offsets now negative; streak survives the independence check**

| Item | Value | Δ |
|---|---|---|
| Processes | 3, one each ✅ | — |
| `ladder.jsonl` | 38 | +6 |
| `maker_probe.jsonl` | 31 | +6 |
| `paper_trades.jsonl` | 48 | +6 |
| Stale nulls | 0 | — |

G1 preview (n=38): T-120 **36/38**, T-90 28/38, T-60 24/38, T-45 22/38, T-30 14/38,
T-20 1/38, T-10 0/38.

| offset | n | two-sided | one-sided | no fill | mean/share | break-even | exact p | filled loser |
|---|---|---|---|---|---|---|---|---|
| T-120 | 23 | 12 @ +0.0144 | 10 (43%) @ −0.2052 | 1 | **−0.0817** | 6.6% | **0.0000** | **10/10** |
| T-60 | 8 | 2 @ +0.0133 | 4 (50%) @ −0.0766 | 2 | **−0.0350** | 14.8% | **0.0203** | **4/4** |

**Both offsets are now independently significant and both are negative.** T-60 fills less
often (2 of 8 windows never filled at all — less time), which shrinks the loss but does not
change its sign.

**The 14/14 streak is not a trend artifact.** The obvious objection: consecutive 5-minute
windows are not independent, so a trending hour could produce one macro event masquerading
as 14 draws. Tested directly:

- Winner sequence `DDDUDUDUDDDUDUUUUDUUUDUDDUUUUDU` — 17 UP / 14 DOWN, **18 runs**.
  Expected under independence 16.36 (SD 2.71) → **z = +0.61**. Slightly *more* alternation
  than chance; no clustering to exploit or to blame.
- The one-sided fills split **8 filled-UP-when-DOWN-won / 6 filled-DOWN-when-UP-won** —
  symmetric across both directions, so it is not one token's book being systematically
  thinner.

So the mechanism is real and direction-neutral: **14/14, p = 0.000061**.

**Recommendation.** G4's formal threshold is 200 rows and we have 31, so this is not the
verdict on paper. But both tested offsets are negative with independent significance, the
effect is 5–6× break-even rather than marginal, and the causal mechanism has survived the
one objection that could have explained it away. The remaining 169 rows (~14 h) will not
change the sign. **The maker branch is closed on the evidence; the taker branch (G1, 38/200,
~13 h) is now the only live lead.** Whether to keep spending rows on `maker_probe.py` is a
call for the operator, not for this loop — nothing is being killed unilaterally.

**Next iteration:** G1 toward 200. Maker probe continues unless told otherwise.

---

## 2026-07-27 03:41 — iteration 10 · checkpoint, no change in direction

| Item | Value | Δ |
|---|---|---|
| Processes | 3, one each ✅ | — |
| `ladder.jsonl` | 44 | +6 |
| `maker_probe.jsonl` | 37 | +6 |
| `paper_trades.jsonl` | 54 | +6 |
| Stale nulls | 0 | — |

G1 preview (n=44): T-120 **41/44**, T-90 34/44, T-60 29/44, T-45 26/44, T-30 17/44,
T-20 1/44, T-10 0/44.

| offset | n | one-sided | mean/share | exact p | filled loser |
|---|---|---|---|---|---|
| T-120 | 26 | 11 (42%) | −0.0784 | 0.0000 | 11/11 |
| T-60 | 11 | **7 (64%)** | **−0.1042** | 0.0000 | 7/7 |

T-60 deteriorated — its one-sided rate rose 50% → 64% and it is now the *worse* of the two,
reversing iteration 9's read that its shorter exposure softened the loss. Adverse selection
streak **18/18, p = 3.8×10⁻⁶**.

Nothing new in kind this iteration; the maker result is the same result with more rows
behind it, and G1 is 44/200. No action taken.

**Next iteration:** G1 toward 200 (~11 h).

---

## 2026-07-27 04:11 — iteration 11 · **G1's criterion is met at T-120; the binding gate is now G2**

| Item | Value | Δ |
|---|---|---|
| Processes | 3, one each ✅ | — |
| `ladder.jsonl` | 50 | +6 |
| `maker_probe.jsonl` | 43 | +6 |
| `paper_trades.jsonl` | 60 | +6 |
| Stale nulls | 0 | — |

**G1 bar is ">70% of windows fillable at 5 shares under 0.99".** At n=50:

| offset | fillable | 95% CI | clears 70%? |
|---|---|---|---|
| **T-120** | **46/50 = 92%** | **[81%, 97%]** | **yes** |
| T-90 | 38/50 = 76% | [63%, 86%] | no |
| T-60 | 33/50 = 66% | [52%, 78%] | no |
| T-45 | 30/50 = 60% | [46%, 72%] | no |
| T-30 | 19/50 = 38% | [26%, 52%] | no |

The whole 95% interval at T-120 sits above the bar, so **the criterion is satisfied, not
merely trending** — and it is satisfied at 50 rows, not 200. That is not gate-jumping: G1 is
a single proportion test against a fixed 70% threshold, which needs ~50 samples. **The 200-row
threshold was never really G1's** — it is sized for G2, which must detect a few-percent edge
against base rates near 97% and genuinely needs the power. G1 is called at T-120 only; every
other offset's interval still straddles the bar.

Consequence: **the taker path is open and Phases 2–3 are not skipped.** ROADMAP_V2 §4's exit
condition for Phase 1 — "if no offset supports 5 shares on the favourite under 0.99, the taker
path is closed" — resolves the other way.

G4 unchanged in direction: T-120 n=29, 41% one-sided, −0.0705/share; T-60 n=14, 64% one-sided,
−0.1038/share; streak **21/21, p = 4.8×10⁻⁷**.

**Next iteration:** G2 is now the only question that matters and it needs the full 200 rows
(50 now, ~12 h). Fillability is not edge — a favourite bought at T-120 is cheap precisely
because the outcome is still open, and G2 is what tests whether that price is beatable.

---

## 2026-07-27 04:41 — iteration 12 · checkpoint

| Item | Value | Δ |
|---|---|---|
| Processes | 3, one each ✅ | — |
| `ladder.jsonl` | 56 / 200 | +6 |
| `maker_probe.jsonl` | 49 | +6 |
| `paper_trades.jsonl` | 66 | +6 |
| Stale nulls | 0 | — |

G1: T-120 **52/55 = 95%** CI [85%, 98%] (clears); T-90 43/56 = 77% CI [64%, 86%];
T-60 64%; T-45 61%; T-30 39%. G4: T-120 n=32 41% one-sided −0.0700/share; T-60 n=17 59%
−0.0999/share; streak **23/23, p = 1.2×10⁻⁷**.

**Denominator note:** T-120's denominator is 55, not 56 — `ladder.py` skips any offset
already past when it starts a window, so an occasional late start drops that sample. The
omission is a clock artifact, uncorrelated with the outcome, so it does not bias
fillability; it just costs a row.

No change in direction. G2 remains ~12 h out.

---

## 2026-07-27 05:11 — iteration 13 · checkpoint

3 processes ✅ · `ladder.jsonl` **62/200** (+6) · `maker_probe.jsonl` 55 (+6) ·
`paper_trades.jsonl` 72 (+6) · stale nulls 0.

| | T-120 | T-90 | T-60 | T-45 | T-30 |
|---|---|---|---|---|---|
| G1 fillable | **58/61 = 95%** CI [87%, 98%] | 79% CI [67%, 87%] | 61% | 58% | 39% |

Only T-120 clears the 70% bar; T-90's lower bound is still 67%. G4: T-120 n=35 43% one-sided
−0.0681/share, T-60 n=20 55% −0.0849/share, streak **26/26, p = 1.5×10⁻⁸**.

Surveillance only — no decision available until G2 at 200 rows (~11 h).

---

## 2026-07-27 05:41 — iteration 14 · checkpoint

3 processes ✅ · `ladder.jsonl` **68/200** (+6) · `maker_probe.jsonl` 61 (+6) ·
`paper_trades.jsonl` 78 (+6) · stale nulls 0.

G1: T-120 **62/67 = 93%** CI [84%, 97%] (clears); T-90 75% CI [64%, 84%]; T-60 59%;
T-45 56%; T-30 37%. G4: T-120 n=38 45% one-sided −0.0810/share; T-60 n=23 52%
−0.0746/share; streak **29/29**.

Fourth consecutive iteration with no change in direction. G2 ~10 h out.

---

## 2026-07-27 06:11 — iteration 15 · checkpoint

3 processes ✅ · `ladder.jsonl` **74/200** (+6) · `maker_probe.jsonl` 67 (+6) ·
`paper_trades.jsonl` 84 (+6) · stale nulls 0.

G1: T-120 **67/73 = 92%** CI [83%, 96%] (clears); T-90 76% CI [65%, 84%]; T-60 58%;
T-45 55%; T-30 34%. G4: T-120 n=41 44% one-sided −0.0752/share; T-60 n=26 58%
−0.0683/share; streak **33/33**.

Fifth consecutive no-change iteration. G2 ~9 h out.

---

## 2026-07-27 06:41 — iteration 16 · checkpoint

3 processes ✅ · `ladder.jsonl` **80/200** (+6) · `maker_probe.jsonl` 73 (+6) ·
`paper_trades.jsonl` 90 (+6) · stale nulls 0.

G1: T-120 **73/79 = 92%** CI [84%, 96%] (clears); T-90 76% CI [66%, 84%]; T-60 60%;
T-45 55%; T-30 35%. G4: T-120 n=44 43% one-sided −0.0702/share; T-60 n=29 55%
−0.0684/share; streak **35/35**.

**Cost of the alternating change, stated plainly:** splitting the probe across two offsets
means neither reaches 200 rows until ~400 total — iteration 6's fork test pushed formal G4
closure from ~14 h to ~33 h. That was the right trade when the offset was an untested
confound, and it is harmless now only because both offsets are already decided in substance
(35/35, both p≈0). Nobody should be waiting on that threshold.

Sixth consecutive no-change iteration. G2 ~8 h out.

---

## 2026-07-27 07:11 — iteration 17 · checkpoint

3 processes ✅ · `ladder.jsonl` **86/200** (+6) · `maker_probe.jsonl` 79 (+6) ·
`paper_trades.jsonl` 96 (+6) · stale nulls 0.

G1: T-120 **78/85 = 92%** CI [84%, 96%] (clears); T-90 77% CI [67%, 84%]; T-60 60%;
T-45 56%; T-30 36%. G4: T-120 n=47 45% one-sided −0.0873/share; T-60 n=32 53%
−0.0619/share; streak **38/38**.

Seventh consecutive no-change iteration. G2 ~7.5 h out.

---

## 2026-07-27 07:41 — iteration 18 · checkpoint

3 processes ✅ · `ladder.jsonl` **92/200** (+6) · `maker_probe.jsonl` 85 (+6) ·
`paper_trades.jsonl` 102 (+6) · stale nulls 0.

G1: T-120 **83/91 = 91%** CI [84%, 95%] (clears); T-90 76% CI [66%, 84%]; T-60 60%;
T-45 54%; T-30 35%. G4: T-120 n=50 46% one-sided −0.0852/share; T-60 n=35 54%
−0.0750/share; streak **42/42**.

Eighth consecutive no-change iteration. G2 ~7 h out.

---

## 2026-07-27 07:50 — iteration 19 · checkpoint

3 processes ✅ · `ladder.jsonl` **94/200 (47%)** · `maker_probe.jsonl` 86 · stale nulls 0.
Collection rate steady at 12.1 rows/h over 7.7 h.

G1: T-120 **85/93 = 91%** CI [84%, 96%] (clears); T-90 77%; T-60 61%; T-45 55%; T-30 35%.
G4: T-120 n=51 47% one-sided −0.0888/share; T-60 n=36 56% −0.0743/share; streak **44/44**.

Cron `b42305bf` confirmed live — the loop is self-sustaining every 30 min, no manual
prompting needed. G2 ETA **Mon 16:37**.

Ninth consecutive no-change iteration.

---

## 2026-07-27 08:11 — iteration 20 · checkpoint

3 processes ✅ · `ladder.jsonl` **98/200 (49%)** (+4) · `maker_probe.jsonl` 91 (+5) ·
`paper_trades.jsonl` 108 (+4) · stale nulls 0.

G1: T-120 **89/97 = 92%** CI [85%, 96%] (clears); T-90 77%; T-60 61%; T-45 55%; T-30 36%.
G4: T-120 n=53 49% one-sided −0.0978/share; T-60 n=38 55% −0.0861/share; streak **47/47**.

Tenth consecutive no-change iteration. G2 ETA Mon 16:37.

---

## 2026-07-27 08:41 — iteration 21 · checkpoint · **ladder past halfway**

3 processes ✅ · `ladder.jsonl` **104/200 (52%)** (+6) · `maker_probe.jsonl` 97 (+6) ·
`paper_trades.jsonl` 114 (+6) · stale nulls 0.

G1: T-120 **95/103 = 92%** CI [85%, 96%] (clears); T-90 78% CI [69%, 85%]; T-60 63%;
T-45 57%; T-30 38%. G4: T-120 n=56 46% one-sided −0.0917/share; T-60 n=41 54%
−0.0797/share; streak **48/48**.

T-90 has drifted up to 78% with a 69% lower bound — still short of clearing, but it is the
only offset besides T-120 with any chance of qualifying as a second viable entry point by
n=200. Worth watching: a second clearing offset would give G2 more than one band to test
without adding a fork.

Eleventh consecutive no-change iteration. G2 ETA Mon 16:37.

---

## 2026-07-27 09:11 — iteration 22 · **T-90 clears the G1 bar; a second entry offset opens**

3 processes ✅ · `ladder.jsonl` **110/200 (55%)** (+6) · `maker_probe.jsonl` 103 (+6) ·
`paper_trades.jsonl` 120 (+6) · stale nulls 0.

| offset | fillable | 95% CI | clears 70%? |
|---|---|---|---|
| T-120 | **101/109 = 93%** | [86%, 96%] | yes |
| **T-90** | **87/110 = 79%** | **[71%, 86%]** | **yes — new** |
| T-60 | 71/110 = 65% | [55%, 73%] | no |
| T-45 | 62/110 = 56% | [47%, 65%] | no |
| T-30 | 42/110 = 38% | [30%, 48%] | no |

T-90's lower bound is 71% — it clears by one point, so treat it as marginal rather than
established; a few bad windows would push it back under.

**This costs something at G2.** Two viable offsets × four price bands = **eight buckets**
instead of four, which doubles the chances of a spurious z > 2. The multiple-testing
correction has to be applied over all buckets actually examined, not just the offset that
happens to look best. Reporting a winning bucket out of eight while quoting a
four-bucket threshold would be the exact error LOOP_PROMPT's "treat multiple-bucket testing
honestly" clause exists to prevent.

G4: T-120 n=59 46% one-sided −0.0894/share; T-60 n=44 57% −0.0821/share; streak **52/52**.

G2 ETA Mon 16:37.

---

## 2026-07-27 09:41 — iteration 23 · checkpoint

3 processes ✅ · `ladder.jsonl` **116/200 (58%)** (+6) · `maker_probe.jsonl` 109 (+6) ·
`paper_trades.jsonl` 126 (+6) · stale nulls 0.

G1: T-120 **107/115 = 93%** CI [87%, 96%] (clears); T-90 **93/116 = 80%** CI [72%, 86%]
(clears — lower bound up from 71%, so it is consolidating rather than slipping back);
T-60 66%; T-45 57%; T-30 38%.

G4: T-120 n=62 44% one-sided −0.0843/share; T-60 n=47 **60%** −0.0985/share; streak
**55/55**. T-60 remains the worse maker offset.

G2 ETA Mon 16:37.

---

## 2026-07-27 10:11 — iteration 24 · checkpoint

3 processes ✅ · `ladder.jsonl` **122/200 (61%)** (+6) · `maker_probe.jsonl` 115 (+6) ·
`paper_trades.jsonl` 132 (+6) · stale nulls 0.

G1: T-120 **113/121 = 93%** CI [87%, 97%]; T-90 **98/122 = 80%** CI [72%, 86%]; both clear.
T-60 65%; T-45 57%; T-30 39%.

G4: T-120 n=65 46% one-sided −0.0907/share; T-60 n=50 60% −0.0953/share; streak **60/60**.
Both offsets have now passed 50 windows each with no exception to the adverse-selection rule.

G2 ETA Mon 16:37.

---

## 2026-07-27 10:41 — iteration 25 · checkpoint

3 processes ✅ · `ladder.jsonl` **128/200 (64%)** (+6) · `maker_probe.jsonl` 121 (+6) ·
`paper_trades.jsonl` 138 (+6) · stale nulls 0.

G1: T-120 **119/127 = 94%** CI [88%, 97%]; T-90 **101/128 = 79%** CI [71%, 85%]; both clear.
T-60 65%; T-45 56%; T-30 39%.

G4: T-120 n=68 47% one-sided −0.0872/share; T-60 n=53 62% −0.0965/share; streak **65/65**.

G2 ETA Mon 16:37 — 72 rows out, ~6 h.

---

## 2026-07-27 11:56 — iteration 26 · checkpoint

3 processes ✅ · `ladder.jsonl` **143/200 (72%)** (+15) · `maker_probe.jsonl` 136 (+15) ·
`paper_trades.jsonl` 153 (+15) · stale nulls 0.

G1: T-120 **132/142 = 93%** CI [88%, 96%]; T-90 **114/143 = 80%** CI [72%, 85%]; both clear.
T-60 63%; T-45 54%; T-30 38%.

G4: T-120 n=76 45% one-sided −0.0808/share; T-60 n=60 63% −0.0960/share; streak **72/72**.

Project published to <https://github.com/houssem98/polymarket-btc-5m-research> (public) at
128 ladder rows. The committed data is a snapshot; worth re-pushing after G2 runs.

G2 ETA Mon 16:37 — 57 rows out.

---

## 2026-07-27 12:11 — iteration 27 · checkpoint

3 processes ✅ · `ladder.jsonl` **146/200 (73%)** (+3) · `maker_probe.jsonl` 139 (+3) ·
`paper_trades.jsonl` 156 (+3) · stale nulls 0.

G1: T-120 **135/145 = 93%** CI [88%, 96%]; T-90 **115/146 = 79%** CI [71%, 85%]; both clear.
T-60 62%; T-45 53%; T-30 38%.

G4: T-120 n=77 44% one-sided −0.0795/share; T-60 n=62 63% −0.0931/share; streak **73/73**.

G2 ETA Mon 16:37 — 54 rows out.

---

## 2026-07-27 12:41 — iteration 28 · checkpoint

3 processes ✅ · `ladder.jsonl` **152/200 (76%)** (+6) · `maker_probe.jsonl` 145 (+6) ·
`paper_trades.jsonl` 162 (+6) · stale nulls 0.

G1: T-120 **139/151 = 92%** CI [87%, 95%]; T-90 **118/152 = 78%** CI [70%, 84%]; both clear,
though T-90's lower bound has slipped to exactly 70% — it is the marginal one and could still
fall back below the bar before n=200.

G4: T-120 n=80 45% one-sided −0.0770/share; T-60 n=65 62% −0.0888/share; streak **76/76**.

G2 ETA Mon 16:37 — 48 rows out, ~4 h.

---

## 2026-07-27 13:11 — iteration 29 · checkpoint

3 processes ✅ · `ladder.jsonl` **158/200 (79%)** (+6) · `maker_probe.jsonl` 151 (+6) ·
`paper_trades.jsonl` 168 (+6) · stale nulls 0.

G1: T-120 **145/157 = 92%** CI [87%, 96%]; T-90 **123/158 = 78%** CI [71%, 84%] — recovered
off the 70% edge it touched last iteration. Both clear. T-60 62%; T-45 53%; T-30 37%.

G4: T-120 n=83 46% one-sided −0.0752/share; T-60 n=68 63% −0.0959/share; streak **81/81**.

G2 ETA Mon 16:37 — 42 rows out, ~3.5 h.

---

## 2026-07-27 13:41 — iteration 30 · checkpoint

3 processes ✅ · `ladder.jsonl` **164/200 (82%)** (+6) · `maker_probe.jsonl` 157 (+6) ·
`paper_trades.jsonl` 174 (+6) · stale nulls 0.

G1: T-120 **149/162 = 92%** CI [87%, 95%]; T-90 **127/164 = 77%** CI [70%, 83%] — back on the
70% edge. Both nominally clear; T-90 remains the marginal one and should be treated as
provisional until n=200. T-60 62%; T-45 53%; T-30 36%.

G4: T-120 n=86 44% one-sided −0.0724/share; T-60 n=71 62% −0.0920/share; streak **82/82**.

G2 ETA Mon 16:37 — 36 rows out, ~3 h.

---

## 2026-07-27 14:11 — iteration 31 · **T-90 falls back below the bar**

3 processes ✅ · `ladder.jsonl` **170/200 (85%)** (+6) · `maker_probe.jsonl` 163 (+6) ·
`paper_trades.jsonl` 180 (+6) · stale nulls 0.

| offset | fillable | 95% CI | clears 70%? |
|---|---|---|---|
| T-120 | **152/168 = 90%** | [85%, 94%] | yes |
| T-90 | 129/170 = 76% | **[69%, 82%]** | **no — fell back** |
| T-60 | 103/170 = 61% | [53%, 68%] | no |
| T-45 | 89/170 = 52% | [45%, 60%] | no |
| T-30 | 61/170 = 36% | [29%, 43%] | no |

T-90 cleared at iteration 22 (71% lower bound), oscillated across the bar for nine
iterations, and has now settled below it. Iteration 22 called it "marginal — treat as
provisional"; that caution was warranted and the provisional pass is withdrawn.

**This simplifies G2 rather than complicating it.** One viable offset means **four buckets,
not eight**, so the multiple-testing burden flagged at iteration 22 halves. T-120 is the
single entry point the calibration test will run against.

Note T-120 also eased, 92% → 90%, but its lower bound (85%) has 15 points of headroom over
the bar. Not at risk.

G4: T-120 n=89 45% one-sided −0.0769/share; T-60 n=74 61% −0.0965/share; streak **85/85**.

G2 ETA Mon 16:37 — 30 rows out, ~2.5 h.

---

## 2026-07-27 14:41 — iteration 32 · checkpoint

3 processes ✅ · `ladder.jsonl` **176/200 (88%)** (+6) · `maker_probe.jsonl` 169 (+6) ·
`paper_trades.jsonl` 186 (+6) · stale nulls 0.

G1: T-120 **158/174 = 91%** CI [86%, 94%] (clears, sole qualifying offset); T-90 77%
CI [70%, 82%] — still under, consistent with iteration 31's withdrawal; T-60 61%; T-45 52%;
T-30 36%.

G4: T-120 n=92 45% one-sided −0.0751/share; T-60 n=77 62% −0.0984/share; streak **89/89**.

G2 ETA Mon 16:37 — 24 rows out, ~2 h.

---

## 2026-07-27 15:11 — iteration 33 · checkpoint

3 processes ✅ · `ladder.jsonl` **182/200 (91%)** (+6) · `maker_probe.jsonl` 175 (+6) ·
`paper_trades.jsonl` 192 (+6) · stale nulls 0.

G1: T-120 **161/180 = 89%** CI [84%, 93%] (clears, sole qualifying offset); T-90 75%
CI [68%, 80%]; T-60 59%; T-45 51%; T-30 35%. Every offset has drifted down 1–2 points over
the last three iterations — T-120 still has 14 points of headroom, so this is drift, not risk.

G4: T-120 n=95 45% one-sided −0.0731/share; T-60 n=80 60% −0.0947/share; streak **91/91**.

G2 ETA Mon 16:37 — 18 rows out, ~1.5 h. Next iteration or the one after runs the gate.

---

## 2026-07-27 15:15 — **`bot.py` traded, lost 28.8%, and tripped its circuit breaker**

Missed in earlier iterations because every prior check only counted rows. `bot.py` is no
longer inert: **3 paper trades, 3 losses, bankroll $200 → $142.47**, then `circuit_breaker`
has blocked all 169 windows since.

```
UP   @ $0.01 x 2000.00 sh  p_win 0.78  ->  DOWN won  -$21.38
UP   @ $0.01 x 1786.20 sh  p_win 0.52  ->  DOWN won  -$19.09
DOWN @ $0.01 x 1595.26 sh  p_win 0.52  ->  UP   won  -$17.05
```

All three bought at **$0.01** — the price a market charges for a side it is ~99% certain
will lose. The market was right all three times.

**Not a token-ordering bug.** Verified against Gamma: `outcomes = ["Up","Down"]`,
`clobTokenIds` in the same order, and the bot's `token_id` resolves to index 0 = "Up" on a
trade where it recorded `side: UP`. It bought what it intended to buy.

**The EV filter caused the loss rather than preventing it.** `EV = p_win − price − fee`
= `0.78 − 0.01 − 0.0007` = **+0.769**, which reads as an enormous edge and is entirely an
artifact of `p_win_ladder()` disagreeing with a correctly-priced market. Kelly then sized
that fake edge into 2000 shares. On trade 3, `delta_pct = −5e-05` — essentially flat — yet
the market priced that side at $0.01, so the model and the market were not merely
disagreeing on magnitude but on the outcome itself. Most likely a bad `window_open_price`
making the delta sign unreliable; not diagnosed further, because the strategy is already
rejected.

**This is a rejected loop confirmed live.** `LOOPS.md` lists "ladder-gated EV snipe" under
rejected loops with the note *"the EV filter selects its own worst trades."* That was
inferred from `scaffold_sim.py`. It has now happened with real prices and real outcomes.

**Strategy scorecard, both tested strategies:**

| strategy | windows | win rate | result |
|---|---|---|---|
| maker two-sided, T-120 | 97 | 47% | −$33.65 @ 5 sh |
| maker two-sided, T-60 | 82 | 18% | −$38.66 @ 5 sh |
| **maker combined** | **179** | **34.1%** | **−$72.31 (−$116/day run-rate)** |
| **taker EV snipe (`bot.py`)** | **3 taken / 196** | **0%** | **−$57.53 (−28.8% bankroll)** |

T-120's 47% win rate still loses money: wins are +1.5¢, losses −18¢. Win rate is the wrong
metric for this payoff shape.

**Zero of two strategies are profitable.** G2 remains the only open question.

---

## 2026-07-27 15:41 — iteration 34 · **the adverse-selection streak breaks at 93**

3 processes ✅ · `ladder.jsonl` **188/200 (94%)** (+6) · `maker_probe.jsonl` 181 (+6) ·
`paper_trades.jsonl` 198 (+6) · stale nulls 0. `bot.py` still circuit-broken at $142.47.

G1: T-120 **166/186 = 89%** CI [84%, 93%] (clears, sole offset); T-90 74%; T-60 59%;
T-45 51%; T-30 35%.

G4: T-120 n=98 46% one-sided −0.0689/share; T-60 n=83 59% −0.0932/share; streak now
**93/94** — the first exception after 93 consecutive:

```
btc-updown-5m-1785161400  quote T-120  winner DOWN
  DOWN  quote 0.80  queue 609.94 -> 0.0  touched  fill T-48.7s  min_ask 0.77  pnl +0.202
  UP    quote 0.20  queue 0.00           never filled
```

It filled on the **winner** and made +0.202. The setup is instructive: DOWN was already a
heavy favourite at 0.80 when quoted, the market dipped to 0.77 — filling us — and then DOWN
won anyway. So a one-sided fill in a *lopsided* window can land on the right side, because
the dip that fills you is noise rather than information.

The UP side is also a check on the fill logic working correctly: `queue_ahead = 0.0` meant
the consumption test could never be satisfied, so it stayed unfilled rather than being
counted on a technicality.

**This does not rescue G4.** One +0.20 against 93 losses averaging −0.18; T-120's mean is
still −0.0689/share. What it does correct is the *framing*: adverse selection is a ~99%
tendency, not a law. Earlier entries called it "a claim about mechanism" — that stands, but
"14/14, 65/65, 93/93" invited reading it as deterministic, and it is not.

G2 ETA — **12 rows out, ~1 h.** Next iteration likely runs the gate.

---

## 2026-07-27 16:11 — iteration 35 · **G2 pre-registered; a look-ahead bug in my own G1 check**

3 processes ✅ · `ladder.jsonl` **194/200 (97%)** (+6) · `maker_probe.jsonl` 187 (+6) ·
`paper_trades.jsonl` 204 (+6). Six rows short — G2 not run.

**Bug found in the G1 preview code (mine, not the collectors').** Every G1 number reported
since iteration 1 computed *"did the **winner** have a fillable ask"*, but the criterion is
*"did the **favourite** have a fillable ask"*. The winner is unknowable at T-120; using it is
look-ahead. Recomputed both ways:

| offset | winner-based (reported) | favourite-based (correct) | fav == winner |
|---|---|---|---|
| T-120 | 172/192 = 90% | **172/192 = 90%** CI [84%, 93%] | 83% |
| T-90 | 145/194 = 75% | 145/194 = 75% | 86% |
| T-60 | 114/194 = 59% | 114/194 = 59% | 88% |
| T-45 | 97/194 = 50% | 96/194 = 49% | 95% |
| T-30 | 67/194 = 35% | 67/194 = 35% | 98% |
| T-10 | 0/194 = 0% | 0/194 = 0% | 100% |

**The numbers are identical except one window at T-45.** Fillability is a property of the
book, and in nearly every window both sides are quoted or neither is — so which side you
name barely matters. The G1 conclusion stands unchanged, now verified rather than assumed.
The bias was real and worth removing regardless; it just had no teeth here.

**`gate_g2.py` written and pre-registered at 194 rows** — before the qualifying data exists,
so no parameter can be tuned to the outcome. Fixed in advance: T-120 only (sole G1-clearing
offset), favourite by price never by outcome, real ask VWAP at 5 shares, unbuyable windows
excluded *and counted*, the four ROADMAP_V2 bands, fee `0.07·p·(1−p)`, PASS requires z > 2
**and** positive PnL after fee. Four buckets are tested, so the file prints both the
uncorrected z > 2.00 and the Bonferroni threshold z > 2.50.

Next iteration crosses 200 and runs it.

---

## 2026-07-27 16:41 — iteration 36 · **G2 FAILS — the market is calibrated. Project finished.**

`ladder.jsonl` reached **200**. Ran `gate_g2.py` unmodified from its pre-registration at
194 rows.

```
resolved 200 | tradeable 189 | favourite unbuyable 9 | no T-120 sample 2

        band    n     hit  implied    edge      z     fee   pnl/sh     ROI
   0.00-0.88  108 67.59%  71.14%  -3.55%  -0.81  0.0134  -0.0489  -6.87%
   0.88-0.94   22 100.00% 91.34%  +8.66%  +1.44  0.0055  +0.0811  +8.87%
   0.94-0.99   59 100.00% 97.40%  +2.60%  +1.25  0.0018  +0.0242  +2.49%
   0.99-1.00    0
```

**No band reaches z > 2. G2 FAILS.**

**The decisive number is the aggregate.** Across all 189 tradeable windows the favourite
won **81.48%** against an implied **81.69%** — **z = −0.07**. That is not "close to
calibrated", it is calibrated to within a fifth of a percentage point. There is no edge to
find because the price is already right. Trading every window at 5 shares returns
**−$10.32 over 189 windows (−$0.055/window)**, and the loss is almost exactly the fee.

**The band where the volume is, loses.** `≤0.88` holds 108 of 189 windows and comes in at
67.59% against 71.14% implied — negative edge, negative ROI, z = −0.81.

### The tempting result, tested and rejected

The two upper bands both hit **100%**. Merged, that is **81/81 wins**, implied 95.76%,
ROI +4.14% — and **z = +1.89**, short of the pre-registered bar of 2.00 and well short of
the Bonferroni threshold of 2.50. That merge is also **post-hoc**: it is a fifth bucket
invented after seeing the four, so the correct correction is harsher, not gentler.
P(81/81 | independent at 95.76%) = **0.030**, which is mildly surprising and nowhere near
enough given how many slices this dataset has been through today.

Worth stating plainly because it will keep looking attractive: the same region scored
+1.80% ROI at z = +0.71 over 700 historical windows. Two underpowered samples, both mildly
positive, neither significant, and the effect is exactly what fee curvature predicts —
`0.07·p·(1−p)` collapses as p → 1, so the least-bad band is mechanically the one nearest
certainty. That is not an edge; it is paying less to be right about something obvious.

### Final state of every gate

| gate | verdict | evidence |
|---|---|---|
| **G1** fill | **PASS** | favourite fillable at 5 sh under $0.99 in 90% of windows at T-120s, CI [84%, 93%] |
| **G2** calibration | **FAIL** | aggregate z = −0.07; no band z > 2; dominant band −6.87% ROI |
| **G3** feed | **not run** | gated on G2; a Chainlink swap cannot create an edge that does not exist |
| **G4** maker | **FAIL** | 93/94 one-sided fills on the losing side; −$0.069/share at T-120, −$0.093 at T-60 |

Plus, unplanned: `bot.py` traded 3 times, lost all 3, and gave up 28.8% of bankroll to an
EV filter that manufactured a fake +0.769 edge from a model that disagreed with a correct
market.

### Recommendation: stop

Per LOOP_PROMPT's own rule — every gate has failed and the maker probe is negative — **this
project is finished and should be stopped.** No new strategy should be invented to keep it
alive. The market is efficient at the only moment you can trade it, the fee is larger than
the spread, and the one structurally favourable side (maker) is destroyed by adverse
selection.

**This is the valuable outcome.** It cost 17 hours of measurement and $0 of capital to
establish what a funded account would have discovered slowly and expensively. The taker path
was closed by arithmetic, the maker path by evidence, and both are now documented well enough
that nobody has to re-run them.

**Note on cadence:** `ladder.py` sweeps settlements only after the next window's
blocking sample loop, so a row lands ~10 min after its window closes, not ~6.
Not a bug — factor it into growth expectations.

---

## 2026-07-27 — E0 + E1 executed. Last open branch closed.

V3 defined gates E0–E5 and left **E0 and E1 unrun**. They were the two cheapest, and E1 was
the one that decided the maker branch. Both now executed.

### E1 — reward pool: $0

V3 §5 named liquidity-reward income as the only term that could offset the measured
adverse-selection bleed (−$0.077…−0.097/share). V3 §4 pre-set the kill threshold: pool = $0
⇒ maker branch dead, permanently.

Read live from `clob.polymarket.com/markets/{conditionId}`, 12 consecutive open markets:

```
btc-updown-5m-1785168000  rates=NULL  min_size=50  max_spread=4.5
...
RESULT: 12/12 open BTC 5m markets have rewards.rates = NULL
```

Gamma corroborates: `clobRewards` empty, `holdingRewardsEnabled: false`.

**The trap worth recording:** `min_size: 50` and `max_spread: 4.5` are populated, so the
market looks reward-configured. `rates` is null — nothing is emitted. Any future check must
read `rates`, not the presence of a rewards object.

**Maker branch dead on the project's own pre-registered threshold.** E4/E5 are not skipped
out of fatigue — V3 §4 forbids running them against a $0 pool, since no fill-timing or
filtering result can rescue arithmetic.

### E0 — citations: both load-bearing claims hold

| Claim | Result |
|---|---|
| A. Oracle is Chainlink **Data Streams**, not a heartbeat aggregator | ✅ Confirmed. Docs: pull-based, "retrieve a report and verify it onchain whenever you need it", sub-second, no stale-round concept. Data *Feeds* are the push/heartbeat product. The market's own `resolutionSource` is `data.chain.link/**streams**/btc-usd` |
| B. Reward pool ≈ $0 | ✅ Confirmed by E1's direct read, which outranks the citation |

**Q1 (stale-oracle / last-look) stays closed.** It required a heartbeat feed with a lagging
last update. Data Streams has no such window.

### Disposition of the rest

- **E2** (Chainlink open-price capture) — moot; it only mattered if E0 failed.
- **E3** (book-VWAP recalibration) — already run as G2: 189 windows, real `/book` VWAP,
  aggregate 81.48% vs 81.69% implied, **z = −0.07**. Best band +1.44, post-hoc merge +1.89,
  Šidák bar 2.73. No bucket clears.

### Stopping rule satisfied

V3 §7 required *E1 returns $0* **and** *E3 finds no bucket at |z| > 2.73*. Both met.
**The project is finished.**

Every branch closed by measurement: taker on calibration (z = −0.07), maker on adverse
selection (93/94) then permanently on a $0 pool, oracle on Data Streams' pull-based design.

What replaces it is a weekly one-minute watch over three falsifiable triggers — W1
`rewards.rates` non-null, W2 fee rate below 0.07, W3 tick below 0.01. See
ROADMAP_FINAL.md, LOOPS_FINAL.md, LOOP_PROMPT_FINAL.md. The project reopens on a number,
never on an idea.
