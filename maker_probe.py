"""Gap 6 — the maker side. Read-only simulation, places nothing.

Every bot in the comparison is a taker, paying fee = shares*0.07*p*(1-p) into a
0.01 spread. Verified live from market.feeSchedule: {rate 0.07, takerOnly True,
rebateRate 0.2}. Makers pay zero and earn 20% of the taker fee on the fill.

Per window this rests one simulated bid a tick inside the touch on BOTH tokens at
T-QUOTE_AT, then watches the book until close. A resting bid at q is hit when a
taker sells into it, observable as best_ask <= q at any later sample.

Logs quote price, queue ahead of us at that price, whether it would have filled,
and the resolved outcome. The open question is whether rebate + captured spread
beats adverse selection: the fills you get are the ones you did not want.

No ClobClient, no key, no post_order.
"""
import json
import pathlib
import time

import requests

GAMMA = "https://gamma-api.polymarket.com/markets"
CLOB = "https://clob.polymarket.com"

WINDOW = 300
QUOTE_OFFSETS = [120, 60]   # alternated per window; T-120 is decided, T-60 is the untested fork
POLL = 10           # seconds between book samples while the quote rests
TICK = 0.01
SHARES = 5          # orderMinSize, verified live
FEE_RATE = 0.07
REBATE_RATE = 0.2
RESOLVE_AFTER = 360
RESOLVE_GIVEUP = 1800

OUT = pathlib.Path(__file__).parent / "maker_probe.jsonl"
S = requests.Session()


def quote_at(window_ts):
    return QUOTE_OFFSETS[(window_ts // WINDOW) % len(QUOTE_OFFSETS)]


def market(window_ts, closed=False):
    p = {"slug": f"btc-updown-5m-{window_ts}"}
    if closed:
        p["closed"] = "true"
    r = S.get(GAMMA, params=p, timeout=8)
    r.raise_for_status()
    m = r.json()
    return m[0] if m else None


def touch(token_id):
    r = S.get(f"{CLOB}/book", params={"token_id": token_id}, timeout=8)
    r.raise_for_status()
    b = r.json()
    asks = sorted((float(a["price"]), float(a["size"])) for a in b["asks"])
    bids = sorted((float(x["price"]), float(x["size"])) for x in b["bids"])
    return {
        "ask": asks[0][0] if asks else None,
        "bid": bids[-1][0] if bids else None,
        "size_at": {round(p, 2): s for p, s in bids},
    }


def resolve(ts):
    m = market(ts, closed=True)
    return None if not m else ("UP" if float(json.loads(m["outcomePrices"])[0]) > 0.5 else "DOWN")


def quote_price(t):
    """One tick inside the touch; join the bid when the spread is already one tick.

    Tick is 0.01 and these books sit at a 0.01 spread most of the window, so
    improving is usually impossible. Joining is the real maker action — it just
    puts you behind the existing queue, which `queue_ahead` records.
    """
    if t["bid"] is None:
        return None, None
    q = round(t["bid"] + TICK, 2)
    if t["ask"] is not None and q >= t["ask"]:
        return t["bid"], "join"
    return q, "improve"


def collect_window(window_ts):
    m = market(window_ts)
    if not m:
        return None
    up_id, down_id = json.loads(m["clobTokenIds"])
    tokens = {"UP": up_id, "DOWN": down_id}
    close_at = window_ts + WINDOW

    wait = (close_at - quote_at(window_ts)) - time.time()
    if wait < -POLL:
        return None
    if wait > 0:
        time.sleep(wait)

    quotes = {}
    for side, tid in tokens.items():
        t = touch(tid)
        q, mode = quote_price(t)
        quotes[side] = {
            "quote": q,
            "mode": mode,
            "touch_bid": t["bid"],
            "touch_ask": t["ask"],
            "queue_ahead": t["size_at"].get(q, 0.0) if q else None,
            "min_size_at_q": t["size_at"].get(q, 0.0) if q else None,
            "touched": False,   # book crossed our price — ignores queue
            "filled": False,    # queue ahead of us actually consumed
            "fill_t": None,
            "min_ask_seen": t["ask"],
        }

    while time.time() < close_at:
        time.sleep(min(POLL, max(0.0, close_at - time.time())))
        for side, tid in tokens.items():
            qs = quotes[side]
            if qs["quote"] is None or qs["filled"]:
                continue
            try:
                t = touch(tid)
            except Exception:
                continue
            q = qs["quote"]
            if t["ask"] is not None:
                if qs["min_ask_seen"] is None or t["ask"] < qs["min_ask_seen"]:
                    qs["min_ask_seen"] = t["ask"]
                if t["ask"] <= q:
                    qs["touched"] = True

            # Queue-aware fill needs BOTH conditions. Size leaving the level is
            # not enough on its own — makers pull quotes near close, and a
            # cancelled level looks identical to a consumed one. Trades only
            # happen at our price if the ask actually came down to it.
            qs["min_size_at_q"] = min(qs["min_size_at_q"], t["size_at"].get(q, 0.0))
            if qs["touched"] and qs["queue_ahead"] - qs["min_size_at_q"] >= SHARES:
                qs["filled"] = True
                qs["fill_t"] = round(time.time() - close_at, 1)

    return {"window_ts": window_ts, "slug": m["slug"], "quote_at": quote_at(window_ts),
            "shares": SHARES, "sides": quotes}


def score(row):
    """PnL per share for each side, assuming the fill happened. Maker fee is zero."""
    for side, qs in row["sides"].items():
        q = qs["quote"]
        if q is None or not qs["filled"]:
            qs["pnl"] = None
            continue
        won = row["winner"] == side
        rebate = REBATE_RATE * FEE_RATE * q * (1 - q)
        qs["rebate"] = round(rebate, 5)
        qs["pnl"] = round((1.0 if won else 0.0) - q + rebate, 5)


def main():
    print(f"maker_probe -> {OUT.name} | quote T-{QUOTE_OFFSETS}s alternating, one tick "
          f"inside touch | poll {POLL}s | READ-ONLY", flush=True)
    pending = {}
    while True:
        now = time.time()
        window_ts = int(now) - (int(now) % WINDOW)
        if window_ts + WINDOW - quote_at(window_ts) <= now:
            window_ts += WINDOW  # offset differs per window, so recompute rather than shift
        time.sleep(max(0.0, window_ts + WINDOW - quote_at(window_ts) - time.time()))

        try:
            row = collect_window(window_ts)
        except Exception as e:
            row = {"window_ts": window_ts, "error": repr(e), "sides": {}}
        if row:
            pending[window_ts] = row
            print(f"{row.get('slug', window_ts)} " + " ".join(
                f"{s}:{v['mode']}@{v['quote']} q{v['queue_ahead']}->{v['min_size_at_q']} "
                f"touch={v['touched']} fill={v['filled']}"
                for s, v in row.get("sides", {}).items()), flush=True)

        for ts in [t for t in pending if t + WINDOW + RESOLVE_AFTER < time.time()]:
            try:
                winner = resolve(ts)
            except Exception:
                winner = None
            if winner is None and time.time() - (ts + WINDOW) < RESOLVE_GIVEUP:
                continue
            r = pending.pop(ts)
            r["winner"] = winner
            if winner:
                score(r)
            with OUT.open("a", encoding="utf-8") as f:
                f.write(json.dumps(r) + "\n")
            print(f"  resolved {ts} -> {winner}", flush=True)


if __name__ == "__main__":
    main()
