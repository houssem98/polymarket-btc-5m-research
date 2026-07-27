"""Runs the scaffold's OWN strategy against the 700 cached real windows.

Reimplements strategy.py + the gating in main.py exactly as written:
  side   = UP if delta > 0 else DOWN
  p_win  = 0.90 / 0.78 / 0.65 / 0.52 by |delta| >= 0.10 / 0.05 / 0.02 / else
  trade  if (p_win - price) >= MIN_EV(0.05) and price <= MAX_ENTRY_PRICE(0.88)

Difference from the scaffold: price is the REAL market ask (mid + half spread)
instead of the hardcoded 0.80, and the fee is applied.
"""
import json
import pathlib

import requests

CACHE = pathlib.Path(__file__).parent / "windows_hist.jsonl"
WINDOW = 300
FEE_RATE = 0.07
HALF_SPREAD = 0.005
MIN_EV = 0.05
MAX_ENTRY_PRICE = 0.88


def klines_1m(start_ms, end_ms):
    bars, cur = {}, start_ms
    while cur < end_ms:
        r = requests.get(
            "https://api.binance.com/api/v3/klines",
            params={"symbol": "BTCUSDT", "interval": "1m", "startTime": cur, "limit": 1000},
            timeout=25,
        )
        r.raise_for_status()
        data = r.json()
        if not data:
            break
        for k in data:
            bars[int(k[0]) // 1000] = (float(k[1]), float(k[4]))  # open, close
        cur = int(data[-1][0]) + 60_000
    return bars


def p_win_ladder(abs_delta):
    if abs_delta >= 0.10:
        return 0.90
    if abs_delta >= 0.05:
        return 0.78
    if abs_delta >= 0.02:
        return 0.65
    return 0.52


def main():
    rows = [json.loads(l) for l in CACHE.read_text(encoding="utf-8").splitlines() if l.strip()]
    rows.sort(key=lambda r: r["ts"])
    bars = klines_1m(rows[0]["ts"] * 1000, (rows[-1]["ts"] + WINDOW) * 1000)
    print(f"windows={len(rows)}  binance 1m bars={len(bars)}\n")

    fired = skipped_ev = skipped_cap = nodata = 0
    wins = pnl = 0.0
    ladder_check = {}

    for r in rows:
        w_open = bars.get(r["ts"])
        m3 = bars.get(r["ts"] + 180)  # close of minute 3 ~= T-60s, the decision point
        if not w_open or not m3:
            nodata += 1
            continue
        open_px, last_px = w_open[0], m3[1]
        delta = (last_px - open_px) / open_px * 100.0
        side = "UP" if delta > 0 else "DOWN"
        p_win = p_win_ladder(abs(delta))

        # calibration of the ladder itself, independent of trading
        b = ladder_check.setdefault(p_win, [0, 0])
        b[0] += 1
        b[1] += side == r["winner"]

        mid = r["up_mid"] if side == "UP" else r["dn_mid"]
        price = min(mid + HALF_SPREAD, 0.999)

        if p_win - price < MIN_EV:
            skipped_ev += 1
            continue
        if price > MAX_ENTRY_PRICE:
            skipped_cap += 1
            continue

        fired += 1
        fee = FEE_RATE * price * (1 - price)
        won = side == r["winner"]
        wins += won
        pnl += (1.0 - price - fee) if won else (-price - fee)

    print("LADDER CALIBRATION (scaffold's hardcoded p_win vs reality)")
    print(f"{'claimed p_win':<15}{'n':<8}{'actual':<10}{'error'}")
    for p in sorted(ladder_check, reverse=True):
        n, w = ladder_check[p]
        print(f"{p:<15.2f}{n:<8}{w/n:<10.1%}{w/n - p:+.1%}")

    print(f"\nTRADE GATING over {len(rows)} windows")
    print(f"  fired            {fired}")
    print(f"  skipped low EV   {skipped_ev}")
    print(f"  skipped >0.88    {skipped_cap}")
    print(f"  no binance data  {nodata}")
    if fired:
        print(f"\nRESULT n={fired} hit={wins/fired:.1%} pnl/trade=${pnl/fired:+.4f} total=${pnl:+.2f}")
        print(f"  per $100 staked: ${pnl/fired/0.5*100:+.2f} (rough, at ~50c avg)")
    else:
        print("\nRESULT: strategy never fires. Zero trades over the whole sample.")


if __name__ == "__main__":
    main()
