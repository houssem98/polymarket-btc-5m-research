"""Samples the BTC 5m up/down book at T-10s and records how it resolved.

No trading. This is the go/no-go dataset: does the T-10s ask price beat the
realized outcome after fees, or is the market already correctly priced?
"""
import json
import pathlib
import time

import requests

GAMMA = "https://gamma-api.polymarket.com/markets"
BOOK = "https://clob.polymarket.com/book"
BINANCE = "https://api.binance.com/api/v3"
WINDOW = 300
SAMPLE_AT = 10  # seconds before close
SHARES = 5.0  # orderMinSize
FEE_RATE = 0.07  # feeSchedule.rate, exponent 1, taker only
RESOLVE_AFTER = 360  # markets flip to closed ~4.6min after the window ends
RESOLVE_GIVEUP = 1800

OUT = pathlib.Path(__file__).parent / "windows.jsonl"


def market(window_ts, closed=False):
    # Gamma hides settled markets unless closed=true is passed explicitly.
    params = {"slug": f"btc-updown-5m-{window_ts}"}
    if closed:
        params["closed"] = "true"
    r = requests.get(GAMMA, params=params, timeout=10)
    r.raise_for_status()
    m = r.json()
    return m[0] if m else None


def book(token_id):
    r = requests.get(BOOK, params={"token_id": token_id}, timeout=10)
    r.raise_for_status()
    return r.json()


def levels(side):
    return sorted((float(x["price"]), float(x["size"])) for x in side)


def vwap(asks, shares):
    need, cost = shares, 0.0
    for price, size in levels(asks):
        take = min(need, size)
        cost += take * price
        need -= take
        if need <= 0:
            return round(cost / shares, 6)
    return None  # book too thin


def fee_per_share(price):
    return FEE_RATE * price * (1.0 - price)


def snapshot(token_id):
    b = book(token_id)
    asks, bids = levels(b["asks"]), levels(b["bids"])
    return {
        "best_ask": asks[0][0] if asks else None,
        "best_bid": bids[-1][0] if bids else None,
        "ask_vwap": vwap(b["asks"], SHARES),
        "ask_depth": round(sum(s for _, s in asks), 2),
    }


def binance_window(window_ts):
    r = requests.get(
        f"{BINANCE}/klines",
        params={"symbol": "BTCUSDT", "interval": "1m", "startTime": window_ts * 1000, "limit": 5},
        timeout=10,
    )
    r.raise_for_status()
    k = r.json()
    last = requests.get(f"{BINANCE}/ticker/price", params={"symbol": "BTCUSDT"}, timeout=10).json()
    return {"open": float(k[0][1]), "last": float(last["price"])}


def sample(window_ts):
    m = market(window_ts)
    if not m:
        return {"window_ts": window_ts, "error": "no_market"}
    up_id, down_id = json.loads(m["clobTokenIds"])
    px = binance_window(window_ts)
    delta = (px["last"] - px["open"]) / px["open"] * 100.0
    return {
        "window_ts": window_ts,
        "slug": m["slug"],
        "sampled_at": int(time.time()),
        "accepting_orders": m["acceptingOrders"],
        "up_token": up_id,
        "down_token": down_id,
        "up": snapshot(up_id),
        "down": snapshot(down_id),
        "binance_open": px["open"],
        "binance_last": px["last"],
        "delta_pct": round(delta, 5),
        "leader": "UP" if delta > 0 else "DOWN",
    }


def resolve(window_ts):
    m = market(window_ts, closed=True)
    if not m:
        return None
    prices = json.loads(m["outcomePrices"])
    return "UP" if float(prices[0]) > 0.5 else "DOWN"


def main():
    print(f"probe -> {OUT}  (sampling T-{SAMPLE_AT}s, {SHARES} shares, fee rate {FEE_RATE})", flush=True)
    pending = {}
    while True:
        now = time.time()
        window_ts = int(now) - (int(now) % WINDOW)
        fire = window_ts + WINDOW - SAMPLE_AT
        if fire <= now:
            window_ts += WINDOW
            fire += WINDOW
        time.sleep(fire - time.time())

        try:
            row = sample(window_ts)
        except Exception as e:
            row = {"window_ts": window_ts, "error": repr(e)}
        pending[window_ts] = row
        print(
            f"{row.get('slug', window_ts)} delta={row.get('delta_pct')} "
            f"leader={row.get('leader')} up_ask={row.get('up', {}).get('ask_vwap')} "
            f"down_ask={row.get('down', {}).get('ask_vwap')}",
            flush=True,
        )

        # Settlement lands ~5min after close, so retry rather than discard.
        for ts in [t for t in pending if t + WINDOW + RESOLVE_AFTER < time.time()]:
            try:
                winner = resolve(ts)
            except Exception:
                winner = None
            if winner is None and time.time() - (ts + WINDOW) < RESOLVE_GIVEUP:
                continue
            row = pending.pop(ts)
            row["winner"] = winner
            with OUT.open("a", encoding="utf-8") as f:
                f.write(json.dumps(row) + "\n")
            print(f"  resolved {ts} -> {winner}", flush=True)


if __name__ == "__main__":
    main()
