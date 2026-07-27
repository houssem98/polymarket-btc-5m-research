# LOOPS.md — Execution Graph

Nine loops. Three run continuously, four are gates, two are build loops that only
open if a gate passes. Gates are the point: each one can close the project.

See [ROADMAP_V2.md](ROADMAP_V2.md) for the evidence behind each gate.

---

## Master graph

```mermaid
flowchart TD
    START([start]) --> L1

    subgraph S1[" L1 — Window clock  ·  1s tick  ·  running "]
        L1{{"time to close<br/>== next offset?"}}
        L1 -->|no| T1[sleep to next offset]
        T1 --> L1
    end

    L1 -->|yes| L2

    subgraph S2[" L2 — Depth sampler  ·  per offset  ·  ladder.py running "]
        L2[resolve slug btc-updown-5m-window_ts] --> L2B[GET /book both tokens]
        L2B --> L2C["record best bid/ask,<br/>ask VWAP @ 5/20/50 sh,<br/>total depth, Binance spot"]
        L2C --> L2D{"more offsets?<br/>120/90/60/45/30/20/10"}
        L2D -->|yes| L1
    end

    L2D -->|no, window closed| L3

    subgraph S3[" L3 — Settlement  ·  T+6min, retry to 30min "]
        L3[GET market closed=true] --> L3B{settled?}
        L3B -->|no, under 30min| L3
        L3B -->|no, over 30min| DROP[log unresolved]
        L3B -->|yes| STORE[(ladder.jsonl)]
    end

    DROP --> L1
    STORE --> L1
    STORE -.weekly.-> G1

    subgraph S4[" L4 — Paper bot  ·  per window  ·  bot.py running "]
        P1[evaluate at T-10s] --> P2{"kelly>0, depth ok,<br/>price<=cap, EV>=0.05?"}
        P2 -->|no| PSKIP[log skip + reason]
        P2 -->|yes| PBUY[log intended FAK order]
        PBUY --> PSET[paper-settle vs real outcome]
        PSET --> PLED[(paper_trades.jsonl)]
        PSKIP --> PLED
    end

    PLED -.weekly.-> G1

    subgraph G[" GATES  ·  weekly, offline "]
        G1{"G1 — any offset where<br/>5 shares of the favourite<br/>fill under 0.99?"}
        G1 -->|no| CLOSED[TAKER PATH CLOSED<br/>book is empty at execution]
        G1 -->|yes| G2{"G2 — any entry band<br/>z &gt; 2 on REAL asks,<br/>net of 0.07·p·1-p fee?"}
        G2 -->|no| CALIB[market calibrated<br/>fee 1.75x spread = bleed]
        G2 -->|yes| G3{"G3 — edge survives<br/>Chainlink feed swap?<br/>5.3% basis error"}
        G3 -->|no| FEED[edge was basis noise]
        G3 -->|yes| EDGE([TAKER EDGE PROVEN])
    end

    CLOSED --> L5
    CALIB --> L5
    FEED --> L5

    subgraph S5[" L5 — Maker probe  ·  Gap 6  ·  the favourable fee sign "]
        M1[simulate resting quote<br/>one tick inside touch] --> M2[log would-fill + what<br/>happened after]
        M2 --> M3{"G4 — rebate + spread<br/>&gt; adverse selection?"}
        M3 -->|no| STOP([NO VIABLE STRATEGY<br/>stop, do not fund])
        M3 -->|yes| MEDGE([MAKER EDGE PROVEN])
        M2 --> M1
    end

    EDGE --> L6
    MEDGE --> L6

    subgraph S6[" L6 — Build  ·  only reachable from a proven edge "]
        B1[swap p_win_ladder for<br/>fitted model] --> B2[paper-trade 200 fills]
        B2 --> B3{live matches backtest?}
        B3 -->|no| B1
        B3 -->|yes| B4[claim engine:<br/>redeemPositions @ T+5min]
        B4 --> B5[deploy 5-share minimum]
        B5 --> B6{"100 live trades<br/>still matching?"}
        B6 -->|no| B5
        B6 -->|yes| GROW([scale size])
    end

    style STOP fill:#c62828,color:#fff
    style CLOSED fill:#c62828,color:#fff
    style CALIB fill:#c62828,color:#fff
    style FEED fill:#c62828,color:#fff
    style GROW fill:#2e7d32,color:#fff
    style EDGE fill:#2e7d32,color:#fff
    style MEDGE fill:#2e7d32,color:#fff
    style L2 fill:#1565c0,color:#fff
    style M1 fill:#1565c0,color:#fff
```

---

## Loop table

| # | Loop | Period | Blocking | Status | Output |
|---|---|---|---|---|---|
| L1 | Window clock | 1s / offset | no | running | — |
| L2 | Depth sampler | 7× per window | **yes** | running | `ladder.jsonl` |
| L3 | Settlement | T+6min, retry→30min | no | running | resolved rows |
| L4 | Paper bot | per window | no | running | `paper_trades.jsonl` |
| L5 | Maker probe | per window | **yes** | running | `maker_probe.jsonl` |
| L6 | Build | on demand | no | gated | — |
| G1 | Fill gate | weekly | **yes** | pending data | open/closed |
| G2 | Calibration gate | weekly | **yes** | pending G1 | z-scores |
| G3 | Feed gate | weekly | **yes** | pending G2 | basis-adjusted |
| G4 | Maker gate | weekly | **yes** | pending L5 | fill vs adverse |

Critical path: **L2 → G1 → G2 → G3 → L6**, with **L5 → G4 → L6** as the parallel and
currently more promising branch.

---

## Rejected loops

Do not build these. Each was tested and failed.

| Loop | Why rejected |
|---|---|
| Micro-hedge / tail bet | −14.30% ROI over 700 windows; tail priced fair at z=−0.03; fee is 6.8% of notional |
| Ladder-gated EV snipe | Scaffold's own logic: 31% hit, −$0.064/trade. The EV filter selects its own worst trades |
| 0.88 price cap | Worst of four bands (−0.70% ROI); skips 50% of windows |
| Multi-RPC in trade path | CLOB orders are signed off-chain and POSTed over HTTP. RPC is not in the trade path |
| T+30s claim loop | Settlement is ~4.6 min. Fires into nothing |
