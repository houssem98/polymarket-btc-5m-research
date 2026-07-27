# LOOP_PROMPT.md — Recurring Driver

Run with the `/loop` skill. Suggested cadence: **30 minutes**.

```
/loop 30m Execute one iteration of LOOP_PROMPT.md in the polymarket project.
```

Omit the interval to let the model self-pace. Everything below is read-only —
no iteration of this loop may place an order.

---

## The prompt

Copy the block below as the loop body.

```
Working dir: c:\Users\unicentrale\Downloads\trading polymarket and equitie , crypto

You are advancing the Polymarket BTC 5m research project. Read ROADMAP_V2.md and
LOOPS.md for state. Do ONE iteration:

STEP 1 — HEALTH
  Check ladder.py and bot.py are each running exactly once:
    Get-CimInstance Win32_Process -Filter "Name='python.exe'"
  If either is missing, restart it in the background with the explicit interpreter
  C:\Users\unicentrale\AppData\Local\Programs\Python\Python312\python.exe
  (the venv shim double-spawns; always use the explicit path).
  If either is running twice, kill the duplicate — both write the same file.

STEP 2 — DATA
  Count resolved rows:  ladder.jsonl, paper_trades.jsonl
  Report the counts and the growth since the previous iteration.
  If a row has "winner": null and is older than 30 minutes, investigate: settlement
  is ~4.6 min, so nulls mean a real failure, not lag.

STEP 3 — GATES (only when the data threshold is met; otherwise say how many more
              windows are needed and stop)

  G1 FILL GATE — needs 200+ resolved rows in ladder.jsonl
    For each offset (120/90/60/45/30/20/10s), compute across windows:
      - % of windows where the FAVOURITE has a fillable ask at 5 / 20 / 50 shares
      - median ask VWAP at each clip size
      - median total ask depth
    Print as a table: offset x clip size.
    PASS if some offset fills 5 favourite shares under 0.99 in >70% of windows.
    FAIL => write the result to ROADMAP_V2.md, declare the taker path closed,
            and skip to STEP 4.

  G2 CALIBRATION GATE — only if G1 passed
    Re-run the band analysis using REAL ask VWAPs from ladder.jsonl instead of
    mid+0.005. Bands: <=0.88, 0.88-0.94, 0.94-0.99, >0.99, at the best offset from G1.
    Subtract fee = 0.07 * p * (1-p) per share.
    Report n, hit, implied, edge, z, ROI per band.
    PASS only if a band has z > 2 AND positive ROI net of fee.
    Treat multiple-bucket testing honestly: mention how many buckets were tried.
    FAIL => market is calibrated. Say so plainly and skip to STEP 4.

  G3 FEED GATE — only if G2 passed
    Re-test the surviving band restricted to windows where |delta| > 2bps, since
    100% of measured Binance/Chainlink disagreements were under 2bps.
    PASS if the edge survives. FAIL => the edge was basis noise.

STEP 4 — MAKER PROBE (Gap 6, the branch with the favourable fee sign)
  If it does not exist yet, build maker_probe.py: read-only, per window, simulate
  resting a bid one tick inside the touch on both tokens. Log quote price, whether
  the market later traded through it (would-fill), and the resolved outcome.
  Makers pay zero fee and earn rebateRate 0.2. The question is whether
  rebate + captured spread beats adverse selection. Start it in the background.
  If it already exists and has 200+ rows, run the G4 analysis:
    fill rate, average outcome conditional on fill, PnL net of zero fee plus rebate.

STEP 5 — REPORT
  Append a dated entry to FINDINGS.md with: row counts, any gate run and its verdict,
  and what the next iteration should do. Keep it to a short table plus 3 lines max.
  Update the status column in ROADMAP_V2.md section 6 if anything changed.

RULES
  - Never place an order. Never add ClobClient, a private key, or post_order to any
    file. Verify with a grep for call-syntax before reporting any file as safe.
  - Verify claims against live APIs before writing them down. Do not assert from
    memory. If something cannot be verified this iteration, say so.
  - Gamma hides settled markets unless closed=true.
  - prices-history "p" is the MIDPOINT, not a tradeable price.
  - Report a failed gate as a real result, not a setback. A closed path is the most
    valuable output this project can produce.
  - If every gate has failed and the maker probe is negative, say the project is
    finished and recommend stopping. Do not invent a new strategy to keep it alive.
```

---

## Thresholds

| Gate | Needs | Currently |
|---|---|---|
| G1 fill | 200 resolved ladder rows | ~1 per 5 min → **~17 h** |
| G2 calibration | G1 pass + same rows | after G1 |
| G3 feed | G2 pass | after G2 |
| G4 maker | 200 maker_probe rows | ~17 h after build |

At 288 windows/day, G1 is reachable in under a day. Do not run a gate early — an
underpowered z-score is how this project talks itself into funding a loss.

---

## Stopping

Call it finished when either:
- **G1 fails** and the maker probe is negative → no viable strategy, stop.
- **G4 passes** → a real edge exists; move to L6 in [LOOPS.md](LOOPS.md), which is the
  first point at which writing execution code is justified.

End the loop with `ScheduleWakeup(stop: true)` or by saying "stop the loop".
