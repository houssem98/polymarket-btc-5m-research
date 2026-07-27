# LOOPS_V3 — Execution Graph

Supersedes [LOOPS.md](LOOPS.md). The V2 graph was four gates fed by three continuous
collectors. V3 is a **short serial chain of kill-experiments** — E0 → E1 → E2 → E3 →
E4 → E5 — because the expensive part is no longer data collection. 181 ladder rows and
174 maker rows already exist; what is missing is verification and arithmetic that takes
minutes.

Evidence behind each node: [ROADMAP_V3.md](ROADMAP_V3.md).

---

## Master graph

```mermaid
flowchart TD
    START([new session]) --> E0

    subgraph V[" VERIFY · minutes · runs first, always "]
        E0["E0 — fetch every cited URL<br/>market rule · data-streams docs<br/>rewards page · arXiv · RTDS docs"]
        E0 --> E0Q{"all load-bearing<br/>quotes check out?"}
    end

    E0Q -->|no| REOPEN["Q1 RE-OPENS<br/>oracle claim unverified"]
    REOPEN --> E2

    E0Q -->|yes| E1

    subgraph M[" MAKER BRANCH · one API read decides it "]
        E1["E1 — read rewards config on<br/>every open BTC 5m market"]
        E1 --> E1Q{"daily pool ><br/>break-even?"}
        E1Q -->|no, pool ~$0| MDEAD["MAKER DEAD<br/>bleed −0.077…−0.097/sh<br/>vs 0 reward income"]
        E1Q -->|yes, funded| E4
        E4["E4 — 200 one-sided fills:<br/>perp mid at fill vs +30s"]
        E4 --> E4Q{"adverse move<br/>AFTER the fill?"}
        E4Q -->|no, precedes fill| HDEAD["HEDGED MAKER DEAD<br/>hedge locks the loss"]
        E4Q -->|yes| E5["E5 — two-sided rate ×<br/>net spread by depth-symmetry decile"]
        E5 --> E5Q{"any decile net<br/>positive after bleed?"}
        E5Q -->|no| FDEAD["FILTERED MAKER DEAD"]
        E5Q -->|yes| MEDGE([MAKER EDGE — build gate])
    end

    MDEAD --> E2
    HDEAD --> E2
    FDEAD --> E2

    subgraph O[" ORACLE · the residual Q1 question "]
        E2["E2 — RTDS crypto_prices_chainlink<br/>first print at boundary<br/>vs published Price-to-Beat"]
        E2 --> E2Q{"materially<br/>different?"}
        E2Q -->|yes| ORACLE([OPEN-CAPTURE RULE WRONG<br/>re-derive settlement, redo Q1])
        E2Q -->|no| E3
    end

    subgraph T[" TAKER BRANCH · data already collected "]
        E3["E3 — recalibrate 700 windows on<br/>REAL /book VWAP @ 5 and 50 sh<br/>net of 0.07·p·(1−p)"]
        E3 --> E3Q{"any bucket<br/>|z| > 2.73<br/>Šidák over 8?"}
        E3Q -->|no| TDEAD["TAKER DEAD<br/>market calibrated"]
        E3Q -->|yes| OOS["out-of-sample<br/>on held-back windows"]
        OOS --> OOSQ{"survives?"}
        OOSQ -->|no| TDEAD
        OOSQ -->|yes| TEDGE([TAKER EDGE — build gate])
    end

    TDEAD --> DONE
    MDEAD -.-> DONE
    DONE{"both branches<br/>closed?"} -->|yes| STOP([PROJECT FINISHED<br/>write up · push · stop])
    DONE -->|no| WAIT[continue collectors]

    subgraph C[" COLLECTORS · continuous · read-only "]
        C1["ladder.py — 181 rows<br/>7 offsets/window → E3"]
        C2["maker_probe.py — 174 rows<br/>alt T-120/T-60 → E4, E5"]
        C3["bot.py — 191 rows<br/>T-10s, 0% fillable → RETIRE"]
    end

    C1 -.feeds.-> E3
    C2 -.feeds.-> E4
    C2 -.feeds.-> E5
    E1Q -.->|pool $0| KILLC2["stop maker_probe.py"]

    style MDEAD fill:#c62828,color:#fff
    style HDEAD fill:#c62828,color:#fff
    style FDEAD fill:#c62828,color:#fff
    style TDEAD fill:#c62828,color:#fff
    style STOP fill:#c62828,color:#fff
    style C3 fill:#6d4c41,color:#fff
    style MEDGE fill:#2e7d32,color:#fff
    style TEDGE fill:#2e7d32,color:#fff
    style ORACLE fill:#ef6c00,color:#fff
    style REOPEN fill:#ef6c00,color:#fff
    style E0 fill:#1565c0,color:#fff
    style E1 fill:#1565c0,color:#fff
```

---

## Node table

| # | Node | Cost | Blocking | Kills | Needs |
|---|---|---|---|---|---|
| E0 | Citation verification | minutes | yes | nothing — it gates trust in E1/E2 | web fetch, ~8 URLs |
| E1 | Reward-pool read | minutes | yes | **maker branch** | CLOB API, open markets |
| E2 | Open-price capture | hours | no | re-opens Q1 if it fails | RTDS WS, ~100 windows |
| E3 | Book-VWAP recalibration | ~1 session | yes | **taker branch** | `ladder.jsonl` (181, growing) |
| E4 | One-sided-fill timing | 3–5 d | no | hedged maker | 200 one-sided fills + perp mid |
| E5 | Two-sided-fill predictability | 5–7 d | no | filtered maker | ≥500 windows |

Critical path: **E0 → E1 → E3**. Everything else is conditional. E4/E5 are unreachable
if E1 returns a $0 pool — do not run them anyway.

## Colour key

🔴 terminal death node · 🟠 re-opens a closed question · 🟢 build gate (only point at
which order-placement code is justified) · 🔵 verification · 🟤 retire

## Rejected loops — carried forward from V2, still rejected

| Loop | Why |
|---|---|
| Micro-hedge / tail bet | −14.30% ROI over 700 windows; tail priced fair, z=−0.03 |
| Ladder-gated EV snipe | 31% hit, −$0.064/trade; the EV filter selects its own worst trades |
| 0.88 price cap | Worst of four bands (−0.70% ROI) |
| Multi-RPC in trade path | CLOB orders are signed off-chain and POSTed over HTTP |
| T+30s claim loop | Settlement is ~4.6 min |
| Naive symmetric two-sided quoting | 85/85 one-sided fills on the losing side, p=3.8e-6 |
| **Settlement manipulation** | Requires capital to move BTC spot; prohibited by Polymarket's market-integrity rules; plausibly illegal. **Not a candidate at any size.** Its only role here is as a risk to a resting maker |
