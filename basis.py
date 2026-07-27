"""Does Binance BTCUSDT actually predict how these markets resolve?

The scaffold trades on Binance, but the market resolves on the Chainlink BTC/USD
stream (market.resolutionSource). If the sign of the Binance 5m candle disagrees
with the resolved outcome, the strategy is measuring the wrong asset.

Uses the windows already cached by backtest.py.
"""
import json
import pathlib

import requests

CACHE = pathlib.Path(__file__).parent / "windows_hist.jsonl"
WINDOW = 300


def klines(start_ms, limit=1000):
    r = requests.get(
        "https://api.binance.com/api/v3/klines",
        params={"symbol": "BTCUSDT", "interval": "5m", "startTime": start_ms, "limit": limit},
        timeout=25,
    )
    r.raise_for_status()
    return {int(k[0]) // 1000: (float(k[1]), float(k[4])) for k in r.json()}


def main():
    rows = [json.loads(l) for l in CACHE.read_text(encoding="utf-8").splitlines() if l.strip()]
    rows.sort(key=lambda r: r["ts"])
    print(f"cached windows: {len(rows)}")

    bars = {}
    start = rows[0]["ts"]
    while start <= rows[-1]["ts"]:
        chunk = klines(start * 1000)
        if not chunk:
            break
        bars.update(chunk)
        start = max(chunk) + WINDOW
    print(f"binance 5m bars: {len(bars)}")

    agree = flat = total = 0
    disagreements = []
    for r in rows:
        bar = bars.get(r["ts"])
        if not bar:
            continue
        o, c = bar
        total += 1
        if c == o:
            flat += 1
            continue
        side = "UP" if c > o else "DOWN"
        if side == r["winner"]:
            agree += 1
        else:
            disagreements.append((r["ts"], o, c, round((c - o) / o * 1e4, 2), r["winner"]))

    print(f"\nBinance 5m candle sign vs resolved outcome: {agree}/{total} = {agree/total:.2%}")
    print(f"exact flat candles: {flat}")
    print(f"disagreements: {len(disagreements)}")
    if disagreements:
        print("\nworst disagreements (bps move, who actually won):")
        for ts, o, c, bps, w in sorted(disagreements, key=lambda d: -abs(d[3]))[:12]:
            print(f"  ts={ts} open={o} close={c} binance={bps:+.2f}bps -> resolved {w}")
        near = sum(1 for d in disagreements if abs(d[3]) < 2.0)
        print(f"\n{near}/{len(disagreements)} disagreements were under 2bps (coin-flip zone)")


if __name__ == "__main__":
    main()
