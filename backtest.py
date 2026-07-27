"""Reconstructs past BTC 5m windows from CLOB price history and tests whether the
late-window price is mispriced enough to trade.

Honest accounting:
  - prices-history 'p' is the MIDPOINT (values land on half-ticks; tick is 0.01).
    You cannot buy at mid, so we pay mid + HALF_SPREAD.
  - fee = shares * 0.07 * price * (1-price), taker only (feeSchedule, verified live).
  - history granularity is ~60s, so the sample is ~T-50s, NOT T-10s. At T-10s the
    market has ~40s more information, so this OVERSTATES any edge. Treat results
    as an upper bound.

Caches to windows_hist.jsonl so reruns don't refetch.
"""
import json
import math
import pathlib
import sys
import time

import requests

GAMMA = "https://gamma-api.polymarket.com/markets"
HIST = "https://clob.polymarket.com/prices-history"
WINDOW = 300
FEE_RATE = 0.07
HALF_SPREAD = 0.005  # half of the observed 1-tick spread
SAMPLE_AT = 10  # seconds before close we pretend to trade

CACHE = pathlib.Path(__file__).parent / "windows_hist.jsonl"
S = requests.Session()


def closed_market(ts):
    r = S.get(GAMMA, params={"slug": f"btc-updown-5m-{ts}", "closed": "true"}, timeout=15)
    r.raise_for_status()
    m = r.json()
    return m[0] if m else None


def history(token_id, ts):
    r = S.get(
        HIST,
        params={"market": token_id, "startTs": ts - 60, "endTs": ts + WINDOW + 120, "fidelity": 1},
        timeout=20,
    )
    r.raise_for_status()
    return r.json().get("history", [])


def last_before(hist, cutoff):
    pts = [h for h in hist if h["t"] <= cutoff]
    return (pts[-1]["p"], pts[-1]["t"]) if pts else (None, None)


def fetch(ts):
    m = closed_market(ts)
    if not m:
        return None
    up_id, down_id = json.loads(m["clobTokenIds"])
    prices = json.loads(m["outcomePrices"])
    close = ts + WINDOW
    uh, dh = history(up_id, ts), history(down_id, ts)
    up_p, up_t = last_before(uh, close - SAMPLE_AT)
    dn_p, dn_t = last_before(dh, close - SAMPLE_AT)
    if up_p is None or dn_p is None:
        return None
    up_settle = [h["p"] for h in uh if h["t"] > close]
    return {
        "ts": ts,
        "up_mid": up_p,
        "dn_mid": dn_p,
        "up_lag": close - up_t,
        "dn_lag": close - dn_t,
        "winner": "UP" if float(prices[0]) > 0.5 else "DOWN",
        "up_settle": up_settle[-1] if up_settle else None,
        "volume": m.get("volumeNum"),
        "liquidity": m.get("liquidityNum"),
    }


def load_cache():
    if not CACHE.exists():
        return {}
    out = {}
    for line in CACHE.read_text(encoding="utf-8").splitlines():
        if line.strip():
            r = json.loads(line)
            out[r["ts"]] = r
    return out


def collect(n):
    cache = load_cache()
    now = int(time.time())
    base = now - (now % WINDOW)
    added = 0
    with CACHE.open("a", encoding="utf-8") as f:
        for i in range(2, n + 2):
            ts = base - i * WINDOW
            if ts in cache:
                continue
            try:
                row = fetch(ts)
            except Exception as e:
                print(f"  {ts} ERR {e!r}", flush=True)
                continue
            if row:
                cache[ts] = row
                f.write(json.dumps(row) + "\n")
                f.flush()
                added += 1
                if added % 25 == 0:
                    print(f"  fetched {added}...", flush=True)
    print(f"collected {added} new, {len(cache)} total")
    return sorted(cache.values(), key=lambda r: r["ts"])


def analyse(rows):
    rows = [r for r in rows if r["up_mid"] is not None]
    print(f"\n{'='*72}\nSAMPLE n={len(rows)}  "
          f"mean sample lag T-{sum(r['up_lag'] for r in rows)/len(rows):.0f}s "
          f"(target T-{SAMPLE_AT}s)\n{'='*72}")

    # Mapping sanity
    ck = [r for r in rows if r["up_settle"] is not None]
    agree = sum(1 for r in ck if (r["up_settle"] > 0.5) == (r["winner"] == "UP"))
    print(f"outcome mapping agrees with token settle: {agree}/{len(ck)}")

    base_up = sum(1 for r in rows if r["winner"] == "UP") / len(rows)
    print(f"base rate UP: {base_up:.1%}\n")

    trades = []
    for r in rows:
        fav, mid = ("UP", r["up_mid"]) if r["up_mid"] > r["dn_mid"] else ("DOWN", r["dn_mid"])
        pay = min(mid + HALF_SPREAD, 0.999)
        fee = FEE_RATE * pay * (1 - pay)
        won = fav == r["winner"]
        trades.append({"mid": mid, "pay": pay, "won": won,
                       "pnl": (1.0 - pay - fee) if won else (-pay - fee)})

    def report(label, sel):
        if not sel:
            return
        n = len(sel)
        hit = sum(t["won"] for t in sel) / n
        avg_pay = sum(t["pay"] for t in sel) / n
        pnl = sum(t["pnl"] for t in sel)
        # is hit rate distinguishable from the price-implied probability?
        se = math.sqrt(max(avg_pay * (1 - avg_pay), 1e-9) / n)
        z = (hit - avg_pay) / se
        print(f"{label:<18} n={n:<5} hit={hit:6.1%}  implied={avg_pay:6.1%}  "
              f"edge={hit-avg_pay:+6.2%}  z={z:+5.2f}  pnl/tr=${pnl/n:+.4f}  tot=${pnl:+.2f}")

    print(f"{'BUCKET':<18} {'n':<7} {'hit':<8} {'implied':<9} {'edge':<9} {'z':<7} {'pnl/tr':<12} total")
    report("ALL FAVOURITES", trades)
    for lo, hi in [(0.5, 0.7), (0.7, 0.85), (0.85, 0.95), (0.95, 1.01)]:
        report(f"  pay {lo:.2f}-{hi:.2f}", [t for t in trades if lo <= t["pay"] < hi])

    print("\nCap at MAX_ENTRY_PRICE=0.88 (scaffold rule):")
    report("  pay <= 0.88", [t for t in trades if t["pay"] <= 0.88])
    skipped = sum(1 for t in trades if t["pay"] > 0.88)
    print(f"  -> cap skips {skipped}/{len(trades)} = {skipped/len(trades):.0%} of windows")

    print("\nz > +2 means priced too cheap (real edge). |z| < 2 means market is calibrated;")
    print("with taker fees a calibrated market is a guaranteed slow loss.")


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 300
    analyse(collect(n))
