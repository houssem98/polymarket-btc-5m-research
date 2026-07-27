"""G2 — the calibration gate. Does the favourite win more often than its price implies?

Pre-registered at 194/200 rows, before the qualifying data existed, so none of the
choices below can be tuned to the result. Read-only; places nothing.

Everything here is decided in advance:

  offset      T-120s only. It is the sole offset clearing G1 (90%, CI [84%, 93%]).
              T-90 cleared at iteration 22 and fell back at iteration 31; it is out.
  favourite   the side with the HIGHER ask VWAP at 5 shares. Determined from prices
              at T-120, never from the outcome -- using the winner would be look-ahead.
  price       that side's real ask VWAP for 5 shares. Not mid, not a midpoint proxy.
  exclusion   windows where the favourite has no ask are dropped: unbuyable is not a
              trade. Dropped windows are reported, not hidden.
  bands       <=0.88, 0.88-0.94, 0.94-0.99, >0.99  (4 buckets, from ROADMAP_V2 s2)
  fee         0.07 * p * (1-p) per share, taker-only, verified from market.feeSchedule
  PASS        some band with z > 2 AND mean PnL/share > 0 after fee.

Four buckets are tested, so a single z>2 is not a 5% result. The Bonferroni-corrected
threshold for 4 tests at alpha=0.05 is |z| > 2.50, and both are printed.
"""
import json
import math
import pathlib

LADDER = pathlib.Path(__file__).parent / "ladder.jsonl"
OFFSET = 120
CLIP = "vwap5"
BANDS = [(0.0, 0.88), (0.88, 0.94), (0.94, 0.99), (0.99, 1.0)]
FEE_RATE = 0.07


def fee(p):
    return FEE_RATE * p * (1 - p)


def rows():
    for line in LADDER.open(encoding="utf-8"):
        r = json.loads(line)
        if r.get("winner"):
            yield r


def favourite(sample):
    """(side, price) by price alone. None price means quoted but unbuyable."""
    u, d = sample["up"][CLIP], sample["down"][CLIP]
    if u is not None and d is not None:
        return ("UP", u) if u > d else ("DOWN", d)
    if u is not None:
        return "DOWN", None      # only the underdog is offered; favourite is unbuyable
    if d is not None:
        return "UP", None
    return None, None


def main():
    trades, no_sample, unbuyable = [], 0, 0
    for r in rows():
        s = next((x for x in r["samples"] if x.get("offset") == OFFSET and "error" not in x), None)
        if not s:
            no_sample += 1
            continue
        side, price = favourite(s)
        if side is None or price is None:
            unbuyable += 1
            continue
        trades.append({"price": price, "won": side == r["winner"]})

    n_all = len(trades) + no_sample + unbuyable
    print(f"G2 — calibration at T-{OFFSET}s, real ask VWAP at 5 shares")
    print(f"resolved windows {n_all} | tradeable {len(trades)} | "
          f"favourite unbuyable {unbuyable} | no T-{OFFSET} sample {no_sample}\n")

    print(f"{'band':>12} {'n':>4} {'hit':>7} {'implied':>8} {'edge':>7} "
          f"{'z':>6} {'fee':>7} {'pnl/sh':>8} {'ROI':>7}")
    passed = []
    for lo, hi in BANDS:
        b = [t for t in trades if lo < t["price"] <= hi]
        if not b:
            print(f"{f'{lo:.2f}-{hi:.2f}':>12} {0:>4}")
            continue
        n = len(b)
        hit = sum(t["won"] for t in b) / n
        implied = sum(t["price"] for t in b) / n
        se = math.sqrt(implied * (1 - implied) / n)
        z = (hit - implied) / se if se else 0.0
        f = sum(fee(t["price"]) for t in b) / n
        pnl = hit - implied - f
        roi = pnl / implied
        print(f"{f'{lo:.2f}-{hi:.2f}':>12} {n:>4} {hit:>6.2%} {implied:>7.2%} "
              f"{hit-implied:>+6.2%} {z:>+6.2f} {f:>7.4f} {pnl:>+8.4f} {roi:>+6.2%}")
        if z > 2 and pnl > 0:
            passed.append((lo, hi, z, pnl))

    print(f"\nbuckets tested: {len(BANDS)}. Uncorrected threshold z>2.00; "
          f"Bonferroni-corrected for {len(BANDS)} tests, z>2.50.")
    if passed:
        print("PASS (uncorrected):", passed)
        print("PASS (corrected):", [p for p in passed if p[2] > 2.50] or "none")
    else:
        print("\nRESULT: FAIL — no band has z > 2 with positive PnL after fee.")
        print("The market is calibrated at T-120s. The taker path is closed.")


if __name__ == "__main__":
    main()
