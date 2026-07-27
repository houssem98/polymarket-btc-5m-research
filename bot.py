"""Polymarket BTC 5m bot — paper mode.

Every bug from ROADMAP.md's table is fixed here, and every number the scaffold
guessed is read from the live API instead:

  slug        deterministic btc-updown-5m-{window_start}, then VERIFIED against Gamma
  token ids   market.clobTokenIds (idx 0 = Up, 1 = Down)
  price       VWAP of the real CLOB ask ladder for the size we want, not 0.80
  open price  the 1m kline whose openTime == window_ts, not klines[-5]
  fee         0.07 * p * (1-p), taker only, subtracted inside EV
  tick        prices rounded UP to the 0.01 tick (conservative for a buyer)
  sizing      quarter Kelly; a Kelly of 0 means NO trade (never forced to MIN_SHARES)
  breaker     3 straight losses pauses until the next UTC day, then resets

This module has no ClobClient, no private key, and no code path that posts an
order. It logs the order it *would* have sent and paper-settles it against the
real resolution. Trading requires adding an executor; that is deliberately absent.
"""
import json
import math
import pathlib
import time
from datetime import datetime, timezone

import requests

GAMMA = "https://gamma-api.polymarket.com/markets"
CLOB = "https://clob.polymarket.com"
BINANCE = "https://api.binance.com/api/v3"

WINDOW = 300
SNIPE_AT = 10          # evaluate at T-10s
STALE_AFTER = 3        # abort if evaluation drags past T-3s
RESOLVE_AFTER = 360    # markets flip to closed ~4.6min after the window ends
RESOLVE_GIVEUP = 1800
MIN_SHARES = 5.0       # orderMinSize, verified live
TICK = 0.01            # orderPriceMinTickSize, verified live
FEE_RATE = 0.07        # feeSchedule.rate, exponent 1, takerOnly
MIN_EV = 0.05          # required net edge per share
MAX_ENTRY_PRICE = 0.88
KELLY_FRACTION = 0.25
MAX_POSITION_FRAC = 0.10   # never risk >10% of bankroll on one window
START_BANKROLL = 200.0

LEDGER = pathlib.Path(__file__).parent / "paper_trades.jsonl"
S = requests.Session()


# ---------------------------------------------------------------- market data

def market(window_ts, closed=False):
    params = {"slug": f"btc-updown-5m-{window_ts}"}
    if closed:
        params["closed"] = "true"   # Gamma hides settled markets without this
    r = S.get(GAMMA, params=params, timeout=8)
    r.raise_for_status()
    m = r.json()
    return m[0] if m else None


def book(token_id):
    r = S.get(f"{CLOB}/book", params={"token_id": token_id}, timeout=8)
    r.raise_for_status()
    return r.json()


def ask_vwap(raw_book, shares):
    """Average fill price for `shares` walking the real ask ladder."""
    asks = sorted((float(a["price"]), float(a["size"])) for a in raw_book["asks"])
    need, cost = shares, 0.0
    for price, size in asks:
        take = min(need, size)
        cost += take * price
        need -= take
        if need <= 0:
            return cost / shares
    return None  # not enough depth to fill


def window_open_price(window_ts):
    """The 1m candle that opens exactly at the window start."""
    r = S.get(
        f"{BINANCE}/klines",
        params={"symbol": "BTCUSDT", "interval": "1m", "startTime": window_ts * 1000, "limit": 1},
        timeout=8,
    )
    r.raise_for_status()
    k = r.json()
    if not k or int(k[0][0]) // 1000 != window_ts:
        return None
    return float(k[0][1])


def spot():
    r = S.get(f"{BINANCE}/ticker/price", params={"symbol": "BTCUSDT"}, timeout=8)
    r.raise_for_status()
    return float(r.json()["price"])


# ------------------------------------------------------------------- strategy

