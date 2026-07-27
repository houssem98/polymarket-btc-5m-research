"""Samples the REAL ask ladder across the whole window timeline.

This is the one measurement nothing else has. Every result so far is either mid-price
(unbuyable) or a single T-10s snapshot (book empty). COMPARISON.md's Gap 1 is real:
no bot in the comparison checks depth, and jmazzini trades T-50s..T-10s blind to it.

For each window, at each offset in OFFSETS, records for BOTH tokens:
  best bid/ask, ask VWAP at 5 / 20 / 50 shares, total ask depth, spread
plus Binance spot, then the resolved outcome.

Answers: when in the window can you actually buy, at what size, and at what real price.
Read-only. Supersedes probe.py.
"""
import json
import pathlib
import time

import requests

GAMMA = "https://gamma-api.polymarket.com/markets"
CLOB = "https://clob.polymarket.com"
BINANCE = "https://api.binance.com/api/v3"

WINDOW = 300
OFFSETS = [120, 90, 60, 45, 30, 20, 10]  # seconds before close
CLIPS = [5, 20, 50]
RESOLVE_AFTER = 360
RESOLVE_GIVEUP = 1800

OUT = pathlib.Path(__file__).parent / "ladder.jsonl"
S = requests.Session()


def market(window_ts, closed=False):
    p = {"slug": f"btc-updown-5m-{window_ts}"}
    if closed:
        p["closed"] = "true"
    r = S.get(GAMMA, params=p, timeout=8)
    r.raise_for_status()
    m = r.json()
    return m[0] if m else None


def book(token_id):
    r = S.get(f"{CLOB}/book", params={"token_id": token_id}, timeout=8)
    r.raise_for_status()
    return r.json()


def vwap(asks, shares):
    need, cost = shares, 0.0
    for price, size in asks:
        take = min(need, size)
        cost += take * price
        need -= take
        if need <= 0:
            return round(cost / shares, 5)
    return None


def side_snapshot(token_id):
    b = book(token_id)
    asks = sorted((float(a["price"]), float(a["size"])) for a in b["asks"])
    bids = sorted((float(x["price"]), float(x["size"])) for x in b["bids"])
    return {
        "ask": asks[0][0] if asks else None,
        "bid": bids[-1][0] if bids else None,
        "ask_depth": round(sum(s for _, s in asks), 2),
        "bid_depth": round(sum(s for _, s in bids), 2),
        **{f"vwap{c}": vwap(asks, c) for c in CLIPS},
    }


def spot():
    r = S.get(f"{BINANCE}/ticker/price", params={"symbol": "BTCUSDT"}, timeout=8)
    r.raise_for_status()
    return float(r.json()["price"])


def window_open(window_ts):
    r = S.get(f"{BINANCE}/klines",
              params={"symbol": "BTCUSDT", "interval": "1m",
                      "startTime": window_ts * 1000, "limit": 1}, timeout=8)
    r.raise_for_status()
    k = r.json()
    return float(k[0][1]) if k and int(k[0][0]) // 1000 == window_ts else None


def resolve(ts):
    m = market(ts, closed=True)
    return None if not m else ("UP" if float(json.loads(m["outcomePrices"])[0]) > 0.5 else "DOWN")


def collect_window(window_ts):
    m = market(window_ts)
    if not m:
        return None
    up_id, down_id = json.loads(m["clobTokenIds"])
    open_px = window_open(window_ts)
    row = {"window_ts": window_ts, "slug": m["slug"], "open_px": open_px,
           "liquidity": m.get("liquidityNum"), "samples": []}

    close_at = window_ts + WINDOW
    for off in OFFSETS:
        target = close_at - off
        wait = target - time.time()
        if wait < -2:
            continue  # already past this offset
        if wait > 0:
            time.sleep(wait)
        try:
            px = spot()
            s = {"offset": off, "t": round(time.time() - close_at, 1), "spot": px,
                 "delta_pct": round((px - open_px) / open_px * 100, 5) if open_px else None,
                 "up": side_snapshot(up_id), "down": side_snapshot(down_id)}
        except Exception as e:
            s = {"offset": off, "error": repr(e)}
        row["samples"].append(s)
    return row


def summarise(row):
    parts = []
    for s in row["samples"]:
        if "error" in s:
            continue
        u, d = s["up"]["vwap5"], s["down"]["vwap5"]
        parts.append(f"T-{s['offset']}:{'' if u is None else f'{u:.3f}'}/"
                     f"{'' if d is None else f'{d:.3f}'}")
    return " ".join(parts)


def main():
    print(f"ladder -> {OUT.name} | offsets {OFFSETS} | clips {CLIPS}", flush=True)
    pending = {}
    while True:
        now = time.time()
        window_ts = int(now) - (int(now) % WINDOW)
        first = window_ts + WINDOW - OFFSETS[0]
        if first <= now:
            window_ts += WINDOW
            first += WINDOW
        time.sleep(max(0.0, first - time.time()))

        try:
            row = collect_window(window_ts)
        except Exception as e:
            row = {"window_ts": window_ts, "error": repr(e), "samples": []}
        if row:
            pending[window_ts] = row
            print(f"{row.get('slug', window_ts)} up/down vwap5 {summarise(row)}", flush=True)

        for ts in [t for t in pending if t + WINDOW + RESOLVE_AFTER < time.time()]:
            try:
                winner = resolve(ts)
            except Exception:
                winner = None
            if winner is None and time.time() - (ts + WINDOW) < RESOLVE_GIVEUP:
                continue
            r = pending.pop(ts)
            r["winner"] = winner
            with OUT.open("a", encoding="utf-8") as f:
                f.write(json.dumps(r) + "\n")
            print(f"  resolved {ts} -> {winner}", flush=True)


if __name__ == "__main__":
    main()