def p_win_ladder(abs_delta_pct):
    """The scaffold's ladder, kept as the default so its behaviour is observable.

    Measured over 700 real windows (scaffold_sim.py): trades gated on this ladder
    hit 31% and lost $0.064/trade. It is here to be replaced by a fitted model,
    not because it works. Swap this function, keep everything else.
    """
    if abs_delta_pct >= 0.10:
        return 0.90
    if abs_delta_pct >= 0.05:
        return 0.78
    if abs_delta_pct >= 0.02:
        return 0.65
    return 0.52


def fee_per_share(price):
    return FEE_RATE * price * (1.0 - price)


def round_to_tick(price):
    """Round UP: a buyer must cross to the next tick, never assume a better one."""
    return min(math.ceil(price / TICK) * TICK, 1.0 - TICK)


# ----------------------------------------------------------------------- risk

class Risk:
    def __init__(self, bankroll=START_BANKROLL):
        self.bankroll = bankroll
        self.loss_streak = 0
        self.paused_on = None  # UTC date the breaker tripped

    def available(self, now):
        today = datetime.fromtimestamp(now, timezone.utc).date()
        if self.paused_on and self.paused_on != today:
            self.paused_on = None
            self.loss_streak = 0
        return self.paused_on is None

    def stake(self, p_win, price):
        b = (1.0 / price) - 1.0
        if b <= 0:
            return 0.0
        kelly = (b * p_win - (1.0 - p_win)) / b
        return max(0.0, kelly * KELLY_FRACTION) * self.bankroll

    def settle(self, won, pnl, now):
        self.bankroll += pnl
        if won:
            self.loss_streak = 0
            return
        self.loss_streak += 1
        if self.loss_streak >= 3:
            self.paused_on = datetime.fromtimestamp(now, timezone.utc).date()


# ------------------------------------------------------------------- decision

def evaluate(window_ts, risk):
    """Returns a decision dict. Never places an order."""
    d = {"window_ts": window_ts, "slug": f"btc-updown-5m-{window_ts}", "ts": int(time.time())}
    close_at = window_ts + WINDOW

    if not risk.available(time.time()):
        return {**d, "action": "skip", "reason": "circuit_breaker"}

    m = market(window_ts)
    if not m:
        return {**d, "action": "skip", "reason": "no_market"}
    if not m.get("acceptingOrders"):
        return {**d, "action": "skip", "reason": "not_accepting_orders"}

    up_id, down_id = json.loads(m["clobTokenIds"])

    open_px = window_open_price(window_ts)
    if open_px is None:
        return {**d, "action": "skip", "reason": "no_window_open_kline"}
    now_px = spot()
    delta = (now_px - open_px) / open_px * 100.0
    side = "UP" if delta > 0 else "DOWN"
    token_id = up_id if side == "UP" else down_id
    p_win = p_win_ladder(abs(delta))
    d |= {"delta_pct": round(delta, 5), "side": side, "p_win": p_win,
          "open_px": open_px, "spot_px": now_px, "token_id": token_id}

    if time.time() > close_at - STALE_AFTER:
        return {**d, "action": "skip", "reason": "too_late"}

    # Price the minimum clip first, so Kelly is computed at the price we'd really
    # pay. Sizing off a worst-case price would reject cheap, genuinely good bets.
    raw = book(token_id)
    indicative = ask_vwap(raw, MIN_SHARES)
    if indicative is None:
        return {**d, "action": "skip", "reason": "insufficient_ask_depth", "shares_wanted": MIN_SHARES}
    quote = round_to_tick(indicative)
    if quote > MAX_ENTRY_PRICE:
        return {**d, "action": "skip", "reason": "above_max_entry", "limit_price": round(quote, 2)}

    # Kelly of zero must mean no trade, never a forced MIN_SHARES clip.
    stake = risk.stake(p_win, quote)
    if stake <= 0:
        return {**d, "action": "skip", "reason": "kelly_zero", "limit_price": round(quote, 2)}

    shares = max(MIN_SHARES, stake / quote)
    cap_shares = (risk.bankroll * MAX_POSITION_FRAC) / quote
    if shares > cap_shares:
        shares = cap_shares
    if shares < MIN_SHARES:
        return {**d, "action": "skip", "reason": "position_cap_below_min_size"}

    # Re-walk the ladder at the real size: bigger clips fill worse.
    fill = ask_vwap(raw, shares)
    if fill is None:
        return {**d, "action": "skip", "reason": "insufficient_ask_depth", "shares_wanted": round(shares, 2)}
    price = round_to_tick(fill)
    d |= {"ask_vwap": round(fill, 4), "limit_price": round(price, 2)}

    if price > MAX_ENTRY_PRICE:
        return {**d, "action": "skip", "reason": "above_max_entry"}

    fee = fee_per_share(price)
    ev = p_win - price - fee
    d |= {"fee_per_share": round(fee, 5), "ev_per_share": round(ev, 5)}
    if ev < MIN_EV:
        return {**d, "action": "skip", "reason": "low_ev"}

    cost = shares * price

    return {**d, "action": "paper_buy", "shares": round(shares, 2), "cost": round(cost, 4),
            "order": {"token_id": token_id, "price": round(price, 2), "size": round(shares, 2),
                      "side": "BUY", "type": "FAK"}}


def resolve(window_ts):
    m = market(window_ts, closed=True)
    if not m:
        return None
    return "UP" if float(json.loads(m["outcomePrices"])[0]) > 0.5 else "DOWN"


# ---------------------------------------------------------------------- loop

def main():
    risk = Risk()
    pending = {}
    print(f"paper bot up | bankroll ${risk.bankroll:.2f} | ledger {LEDGER.name}", flush=True)
    print("no ClobClient, no key, no post_order in this module\n", flush=True)

    while True:
        now = time.time()
        window_ts = int(now) - (int(now) % WINDOW)
        fire = window_ts + WINDOW - SNIPE_AT
        if fire <= now:
            window_ts += WINDOW
            fire += WINDOW
        time.sleep(max(0.0, fire - time.time()))

        try:
            d = evaluate(window_ts, risk)
        except Exception as e:
            d = {"window_ts": window_ts, "action": "skip", "reason": f"error:{e!r}"}

        if d["action"] == "paper_buy":
            pending[window_ts] = d
            print(f"{d['slug']} BUY {d['shares']}sh {d['side']} @ {d['order']['price']} "
                  f"ev={d['ev_per_share']:+.4f} delta={d['delta_pct']:+.4f}%", flush=True)
        else:
            print(f"{d['slug']} skip: {d['reason']}"
                  + (f" delta={d['delta_pct']:+.4f}%" if "delta_pct" in d else ""), flush=True)
            _write(d)

        # Settlement lands ~5min after close, so retry rather than discard.
        for ts in [t for t in pending if t + WINDOW + RESOLVE_AFTER < time.time()]:
            try:
                winner = resolve(ts)
            except Exception:
                winner = None
            if winner is None:
                if time.time() - (ts + WINDOW) < RESOLVE_GIVEUP:
                    continue
                t = pending.pop(ts)
                _write({**t, "reason": "unresolved"})
                continue
            t = pending.pop(ts)
            won = t["side"] == winner
            fee = t["fee_per_share"] * t["shares"]
            pnl = (t["shares"] * (1.0 - t["limit_price"]) - fee) if won \
                else (-t["shares"] * t["limit_price"] - fee)
            risk.settle(won, pnl, time.time())
            t |= {"winner": winner, "won": won, "pnl": round(pnl, 4),
                  "bankroll": round(risk.bankroll, 2)}
            print(f"  settle {t['slug']} -> {winner} {'WIN' if won else 'LOSS'} "
                  f"pnl=${pnl:+.3f} bankroll=${risk.bankroll:.2f}"
                  + (f" [BREAKER {risk.paused_on}]" if risk.paused_on else ""), flush=True)
            _write(t)


def _write(row):
    with LEDGER.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, default=str) + "\n")


if __name__ == "__main__":
    main()
